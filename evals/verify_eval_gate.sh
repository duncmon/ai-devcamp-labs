#!/usr/bin/env bash
# Verification script for Lab 4 Step 6: Cloud Build Eval-Gate Logic
# Replicates the exact parsing logic from cloudbuild.yaml against red, green, and empty logs.

set -euo pipefail

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

evaluate_log() {
  local label="$1"
  local log_path="$2"
  
  echo -e "\n${BLUE}======================================================================${NC}"
  echo -e "${YELLOW}Testing Gate Scenario: ${label}${NC}"
  echo -e "Log source: ${log_path}"
  echo -e "${BLUE}----------------------------------------------------------------------${NC}"

  # Replicate Cloud Build step 1 parsing logic exactly:
  # FAILED=$(grep -oE "Tests failed: [0-9]+" /tmp/eval_output.log | tail -1 | grep -oE "[0-9]+")
  FAILED=$(grep -oE "Tests failed: [0-9]+" "$log_path" 2>/dev/null | tail -1 | grep -oE "[0-9]+" || true)

  if [ -z "$FAILED" ]; then
    echo -e "${RED}❌ Could not parse eval result — treating as failure (FAIL-CLOSED INVARIANT).${NC}"
    echo -e "Exit Code: 1 (Deploy blocked)"
    return 1
  fi

  if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}❌ Golden evalset regression: ${FAILED} test(s) failed. Blocking deploy.${NC}"
    echo -e "Exit Code: 1 (Deploy blocked)"
    return 1
  fi

  echo -e "${GREEN}✅ Golden evalset passed clean (0 failures).${NC}"
  echo -e "Exit Code: 0 (Deploy permitted)"
  return 0
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RED_LOG="${REPO_ROOT}/docs/screenshots/lab4-step2-red-run.txt"
GREEN_LOG="${REPO_ROOT}/docs/screenshots/lab4-step2-green-recovery.txt"
EMPTY_LOG="/tmp/empty_eval_gate_test.log"
touch "${EMPTY_LOG}"

echo -e "${YELLOW}Starting Cloud Build Eval-Gate Simulation...${NC}"

# Case 1: Red Run (Regression)
set +e
evaluate_log "1. Intentional Regression (Broken Brand Voice)" "$RED_LOG"
STATUS_RED=$?

# Case 2: Green Recovery (Clean)
evaluate_log "2. Clean Baseline Recovery (Passing Golden Set)" "$GREEN_LOG"
STATUS_GREEN=$?

# Case 3: Empty / Corrupt Output (Fail-Closed)
evaluate_log "3. Empty / Unparseable Output (Fail-Closed Defense)" "$EMPTY_LOG"
STATUS_EMPTY=$?
set -e

rm -f "${EMPTY_LOG}"

echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${YELLOW}Eval-Gate Summary Verification Matrix:${NC}"
echo -e "  • Broken Code (Regression):     Exit ${STATUS_RED} (Expected: 1) -> $( [ $STATUS_RED -eq 1 ] && echo -e "${GREEN}VERIFIED${NC}" || echo -e "${RED}FAILED${NC}" )"
echo -e "  • Clean Code (Golden Pass):     Exit ${STATUS_GREEN} (Expected: 0) -> $( [ $STATUS_GREEN -eq 0 ] && echo -e "${GREEN}VERIFIED${NC}" || echo -e "${RED}FAILED${NC}" )"
echo -e "  • Empty/Corrupt (Fail-Closed):  Exit ${STATUS_EMPTY} (Expected: 1) -> $( [ $STATUS_EMPTY -eq 1 ] && echo -e "${GREEN}VERIFIED${NC}" || echo -e "${RED}FAILED${NC}" )"
echo -e "${BLUE}======================================================================${NC}"
