"""
Scheduler — Manages delayed message dispatch.
Messages are queued with a future send time and dispatched when ready.
Persists to SQLite so scheduled messages survive restarts.
"""

import json
import time
from typing import Optional
from integrations.slack import SlackClient
from integrations.github import GitHubClient
from memory.store import get_connection


class ScheduledMessage:
    def __init__(self, agent_name: str, text: str, send_at: float,
                 trigger_msg_ts: str = "", actions: list = None):
        self.agent_name = agent_name
        self.text = text
        self.send_at = send_at
        self.trigger_msg_ts = trigger_msg_ts
        self.actions = actions or []
        self.retry_count = 0
        self.max_retries = 3
    
    def is_ready(self) -> bool:
        return time.time() >= self.send_at
    
    def seconds_until(self) -> float:
        return max(0, self.send_at - time.time())


class Scheduler:
    def __init__(self, slack: SlackClient, github: GitHubClient):
        self.slack = slack
        self.github = github
        self.pending: list[ScheduledMessage] = []
        self._load_from_db()
    
    def _load_from_db(self):
        """Load persisted scheduled messages on startup (only undispatched)."""
        conn = None
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT id, agent_name, text, send_at, trigger_msg_ts, actions, retry_count "
                "FROM scheduled_messages WHERE dispatched = 0"
            ).fetchall()
            
            for row in rows:
                msg = ScheduledMessage(
                    agent_name=row["agent_name"],
                    text=row["text"],
                    send_at=row["send_at"],
                    trigger_msg_ts=row["trigger_msg_ts"],
                    actions=json.loads(row["actions"]) if row["actions"] else [],
                )
                msg.retry_count = row["retry_count"]
                msg.db_id = row["id"]
                self.pending.append(msg)
            
            if rows:
                print(f"[Scheduler] Restored {len(rows)} pending messages from DB")
        except Exception as e:
            print(f"[Scheduler] Error loading from DB: {e}")
        finally:
            if conn:
                conn.close()
    
    def _persist(self, msg: ScheduledMessage):
        """Save a scheduled message to DB."""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.execute(
                "INSERT INTO scheduled_messages (agent_name, text, send_at, trigger_msg_ts, actions, retry_count) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (msg.agent_name, msg.text, msg.send_at, msg.trigger_msg_ts,
                 json.dumps(msg.actions), msg.retry_count)
            )
            msg.db_id = cursor.lastrowid
            conn.commit()
        except Exception as e:
            print(f"[Scheduler] Error persisting: {e}")
        finally:
            if conn:
                conn.close()
    
    def _remove_from_db(self, msg: ScheduledMessage):
        """Remove a scheduled message from DB."""
        db_id = getattr(msg, 'db_id', None)
        if db_id is None:
            return
        conn = None
        try:
            conn = get_connection()
            conn.execute("DELETE FROM scheduled_messages WHERE id = ?", (db_id,))
            conn.commit()
        except Exception as e:
            print(f"[Scheduler] Error removing from DB: {e}")
        finally:
            if conn:
                conn.close()
    
    def _update_in_db(self, msg: ScheduledMessage):
        """Update retry count and send_at in DB."""
        db_id = getattr(msg, 'db_id', None)
        if db_id is None:
            return
        conn = None
        try:
            conn = get_connection()
            conn.execute(
                "UPDATE scheduled_messages SET send_at = ?, retry_count = ? WHERE id = ?",
                (msg.send_at, msg.retry_count, db_id)
            )
            conn.commit()
        except Exception as e:
            print(f"[Scheduler] Error updating DB: {e}")
        finally:
            if conn:
                conn.close()
    
    def _mark_dispatched(self, msg: ScheduledMessage):
        """Mark message as dispatched in DB (idempotent send protection)."""
        db_id = getattr(msg, 'db_id', None)
        if db_id is None:
            return
        conn = None
        try:
            conn = get_connection()
            conn.execute(
                "UPDATE scheduled_messages SET dispatched = 1 WHERE id = ?", (db_id,)
            )
            conn.commit()
        except Exception as e:
            print(f"[Scheduler] Error marking dispatched: {e}")
        finally:
            if conn:
                conn.close()
    
    def _unmark_dispatched(self, msg: ScheduledMessage):
        """Unmark dispatched (for retry after send failure)."""
        db_id = getattr(msg, 'db_id', None)
        if db_id is None:
            return
        conn = None
        try:
            conn = get_connection()
            conn.execute(
                "UPDATE scheduled_messages SET dispatched = 0 WHERE id = ?", (db_id,)
            )
            conn.commit()
        except Exception as e:
            print(f"[Scheduler] Error unmarking dispatched: {e}")
        finally:
            if conn:
                conn.close()
    
    def schedule(self, agent_name: str, text: str, delay_seconds: int,
                 trigger_msg_ts: str = "", actions: list = None):
        """Add a message to the dispatch queue (persisted to DB)."""
        send_at = time.time() + delay_seconds
        msg = ScheduledMessage(
            agent_name=agent_name,
            text=text,
            send_at=send_at,
            trigger_msg_ts=trigger_msg_ts,
            actions=actions or []
        )
        self.pending.append(msg)
        self._persist(msg)
        
        minutes = delay_seconds / 60
        print(f"[Scheduler] {agent_name} scheduled in {minutes:.1f}min")
    
    def dispatch_ready(self):
        """Send all messages whose delay has expired."""
        ready = [m for m in self.pending if m.is_ready()]
        
        for msg in ready:
            # Mark as dispatched BEFORE sending (idempotent: won't re-send on restart)
            self._mark_dispatched(msg)
            
            # Send Slack message
            send_ok = self.slack.send_message(msg.agent_name, msg.text)
            
            if not send_ok:
                # Slack send failed — unmark and retry
                msg.retry_count += 1
                if msg.retry_count >= msg.max_retries:
                    print(f"[Scheduler] Dropping message from {msg.agent_name} after {msg.max_retries} send retries")
                    self.pending.remove(msg)
                    self._remove_from_db(msg)
                else:
                    msg.send_at = time.time() + 60
                    self._unmark_dispatched(msg)
                    self._update_in_db(msg)
                    print(f"[Scheduler] Slack send failed, will retry ({msg.retry_count}/{msg.max_retries})")
                continue
            
            # Execute any actions (wiki, issues, etc.)
            for action in msg.actions:
                try:
                    self._execute_action(action, msg.agent_name)
                except Exception as e:
                    print(f"[Scheduler] Action failed for {msg.agent_name}: {e}")
                    # Actions failed but Slack message was sent — don't retry
            
            self.pending.remove(msg)
            self._remove_from_db(msg)
    
    def _execute_action(self, action: dict, agent_name: str):
        """Execute a GitHub action (wiki write, issue create, etc.)."""
        action_type = action.get("type", "")
        
        if action_type == "wiki_write":
            self.github.push_wiki(
                title=action["title"],
                content=action["content"],
                agent_name=agent_name
            )
        
        elif action_type == "issue_create":
            url = self.github.create_issue(
                title=action["title"],
                body=action["body"],
                agent_name=agent_name
            )
            if url:
                # Optionally announce the URL in Slack
                self.slack.send_message(
                    agent_name,
                    f"created: {url}"
                )
        
        elif action_type == "issue_comment":
            self.github.comment_issue(
                issue_number=action["issue_number"],
                body=action["body"],
                agent_name=agent_name
            )
    
    def get_pending_for_trigger(self, trigger_ts: str) -> list:
        """Get all pending messages triggered by a specific message."""
        return [m for m in self.pending if m.trigger_msg_ts == trigger_ts]
    
    def pending_count(self) -> int:
        return len(self.pending)
