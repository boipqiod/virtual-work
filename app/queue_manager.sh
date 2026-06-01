#!/bin/bash
# ==============================================================================
# Queue Manager Script - Refactored for GitHub Issues & Wiki Integration
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$WORKSPACE_DIR/.env" ]; then
  export $(grep -v '^#' "$WORKSPACE_DIR/.env" | xargs)
fi

OUTBOX_FILE="$WORKSPACE_DIR/agent_io/outbox/final_response.json"

if [ ! -f "$OUTBOX_FILE" ]; then
  echo "No messages in outbox."
  exit 0
fi

export OUTBOX_FILE
export WORKSPACE_DIR

python3 -c "
import json
import urllib.request
import urllib.parse
import os
import sys
import subprocess
import re

sys.path.insert(0, os.path.join(os.environ.get('WORKSPACE_DIR', ''), 'app'))

outbox_path = os.environ.get('OUTBOX_FILE')
workspace_dir = os.environ.get('WORKSPACE_DIR', '')

CHARACTER_CONFIG = {
    'Sarah': {'username': 'Sarah (CEO)', 'icon_emoji': ':woman-office-worker:', 'webhook': os.environ.get('SLACK_WEBHOOK_SARAH', '')},
    'Liam': {'username': 'Liam (PM)', 'icon_emoji': ':clipboard:', 'webhook': os.environ.get('SLACK_WEBHOOK_LIAM', '')},
    'Chloe': {'username': 'Chloe (Sales)', 'icon_emoji': ':moneybag:', 'webhook': os.environ.get('SLACK_WEBHOOK_CHLOE', '')},
    'Aiden': {'username': 'Aiden (Tech Lead)', 'icon_emoji': ':computer:', 'webhook': os.environ.get('SLACK_WEBHOOK_AIDEN', '')}
}

AUTHOR_MAP = {
    'Sarah': {'name': 'Sarah', 'email': 'sarah@virtualoffice.com'},
    'Liam': {'name': 'Liam', 'email': 'liam@virtualoffice.com'},
    'Chloe': {'name': 'Chloe', 'email': 'chloe@virtualoffice.com'},
    'Aiden': {'name': 'Aiden', 'email': 'aiden@virtualoffice.com'}
}

def get_bot_token(author_name):
    try:
        auth_script = os.path.join(workspace_dir, 'app', 'github_app_auth.js')
        res = subprocess.run(['node', auth_script, author_name], capture_output=True, text=True)
        if res.returncode == 0:
            return res.stdout.strip()
        else:
            print(f\"Auth failed for {author_name}: {res.stderr.strip()}\")
            return None
    except Exception as e:
        print(f\"Error fetching token: {e}\")
        return None

def create_github_issue(summary, description, author_name):
    repo_path = os.environ.get('PRODUCT_REPO_PATH') or workspace_dir
    repo = os.environ.get('GITHUB_REPO')
    cmd = [
        'gh', 'issue', 'create',
        '--title', summary,
        '--body', description or 'Created by Virtual Office Agent.'
    ]
    if repo:
        cmd += ['-R', repo]
    
    token = get_bot_token(author_name)
    env = os.environ.copy()
    if token:
        env['GH_TOKEN'] = token
        
    try:
        res = subprocess.run(cmd, cwd=repo_path, env=env, capture_output=True, text=True, check=True)
        issue_url = res.stdout.strip()
        print(f'Successfully created GitHub issue: {issue_url}')
        return True, issue_url
    except Exception as e:
        err_msg = e.stderr if hasattr(e, 'stderr') else str(e)
        print(f'Error creating GitHub issue: {err_msg}')
        return False, err_msg

def publish_to_wiki(page_title, markdown_content, author_name, author_email, token):
    wiki_url = os.environ.get('WIKI_REPO_URL')
    if not wiki_url:
        print('WIKI_REPO_URL env variable not set.')
        return False, 'WIKI_REPO_URL not set.'
    
    temp_wiki_dir = '/tmp/shout_wiki_temp'
    
    auth_wiki_url = wiki_url
    if token and wiki_url.startswith('https://github.com/'):
        auth_wiki_url = wiki_url.replace('https://github.com/', f'https://x-access-token:{token}@github.com/')
        
    try:
        if not os.path.exists(temp_wiki_dir):
            subprocess.run(['git', 'clone', auth_wiki_url, temp_wiki_dir], check=True, capture_output=True)
        else:
            subprocess.run(['git', '-C', temp_wiki_dir, 'remote', 'set-url', 'origin', auth_wiki_url], check=True, capture_output=True)
            subprocess.run(['git', '-C', temp_wiki_dir, 'pull'], check=True, capture_output=True)
        
        safe_title = page_title.replace(' ', '-')
        filepath = os.path.join(temp_wiki_dir, f'{safe_title}.md')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        subprocess.run(['git', '-C', temp_wiki_dir, 'add', f'{safe_title}.md'], check=True, capture_output=True)
        
        status_res = subprocess.run(['git', '-C', temp_wiki_dir, 'status', '--porcelain'], check=True, capture_output=True, text=True)
        if status_res.stdout.strip():
            commit_cmd = [
                'git', '-C', temp_wiki_dir,
                '-c', f'user.name={author_name}',
                '-c', f'user.email={author_email}',
                'commit', '-m', f'docs: update {page_title} wiki page'
            ]
            subprocess.run(commit_cmd, check=True, capture_output=True)
            subprocess.run(['git', '-C', temp_wiki_dir, 'push', 'origin', 'HEAD'], check=True, capture_output=True)
            print(f'Successfully pushed wiki page: {page_title}')
        else:
            print(f'Wiki page {page_title} is already up to date.')
        
        base_url = wiki_url.replace('.wiki.git', '/wiki').replace('git@github.com:', 'https://github.com/')
        wiki_page_url = f'{base_url}/{safe_title}'
        return True, wiki_page_url
        
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr if hasattr(e, 'stderr') else str(e)
        print(f'Error in Git Wiki operations: {err_msg}')
        return False, err_msg
    except Exception as e:
        print(f'Error in Wiki publishing: {e}')
        return False, str(e)

try:
    with open(outbox_path, 'r') as f:
        data = json.load(f)
except Exception as e:
    print(f'Error reading outbox: {e}')
    exit(1)

responses = data if isinstance(data, list) else data.get('responses', [data] if isinstance(data, dict) else [])

current_event_path = os.path.join(workspace_dir, 'agent_io', 'inbox', 'current_event.json')
event_context = {}
try:
    with open(current_event_path, 'r') as f:
        event_context = json.load(f)
except:
    pass

for resp in responses:
    char_name = resp.get('character', resp.get('sender', 'System'))
    text = resp.get('text', '')
    target_channel = resp.get('target_channel', 'slack')
    
    if not text: continue
    
    cfg = CHARACTER_CONFIG.get(char_name, {'username': char_name, 'icon_emoji': ':robot_face:', 'webhook': ''})
    formatted_header = f\"🦊 [{cfg['username']}]\"
    
    # Check for GitHub Wiki publication trigger: [WIKI_WRITE: Page Title]
    match = re.match(r'^\[WIKI_WRITE:\s*(.*?)\]\s*\n?(.*)', text, re.DOTALL | re.IGNORECASE)
    if match:
        page_title = match.group(1).strip()
        markdown_body = match.group(2).strip()
        
        author_info = AUTHOR_MAP.get(char_name, {'name': char_name, 'email': f'{char_name.lower()}@virtualoffice.com'})
        wiki_url = os.environ.get('WIKI_REPO_URL')
        
        if wiki_url:
            print(f'Detected Wiki action. Publishing page: {page_title}...')
            token = get_bot_token(char_name)
            success, wiki_page_url = publish_to_wiki(page_title, markdown_body, author_info['name'], author_info['email'], token)
            if success:
                text = f\"I've published the document to the GitHub Wiki: **{page_title}**\\nView here: {wiki_page_url}\"
            else:
                text = f\"Tried to publish **{page_title}** to GitHub Wiki but failed: {wiki_page_url}\"
        else:
            print('--- DRY RUN (WIKI) ---')
            print(f'Wiki: {page_title}')
            print(f'Content:\n{markdown_body}')
            print('----------------------')
            text = f\"[Dry Run] Published GitHub Wiki page: **{page_title}**\"

    # Check for GitHub Issue creation trigger: [ISSUE_CREATE: Summary | Description]
    issue_create_match = re.search(r'\[ISSUE_CREATE:\s*(.*?)(?:\s*\|\s*(.*?))?\]', text, re.DOTALL | re.IGNORECASE)
    if issue_create_match:
        issue_summary = issue_create_match.group(1).strip()
        issue_desc = issue_create_match.group(2).strip() if issue_create_match.group(2) else ''
        
        repo_path = os.environ.get('PRODUCT_REPO_PATH')
        
        if repo_path:
            print(f'Detected GitHub Issue creation action. Creating issue: {issue_summary}...')
            success, issue_link = create_github_issue(issue_summary, issue_desc, char_name)
            if success:
                text = text.replace(issue_create_match.group(0), f'**[Issue: {issue_summary}]({issue_link})**')
            else:
                text = text.replace(issue_create_match.group(0), f'[Failed to create GitHub Issue: {issue_link}]')
        else:
            print('--- DRY RUN (GITHUB ISSUE CREATE) ---')
            print(f'Summary: {issue_summary}')
            print(f'Description: {issue_desc}')
            print('-------------------------------------')
            text = text.replace(issue_create_match.group(0), f'**[Dry Run Issue: {issue_summary}]**')

    # Check for GitHub Issue comment trigger: [ISSUE_COMMENT: #number]
    issue_comment_match = re.search(r'\[ISSUE_COMMENT:\s*#?(\d+)\]\s*\n?(.*)', text, re.DOTALL | re.IGNORECASE)
    if issue_comment_match:
        issue_number = issue_comment_match.group(1).strip()
        comment_body = issue_comment_match.group(2).strip()
        repo = os.environ.get('GITHUB_REPO', '')
        repo_path = os.environ.get('PRODUCT_REPO_PATH') or workspace_dir

        if repo:
            issue_url = f'https://github.com/{repo}/issues/{issue_number}'
            body = f\"{formatted_header}\\n\\n{comment_body}\"
            print(f'Detected Issue Comment action. Commenting on issue #{issue_number}...')
            try:
                token = get_bot_token(char_name)
                env = os.environ.copy()
                if token:
                    env['GH_TOKEN'] = token
                cmd = ['gh', 'issue', 'comment', issue_url, '--body', body]
                subprocess.run(cmd, cwd=repo_path, env=env, check=True, capture_output=True)
                print(f'Successfully commented on issue #{issue_number}.')
                text = f\"Commented on GitHub Issue #{issue_number}: {issue_url}\"
            except Exception as e:
                err_msg = e.stderr if hasattr(e, 'stderr') else str(e)
                print(f'Error commenting on issue #{issue_number}: {err_msg}')
                text = f\"Failed to comment on GitHub Issue #{issue_number}: {err_msg}\"
        else:
            print('--- DRY RUN (ISSUE COMMENT) ---')
            print(f'Issue: #{issue_number}')
            print(f'Comment: {comment_body}')
            print('-------------------------------')
            text = f\"[Dry Run] Commented on Issue #{issue_number}\"

    # Check for GitHub Issue close trigger: [ISSUE_CLOSE: #number]
    issue_close_match = re.search(r'\[ISSUE_CLOSE:\s*#?(\d+)\]', text, re.IGNORECASE)
    if issue_close_match:
        issue_number = issue_close_match.group(1).strip()
        repo = os.environ.get('GITHUB_REPO', '')
        repo_path = os.environ.get('PRODUCT_REPO_PATH') or workspace_dir

        if repo:
            issue_url = f'https://github.com/{repo}/issues/{issue_number}'
            print(f'Detected Issue Close action. Closing issue #{issue_number}...')
            try:
                token = get_bot_token(char_name)
                env = os.environ.copy()
                if token:
                    env['GH_TOKEN'] = token
                cmd = ['gh', 'issue', 'close', issue_url]
                if repo:
                    cmd += ['-R', repo]
                subprocess.run(cmd, cwd=repo_path, env=env, check=True, capture_output=True)
                print(f'Successfully closed issue #{issue_number}.')
                text = text.replace(issue_close_match.group(0), f'Closed GitHub Issue #{issue_number}: {issue_url}')
            except Exception as e:
                err_msg = e.stderr if hasattr(e, 'stderr') else str(e)
                print(f'Error closing issue #{issue_number}: {err_msg}')
                text = text.replace(issue_close_match.group(0), f'[Failed to close Issue #{issue_number}: {err_msg}]')
        else:
            print('--- DRY RUN (ISSUE CLOSE) ---')
            print(f'Issue: #{issue_number}')
            print('-----------------------------')
            text = text.replace(issue_close_match.group(0), f'[Dry Run] Closed Issue #{issue_number}')

    # Check for Task Update trigger: [TASK_UPDATE: TASK-001 | field | value]
    task_update_match = re.search(r'\[TASK_UPDATE:\s*(TASK-\d+)\s*\|\s*(\w+)\s*\|\s*(.*?)\]', text, re.IGNORECASE)
    if task_update_match:
        task_id = task_update_match.group(1).strip()
        task_field = task_update_match.group(2).strip()
        task_value = task_update_match.group(3).strip()
        print(f'Detected Task Update action. Updating {task_id}: {task_field} = {task_value}')
        try:
            from task_manager import update_task_status, update_task_field
            if task_field == 'status':
                update_task_status(task_id, task_value)
            else:
                update_task_field(task_id, task_field, task_value)
            print(f'Successfully updated task {task_id}.')
        except Exception as e:
            print(f'Error updating task {task_id}: {e}')
        text = text.replace(task_update_match.group(0), '').strip()

    if target_channel == 'slack':
        webhook_url = cfg.get('webhook') or os.environ.get('SLACK_WEBHOOK_URL', '')
        payload = {'text': text, 'username': cfg['username'], 'icon_emoji': cfg['icon_emoji']}
        if not webhook_url:
            print('--- DRY RUN (SLACK) ---')
            print(f'[{cfg[\"username\"]} {cfg[\"icon_emoji\"]}]\\n{text}')
            print('-----------------------')
        else:
            req = urllib.request.Request(webhook_url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req) as response:
                    print(f'Sent Slack message from {char_name}. Status: {response.getcode()}')
            except Exception as e:
                print(f'Error sending Slack for {char_name}: {e}')
                
    elif target_channel == 'github' or target_channel == 'jira' or target_channel == 'github_project':
        pr_url = event_context.get('html_url') or event_context.get('pull_request', {}).get('html_url') or event_context.get('issue', {}).get('html_url') or event_context.get('item', {}).get('url')
        if pr_url:
            body = f\"{formatted_header}\\n\\n{text}\"
            print(f'Posting comment to GitHub: {pr_url}...')
            try:
                token = get_bot_token(char_name)
                env = os.environ.copy()
                if token:
                    env['GH_TOKEN'] = token
                subprocess.run(['gh', 'issue', 'comment', pr_url, '--body', body], env=env, check=True, capture_output=True)
                print(f'Successfully commented on GitHub.')
            except Exception as e:
                err_msg = e.stderr if hasattr(e, 'stderr') else str(e)
                print(f'Error commenting on GitHub: {err_msg}')
        else:
            print(f'Error: Could not find GitHub URL in event context for {char_name}.')

# Clear outbox
try:
    os.remove(outbox_path)
    print('Cleared outbox file.')
except Exception as e:
    print(f'Error clearing outbox: {e}')
"
