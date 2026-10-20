#!/usr/bin/env bash
# ==============================================================================
# run-frontend.sh — Social Spark Next.js Frontend Launcher
# Enforces Twelve-Factor Principle 3: Deterministic Launch Profiles
# Compatible with macOS Darwin (Bash 3.2+) and Linux
# ==============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
METADATA_FILE="$REPO_ROOT/deployment_metadata.json"

PROFILE="local"

usage() {
  cat << 'EOF'
Usage: ./run-frontend.sh [OPTIONS]

Launch the Social Spark CopilotKit Next.js frontend with explicit backend binding.

Options:
  --local, -l    Bind to local ADK backend (default: http://localhost:8000)
  --cloud, -c    Bind to deployed Vertex AI Reasoning Engine using deployment_metadata.json
  --help, -h     Show this help message and exit

Environment Variables:
  ADK_BACKEND_ORIGIN    Override target backend origin directly
EOF
  exit 0
}

# --- Pure-Bash CLI Argument Parsing ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --local|-l)
      PROFILE="local"
      shift
      ;;
    --cloud|-c)
      PROFILE="cloud"
      shift
      ;;
    --help|-h)
      usage
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Error: Unknown argument '$1'" >&2
      echo "Run './run-frontend.sh --help' for usage." >&2
      exit 1
      ;;
  esac
done

# --- Profile Resolution & Binding ---
if [[ "$PROFILE" == "cloud" ]]; then
  if [[ ! -f "$METADATA_FILE" ]]; then
    echo "Error: Cloud profile requested, but '$METADATA_FILE' was not found." >&2
    echo "Deploy a Reasoning Engine first with 'agents-cli deploy'." >&2
    exit 1
  fi

  # Extract remote_agent_runtime_id via defensive 3-tier cascade (jq -> python3 -> sed)
  if command -v jq >/dev/null 2>&1; then
    REMOTE_ID=$(jq -r '.remote_agent_runtime_id // empty' "$METADATA_FILE" 2>/dev/null || true)
  elif command -v python3 >/dev/null 2>&1; then
    REMOTE_ID=$(python3 -c "import json, sys; print(json.load(open(sys.argv[1])).get('remote_agent_runtime_id', ''))" "$METADATA_FILE" 2>/dev/null || true)
  else
    REMOTE_ID=$(sed -n 's/.*"remote_agent_runtime_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$METADATA_FILE" 2>/dev/null || true)
  fi

  if [[ -z "$REMOTE_ID" ]]; then
    echo "Error: 'remote_agent_runtime_id' is missing or empty in '$METADATA_FILE'." >&2
    exit 1
  fi

  # Extract location from resource ID: projects/<num>/locations/<location>/reasoningEngines/<id>
  LOCATION=$(echo "$REMOTE_ID" | cut -d'/' -f4)
  if [[ -z "$LOCATION" ]]; then
    echo "Error: Could not extract location from remote_agent_runtime_id: $REMOTE_ID" >&2
    exit 1
  fi

  export ADK_BACKEND_ORIGIN="https://${LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/${REMOTE_ID}/api"
  echo "=========================================================="
  echo " [run-frontend] Profile: CLOUD (Vertex AI Reasoning Engine)"
  echo " [run-frontend] Target:  $REMOTE_ID"
  echo " [run-frontend] Origin:  $ADK_BACKEND_ORIGIN"
  echo "=========================================================="
else
  export ADK_BACKEND_ORIGIN="http://localhost:8000"
  echo "=========================================================="
  echo " [run-frontend] Profile: LOCAL (:8000)"
  echo " [run-frontend] Origin:  $ADK_BACKEND_ORIGIN"
  echo "=========================================================="
fi

# --- Execution ---
cd "$REPO_ROOT/frontend"
npm install
exec npm run dev
