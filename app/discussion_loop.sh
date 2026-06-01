#!/bin/bash
# ==============================================================================
# Discussion Loop Script
# Drives AI-to-AI dialogue for tasks in "discussing" state.
# Runs on a 30-minute interval by default (DISCUSSION_INTERVAL env var).
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"

# Robustly load env
load_env() {
  local env_file="$1"
  if [ -f "$env_file" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      if [[ ! "$line" =~ ^[[:space:]]*# ]] && [[ "$line" =~ [[:space:]]*=[[:space:]]* ]]; then
        local key=$(echo "$line" | cut -d'=' -f1 | xargs)
        local val=$(echo "$line" | cut -d'=' -f2- | xargs)
        val="${val%\"}"
        val="${val#\"}"
        val="${val%\'}"
        val="${val#\'}"
        export "$key"="$val"
      fi
    done < "$env_file"
  fi
}

load_env "$WORKSPACE_DIR/.env"

# Use DISCUSSION_INTERVAL (seconds). Default to 30 minutes (1800s)
INTERVAL=${DISCUSSION_INTERVAL:-1800}

echo "Starting Discussion Loop..."
echo "Interval: ${INTERVAL}s"

while true; do
  echo "=== Running Discussion Cycle at $(date) ==="

  # Execute discussion runner to advance AI-to-AI dialogues
  python3 "$SCRIPT_DIR/discussion_runner.py"

  # Dispatch output if created
  if [ -f "$WORKSPACE_DIR/agent_io/outbox/final_response.json" ]; then
    echo "Discussion responses generated! Dispatching..."
    bash "$SCRIPT_DIR/queue_manager.sh"
  fi

  echo "Sleeping for ${INTERVAL}s..."
  sleep "$INTERVAL"
done
