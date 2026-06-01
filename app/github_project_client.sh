#!/bin/bash
# ==============================================================================
# GitHub Project Client Script
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$WORKSPACE_DIR/.env" ]; then
  # Load env variables safely without breaking on spaces
  while IFS= read -r line || [ -n "$line" ]; do
    if [[ ! "$line" =~ ^[[:space:]]*# ]] && [[ "$line" =~ [[:space:]]*=[[:space:]]* ]]; then
      key=$(echo "$line" | cut -d'=' -f1 | xargs)
      val=$(echo "$line" | cut -d'=' -f2- | xargs)
      val="${val%\"}"
      val="${val#\"}"
      val="${val%\'}"
      val="${val#\'}"
      export "$key"="$val"
    fi
  done < "$WORKSPACE_DIR/.env"
fi

if [ -z "$GITHUB_PROJECT_OWNER" ] || [ -z "$GITHUB_PROJECT_NUMBER" ]; then
  exit 0
fi

if ! command -v gh &> /dev/null; then
  exit 0
fi

STATUS_FILE="$WORKSPACE_DIR/agent_io/github_project_status.json"
if [ ! -f "$STATUS_FILE" ]; then
  echo '{"items": {}}' > "$STATUS_FILE"
fi

export STATUS_FILE
export GITHUB_PROJECT_OWNER
export GITHUB_PROJECT_NUMBER

# Run gh command and catch errors
PROJECT_DATA=$(gh project item-list "$GITHUB_PROJECT_NUMBER" --owner "$GITHUB_PROJECT_OWNER" --format json 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  if [[ "$PROJECT_DATA" == *"missing required scopes"* ]]; then
    echo "[GitHub Project Client] Auth scope missing. Please run: gh auth refresh -s read:project"
  else
    echo "[GitHub Project Client] Error fetching project: $PROJECT_DATA"
  fi
  exit 0
fi

export PROJECT_DATA
python3 -c "
import os, json, sys

status_file = os.environ.get('STATUS_FILE')
project_raw = os.environ.get('PROJECT_DATA', '{}')

try:
    project_json = json.loads(project_raw)
except Exception as e:
    print(f'[GitHub Project Client] Failed to parse project JSON: {e}')
    sys.exit(0)

# Check for structure
items = project_json.get('items', [])
if not items:
    sys.exit(0)

# Load previous status
try:
    with open(status_file, 'r') as f:
        prev_data = json.load(f)
except Exception:
    prev_data = {'items': {}}

prev_items = prev_data.get('items', {})
new_items_status = {}
detected_event = None

for item in items:
    item_id = item.get('id')
    if not item_id:
        continue
    
    current_status = item.get('status', 'Todo')
    content = item.get('content', {})
    title = content.get('title', 'Untitled')
    item_type = content.get('type', 'DraftIssue')
    number = content.get('number', '')
    url = content.get('url', '')
    
    new_items_status[item_id] = current_status
    
    # Check if we already knew about this item and if its status changed
    if item_id in prev_items:
        old_status = prev_items[item_id]
        if old_status != current_status:
            # We found a transition!
            detected_event = {
                'source': 'github_project',
                'action': 'card_moved',
                'item': {
                    'id': item_id,
                    'title': title,
                    'type': item_type,
                    'number': number,
                    'url': url,
                    'from_status': old_status,
                    'to_status': current_status
                }
            }
            # Just take the first transition to prevent flooding
            break
    else:
        # New item added to project
        pass

# Save the updated status
prev_data['items'] = new_items_status
with open(status_file, 'w') as f:
    json.dump(prev_data, f, indent=2)

if detected_event:
    # Check if there is already an event in the inbox
    out_path = os.path.join('$WORKSPACE_DIR', 'agent_io', 'inbox', 'current_event.json')
    if not os.path.exists(out_path):
        with open(out_path, 'w') as f:
            json.dump(detected_event, f, indent=2)
        print(f'[GitHub Project Client] Wrote event: \"{detected_event[\"item\"][\"title\"]}\" moved to {detected_event[\"item\"][\"to_status\"]}')
        
        # Save to raw history as well
        today = '$(date +%Y-%m-%d)'
        mem_dir = os.path.join('$WORKSPACE_DIR', 'agent_io', 'memory', today)
        os.makedirs(mem_dir, exist_ok=True)
        with open(os.path.join(mem_dir, 'raw_history.jsonl'), 'a') as f:
            f.write(json.dumps(detected_event) + '\n')
"
