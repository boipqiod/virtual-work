"""
Slack Integration — Read and write messages to Slack.
Uses Bot Token for reading, Webhooks for writing (per-character).
Includes minimal post-processing before dispatch.
"""

import os
import re
import json
import urllib.request
import urllib.parse
from typing import Optional


WIKI_BASE_URL = "https://github.com/boipqiod/shout/wiki"


def _env(key: str) -> str:
    return os.environ.get(key, "")


class SlackClient:
    def __init__(self):
        self.bot_token = _env("SLACK_BOT_TOKEN")
        self.channel_id = _env("SLACK_CHANNEL_ID")
        self.webhooks = {
            "Liam": _env("SLACK_WEBHOOK_LIAM"),
            "Aiden": _env("SLACK_WEBHOOK_AIDEN"),
            "Sarah": _env("SLACK_WEBHOOK_SARAH"),
            "Chloe": _env("SLACK_WEBHOOK_CHLOE"),
        }
        self.character_display = {
            "Liam": {"username": "Liam (PM)", "icon_emoji": ":clipboard:"},
            "Aiden": {"username": "Aiden (Tech Lead)", "icon_emoji": ":computer:"},
            "Sarah": {"username": "Sarah (CEO)", "icon_emoji": ":briefcase:"},
            "Chloe": {"username": "Chloe (Sales)", "icon_emoji": ":chart_with_upwards_trend:"},
        }
        # User ID → display name cache
        self._user_cache: dict = {}
    
    def fetch_new_messages(self, last_ts: str = "") -> list:
        """
        Fetch messages newer than last_ts from the channel.
        Paginates to avoid losing messages during downtime.
        Returns list of message dicts, oldest first.
        """
        if not self.bot_token or not self.channel_id:
            return []
        
        all_messages = []
        cursor = None
        max_pages = 5  # Safety cap: max 50 messages per cycle
        
        for _ in range(max_pages):
            url = "https://slack.com/api/conversations.history"
            params = {
                "channel": self.channel_id,
                "limit": "10",
            }
            if last_ts:
                params["oldest"] = last_ts
            if cursor:
                params["cursor"] = cursor
            
            query = urllib.parse.urlencode(params)
            req = urllib.request.Request(
                f"{url}?{query}",
                headers={"Authorization": f"Bearer {self.bot_token}"}
            )
            
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                
                if not data.get("ok"):
                    print(f"[Slack] API error: {data.get('error')}")
                    break
                
                messages = data.get("messages", [])
                # Filter out the exact last_ts message
                messages = [m for m in messages if m.get("ts") != last_ts]
                all_messages.extend(messages)
                
                # Check if there are more pages
                response_metadata = data.get("response_metadata", {})
                cursor = response_metadata.get("next_cursor", "")
                if not cursor:
                    break
            
            except Exception as e:
                print(f"[Slack] Error fetching messages: {e}")
                break
        
        # Return oldest first
        all_messages.sort(key=lambda m: m.get("ts", ""))
        return all_messages
    
    def resolve_user_id(self, user_id: str) -> str:
        """Resolve a Slack user ID (U0ABC123) to a display name. Cached."""
        if not user_id or not user_id.startswith("U"):
            return user_id
        
        # Hardcoded mapping for agent User IDs (due to missing users:read scope)
        static_map = {
            "U0B6UE1PKE1": "Sarah",
            "U0B7S4N8MPA": "Liam",
            "U0B6GCDPWVD": "Aiden",
            "U0B6UEJ1D6H": "Chloe",
        }
        if user_id in static_map:
            return static_map[user_id]
            
        if user_id in self._user_cache:
            return self._user_cache[user_id]
        
        if not self.bot_token:
            return user_id
        
        url = f"https://slack.com/api/users.info?user={user_id}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self.bot_token}"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            if data.get("ok"):
                user = data.get("user", {})
                name = (user.get("profile", {}).get("display_name")
                        or user.get("real_name")
                        or user.get("name")
                        or user_id)
                self._user_cache[user_id] = name
                return name
        except Exception:
            pass
        
        self._user_cache[user_id] = user_id  # Cache failures too
        return user_id
    
    def enrich_message(self, msg: dict) -> dict:
        """Add resolved username and decode Slack formatting in message text."""
        # Resolve user ID to display name
        username = msg.get("username")
        if not username:
            user_id = msg.get("user", "")
            username = self.resolve_user_id(user_id) if user_id else "unknown"
        msg["username"] = username
        
        # Decode Slack-encoded text
        text = msg.get("text", "")
        text = self._decode_slack_text(text)
        msg["text"] = text
        
        return msg
    
    def _decode_slack_text(self, text: str) -> str:
        """Decode Slack's special encoding in message text.
        <@U123> → @display_name
        <#C123|channel> → #channel
        <http://url|label> → label
        &amp; &lt; &gt; → & < >
        """
        # User mentions: <@U0ABC123>
        def replace_user_mention(m):
            uid = m.group(1)
            name = self.resolve_user_id(uid)
            return f"@{name}"
        text = re.sub(r'<@(U[A-Z0-9]+)>', replace_user_mention, text)
        
        # Channel mentions: <#C123|channel-name> or <#C123>
        text = re.sub(r'<#([A-Z0-9]+)(?:\|([^>]+))?>', lambda m: f'#{m.group(2) or m.group(1)}', text)
        
        # URLs with labels: <http://url|label>
        text = re.sub(r'<(https?://[^|>]+)\|([^>]+)>', r'\2', text)
        
        # URLs without labels: <http://url>
        text = re.sub(r'<(https?://[^>]+)>', r'\1', text)
        
        # HTML entities
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        
        return text
    
    def send_message(self, agent_name: str, text: str) -> bool:
        """Send a message to Slack as a specific character via webhook.
        Returns True on success, False on failure.
        """
        # Post-process before sending
        text = self._clean_message(text)
        if not text:
            print(f"[Slack] Message from {agent_name} discarded (empty after cleaning)")
            return True  # Not a send failure, intentional discard
        
        webhook_url = self.webhooks.get(agent_name, "")
        display = self.character_display.get(agent_name, {
            "username": agent_name,
            "icon_emoji": ":robot_face:"
        })
        
        if not webhook_url:
            # Dry run
            print(f"[Slack DRY RUN] [{display['username']}]: {text}")
            return True
        
        payload = {
            "text": text,
            "username": display["username"],
            "icon_emoji": display["icon_emoji"],
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.getcode()
                if status == 200:
                    print(f"[Slack] Sent message from {agent_name}")
                    return True
                else:
                    print(f"[Slack] Unexpected status {status} from {agent_name}")
                    return False
        except Exception as e:
            print(f"[Slack] Error sending message from {agent_name}: {e}")
            return False
    
    def _clean_message(self, text: str) -> Optional[str]:
        """
        Minimal post-processing. Fix known AI output issues.
        Keep it simple — the prompt should do most of the work.
        """
        if not text:
            return None
        
        # Fix wiki links: file:/// paths or relative paths → GitHub wiki URL
        text = re.sub(
            r'\[([^\]]+)\]\(file:///[^)]*?/([^/)]+?)(?:\.md)?\)',
            lambda m: f'[{m.group(1)}]({WIKI_BASE_URL}/{m.group(2)})',
            text
        )
        text = re.sub(
            r'\[([^\]]+)\]\((?:shout_wiki|wiki)/([^)]+?)(?:\.md)?\)',
            lambda m: f'[{m.group(1)}]({WIKI_BASE_URL}/{m.group(2)})',
            text
        )
        
        # Detect prompt leakage — discard if found
        leakage_signals = ["<decision>", "<delay>", "<response>", "<actions>",
                           "## Task", "## Context", "## Instructions", "Output format:"]
        if any(signal in text for signal in leakage_signals):
            print("[Slack] Prompt leakage detected. Discarding message.")
            return None
        
        return text.strip()
