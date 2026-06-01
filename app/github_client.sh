#!/bin/bash
# ==============================================================================
# GitHub Client Script - Refactored
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$WORKSPACE_DIR/.env" ]; then
  export $(grep -v '^#' "$WORKSPACE_DIR/.env" | xargs)
fi

if [ -z "$GITHUB_REPO" ]; then exit 0; fi
if ! command -v gh &> /dev/null; then exit 0; fi

STATUS_FILE="$WORKSPACE_DIR/agent_io/github_status.json"
if [ ! -f "$STATUS_FILE" ]; then
  echo '{"last_id": ""}' > "$STATUS_FILE"
fi

export STATUS_FILE
LAST_ID=$(python3 -c "import os, json; print(json.load(open(os.environ.get('STATUS_FILE'))).get('last_id', ''))")

EVENTS=$(gh api "repos/$GITHUB_REPO/events?per_page=1" 2>/dev/null)
if [ $? -ne 0 ] || [ -z "$EVENTS" ] || [ "$EVENTS" = "[]" ]; then exit 0; fi

export EVENTS LAST_ID
python3 -c "
import os, json
events = json.loads(os.environ.get('EVENTS', '[]'))
if not events: exit(0)
ev = events[0]
ev_id = str(ev.get('id', ''))
last_id = str(os.environ.get('LAST_ID', ''))
if not ev_id or ev_id == last_id: exit(0)

ev['source'] = 'github'
out_path = os.path.join('$WORKSPACE_DIR', 'agent_io', 'inbox', 'current_event.json')
with open(out_path, 'w') as f:
    json.dump(ev, f, indent=2)

status_file = os.environ.get('STATUS_FILE')
with open(status_file, 'r') as f: data = json.load(f)
data['last_id'] = ev_id
with open(status_file, 'w') as f: json.dump(data, f, indent=2)

today = '$(date +%Y-%m-%d)'
mem_dir = os.path.join('$WORKSPACE_DIR', 'agent_io', 'memory', today)
os.makedirs(mem_dir, exist_ok=True)
with open(os.path.join(mem_dir, 'raw_history.jsonl'), 'a') as f:
    f.write(json.dumps(ev) + '\n')

print(f'New GitHub event: {ev_id}')
"
