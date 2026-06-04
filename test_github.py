#!/usr/bin/env python3
"""
Virtual Office — GitHub Connectivity Smoke Test (Including App Personas)
Verifies GITHUB_REPO, GITHUB_TOKEN, and gh CLI before running the full system.
Also tests the 4 GitHub App Personas (Liam, Aiden, Sarah, Chloe) using PEM keys.

Usage: python3 test_github.py [--write]
  Without --write: tests reading connectivity and verifies App tokens (safe)
  With --write: creates a test issue as Liam, posts comments as Aiden, Sarah, Chloe, 
                and closes it as Liam using their App tokens to verify write access.
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.error

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
NC = "\033[0m"

def header(s): print(f"\n{CYAN}━━━ {s} ━━━{NC}")
def passed(s): print(f"  {GREEN}PASS{NC} {s}")
def failed(s): print(f"  {RED}FAIL{NC} {s}")
def info(s): print(f"  {YELLOW}INFO{NC} {s}")

WRITE_MODE = "--write" in sys.argv

# ─────────────────────────────────────────────────────────────────────────────
header("1. Environment Variables & App Configurations")
# ─────────────────────────────────────────────────────────────────────────────

repo = os.environ.get("GITHUB_REPO", "")
token = os.environ.get("GITHUB_TOKEN", "")

if repo:
    passed(f"GITHUB_REPO = {repo}")
else:
    failed("GITHUB_REPO is not set in .env")

if token:
    passed(f"GITHUB_TOKEN = {token[:8]}...")
else:
    info("GITHUB_TOKEN is not set in .env (will rely on active 'gh auth' CLI credentials for backup)")

# Verify if App configs are set
agents = ["Liam", "Aiden", "Sarah", "Chloe"]
app_configs_found = True
for agent in agents:
    app_id = os.environ.get(f"{agent.upper()}_APP_ID", "")
    pem_path = os.environ.get(f"{agent.upper()}_PEM_PATH", "")
    if app_id and pem_path:
        passed(f"{agent} App Configured (ID: {app_id}, PEM: {pem_path})")
    else:
        failed(f"{agent} App Missing configurations ({agent.upper()}_APP_ID or {agent.upper()}_PEM_PATH is empty)")
        app_configs_found = False

# ─────────────────────────────────────────────────────────────────────────────
header("2. GitHub CLI (gh) Verification")
# ─────────────────────────────────────────────────────────────────────────────

try:
    which_gh = subprocess.run(["which", "gh"], capture_output=True, text=True)
    if which_gh.returncode == 0:
        passed(f"gh CLI found: {which_gh.stdout.strip()}")
        
        # Test auth status
        auth_status = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        if auth_status.returncode == 0:
            passed("gh CLI is authenticated")
            for line in auth_status.stderr.splitlines():
                if "Logged in to" in line or "Account:" in line or "Token:" in line:
                    info(f"  {line.strip()}")
        else:
            failed(f"gh CLI authentication check failed: {auth_status.stderr.strip()}")
    else:
        failed("gh CLI is not installed or not in PATH")
except Exception as e:
    failed(f"Failed to check gh CLI: {e}")

# ─────────────────────────────────────────────────────────────────────────────
header("3. GitHub App Personas — Token Generation & Read Check")
# ─────────────────────────────────────────────────────────────────────────────

agent_tokens = {}
auth_script = "integrations/github_app_auth.js"

if not os.path.exists(auth_script):
    failed(f"Auth script not found at {auth_script}")
    app_configs_found = False

if app_configs_found:
    for agent in agents:
        try:
            # Generate token using integrations/github_app_auth.js
            result = subprocess.run(
                ["node", auth_script, agent],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                agent_token = result.stdout.strip()
                if agent_token:
                    passed(f"{agent} token generated: {agent_token[:12]}...")
                    agent_tokens[agent] = agent_token
                    
                    # Test REST API read using this specific agent token
                    url = f"https://api.github.com/repos/{repo}"
                    req = urllib.request.Request(url)
                    req.add_header("Authorization", f"Bearer {agent_token}")
                    req.add_header("Accept", "application/vnd.github+json")
                    req.add_header("User-Agent", "virtual-office-smoke-test")
                    
                    try:
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            passed(f"  {agent} token has read access to {repo} (HTTP 200)")
                    except urllib.error.HTTPError as e:
                        failed(f"  {agent} token failed read access test: HTTP {e.code} {e.reason}")
                else:
                    failed(f"{agent} generated token is empty")
            else:
                failed(f"{agent} token generation failed: {result.stderr.strip()}")
        except Exception as e:
            failed(f"Error checking {agent} token: {e}")
else:
    info("Skipping GitHub App token tests due to missing configurations or script.")

# ─────────────────────────────────────────────────────────────────────────────
header("4. REST API — General Event Polling (Read)")
# ─────────────────────────────────────────────────────────────────────────────

if repo:
    url = f"https://api.github.com/repos/{repo}/events?per_page=3"
    req = urllib.request.Request(url)
    if token:
         req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "virtual-office-smoke-test")
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            events = json.loads(resp.read().decode())
        passed(f"API Events readable — fetched {len(events)} recent events")
        for ev in events[:3]:
            ev_type = ev.get("type", "UnknownEvent")
            actor = ev.get("actor", {}).get("login", "?")
            created = ev.get("created_at", "")
            info(f"  [{created}] {actor} triggered {ev_type}")
    except urllib.error.HTTPError as e:
        failed(f"Failed to fetch events: HTTP {e.code} {e.reason}")
    except Exception as e:
        failed(f"Error fetching events: {e}")

# ─────────────────────────────────────────────────────────────────────────────
header("5. Write Access & Multi-Agent Flow Verification")
# ─────────────────────────────────────────────────────────────────────────────

if repo:
    if WRITE_MODE:
        if len(agent_tokens) == 4:
            try:
                # 1. Liam App creates the issue
                info("Creating test issue as Liam (PM) App...")
                env_liam = os.environ.copy()
                env_liam["GH_TOKEN"] = agent_tokens["Liam"]
                
                test_title = "GitHub Connection Test — Virtual Office Multi-Agent Flow"
                test_body = "This is a temporary issue created by test_github.py to verify write permissions of our GitHub Apps."
                
                create_res = subprocess.run(
                    ["gh", "issue", "create", "-R", repo, "--title", test_title, "--body", test_body],
                    env=env_liam, capture_output=True, text=True, timeout=30
                )
                if create_res.returncode == 0:
                    issue_url = create_res.stdout.strip()
                    passed(f"Issue created successfully by Liam App: {issue_url}")
                    issue_num = issue_url.split("/")[-1]
                    
                    # 2. Aiden App comments on the issue
                    info("Posting comment as Aiden (Tech Lead) App...")
                    env_aiden = os.environ.copy()
                    env_aiden["GH_TOKEN"] = agent_tokens["Aiden"]
                    comment_aiden = "Checking the codebase connection. Looks fine, but what happens when the DB connection drops?"
                    
                    comment_res = subprocess.run(
                        ["gh", "issue", "comment", issue_url, "--body", comment_aiden],
                        env=env_aiden, capture_output=True, text=True, timeout=15
                    )
                    if comment_res.returncode == 0:
                        passed("Aiden App comment posted successfully")
                    else:
                        failed(f"Aiden App failed to comment: {comment_res.stderr.strip()}")
                        
                    # 3. Sarah App comments on the issue
                    info("Posting comment as Sarah (CEO) App...")
                    env_sarah = os.environ.copy()
                    env_sarah["GH_TOKEN"] = agent_tokens["Sarah"]
                    comment_sarah = "Thanks Aiden. So, how does this move the needle?"
                    
                    comment_res = subprocess.run(
                        ["gh", "issue", "comment", issue_url, "--body", comment_sarah],
                        env=env_sarah, capture_output=True, text=True, timeout=15
                    )
                    if comment_res.returncode == 0:
                        passed("Sarah App comment posted successfully")
                    else:
                        failed(f"Sarah App failed to comment: {comment_res.stderr.strip()}")
                        
                    # 4. Chloe App comments on the issue
                    info("Posting comment as Chloe (Sales/Mkt) App...")
                    env_chloe = os.environ.copy()
                    env_chloe["GH_TOKEN"] = agent_tokens["Chloe"]
                    comment_chloe = "Love the vibe, but clients won't buy it without Y."
                    
                    comment_res = subprocess.run(
                        ["gh", "issue", "comment", issue_url, "--body", comment_chloe],
                        env=env_chloe, capture_output=True, text=True, timeout=15
                    )
                    if comment_res.returncode == 0:
                        passed("Chloe App comment posted successfully")
                    else:
                        failed(f"Chloe App failed to comment: {comment_res.stderr.strip()}")
                        
                    # 5. Liam App closes the issue
                    info(f"Closing test issue #{issue_num} as Liam App...")
                    close_res = subprocess.run(
                        ["gh", "issue", "close", "-R", repo, issue_num],
                        env=env_liam, capture_output=True, text=True, timeout=15
                    )
                    if close_res.returncode == 0:
                        passed(f"Test issue #{issue_num} closed successfully by Liam App.")
                    else:
                        failed(f"Failed to close test issue: {close_res.stderr.strip()}")
                        
                else:
                    failed(f"Failed to create test issue as Liam: {create_res.stderr.strip()}")
            except Exception as e:
                failed(f"Error during multi-agent flow check: {e}")
        else:
            failed("Cannot run multi-agent write test because not all 4 App tokens were generated successfully.")
    else:
        info("Write mode skipped. Run 'python3 test_github.py --write' to test multi-agent write comments via App tokens.")
else:
    failed("Cannot test write permissions without GITHUB_REPO configured")

print()
