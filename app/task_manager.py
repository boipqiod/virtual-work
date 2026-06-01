"""
Task Manager Module
====================
CRUD utility for agent_io/agent_tasks.json.
All runner scripts (active_runner.py, discussion_runner.py, ai_runner.py)
import this module to read/write the shared AI team task board.
"""

import os
import json
import copy
from datetime import datetime
from typing import Optional, List, Dict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(SCRIPT_DIR)
TASKS_FILE = os.path.join(WORKSPACE_DIR, "agent_io", "agent_tasks.json")

# Default dialogue settings
DEFAULT_MAX_TURNS = 3


# ------------------------------------------------------------------------------
# Core I/O
# ------------------------------------------------------------------------------
def load_tasks() -> dict:
    """Load the agent_tasks.json file. Returns the full data dict."""
    if not os.path.exists(TASKS_FILE):
        default = {"active_sprint": "Sprint-1", "next_task_id": 1, "tasks": []}
        save_tasks(default)
        return default
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_tasks(data: dict):
    """Persist the full data dict back to agent_tasks.json."""
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------------------
# Task CRUD
# ------------------------------------------------------------------------------
def create_task(
    creator: str,
    title: str,
    description: str = "",
    task_type: str = "document",
    assignee: str = None,
    deliverable: str = "issue_comment",
    trigger_type: str = "next_cycle",
    scheduled_time: str = None,
    github_issue_url: str = None,
    github_issue_number: int = None,
) -> dict:
    """
    Create a new task entry and append it to agent_tasks.json.
    Returns the newly created task dict.
    """
    data = load_tasks()
    task_id = f"TASK-{data['next_task_id']:03d}"
    now = datetime.now().isoformat(timespec="seconds")

    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "creator": creator,
        "assignee": assignee or creator,
        "type": task_type,
        "status": "backlog",
        "github_issue_url": github_issue_url,
        "github_issue_number": github_issue_number,
        "deliverable": deliverable,
        "deliverable_ref": None,
        "created_at": now,
        "completed_at": None,
        "schedule": {
            "trigger_type": trigger_type,
            "scheduled_time": scheduled_time,
            "last_executed_at": None,
        },
        "dialogue": {
            "state": "idle",
            "turn_count": 0,
            "max_turns": DEFAULT_MAX_TURNS,
            "last_speaker": None,
            "thread": [],
        },
    }

    data["tasks"].append(task)
    data["next_task_id"] += 1
    save_tasks(data)
    print(f"[TaskManager] Created {task_id}: {title} (assignee: {task['assignee']})")
    return task


def get_task(task_id: str) -> Optional[dict]:
    """Return a single task by ID, or None if not found."""
    data = load_tasks()
    for t in data["tasks"]:
        if t["id"] == task_id:
            return t
    return None


def update_task_status(task_id: str, new_status: str):
    """Update a task's status field (backlog / in_progress / done)."""
    data = load_tasks()
    for t in data["tasks"]:
        if t["id"] == task_id:
            old = t["status"]
            t["status"] = new_status
            if new_status == "done" and not t.get("completed_at"):
                t["completed_at"] = datetime.now().isoformat(timespec="seconds")
            save_tasks(data)
            print(f"[TaskManager] {task_id} status: {old} → {new_status}")
            return
    print(f"[TaskManager] Task {task_id} not found.")


def update_task_field(task_id: str, field: str, value):
    """Update an arbitrary top-level field on a task."""
    data = load_tasks()
    for t in data["tasks"]:
        if t["id"] == task_id:
            t[field] = value
            save_tasks(data)
            return
    print(f"[TaskManager] Task {task_id} not found.")


def get_tasks_by_status(status: str) -> list:
    """Return all tasks matching the given status."""
    data = load_tasks()
    return [t for t in data["tasks"] if t["status"] == status]


def get_tasks_by_assignee(name: str) -> list:
    """Return all tasks assigned to a specific team member."""
    data = load_tasks()
    return [t for t in data["tasks"] if t.get("assignee", "").lower() == name.lower()]


def get_active_tasks() -> list:
    """Return tasks that are backlog or in_progress (not done)."""
    data = load_tasks()
    return [t for t in data["tasks"] if t["status"] in ("backlog", "in_progress")]


# ------------------------------------------------------------------------------
# Dialogue Management
# ------------------------------------------------------------------------------
def add_dialogue_entry(task_id: str, speaker: str, text: str, action: str = "comment"):
    """
    Append a dialogue entry to a task's thread.
    Increments turn_count and updates last_speaker.
    If turn_count reaches max_turns, auto-resolves the dialogue.
    """
    data = load_tasks()
    for t in data["tasks"]:
        if t["id"] == task_id:
            dlg = t["dialogue"]
            now = datetime.now().isoformat(timespec="seconds")
            dlg["thread"].append({
                "speaker": speaker,
                "action": action,
                "text": text,
                "timestamp": now,
            })
            dlg["turn_count"] += 1
            dlg["last_speaker"] = speaker

            if dlg["turn_count"] >= dlg["max_turns"]:
                dlg["state"] = "resolved"
                print(f"[TaskManager] {task_id} dialogue auto-resolved (max turns reached).")
            else:
                dlg["state"] = "discussing"

            save_tasks(data)
            print(f"[TaskManager] {task_id} dialogue turn {dlg['turn_count']}/{dlg['max_turns']} by {speaker}")
            return
    print(f"[TaskManager] Task {task_id} not found for dialogue update.")


def start_discussion(task_id: str, speaker: str, text: str):
    """
    Start a new discussion on a task.
    Sets dialogue.state to 'discussing' and adds the first entry.
    """
    data = load_tasks()
    for t in data["tasks"]:
        if t["id"] == task_id:
            dlg = t["dialogue"]
            if dlg["state"] == "resolved":
                print(f"[TaskManager] {task_id} dialogue already resolved. Skipping.")
                return
            dlg["state"] = "discussing"
            save_tasks(data)
            break
    add_dialogue_entry(task_id, speaker, text, action="comment")


def check_dialogue_limit(task_id: str) -> bool:
    """Return True if the task has reached its max dialogue turns."""
    task = get_task(task_id)
    if not task:
        return True
    dlg = task["dialogue"]
    return dlg["turn_count"] >= dlg["max_turns"]


def resolve_dialogue(task_id: str):
    """Manually set a task's dialogue state to resolved."""
    data = load_tasks()
    for t in data["tasks"]:
        if t["id"] == task_id:
            t["dialogue"]["state"] = "resolved"
            save_tasks(data)
            print(f"[TaskManager] {task_id} dialogue manually resolved.")
            return


def get_discussing_tasks() -> list:
    """Return all tasks where dialogue.state == 'discussing' and turn_count < max_turns."""
    data = load_tasks()
    result = []
    for t in data["tasks"]:
        dlg = t["dialogue"]
        if dlg["state"] == "discussing" and dlg["turn_count"] < dlg["max_turns"]:
            result.append(t)
    return result


# ------------------------------------------------------------------------------
# Archival
# ------------------------------------------------------------------------------
def archive_completed_tasks() -> list:
    """
    Remove all 'done' tasks from the active board and return them.
    Used by daily_compressor.sh at midnight.
    """
    data = load_tasks()
    completed = [t for t in data["tasks"] if t["status"] == "done"]
    data["tasks"] = [t for t in data["tasks"] if t["status"] != "done"]
    save_tasks(data)
    if completed:
        print(f"[TaskManager] Archived {len(completed)} completed tasks.")
    return completed


def get_tasks_summary() -> str:
    """
    Generate a human-readable text summary of the current task board.
    Used as context injection for AI prompts.
    """
    data = load_tasks()
    if not data["tasks"]:
        return "No tasks on the board."

    lines = [f"Sprint: {data['active_sprint']}", ""]
    for t in data["tasks"]:
        status_emoji = {"backlog": "📋", "in_progress": "🔨", "done": "✅"}.get(t["status"], "❓")
        dlg_info = ""
        if t["dialogue"]["state"] == "discussing":
            dlg_info = f" [💬 discussing {t['dialogue']['turn_count']}/{t['dialogue']['max_turns']}]"
        elif t["dialogue"]["state"] == "resolved":
            dlg_info = " [💬 resolved]"

        assignee = t.get("assignee", "Unassigned")
        lines.append(f"{status_emoji} {t['id']}: {t['title']} ({assignee}){dlg_info}")
        if t.get("github_issue_url"):
            lines.append(f"   └─ {t['github_issue_url']}")

    return "\n".join(lines)
