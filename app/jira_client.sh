#!/bin/bash
# ==============================================================================
# Jira Client Script
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$WORKSPACE_DIR/.env" ]; then
  export $(grep -v '^#' "$WORKSPACE_DIR/.env" | xargs)
fi

if [ -z "$JIRA_DOMAIN" ] || [ -z "$JIRA_EMAIL" ] || [ -z "$JIRA_API_TOKEN" ] || [ -z "$JIRA_PROJECT_KEY" ]; then
  exit 0
fi

# Clean JIRA_DOMAIN by removing leading protocol scheme if present
CLEAN_JIRA_DOMAIN=$(echo "$JIRA_DOMAIN" | sed -e 's|^https://||' -e 's|^http://||')

STATUS_FILE="$WORKSPACE_DIR/agent_io/jira_status.json"
if [ ! -f "$STATUS_FILE" ]; then
  echo '{"last_updated": ""}' > "$STATUS_FILE"
fi

export STATUS_FILE
LAST_UPDATED=$(python3 -c "import os, json; print(json.load(open(os.environ.get('STATUS_FILE'))).get('last_updated', ''))")

JQL="project=$JIRA_PROJECT_KEY ORDER BY updated DESC"
JQL_ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$JQL'))")

RESPONSE=$(curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -H "Accept: application/json" \
  "https://$CLEAN_JIRA_DOMAIN/rest/api/3/search?jql=$JQL_ENCODED&maxResults=1")

export RESPONSE LAST_UPDATED
python3 -c "
import os, json
try:
    res = json.loads(os.environ.get('RESPONSE', '{}'))
except:
    exit(0)
    
issues = res.get('issues', [])
if not issues: exit(0)
issue = issues[0]
updated = issue.get('fields', {}).get('updated', '')
last_updated = os.environ.get('LAST_UPDATED', '')

if not updated or updated == last_updated: exit(0)

issue['source'] = 'jira'
out_path = os.path.join('$WORKSPACE_DIR', 'agent_io', 'inbox', 'current_event.json')
with open(out_path, 'w') as f:
    json.dump(issue, f, indent=2)

status_file = os.environ.get('STATUS_FILE')
with open(status_file, 'r') as f: data = json.load(f)
data['last_updated'] = updated
with open(status_file, 'w') as f: json.dump(data, f, indent=2)

today = '$(date +%Y-%m-%d)'
mem_dir = os.path.join('$WORKSPACE_DIR', 'agent_io', 'memory', today)
os.makedirs(mem_dir, exist_ok=True)
with open(os.path.join(mem_dir, 'raw_history.jsonl'), 'a') as f:
    f.write(json.dumps(issue) + '\n')

print(f'New Jira event: {issue.get(\"key\")}')
"
