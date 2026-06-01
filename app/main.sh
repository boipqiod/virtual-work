#!/bin/bash
# ==============================================================================
# Main Orchestrator Loop Script - Refactored
# ==============================================================================

# Verify python3 presence
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"

echo "Starting Virtual Office Orchestrator..."
echo "Press [CTRL+C] to stop."

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

INTERVAL=${LOOP_INTERVAL:-10}

while true; do
  echo "=== Running check at $(date) ==="
  
  # 1. Fetch Slack messages
  echo "Checking Slack messages..."
  bash "$SCRIPT_DIR/slack_client.sh"
  
  # 2. Fetch Github Events
  echo "Checking GitHub events..."
  bash "$SCRIPT_DIR/github_client.sh"
  
  # 3. Fetch GitHub Project Events
  echo "Checking GitHub Project events..."
  bash "$SCRIPT_DIR/github_project_client.sh"

  # 4. Check Daily Scheduler
  echo "Checking daily scheduler..."
  bash "$SCRIPT_DIR/daily_scheduler.sh"
  
  # 3. Check if there is a new event in inbox
  if [ -f "$WORKSPACE_DIR/agent_io/inbox/current_event.json" ]; then
    echo "Processing inbox event..."
    # Execute the AI agent pipeline (router -> personas -> validator)
    python3 "$SCRIPT_DIR/ai_runner.py"
    
    # Process outbox queue
    echo "Checking and processing outbox queue..."
    bash "$SCRIPT_DIR/queue_manager.sh"
    
    # Move processed event to avoid double-processing
    mv "$WORKSPACE_DIR/agent_io/inbox/current_event.json" "$WORKSPACE_DIR/agent_io/inbox/processed_event.json"
  fi
  
  echo "Sleeping for ${INTERVAL}s..."
  sleep "$INTERVAL"
done
