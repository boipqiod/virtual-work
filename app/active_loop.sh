#!/bin/bash
# ==============================================================================
# Proactive Conversation Loop Script
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

# Use ACTIVE_INTERVAL (seconds). Default to 2 hours (7200s)
INTERVAL=${ACTIVE_INTERVAL:-7200}

echo "Starting Proactive Conversation Loop..."
echo "Interval: ${INTERVAL}s"

while true; do
  echo "=== Running Proactive Check at $(date) ==="
  
  # Execute active runner to make decisions
  python3 "$SCRIPT_DIR/active_runner.py"
  
  # Dispatch output if created
  if [ -f "$WORKSPACE_DIR/agent_io/outbox/final_response.json" ]; then
    echo "New proactive message generated! Dispatching to Slack..."
    bash "$SCRIPT_DIR/queue_manager.sh"
  fi
  
  echo "Sleeping for ${INTERVAL}s..."
  sleep "$INTERVAL"
done
