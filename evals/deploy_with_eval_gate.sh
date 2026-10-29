#!/usr/bin/env bash
# Production-grade Local CI/CD Evaluation Gate
# Replicates the exact Cloud Build container gate logic against live ADK execution.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

EVAL_TARGET="${1:-evals/golden.json:on_brand_draft}"
DEPLOY_ACTION="${2:-dry-run}"
LOG_FILE="/tmp/eval_live_gate.log"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${YELLOW}🛡️  Stage 1: Launching Background Mock Memory Agent Sidecar...${NC}"
echo -e "${BLUE}======================================================================${NC}"

# Check if port 8001 is already in use
MOCK_STARTED=false
if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null ; then
  echo "Mock memory agent already active on port 8001."
else
  uv run python backend/mock_memory_agent.py &
  MOCK_PID=$!
  MOCK_STARTED=true
  echo "Started mock memory agent with PID: ${MOCK_PID}. Waiting 3s for readiness..."
  sleep 3
fi

cleanup() {
  if [ "$MOCK_STARTED" = true ] && [ -n "${MOCK_PID:-}" ]; then
    echo -e "\n${YELLOW}Cleaning up mock memory agent sidecar (PID ${MOCK_PID})...${NC}"
    kill "$MOCK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${YELLOW}🧪 Stage 2: Executing Live ADK Evaluation Gate (${EVAL_TARGET})...${NC}"
echo -e "${BLUE}======================================================================${NC}"

export MEMORY_AGENT_CARD_URL="http://localhost:8001/.well-known/agent.json"
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-ai-devcamp-duncan-395792}"
export GOOGLE_CLOUD_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"

set +e
uv run adk eval backend/social_poster "${EVAL_TARGET}" \
  --config_file_path evals/eval_config.json 2>&1 | tee "${LOG_FILE}"
EVAL_CLI_EXIT=$?
set -e

echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${YELLOW}🔍 Stage 3: Defensive Parsing & Gate Enforcement (Exit code $EVAL_CLI_EXIT)...${NC}"
echo -e "${BLUE}======================================================================${NC}"

FAILED=$(grep -oE "Tests failed: [0-9]+" "${LOG_FILE}" 2>/dev/null | tail -1 | grep -oE "[0-9]+" || true)

if [ -z "$FAILED" ]; then
  echo -e "${RED}❌ Could not parse eval result from log — treating as failure (FAIL-CLOSED INVARIANT).${NC}"
  echo -e "${RED}🛑 DEPLOYMENT BLOCKED.${NC}"
  exit 1
fi

if [ "$FAILED" -gt 0 ]; then
  echo -e "${RED}❌ Golden evalset regression detected: ${FAILED} test(s) failed.${NC}"
  echo -e "${RED}🛑 DEPLOYMENT BLOCKED. Pipeline aborted before deploy step.${NC}"
  exit 1
fi

echo -e "${GREEN}✅ All evaluation cases passed clean (0 failures).${NC}"
echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${GREEN}🚀 Stage 4: Triggering Production Deployment Gate...${NC}"
echo -e "${BLUE}======================================================================${NC}"

if [ "${DEPLOY_ACTION}" = "dry-run" ]; then
  echo -e "${GREEN}Deploy gate OPEN. [DRY-RUN]: Would execute target deployment:${NC}"
  echo -e "  -> gcloud run deploy social-poster --source=. --region=us-central1"
  echo -e "  -> (or agents-cli deploy --deployment-target agent_runtime)"
  echo -e "${GREEN}Pipeline succeeded.${NC}"
  exit 0
else
  echo -e "${GREEN}Deploy gate OPEN. Executing live deployment action...${NC}"
  # Here live deploy action would execute
fi
