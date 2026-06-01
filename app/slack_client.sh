#!/bin/bash
# ==============================================================================
# Slack Client Script - Refactored
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

# Verify SLACK_BOT_TOKEN and SLACK_CHANNEL_ID
if [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_CHANNEL_ID" ]; then
  echo "Error: SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not set." >&2
  exit 1
fi

STATUS_FILE="$WORKSPACE_DIR/agent_io/status.json"
# Ensure status.json exists
if [ ! -f "$STATUS_FILE" ]; then
  echo '{"last_ts": "", "mode": "normal"}' > "$STATUS_FILE"
fi

# Read last_ts via environment variable import in Python
export STATUS_FILE
LAST_TS=$(python3 -c "import os, json; print(json.load(open(os.environ.get('STATUS_FILE'))).get('last_ts', ''))")

# Fetch latest message from Slack channel history
RESPONSE=$(curl -s -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  "https://slack.com/api/conversations.history?channel=$SLACK_CHANNEL_ID&limit=1")

# Validate Slack API response
export RESPONSE
OK=$(python3 -c "import os, json; res=json.loads(os.environ.get('RESPONSE', '{}')); print(res.get('ok', False))")
if [ "$OK" != "True" ]; then
  echo "Error fetching slack channel history: $RESPONSE" >&2
  exit 1
fi

# Extract latest message info
LATEST_MSG=$(python3 -c "import os, json; res=json.loads(os.environ.get('RESPONSE', '{}')); msgs=res.get('messages', []); msg=msgs[0] if msgs else {}; 
if msg: msg['source'] = 'slack'
print(json.dumps(msg))")

if [ "$LATEST_MSG" = "{}" ]; then
  echo "No messages in slack channel."
  exit 0
fi

export LATEST_MSG
NEW_TS=$(python3 -c "import os, json; msg=json.loads(os.environ.get('LATEST_MSG', '{}')); print(msg.get('ts', ''))")

# Compare ts using python3
export NEW_TS LAST_TS
IS_NEW=$(python3 -c "import os; new_ts=os.environ.get('NEW_TS'); last_ts=os.environ.get('LAST_TS'); print(float(new_ts) > float(last_ts) if last_ts and new_ts else True)")

if [ "$IS_NEW" = "True" ]; then
  echo "New message detected: $NEW_TS"
  # Write to inbox/current_event.json
  mkdir -p "$WORKSPACE_DIR/agent_io/inbox"
  echo "$LATEST_MSG" > "$WORKSPACE_DIR/agent_io/inbox/current_event.json"

  # Save to daily raw_history.jsonl
  TODAY=$(date +"%Y-%m-%d")
  HIST_DIR="$WORKSPACE_DIR/agent_io/memory/$TODAY"
  mkdir -p "$HIST_DIR"
  echo "$LATEST_MSG" >> "$HIST_DIR/raw_history.jsonl"

  # Update status.json
  export STATUS_FILE NEW_TS
  python3 -c "
import os, json
status_file = os.environ.get('STATUS_FILE')
new_ts = os.environ.get('NEW_TS')
with open(status_file, 'r') as f:
    data = json.load(f)
data['last_ts'] = new_ts
with open(status_file, 'w') as f:
    json.dump(data, f, indent=2)
"
else
  echo "No new message."
fi
