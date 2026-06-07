"""
MCP Server for Virtual Office — provides tools for agents to query project state.
Runs as a stdio-based MCP server invoked by agy.
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "memory.db"))
PROGRESS_PATH = os.environ.get("PROGRESS_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "progress.json"))
WIKI_DIR = os.environ.get("WIKI_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shout_wiki"))
GITHUB_REPO = os.environ.get("GITHUB_REPO", "boipqiod/shout")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --- Tool implementations ---

def get_progress():
    """Current sprint, tasks, what's next, blocked items."""
    if not os.path.exists(PROGRESS_PATH):
        return {"error": "progress.json not found"}
    with open(PROGRESS_PATH) as f:
        return json.load(f)


def get_my_actions(agent: str, days: int = 7):
    """Recent actions by a specific agent."""
    conn = get_db()
    try:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT date, type, title, summary FROM actions WHERE agent = ? AND date >= ? ORDER BY date DESC",
            (agent, since)
        ).fetchall()
        return {"actions": [dict(r) for r in rows]}
    except Exception as e:
        return {"actions": [], "error": str(e)}
    finally:
        conn.close()


def get_recent_messages(limit: int = 20):
    """Recent Slack messages."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT ts, username, text FROM messages ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return {"messages": [dict(r) for r in reversed(rows)]}
    except Exception as e:
        return {"messages": [], "error": str(e)}
    finally:
        conn.close()


def get_open_issues():
    """GitHub open issues."""
    try:
        result = subprocess.run(
            ["gh", "issue", "list", "-R", GITHUB_REPO, "--json", "number,title,assignees,state,createdAt", "-L", "20"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            issues = json.loads(result.stdout)
            return {"issues": [{"number": i["number"], "title": i["title"],
                               "assignee": i["assignees"][0]["login"] if i.get("assignees") else None,
                               "state": i["state"], "created": i.get("createdAt", "")} for i in issues]}
        return {"issues": [], "error": result.stderr[:200]}
    except Exception as e:
        return {"issues": [], "error": str(e)}


def get_pr_diff(pr_number: int):
    """Get diff for a specific PR."""
    try:
        meta = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "-R", GITHUB_REPO, "--json", "title,author,files"],
            capture_output=True, text=True, timeout=15
        )
        diff = subprocess.run(
            ["gh", "pr", "diff", str(pr_number), "-R", GITHUB_REPO],
            capture_output=True, text=True, timeout=15
        )
        info = json.loads(meta.stdout) if meta.returncode == 0 else {}
        diff_text = diff.stdout[:4000] if diff.returncode == 0 else "(diff unavailable)"
        return {"title": info.get("title", ""), "author": info.get("author", {}).get("login", ""),
                "diff": diff_text, "files_changed": [f["path"] for f in info.get("files", [])]}
    except Exception as e:
        return {"error": str(e)}


def get_wiki_list():
    """List existing wiki pages."""
    if not os.path.exists(WIKI_DIR):
        return {"pages": []}
    pages = [f.replace(".md", "").replace("-", " ") for f in os.listdir(WIKI_DIR)
             if f.endswith(".md") and not f.startswith(".")]
    return {"pages": sorted(pages)}


def get_blocked_tasks():
    """Tasks that are blocked."""
    progress = get_progress()
    if "error" in progress:
        return progress
    return {"blocked": progress.get("blocked", [])}


def get_team_activity(days: int = 3):
    """Recent activity per team member."""
    conn = get_db()
    try:
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT agent, date, type, title, summary FROM actions WHERE date >= ? ORDER BY date DESC",
            (since,)
        ).fetchall()
        activity = {}
        for r in rows:
            agent = r["agent"]
            if agent not in activity:
                activity[agent] = []
            activity[agent].append({"date": r["date"], "type": r["type"], "title": r["title"]})

        # Simon's message activity
        msg_rows = conn.execute(
            "SELECT username, text, created_at FROM messages WHERE is_bot = 0 AND created_at >= ? ORDER BY created_at DESC LIMIT 5",
            (since,)
        ).fetchall()
        if msg_rows:
            activity["Simon"] = {"last_seen": msg_rows[0]["created_at"],
                                 "recent_messages": len(msg_rows)}
        return {"activity": activity}
    except Exception as e:
        return {"activity": {}, "error": str(e)}
    finally:
        conn.close()


def get_simon_status():
    """Simon's last activity and current task."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT text, created_at FROM messages WHERE is_bot = 0 ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        last_msg = dict(row) if row else None
    except Exception:
        last_msg = None
    finally:
        conn.close()

    progress = get_progress()
    current_task = None
    if "tasks" not in progress or "error" in progress:
        pass
    else:
        for t in progress.get("tasks", []):
            if t.get("assignee") == "Simon" and t.get("status") in ("in-progress", "todo"):
                current_task = t
                break

    days_since = None
    if last_msg and last_msg.get("created_at"):
        try:
            last_dt = datetime.fromisoformat(last_msg["created_at"].replace("Z", ""))
            days_since = (datetime.utcnow() - last_dt).days
        except (ValueError, TypeError):
            pass

    return {
        "last_message_time": last_msg.get("created_at") if last_msg else None,
        "last_message_text": last_msg.get("text", "")[:100] if last_msg else None,
        "days_since_update": days_since,
        "current_task": current_task
    }


def update_progress(action: str, **kwargs):
    """Update progress state."""
    if not os.path.exists(PROGRESS_PATH):
        return {"error": "progress.json not found"}

    with open(PROGRESS_PATH) as f:
        data = json.load(f)

    if action == "add_log":
        agent = kwargs.get("agent", "unknown")
        entry = kwargs.get("entry", "")
        # Also write to actions table
        conn = get_db()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO actions (agent, date, type, title, summary) VALUES (?, ?, ?, ?, ?)",
                (agent, datetime.utcnow().strftime("%Y-%m-%d"), kwargs.get("type", "other"),
                 kwargs.get("title", entry[:50]), entry)
            )
            conn.commit()
        finally:
            conn.close()
        return {"ok": True}

    elif action == "update_task":
        task_id = kwargs.get("task_id")
        status = kwargs.get("status")
        for t in data.get("tasks", []):
            if t["id"] == task_id:
                t["status"] = status
                break
        with open(PROGRESS_PATH, "w") as f:
            json.dump(data, f, indent=2)
        return {"ok": True}

    return {"error": f"unknown action: {action}"}


# --- MCP Protocol (stdio JSON-RPC) ---

TOOLS = {
    "get_progress": {"fn": get_progress, "desc": "Get current sprint, tasks, what's next, and blocked items", "params": {}},
    "get_my_actions": {"fn": get_my_actions, "desc": "Get recent actions by a specific agent (to avoid repeating work)", "params": {"agent": "string", "days": "integer (default 7)"}},
    "get_recent_messages": {"fn": get_recent_messages, "desc": "Get recent Slack messages", "params": {"limit": "integer (default 20)"}},
    "get_open_issues": {"fn": get_open_issues, "desc": "Get GitHub open issues list", "params": {}},
    "get_pr_diff": {"fn": get_pr_diff, "desc": "Get diff for a specific PR (for code review)", "params": {"pr_number": "integer"}},
    "get_wiki_list": {"fn": get_wiki_list, "desc": "List existing wiki pages (to avoid duplicates)", "params": {}},
    "get_blocked_tasks": {"fn": get_blocked_tasks, "desc": "Get tasks that are currently blocked", "params": {}},
    "get_team_activity": {"fn": get_team_activity, "desc": "Get recent activity per team member", "params": {"days": "integer (default 3)"}},
    "get_simon_status": {"fn": get_simon_status, "desc": "Get Simon's last message time, current task, and days since update", "params": {}},
    "update_progress": {"fn": update_progress, "desc": "Update progress (add action log or change task status)", "params": {"action": "string", "agent": "string", "entry": "string"}},
}


def handle_request(request):
    """Handle a JSON-RPC request."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "virtual-office", "version": "1.0.0"}
        }}

    elif method == "notifications/initialized":
        return None  # no response needed

    elif method == "tools/list":
        tools = []
        for name, info in TOOLS.items():
            schema = {"type": "object", "properties": {}, "required": []}
            for pname, ptype in info["params"].items():
                if "integer" in ptype:
                    schema["properties"][pname] = {"type": "integer"}
                else:
                    schema["properties"][pname] = {"type": "string"}
                if "default" not in ptype:
                    schema["required"].append(pname)
            tools.append({"name": name, "description": info["desc"], "inputSchema": schema})
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        if tool_name in TOOLS:
            try:
                result = TOOLS[tool_name]["fn"](**arguments)
                return {"jsonrpc": "2.0", "id": req_id, "result": {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]
                }}
            except Exception as e:
                return {"jsonrpc": "2.0", "id": req_id, "result": {
                    "content": [{"type": "text", "text": json.dumps({"error": str(e)})}], "isError": True
                }}
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main():
    """Run MCP server over stdio."""
    # Ensure actions table exists
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent TEXT,
        date TEXT,
        type TEXT,
        title TEXT,
        summary TEXT,
        UNIQUE(agent, date, title)
    )""")
    conn.commit()
    conn.close()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            pass


if __name__ == "__main__":
    main()
