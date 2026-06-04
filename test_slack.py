#!/usr/bin/env python3
"""
Virtual Office — Slack Connectivity Smoke Test
Verifies tokens and webhooks work before running the full system.

Usage: python3 test_slack.py [--send]
  Without --send: only tests reading (safe)
  With --send: sends a test message to each webhook (visible in Slack)
"""

import os
import sys
import json
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

SEND_MODE = "--send" in sys.argv

# ─────────────────────────────────────────────────────────────────────────────
header("1. Environment Variables")
# ─────────────────────────────────────────────────────────────────────────────

required = {
    "SLACK_BOT_TOKEN": os.environ.get("SLACK_BOT_TOKEN", ""),
    "SLACK_CHANNEL_ID": os.environ.get("SLACK_CHANNEL_ID", ""),
}
webhooks = {
    "Liam": os.environ.get("SLACK_WEBHOOK_LIAM", ""),
    "Aiden": os.environ.get("SLACK_WEBHOOK_AIDEN", ""),
    "Sarah": os.environ.get("SLACK_WEBHOOK_SARAH", ""),
    "Chloe": os.environ.get("SLACK_WEBHOOK_CHLOE", ""),
}

for key, val in required.items():
    if val:
        passed(f"{key} = {val[:20]}...")
    else:
        failed(f"{key} is empty")

for name, url in webhooks.items():
    if url:
        passed(f"SLACK_WEBHOOK_{name.upper()} = ...{url[-20:]}")
    else:
        failed(f"SLACK_WEBHOOK_{name.upper()} is empty")

# ─────────────────────────────────────────────────────────────────────────────
header("2. Bot Token — auth.test")
# ─────────────────────────────────────────────────────────────────────────────

token = required["SLACK_BOT_TOKEN"]
if token:
    req = urllib.request.Request(
        "https://slack.com/api/auth.test",
        headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data.get("ok"):
            passed(f"Bot authenticated: {data.get('user', '?')} in team {data.get('team', '?')}")
        else:
            failed(f"auth.test failed: {data.get('error')}")
    except Exception as e:
        failed(f"auth.test error: {e}")
else:
    failed("No bot token to test")

# ─────────────────────────────────────────────────────────────────────────────
header("3. Bot Token — conversations.history (read)")
# ─────────────────────────────────────────────────────────────────────────────

channel = required["SLACK_CHANNEL_ID"]
if token and channel:
    url = f"https://slack.com/api/conversations.history?channel={channel}&limit=3"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        if data.get("ok"):
            msgs = data.get("messages", [])
            passed(f"Channel readable — {len(msgs)} recent messages")
            for m in msgs[:3]:
                who = m.get("username", m.get("user", "?"))
                text = m.get("text", "")[:60]
                info(f"  [{who}]: {text}")
        else:
            err = data.get("error", "unknown")
            if err == "channel_not_found":
                failed(f"Channel {channel} not found — bot might not be in the channel")
            elif err == "not_in_channel":
                failed(f"Bot is not a member of channel {channel}")
            else:
                failed(f"conversations.history failed: {err}")
    except Exception as e:
        failed(f"conversations.history error: {e}")
else:
    failed("Missing token or channel ID")

# ─────────────────────────────────────────────────────────────────────────────
header("4. Bot Token — users.info (for user ID resolution)")
# ─────────────────────────────────────────────────────────────────────────────

if token:
    # Try to resolve the bot's own user ID
    req = urllib.request.Request(
        "https://slack.com/api/auth.test",
        headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        bot_user_id = data.get("user_id", "")
        
        if bot_user_id:
            url = f"https://slack.com/api/users.info?user={bot_user_id}"
            req2 = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                data2 = json.loads(resp2.read().decode())
            if data2.get("ok"):
                user = data2.get("user", {})
                name = user.get("real_name", user.get("name", "?"))
                passed(f"users.info works — resolved bot as: {name}")
            else:
                err = data2.get("error", "unknown")
                if err == "users:read":
                    failed("users.info scope missing — add 'users:read' to bot scopes")
                else:
                    failed(f"users.info failed: {err}")
    except Exception as e:
        failed(f"users.info error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
header("5. Webhooks — connectivity")
# ─────────────────────────────────────────────────────────────────────────────

if SEND_MODE:
    info("--send mode: will post test messages to Slack!")
    for name, url in webhooks.items():
        if not url:
            continue
        payload = json.dumps({
            "text": f"[TEST] {name} webhook connectivity check ✓",
            "username": f"{name} (Test)",
            "icon_emoji": ":white_check_mark:",
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.getcode() == 200:
                    passed(f"{name} webhook sent successfully")
                else:
                    failed(f"{name} webhook returned {resp.getcode()}")
        except urllib.error.HTTPError as e:
            failed(f"{name} webhook HTTP error: {e.code} {e.reason}")
        except Exception as e:
            failed(f"{name} webhook error: {e}")
else:
    info("Skipping webhook send test (use --send to actually post to Slack)")
    info("Checking URL format only...")
    for name, url in webhooks.items():
        if url and url.startswith("https://hooks.slack.com/"):
            passed(f"{name} webhook URL format OK")
        elif url:
            failed(f"{name} webhook URL doesn't start with https://hooks.slack.com/")
        else:
            failed(f"{name} webhook URL is empty")

# ─────────────────────────────────────────────────────────────────────────────
header("요약")
# ─────────────────────────────────────────────────────────────────────────────

print()
if not SEND_MODE:
    info("Run with --send to test webhook delivery (posts to Slack)")
print()
