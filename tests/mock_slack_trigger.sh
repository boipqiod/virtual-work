#!/bin/bash
# ==============================================================================
# Mock Slack Trigger Test Script - Refactored
# ==============================================================================
# This script simulates an incoming Slack event.
# ==============================================================================

# Verify python3 presence
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required." >&2
  exit 1
fi

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

echo "=== Starting Mock Slack Trigger Event ==="

# 1. Ensure directories exist
mkdir -p "$WORKSPACE_DIR/agent_io/inbox"
mkdir -p "$WORKSPACE_DIR/agent_io/outbox"
mkdir -p "$WORKSPACE_DIR/agent_io/memory"

# Generate mock TS (current unix epoch)
MOCK_TS=$(date +%s).000000

# 2. Write simulated user message to inbox/current_event.json
echo "Creating mock Slack incoming message..."
cat << EOF > "$WORKSPACE_DIR/agent_io/inbox/current_event.json"
{
  "client_msg_id": "mock-uuid-12345",
  "type": "message",
  "text": "Hello team, can we get an update on the deployment plan?",
  "user": "U-MOCK-USER",
  "ts": "$MOCK_TS",
  "blocks": [
    {
      "type": "rich_text",
      "block_id": "mock-block",
      "elements": [
        {
          "type": "rich_text_section",
          "elements": [
            {
              "type": "text",
              "text": "Hello team, can we get an update on the deployment plan?"
            }
          ]
        }
      ]
    }
  ],
  "team": "T-MOCK-TEAM",
  "channel": "C-MOCK-CHANNEL",
  "event_ts": "$MOCK_TS"
}
EOF
echo "Saved incoming message to agent_io/inbox/current_event.json"

# 3. Create simulated response in outbox/final_response.json
echo "Creating mock agent responses..."
cat << EOF > "$WORKSPACE_DIR/agent_io/outbox/final_response.json"
[
  {
    "character": "Sarah",
    "text": "Thanks for asking! Aiden, could you share where we stand with the technical readiness?"
  },
  {
    "character": "Aiden",
    "text": "Sure, Sarah. We have resolved the major blockages. I am currently running the final sanity check on the staging environment."
  }
]
EOF
echo "Saved agent responses to agent_io/outbox/final_response.json"

# 4. Execute the Queue Manager to dispatch the outbox messages
echo "Executing app/queue_manager.sh to process the outbox..."
if [ -f "$WORKSPACE_DIR/app/queue_manager.sh" ]; then
  bash "$WORKSPACE_DIR/app/queue_manager.sh"
else
  echo "Error: queue_manager.sh not found." >&2
  exit 1
fi

# 5. Archive the event and clean up
echo "Archiving processed event..."
mv "$WORKSPACE_DIR/agent_io/inbox/current_event.json" "$WORKSPACE_DIR/agent_io/inbox/processed_event.json"

# 6. Save event to daily raw_history.jsonl (minified single-line JSON)
TODAY=$(date +"%Y-%m-%d")
HIST_DIR="$WORKSPACE_DIR/agent_io/memory/$TODAY"
mkdir -p "$HIST_DIR"
python3 -c "import json, sys; print(json.dumps(json.load(open(sys.argv[1]))))" "$WORKSPACE_DIR/agent_io/inbox/processed_event.json" >> "$HIST_DIR/raw_history.jsonl"

# 7. Update status.json last_ts
STATUS_FILE="$WORKSPACE_DIR/agent_io/status.json"
export STATUS_FILE MOCK_TS
python3 -c "
import os, json
status_file = os.environ.get('STATUS_FILE')
mock_ts = os.environ.get('MOCK_TS')
try:
    with open(status_file, 'r') as f:
        data = json.load(f)
except Exception:
    data = {}
data['last_ts'] = mock_ts
with open(status_file, 'w') as f:
    json.dump(data, f, indent=2)
"

echo "=== Mock Slack Trigger Event Completed Successfully ==="
