"""
GitHub Integration — Issues, PRs, Wiki, Events.
Uses gh CLI for actions, REST API for event polling.
"""

import os
import re
import json
import subprocess
import time
import urllib.request
from typing import Optional


def _env(key: str) -> str:
    return os.environ.get(key, "")


class GitHubClient:
    def __init__(self):
        self.repo = _env("GITHUB_REPO")
        self.token = _env("GITHUB_TOKEN")
        self._project_state_cache = ""
        self._project_state_ts = 0
        self._project_state_ttl = 300  # 5 minutes
        # Exponential backoff for event polling
        self._event_backoff = 0  # seconds to skip
        self._event_next_allowed = 0  # timestamp
    
    def fetch_new_events(self, last_event_id: str = "") -> list:
        """Fetch new repository events since last_event_id. With exponential backoff."""
        if not self.repo:
            return []
        
        # Check backoff
        now = time.time()
        if now < self._event_next_allowed:
            return []
        
        url = f"https://api.github.com/repos/{self.repo}/events?per_page=5"
        req = urllib.request.Request(url)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                events = json.loads(resp.read().decode())
            
            # Success — reset backoff
            self._event_backoff = 0
            
            if not events:
                return []
            
            # Filter to only new events
            new_events = []
            for ev in events:
                ev_id = str(ev.get("id", ""))
                if ev_id == last_event_id:
                    break
                ev["source"] = "github"
                new_events.append(ev)
            
            # Return oldest first
            new_events.reverse()
            return new_events
        
        except Exception as e:
            # Exponential backoff: 60s, 120s, 240s, 480s, max 900s (15 min)
            self._event_backoff = min((self._event_backoff or 30) * 2, 900)
            self._event_next_allowed = time.time() + self._event_backoff
            print(f"[GitHub] Error fetching events: {e}. Backoff {self._event_backoff}s")
            return []
    
    def get_project_state(self) -> str:
        """Get a summary of current issues and PRs (cached for 5 min)."""
        now = time.time()
        if now - self._project_state_ts < self._project_state_ttl and self._project_state_cache:
            return self._project_state_cache
        
        if not self.repo:
            return "GitHub repo not configured."
        
        lines = []
        
        # Open issues
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "-R", self.repo, "--limit", "5",
                 "--json", "number,title,state,assignees"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                issues = json.loads(result.stdout)
                for issue in issues:
                    assignee = issue.get("assignees", [{}])
                    assignee_name = assignee[0].get("login", "unassigned") if assignee else "unassigned"
                    lines.append(f"- Issue #{issue['number']}: {issue['title']} ({issue['state']}, {assignee_name})")
        except Exception as e:
            print(f"[GitHub] Error fetching issues: {e}")
        
        # Open PRs
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "-R", self.repo, "--limit", "5",
                 "--json", "number,title,state,author"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                prs = json.loads(result.stdout)
                for pr in prs:
                    author = pr.get("author", {}).get("login", "unknown")
                    lines.append(f"- PR #{pr['number']}: {pr['title']} ({pr['state']}, by {author})")
        except Exception as e:
            print(f"[GitHub] Error fetching PRs: {e}")
        
        self._project_state_cache = "\n".join(lines) if lines else "No active issues or PRs."
        self._project_state_ts = now
        return self._project_state_cache
    
    def _get_agent_token(self, agent_name: str) -> Optional[str]:
        """Obtain a GitHub App installation token for the agent if configured."""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        auth_script = os.path.join(script_dir, "github_app_auth.js")
        
        if not os.path.exists(auth_script):
            return None
            
        upper_name = agent_name.upper()
        app_id = os.environ.get(f"{upper_name}_APP_ID")
        pem_path = os.environ.get(f"{upper_name}_PEM_PATH")
        
        if not app_id or not pem_path:
            return None
            
        try:
            result = subprocess.run(
                ["node", auth_script, agent_name],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                token = result.stdout.strip()
                if token:
                    return token
            else:
                print(f"[GitHub] Error getting token for {agent_name}: {result.stderr.strip()}")
        except Exception as e:
            print(f"[GitHub] Error calling token script for {agent_name}: {e}")
            
        return None

    def create_issue(self, title: str, body: str, agent_name: str) -> Optional[str]:
        """Create a GitHub issue. Returns the issue URL or None."""
        if not self.repo:
            print(f"[GitHub DRY RUN] Create issue: {title}")
            return None
        
        token = self._get_agent_token(agent_name) or self.token
        env = os.environ.copy()
        if token:
            env["GH_TOKEN"] = token
        
        try:
            result = subprocess.run(
                ["gh", "issue", "create", "-R", self.repo,
                 "--title", title, "--body", body],
                env=env, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                print(f"[GitHub] Created issue: {url}")
                return url
            else:
                print(f"[GitHub] Error creating issue: {result.stderr}")
                return None
        except Exception as e:
            print(f"[GitHub] Error: {e}")
            return None
    
    def comment_issue(self, issue_number: str, body: str, agent_name: str):
        """Add a comment to an issue or PR."""
        if not self.repo:
            print(f"[GitHub DRY RUN] Comment on #{issue_number}: {body[:50]}...")
            return
        
        url = f"https://github.com/{self.repo}/issues/{issue_number}"
        
        token = self._get_agent_token(agent_name) or self.token
        env = os.environ.copy()
        if token:
            env["GH_TOKEN"] = token
            # When authenticated via App, we don't need the bold prefix
            full_body = body
        else:
            display_name = {
                "Liam": "Liam (PM)",
                "Aiden": "Aiden (Tech Lead)",
                "Sarah": "Sarah (CEO)",
                "Chloe": "Chloe (Sales)",
            }.get(agent_name, agent_name)
            full_body = f"**[{display_name}]**\n\n{body}"
        
        try:
            result = subprocess.run(
                ["gh", "issue", "comment", url, "--body", full_body],
                env=env, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                print(f"[GitHub] Commented on #{issue_number}")
            else:
                print(f"[GitHub] Error commenting: {result.stderr}")
        except Exception as e:
            print(f"[GitHub] Error: {e}")
    
    def push_wiki(self, title: str, content: str, agent_name: str):
        """Write a wiki page to the local shout_wiki/ directory."""
        wiki_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "shout_wiki"
        )
        os.makedirs(wiki_dir, exist_ok=True)
        
        safe_title = re.sub(r'[ /\\:*?<>|]', '-', title)
        filepath = os.path.join(wiki_dir, f"{safe_title}.md")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"[GitHub] Wiki page written: {filepath}")
        # TODO: git commit + push to wiki repo if configured
