"""
Discussion Runner
==================
Drives AI-to-AI dialogue for tasks whose dialogue.state == "discussing".
Each cycle:
  1. Loads discussing tasks from task_manager
  2. Determines the next speaker (different from last_speaker)
  3. Builds a persona-aware prompt with full dialogue thread
  4. Calls agy to generate the next turn
  5. Records the turn and writes outbox responses for dispatch
"""

import os
import sys
import json
import subprocess
import re

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(SCRIPT_DIR)
AGENT_IO_DIR = os.path.join(WORKSPACE_DIR, "agent_io")
OUTBOX_FILE = os.path.join(AGENT_IO_DIR, "outbox", "final_response.json")
GLOBAL_CONTEXT_FILE = os.path.join(AGENT_IO_DIR, "memory", "global_context.md")

# Max tasks to process per cycle (avoid API overload)
MAX_TASKS_PER_CYCLE = 3

# Speaker rotation map: given the last speaker, who can speak next
SPEAKER_ROTATION = {
    "liam":  ["aiden", "sarah"],
    "aiden": ["liam"],
    "chloe": ["liam", "aiden"],
    "sarah": ["liam"],
}

# Fallback ordering when rotation map doesn't cover a speaker
ALL_SPEAKERS = ["liam", "aiden", "sarah", "chloe"]

# ---------------------------------------------------------------------------
# Import task_manager from the same directory
# ---------------------------------------------------------------------------
sys.path.insert(0, SCRIPT_DIR)
import task_manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_file(path: str) -> str:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def run_agy(prompt: str) -> str:
    """Executes 'agy -p' inside the local workspace directory."""
    print("[Discussion Runner] Executing agy agent...")
    try:
        result = subprocess.run(
            [
                "agy",
                "--add-dir", WORKSPACE_DIR,
                "--dangerously-skip-permissions",
                "-p", prompt,
            ],
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[Discussion Runner] Error running agy: {e.stderr}", file=sys.stderr)
        return ""


def determine_next_speaker(task: dict) -> str:
    """
    Pick the next speaker for this task's dialogue.
    Rules:
      - Must NOT be the same as last_speaker
      - Prefer someone from the SPEAKER_ROTATION map
      - Fall back to task creator or assignee if not in the map
    """
    dlg = task["dialogue"]
    last = (dlg.get("last_speaker") or "").lower()
    creator = (task.get("creator") or "").lower()
    assignee = (task.get("assignee") or "").lower()

    # Build candidate list from rotation map
    candidates = list(SPEAKER_ROTATION.get(last, []))

    # Prioritise task participants (creator / assignee) if they appear in candidates
    task_participants = [p for p in [creator, assignee] if p and p != last]
    prioritised = [c for c in candidates if c in task_participants]
    if prioritised:
        return prioritised[0].capitalize()

    # If rotation map gave candidates, use the first one
    if candidates:
        return candidates[0].capitalize()

    # Fallback: pick any speaker that isn't the last one
    for s in task_participants:
        if s != last and s in ALL_SPEAKERS:
            return s.capitalize()
    for s in ALL_SPEAKERS:
        if s != last:
            return s.capitalize()

    # Absolute fallback
    return "Liam"


def build_prompt(task: dict, speaker: str, persona_content: str, global_context: str) -> str:
    """
    Assemble the full prompt for the next discussion turn.
    """
    dlg = task["dialogue"]
    thread_text = ""
    for entry in dlg.get("thread", []):
        thread_text += f"[{entry['speaker']}] ({entry.get('timestamp', '')}): {entry['text']}\n"

    if not thread_text:
        thread_text = "(No prior dialogue yet.)"

    prompt = (
        f"@{speaker.lower()}\n\n"
        f"Your Persona Definition and Constraints:\n"
        f"{persona_content}\n\n"
        f"=== GLOBAL CONTEXT ===\n"
        f"{global_context}\n\n"
        f"=== TASK CONTEXT ===\n"
        f"Task ID: {task['id']}\n"
        f"Title: {task['title']}\n"
        f"Description: {task.get('description', 'N/A')}\n"
        f"Type: {task.get('type', 'N/A')}\n"
        f"Creator: {task.get('creator', 'N/A')}\n"
        f"Assignee: {task.get('assignee', 'N/A')}\n"
        f"Status: {task.get('status', 'N/A')}\n"
        f"Turn: {dlg['turn_count'] + 1}/{dlg['max_turns']}\n\n"
        f"=== DIALOGUE SO FAR ===\n"
        f"{thread_text}\n"
        f"=== INSTRUCTIONS ===\n"
        f"You are {speaker}. Continue the team discussion above naturally.\n"
        f"- Address what the previous speaker said and advance the conversation.\n"
        f"- Be constructive: propose next steps, share insights, or ask clarifying questions.\n"
        f"- Stay in character per your persona constraints.\n"
        f"- Keep your response concise (2-4 sentences).\n\n"
    )

    # Add closing-turn guidance if this is the final turn
    if dlg["turn_count"] + 1 >= dlg["max_turns"]:
        prompt += (
            "NOTE: This is the FINAL turn of the discussion. "
            "Wrap up the conversation with a clear conclusion or agreed action item.\n\n"
        )

    prompt += (
        "CRITICAL FORMATTING REQUIREMENT:\n"
        "You MUST wrap your final reply strictly inside <response>...</response> tags.\n"
        "Everything outside these tags will be discarded.\n"
        "For example:\n"
        "<response>Sounds good, I'll update the docs today.</response>"
    )
    return prompt


def extract_response(raw: str) -> str:
    """Extract text from <response>...</response> tags."""
    match = re.search(r"<response>(.*?)</response>", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw.strip()


def build_outbox_entry(task: dict, speaker: str, text: str) -> dict:
    """
    Create an outbox response object.
    If the task has a github_issue_url, target GitHub and format as issue comment.
    Otherwise target Slack.
    """
    github_url = task.get("github_issue_url")
    issue_number = task.get("github_issue_number")

    if github_url and issue_number:
        return {
            "character": speaker,
            "text": f"[ISSUE_COMMENT: #{issue_number}]\n{text}",
            "target_channel": "github",
        }
    else:
        return {
            "character": speaker,
            "text": text,
            "target_channel": "slack",
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("[Discussion Runner] Starting discussion cycle...")

    # 1. Load discussing tasks
    discussing = task_manager.get_discussing_tasks()
    if not discussing:
        print("[Discussion Runner] No tasks in 'discussing' state. Nothing to do.")
        return

    print(f"[Discussion Runner] Found {len(discussing)} discussing task(s).")

    # Cap at MAX_TASKS_PER_CYCLE
    tasks_to_process = discussing[:MAX_TASKS_PER_CYCLE]
    if len(discussing) > MAX_TASKS_PER_CYCLE:
        print(f"[Discussion Runner] Processing first {MAX_TASKS_PER_CYCLE} of {len(discussing)} tasks.")

    # Load global context once
    global_context = load_file(GLOBAL_CONTEXT_FILE)

    final_responses = []
    resolved_tasks = []

    for task in tasks_to_process:
        task_id = task["id"]
        print(f"\n[Discussion Runner] --- Processing {task_id}: {task['title']} ---")

        # 2a. Determine next speaker
        speaker = determine_next_speaker(task)
        print(f"[Discussion Runner] Next speaker: {speaker}")

        # 2b. Load persona
        persona_path = os.path.join(
            WORKSPACE_DIR, ".gemini", "agents", f"{speaker.lower()}.md"
        )
        persona_content = load_file(persona_path)
        if not persona_content:
            print(f"[Discussion Runner] Warning: No persona file for {speaker} at {persona_path}")

        # 2c. Build prompt
        prompt = build_prompt(task, speaker, persona_content, global_context)

        # 2d. Call agy
        raw_output = run_agy(prompt)
        if not raw_output:
            print(f"[Discussion Runner] No response from agy for {task_id}. Skipping.")
            continue

        # 2e. Parse response
        response_text = extract_response(raw_output)
        print(f"[Discussion Runner] {speaker}'s response: {response_text[:120]}...")

        # 2f. Build outbox entry
        outbox_entry = build_outbox_entry(task, speaker, response_text)
        final_responses.append(outbox_entry)

        # 2g. Record the dialogue turn (auto-resolves at max_turns)
        task_manager.add_dialogue_entry(task_id, speaker, response_text, action="comment")

        # Check if this task just hit max_turns
        if task_manager.check_dialogue_limit(task_id):
            print(f"[Discussion Runner] {task_id} reached max turns — dialogue resolved.")
            resolved_tasks.append(task)

    # 3. For resolved tasks with GitHub issues, add a close action
    for task in resolved_tasks:
        issue_number = task.get("github_issue_number")
        if issue_number:
            close_entry = {
                "character": "System",
                "text": f"[ISSUE_CLOSE: #{issue_number}]",
                "target_channel": "github",
            }
            final_responses.append(close_entry)
            print(f"[Discussion Runner] Queued ISSUE_CLOSE for #{issue_number}")

    # 4. Write outbox
    if final_responses:
        os.makedirs(os.path.dirname(OUTBOX_FILE), exist_ok=True)
        with open(OUTBOX_FILE, "w", encoding="utf-8") as f:
            json.dump(final_responses, f, indent=2, ensure_ascii=False)
        print(f"\n[Discussion Runner] Cycle complete. Saved {len(final_responses)} response(s) to outbox.")
    else:
        print("\n[Discussion Runner] Cycle complete. No responses generated.")


if __name__ == "__main__":
    main()
