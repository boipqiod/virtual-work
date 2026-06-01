#!/bin/bash
# ==============================================================================
# Daily Scheduler Script
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"
TODAY=$(date +"%Y-%m-%d")

STATUS_FILE="$WORKSPACE_DIR/agent_io/scheduler_status.json"
if [ ! -f "$STATUS_FILE" ]; then
  echo '{"last_run": ""}' > "$STATUS_FILE"
fi

export STATUS_FILE TODAY
python3 -c "
import os, json
status_file = os.environ.get('STATUS_FILE')
today = os.environ.get('TODAY')

with open(status_file, 'r') as f:
    data = json.load(f)

last_run = data.get('last_run', '')
if last_run != today:
    event = {
        'source': 'system',
        'type': 'daily_planning_trigger',
        'text': 'Good morning team! Please conduct your daily standup and sprint planning.'
    }
    out_path = os.path.join('$WORKSPACE_DIR', 'agent_io', 'inbox', 'current_event.json')
    with open(out_path, 'w') as f:
        json.dump(event, f, indent=2)
    
    data['last_run'] = today
    with open(status_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print('Daily Scheduler: Injected daily_planning_trigger into inbox.')
"
