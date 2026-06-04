"""
Memory Store — SQLite-based persistent memory for the Virtual Office.
Stores conversation history, agent state, and project events.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "memory.db")

# Bot display names used by webhooks (must match orchestrator.bot_usernames)
BOT_USERNAMES = {"Liam (PM)", "Aiden (Tech Lead)", "Sarah (CEO)", "Chloe (Sales)"}


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT UNIQUE,
            source TEXT DEFAULT 'slack',
            username TEXT,
            text TEXT,
            is_bot INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE INDEX IF NOT EXISTS idx_messages_bot_time
            ON messages(is_bot, created_at);
        
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            event_type TEXT,
            payload TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS agent_state (
            agent_name TEXT PRIMARY KEY,
            state TEXT DEFAULT 'offline',
            last_slack_check TEXT,
            last_work_time TEXT,
            last_ambient_chat TEXT,
            next_work_time TEXT,
            energy REAL DEFAULT 1.0
        );
        
        CREATE TABLE IF NOT EXISTS daily_summaries (
            date TEXT PRIMARY KEY,
            summary TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE IF NOT EXISTS kv (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        
        CREATE TABLE IF NOT EXISTS scheduled_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT,
            text TEXT,
            send_at REAL,
            trigger_msg_ts TEXT DEFAULT '',
            actions TEXT DEFAULT '[]',
            retry_count INTEGER DEFAULT 0,
            dispatched INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


class MemoryStore:
    def __init__(self):
        init_db()
    
    def save_message(self, msg: dict):
        """Save a Slack message to history."""
        conn = get_connection()
        ts = msg.get("ts", "")
        username = msg.get("username", msg.get("user", "unknown"))
        text = msg.get("text", "")
        is_bot = 1 if (
            msg.get("subtype") == "bot_message"
            or msg.get("bot_id")
            or username in BOT_USERNAMES
        ) else 0
        
        try:
            conn.execute(
                "INSERT OR IGNORE INTO messages (ts, source, username, text, is_bot) VALUES (?, ?, ?, ?, ?)",
                (ts, "slack", username, text, is_bot)
            )
            conn.commit()
        except Exception as e:
            print(f"[Memory] Error saving message: {e}")
        finally:
            conn.close()
    
    def save_event(self, event: dict):
        """Save a GitHub event."""
        conn = get_connection()
        event_id = str(event.get("id", ""))
        event_type = event.get("type", "unknown")
        
        try:
            conn.execute(
                "INSERT OR IGNORE INTO events (event_id, event_type, payload) VALUES (?, ?, ?)",
                (event_id, event_type, json.dumps(event))
            )
            conn.commit()
        except Exception as e:
            print(f"[Memory] Error saving event: {e}")
        finally:
            conn.close()
    
    def get_recent_messages(self, limit: int = 50) -> list:
        """Get the most recent messages."""
        conn = None
        try:
            conn = get_connection()
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            # Return in chronological order
            return [dict(r) for r in reversed(rows)]
        finally:
            if conn:
                conn.close()
    
    def count_recent_bot_messages(self, minutes: int = 10) -> int:
        """Count bot messages in the last N minutes."""
        conn = None
        try:
            conn = get_connection()
            cutoff = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE is_bot = 1 AND created_at > ?",
                (cutoff,)
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            if conn:
                conn.close()
    
    def get_context(self) -> str:
        """Build context string for AI prompts."""
        # Load project context
        ctx_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "project_context.md"
        )
        project_ctx = ""
        if os.path.exists(ctx_path):
            with open(ctx_path, "r") as f:
                project_ctx = f.read()
        
        # Recent conversation
        messages = self.get_recent_messages(50)
        conversation = ""
        for msg in messages:
            who = msg["username"]
            text = msg["text"]
            conversation += f"[{who}]: {text}\n"
        
        # Yesterday's summary
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        conn = None
        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT summary FROM daily_summaries WHERE date = ?", (yesterday,)
            ).fetchone()
            yesterday_summary = row["summary"] if row else "No summary available."
        finally:
            if conn:
                conn.close()
        
        return f"""## Project Info
{project_ctx}

## Yesterday's Summary
{yesterday_summary}

## Recent Conversation (last 50 messages)
{conversation}
"""
    
    def get_last_ambient_chat_time(self) -> Optional[datetime]:
        """Get the last time any agent initiated casual chat."""
        conn = None
        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT value FROM kv WHERE key = 'last_ambient_chat'"
            ).fetchone()
        finally:
            if conn:
                conn.close()
        if row:
            try:
                return datetime.fromisoformat(row["value"])
            except (ValueError, TypeError):
                return None
        return None
    
    def set_last_ambient_chat_time(self):
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)",
            ("last_ambient_chat", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    
    def get_last_ts(self) -> str:
        """Get the last processed Slack message timestamp."""
        conn = None
        try:
            conn = get_connection()
            row = conn.execute("SELECT value FROM kv WHERE key = 'last_slack_ts'").fetchone()
            return row["value"] if row else ""
        finally:
            if conn:
                conn.close()
    
    def set_last_ts(self, ts: str):
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)",
            ("last_slack_ts", ts)
        )
        conn.commit()
        conn.close()
    
    def get_last_github_event_id(self) -> str:
        conn = None
        try:
            conn = get_connection()
            row = conn.execute("SELECT value FROM kv WHERE key = 'last_github_event_id'").fetchone()
            return row["value"] if row else ""
        finally:
            if conn:
                conn.close()
    
    def set_last_github_event_id(self, event_id: str):
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO kv (key, value) VALUES (?, ?)",
            ("last_github_event_id", event_id)
        )
        conn.commit()
        conn.close()
    
    def save_daily_summary(self, date: str, summary: str):
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO daily_summaries (date, summary) VALUES (?, ?)",
            (date, summary)
        )
        conn.commit()
        conn.close()
