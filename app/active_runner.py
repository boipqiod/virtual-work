import os
import sys
import json
import subprocess
import re
from datetime import datetime, timedelta

# Sibling module import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import task_manager

# ------------------------------------------------------------------------------
# Configuration & Paths
# ------------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(SCRIPT_DIR)
AGENT_IO_DIR = os.path.join(WORKSPACE_DIR, "agent_io")
PROMPTS_DIR = os.path.join(WORKSPACE_DIR, "config_harness", "subagent_prompts")

OUTBOX_FILE = os.path.join(AGENT_IO_DIR, "outbox", "final_response.json")
GLOBAL_CONTEXT_FILE = os.path.join(AGENT_IO_DIR, "memory", "global_context.md")
PERSONAS_DIR = os.path.join(WORKSPACE_DIR, ".gemini", "agents")

# Map of assignee names to persona file basenames
TEAM_MEMBERS = ["sarah", "liam", "chloe", "aiden"]

# Task types eligible for discussion seeding after completion
DISCUSSION_WORTHY_TYPES = {"document", "research", "planning"}

# Deliverable-to-reviewer mapping (who should review whose work)
REVIEW_PAIRS = {
    "sarah": "liam",
    "liam": "aiden",
    "chloe": "liam",
    "aiden": "sarah",
}


# ------------------------------------------------------------------------------
# Environment Loader
# ------------------------------------------------------------------------------
def load_env():
    env_vars = {}
    env_path = os.path.join(WORKSPACE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip().strip('"').strip("'")
    return env_vars


ENV = load_env()


# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
def run_agy(prompt):
    """Call the agy CLI with the given prompt and return stdout."""
    print(f"[Active Runner] Executing agy agent...")
    try:
        result = subprocess.run(
            ["agy", "--add-dir", WORKSPACE_DIR, "--dangerously-skip-permissions", "-p", prompt],
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[Active Runner] Error running agy: {e.stderr}", file=sys.stderr)
        return ""


def load_file(path):
    """Load a text file if it exists, otherwise return empty string."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def get_github_status(repo_name):
    """Fetch GitHub status via gh CLI, or return mock data if unavailable."""
    if not repo_name or repo_name == "owner/repo":
        print("[Active Runner] GITHUB_REPO is placeholder/empty. Loading mock GitHub metadata for testing.")
        return (
            "- Pull Request #15: 'feat: add login API' (Created 2 hours ago, Author: user, Needs Code Review)\n"
            "- Issue #3: 'db connection pool drops under heavy load' (Stale for 2 days, Status: Open, Priority: High)\n"
            "- Recent Commits: 'wip: fix landing page css alignment' (Committed 1 hour ago by user)"
        )

    print(f"[Active Runner] Fetching real GitHub status for {repo_name}...")
    try:
        issues_res = subprocess.run(
            ["gh", "issue", "list", "-R", repo_name, "--limit", "5", "--json", "number,title,createdAt,state"],
            capture_output=True, text=True,
        )
        prs_res = subprocess.run(
            ["gh", "pr", "list", "-R", repo_name, "--limit", "5", "--json", "number,title,createdAt,state"],
            capture_output=True, text=True,
        )

        status_lines = []
        if prs_res.returncode == 0 and prs_res.stdout.strip():
            prs = json.loads(prs_res.stdout)
            for pr in prs:
                status_lines.append(
                    f"- Pull Request #{pr['number']}: '{pr['title']}' (Status: {pr['state']}, Created: {pr['createdAt']})"
                )
        if issues_res.returncode == 0 and issues_res.stdout.strip():
            issues = json.loads(issues_res.stdout)
            for issue in issues:
                status_lines.append(
                    f"- Issue #{issue['number']}: '{issue['title']}' (Status: {issue['state']}, Created: {issue['createdAt']})"
                )

        if not status_lines:
            return "No active PRs or Issues found on GitHub."
        return "\n".join(status_lines)
    except Exception as e:
        print(f"[Active Runner] Error fetching real GitHub data: {e}. Falling back to mock data.")
        return (
            "- Pull Request #15: 'feat: add login API' (Created 2 hours ago, Needs Code Review)\n"
            "- Issue #3: 'db connection pool drops' (Stale for 2 days, Status: Open)"
        )


# ------------------------------------------------------------------------------
# Phase A: Planning
# ------------------------------------------------------------------------------
def phase_planning(global_context, github_status, yesterday_summary):
    """
    Call the AI work planner to analyze the current state and produce
    new tasks + pickup decisions. Returns the parsed plan dict or None.
    """
    print("\n" + "=" * 60)
    print("[Phase A] PLANNING — Analyzing project state and assigning work")
    print("=" * 60)

    # Load current task board summary
    agent_tasks_summary = task_manager.get_tasks_summary()
    print(f"[Phase A] Current board:\n{agent_tasks_summary}")

    # Load the planner prompt template
    prompt_template = load_file(os.path.join(PROMPTS_DIR, "work_planner.txt"))
    if not prompt_template:
        print("[Phase A] Error: work_planner.txt not found.")
        return None

    prompt = prompt_template.replace("{global_context}", global_context)
    prompt = prompt.replace("{agent_tasks}", agent_tasks_summary)
    prompt = prompt.replace("{github_status}", github_status)
    prompt = prompt.replace("{yesterday_summary}", yesterday_summary or "No summary available (first run or new day).")
    prompt += "\n\nCRITICAL: You MUST wrap your JSON response inside <plan>...</plan> tags."

    # Call the AI planner
    raw_response = run_agy(prompt)
    if not raw_response:
        print("[Phase A] Failed to get response from planner agent.")
        return None

    # Parse <plan>...</plan> tags
    plan = _extract_tagged_json(raw_response, "plan")
    if not plan:
        print(f"[Phase A] Could not parse plan from response:\n{raw_response[:500]}")
        return None

    print(f"[Phase A] Plan reasoning: {plan.get('reasoning', 'N/A')}")

    # --- Execute the plan ---

    # 1. Create new tasks
    new_tasks = plan.get("new_tasks", [])
    created_ids = []
    for nt in new_tasks:
        assignee = nt.get("assignee", "").lower()
        if assignee not in TEAM_MEMBERS:
            print(f"[Phase A] Skipping task with invalid assignee '{assignee}': {nt.get('title')}")
            continue

        task = task_manager.create_task(
            creator="planner",
            title=nt.get("title", "Untitled Task"),
            description=nt.get("description", ""),
            task_type=nt.get("type", "document"),
            assignee=assignee,
            deliverable=nt.get("deliverable", "internal_note"),
            trigger_type="next_cycle",
            github_issue_number=nt.get("github_issue_number"),
        )
        # Immediately move to in_progress so it gets executed this cycle
        task_manager.update_task_status(task["id"], "in_progress")
        created_ids.append(task["id"])

    if created_ids:
        print(f"[Phase A] Created and activated {len(created_ids)} new tasks: {created_ids}")

    # 2. Pick up backlog tasks
    pickup_tasks = plan.get("pickup_tasks", [])
    picked_up_ids = []
    for pt in pickup_tasks:
        task_id = pt.get("task_id", "")
        existing = task_manager.get_task(task_id)
        if existing and existing["status"] == "backlog":
            task_manager.update_task_status(task_id, "in_progress")
            picked_up_ids.append(task_id)
            print(f"[Phase A] Picked up {task_id}: {pt.get('reason', 'N/A')}")
        else:
            print(f"[Phase A] Cannot pick up {task_id} (not found or not in backlog).")

    if picked_up_ids:
        print(f"[Phase A] Picked up {len(picked_up_ids)} backlog tasks: {picked_up_ids}")

    total = len(created_ids) + len(picked_up_ids)
    if total == 0:
        print("[Phase A] No new work planned. Board is sufficient.")

    return plan


# ------------------------------------------------------------------------------
# Phase B: Execution
# ------------------------------------------------------------------------------
def phase_execution(global_context):
    """
    Execute all in_progress tasks by calling the AI with each task's
    assignee persona. Parse action tags from the response and collect
    outbox messages. Returns list of completed task dicts.
    """
    print("\n" + "=" * 60)
    print("[Phase B] EXECUTION — Running in-progress tasks")
    print("=" * 60)

    in_progress = task_manager.get_tasks_by_status("in_progress")
    if not in_progress:
        print("[Phase B] No in-progress tasks to execute.")
        return []

    # Load executor prompt template
    prompt_template = load_file(os.path.join(PROMPTS_DIR, "work_executor.txt"))
    if not prompt_template:
        print("[Phase B] Error: work_executor.txt not found.")
        return []

    outbox_messages = []
    completed_tasks = []

    for task in in_progress:
        task_id = task["id"]
        assignee = task.get("assignee", "").lower()
        task_type = task.get("type", "document")
        deliverable = task.get("deliverable", "internal_note")

        print(f"\n--- Executing {task_id}: {task['title']} (assignee: {assignee}) ---")

        # Load the assignee's persona
        persona_path = os.path.join(PERSONAS_DIR, f"{assignee}.md")
        persona_content = load_file(persona_path)
        if not persona_content:
            print(f"[Phase B] Warning: Persona file not found for '{assignee}'. Using generic.")
            persona_content = f"You are {assignee}, a team member at Shout Financial."

        # Build the prompt
        prompt = prompt_template.replace("{assignee}", assignee.capitalize())
        prompt = prompt.replace("{task_id}", task_id)
        prompt = prompt.replace("{task_title}", task.get("title", ""))
        prompt = prompt.replace("{task_description}", task.get("description", ""))
        prompt = prompt.replace("{task_type}", task_type)
        prompt = prompt.replace("{deliverable}", deliverable)
        prompt = prompt.replace("{persona_content}", persona_content)
        prompt = prompt.replace("{global_context}", global_context)
        prompt += "\n\nCRITICAL: You MUST wrap your response inside <work>...</work> tags."

        # Call the AI executor
        raw_response = run_agy(prompt)
        if not raw_response:
            print(f"[Phase B] Failed to get response for {task_id}. Skipping.")
            continue

        # Extract <work>...</work> content
        work_content = _extract_tagged_text(raw_response, "work")
        if not work_content:
            print(f"[Phase B] Could not parse <work> tags for {task_id}. Using raw response.")
            work_content = raw_response

        # Parse action tags and build outbox messages
        actions = _parse_action_tags(work_content)
        for action in actions:
            msg = _action_to_outbox(action, assignee, task_id)
            if msg:
                outbox_messages.append(msg)

        # If no action tags were found, create a default slack message with the summary
        if not actions:
            summary_line = _extract_summary(work_content)
            if summary_line:
                outbox_messages.append({
                    "character": assignee.capitalize(),
                    "text": summary_line,
                    "target_channel": "slack",
                    "task_id": task_id,
                })

        # Mark task as done
        task_manager.update_task_status(task_id, "done")

        # Store the work output as the deliverable reference
        summary = _extract_summary(work_content) or f"Completed: {task['title']}"
        task_manager.update_task_field(task_id, "deliverable_ref", summary)

        completed_tasks.append(task)
        print(f"[Phase B] ✅ Completed {task_id}: {task['title']}")

    # Write all outbox messages
    if outbox_messages:
        _write_outbox(outbox_messages)
        print(f"\n[Phase B] Wrote {len(outbox_messages)} messages to outbox.")
    else:
        print("\n[Phase B] No outbox messages produced.")

    return completed_tasks


# ------------------------------------------------------------------------------
# Phase C: Discussion Seeding
# ------------------------------------------------------------------------------
def phase_discussion_seeding(completed_tasks):
    """
    For tasks that just completed and have discussion-worthy deliverables,
    seed a discussion thread so discussion_runner.py picks it up next cycle.
    """
    print("\n" + "=" * 60)
    print("[Phase C] DISCUSSION SEEDING — Creating review threads")
    print("=" * 60)

    seeded_count = 0

    for task in completed_tasks:
        task_id = task["id"]
        task_type = task.get("type", "")
        assignee = task.get("assignee", "").lower()

        # Only seed discussions for discussion-worthy task types
        if task_type not in DISCUSSION_WORTHY_TYPES:
            print(f"[Phase C] Skipping {task_id} (type '{task_type}' not discussion-worthy).")
            continue

        # Determine who should review
        reviewer = REVIEW_PAIRS.get(assignee)
        if not reviewer:
            print(f"[Phase C] No reviewer mapped for {assignee}. Skipping {task_id}.")
            continue

        # Re-fetch the task to get the latest state (it's now 'done')
        current_task = task_manager.get_task(task_id)
        if not current_task:
            continue

        # Don't seed if a discussion is already active or resolved
        if current_task["dialogue"]["state"] != "idle":
            print(f"[Phase C] {task_id} already has a discussion. Skipping.")
            continue

        # Seed the discussion
        deliverable_ref = current_task.get("deliverable_ref", task["title"])
        seed_text = (
            f"Hey @{reviewer}, I just finished '{task['title']}'. "
            f"Could you take a look and let me know your thoughts? "
            f"Summary: {deliverable_ref}"
        )

        task_manager.start_discussion(task_id, assignee, seed_text)
        seeded_count += 1
        print(f"[Phase C] 💬 Seeded discussion on {task_id}: {assignee} → {reviewer}")

    if seeded_count == 0:
        print("[Phase C] No discussions seeded this cycle.")
    else:
        print(f"[Phase C] Seeded {seeded_count} discussion(s).")


# ------------------------------------------------------------------------------
# Parsing Helpers
# ------------------------------------------------------------------------------
def _extract_tagged_json(text, tag_name):
    """Extract JSON from inside <tag>...</tag> markers."""
    pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    else:
        # Fallback: try to find raw JSON
        json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            return None

    # Clean markdown code fences if present
    if json_str.startswith("```"):
        lines = json_str.split("\n")
        json_str = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"[Parser] JSON decode error for <{tag_name}>: {e}")
        return None


def _extract_tagged_text(text, tag_name):
    """Extract raw text from inside <tag>...</tag> markers."""
    pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _extract_summary(work_content):
    """Extract the SUMMARY: line from work output."""
    for line in work_content.split("\n"):
        if line.strip().upper().startswith("SUMMARY:"):
            return line.strip()[len("SUMMARY:"):].strip()
    return None


def _parse_action_tags(work_content):
    """
    Parse action tags from work output.
    Returns list of dicts: {action, arg, body}
    """
    actions = []

    # Match action tags like [WIKI_WRITE: Title], [ISSUE_CREATE: Title | Desc], etc.
    tag_pattern = r'\[(WIKI_WRITE|ISSUE_CREATE|ISSUE_COMMENT|ISSUE_CLOSE|SLACK_MESSAGE)(?::\s*([^\]]*))?\]'
    matches = list(re.finditer(tag_pattern, work_content))

    for i, match in enumerate(matches):
        action_type = match.group(1)
        action_arg = match.group(2).strip() if match.group(2) else ""

        # Extract body: text between this tag and the next tag (or SUMMARY or end)
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            # Find SUMMARY line or end of content
            summary_match = re.search(r'\nSUMMARY:', work_content[start:], re.IGNORECASE)
            end = start + summary_match.start() if summary_match else len(work_content)

        body = work_content[start:end].strip()

        actions.append({
            "action": action_type,
            "arg": action_arg,
            "body": body,
        })

    return actions


def _action_to_outbox(action, assignee, task_id):
    """Convert a parsed action tag into an outbox message dict."""
    action_type = action["action"]
    arg = action["arg"]
    body = action["body"]

    if action_type == "WIKI_WRITE":
        # Write the wiki page to shout_wiki/
        wiki_dir = os.path.join(WORKSPACE_DIR, "shout_wiki")
        os.makedirs(wiki_dir, exist_ok=True)
        safe_title = re.sub(r'[^\w\s-]', '', arg).strip().replace(' ', '_')
        wiki_path = os.path.join(wiki_dir, f"{safe_title}.md")
        with open(wiki_path, "w", encoding="utf-8") as f:
            f.write(body)
        print(f"[Action] WIKI_WRITE → {wiki_path}")
        return {
            "character": assignee.capitalize(),
            "text": f"📝 I've updated the wiki page: **{arg}**",
            "target_channel": "slack",
            "task_id": task_id,
        }

    elif action_type == "ISSUE_CREATE":
        # Parse "Title | Description"
        parts = arg.split("|", 1)
        title = parts[0].strip()
        desc = parts[1].strip() if len(parts) > 1 else body
        return {
            "character": assignee.capitalize(),
            "text": f"📋 Created issue: **{title}**\n{desc}",
            "target_channel": "github_issue_create",
            "issue_title": title,
            "issue_body": desc,
            "task_id": task_id,
        }

    elif action_type == "ISSUE_COMMENT":
        # arg is like "#15"
        issue_num = arg.replace("#", "").strip()
        return {
            "character": assignee.capitalize(),
            "text": body,
            "target_channel": "github_issue_comment",
            "issue_number": issue_num,
            "task_id": task_id,
        }

    elif action_type == "ISSUE_CLOSE":
        issue_num = arg.replace("#", "").strip()
        return {
            "character": assignee.capitalize(),
            "text": f"Closing issue #{issue_num}.",
            "target_channel": "github_issue_close",
            "issue_number": issue_num,
            "task_id": task_id,
        }

    elif action_type == "SLACK_MESSAGE":
        return {
            "character": assignee.capitalize(),
            "text": body,
            "target_channel": "slack",
            "task_id": task_id,
        }

    return None


def _write_outbox(messages):
    """Write messages to the outbox file for queue_manager.sh to dispatch."""
    os.makedirs(os.path.dirname(OUTBOX_FILE), exist_ok=True)
    with open(OUTBOX_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)


# ------------------------------------------------------------------------------
# Main Flow: 3-Phase Autonomous Work Cycle
# ------------------------------------------------------------------------------
def main():
    print("=" * 60)
    print(f"[Active Runner] Autonomous Work Cycle — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # --- Gather shared context ---
    global_context = load_file(GLOBAL_CONTEXT_FILE)
    github_status = get_github_status(ENV.get("GITHUB_REPO"))

    # Load yesterday's summary
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_summary_path = os.path.join(AGENT_IO_DIR, "memory", yesterday, "daily_summary.md")
    yesterday_summary = load_file(yesterday_summary_path)

    # --- Phase A: Planning ---
    plan = phase_planning(global_context, github_status, yesterday_summary)

    # --- Phase B: Execution ---
    completed_tasks = phase_execution(global_context)

    # --- Phase C: Discussion Seeding ---
    phase_discussion_seeding(completed_tasks)

    # --- Summary ---
    print("\n" + "=" * 60)
    print("[Active Runner] Cycle complete.")
    board_summary = task_manager.get_tasks_summary()
    print(f"[Active Runner] Final board state:\n{board_summary}")
    print("=" * 60)


if __name__ == "__main__":
    main()
