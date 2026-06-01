import os
import sys
import json
import subprocess
import concurrent.futures
import re


# ------------------------------------------------------------------------------
# Configuration & Paths
# ------------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(SCRIPT_DIR)
AGENT_IO_DIR = os.path.join(WORKSPACE_DIR, "agent_io")
PROMPTS_DIR = os.path.join(WORKSPACE_DIR, "config_harness", "subagent_prompts")

INBOX_FILE = os.path.join(AGENT_IO_DIR, "inbox", "current_event.json")
OUTBOX_FILE = os.path.join(AGENT_IO_DIR, "outbox", "final_response.json")
GLOBAL_CONTEXT_FILE = os.path.join(AGENT_IO_DIR, "memory", "global_context.md")

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
def run_agy(prompt):
    """
    Executes 'agy -p' inside the local workspace directory.
    """
    print(f"[AI Runner] Executing agy agent...")
    try:
        result = subprocess.run(
            ["agy", "--add-dir", WORKSPACE_DIR, "--dangerously-skip-permissions", "-p", prompt],
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[AI Runner] Error running agy: {e.stderr}", file=sys.stderr)
        return ""

def load_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# ------------------------------------------------------------------------------
# Main Pipeline
# ------------------------------------------------------------------------------
def main():
    if not os.path.exists(INBOX_FILE):
        print("[AI Runner] No incoming event in inbox.")
        sys.exit(0)

    print("[AI Runner] Starting AI Harness Pipeline...")

    # 1. Load context and incoming event
    incoming_event = load_file(INBOX_FILE)
    global_context = load_file(GLOBAL_CONTEXT_FILE)
    
    incoming_event_json = {}
    try:
        incoming_event_json = json.loads(incoming_event)
    except Exception:
        pass
    
    event_source = incoming_event_json.get("source", "slack")
    default_target = "slack" if event_source in ("system", "unknown") else event_source

    
    # Get last 10 lines of history if available
    import datetime
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    history_file = os.path.join(AGENT_IO_DIR, "memory", today, "raw_history.jsonl")
    history = ""
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            lines = f.readlines()
            history = "".join(lines[-10:])
    
    # 2. Stage 1: Routing
    router_prompt_template = load_file(os.path.join(PROMPTS_DIR, "router.txt"))
    if not router_prompt_template:
        print("[AI Runner] Router prompt not found.")
        sys.exit(1)

    sys.path.insert(0, SCRIPT_DIR)
    import task_manager
    agent_tasks = task_manager.get_tasks_summary()

    router_prompt = router_prompt_template.replace("{global_context}", global_context)
    router_prompt = router_prompt.replace("{agent_tasks}", agent_tasks)
    router_prompt = router_prompt.replace("{history}", history)
    router_prompt = router_prompt.replace("{incoming_event}", incoming_event)
    
    router_prompt += f"\n\nNOTE: This event came from: {event_source.upper()}. "
    router_prompt += "Respond with a JSON object. You MUST wrap the JSON object strictly inside <router>...</router> tags. Do not put any other text inside the tags."
    
    router_raw_output = run_agy(router_prompt)
    if not router_raw_output:
        print("[AI Runner] Failed to get response from Router.")
        sys.exit(1)

    # Extract JSON inside <router>...</router> tags
    router_json_str = ""
    match = re.search(r'<router>(.*?)</router>', router_raw_output, re.DOTALL)
    if match:
        router_json_str = match.group(1).strip()
    else:
        # Fallback to finding the first '{' and last '}'
        json_match = re.search(r'(\{.*\})', router_raw_output, re.DOTALL)
        if json_match:
            router_json_str = json_match.group(1).strip()
        else:
            router_json_str = router_raw_output
            if router_json_str.startswith("```"):
                router_json_str = "\n".join(router_json_str.split("\n")[1:-1])

    try:
        router_result = json.loads(router_json_str)
    except Exception as e:
        print(f"[AI Runner] Router returned invalid JSON: {router_raw_output}\nError: {e}")
        sys.exit(1)

    print(f"[AI Runner] Router Decision: {router_result}")

    if not router_result.get("should_respond", False):
        print("[AI Runner] Router decided no response is needed.")
        sys.exit(0)

    final_responses = []

    # 3. Stage 2: Persona Generation (Executed Sequentially)
    def process_speaker(speaker, active_history):
        speaker_lower = speaker.lower()
        
        # Load the persona settings manually to ensure they are strictly enforced
        persona_path = os.path.join(WORKSPACE_DIR, ".gemini", "agents", f"{speaker_lower}.md")
        persona_content = load_file(persona_path)
        
        prompt = (
            f"@{speaker_lower}\n\n"
            f"Your Persona Definition and Constraints:\n"
            f"{persona_content}\n\n"
            f"Current Tasks Board:\n"
            f"{agent_tasks}\n\n"
            f"Context:\n{active_history}\n\n"
            f"Latest message to reply to:\n{incoming_event}\n\n"
            f"Please reply to the message as {speaker} strictly adhering to all your Persona Definition and Constraints.\n"
            f"Ensure you follow your style constraints (such as length limits, capitalization rules, banned words, and catchphrase guidelines).\n\n"
            f"CRITICAL FORMATTING REQUIREMENT:\n"
            f"You MUST wrap your final chat response strictly inside <response>...</response> tags.\n"
            f"Do NOT include the tags inside the response text itself. Everything outside these tags (such as your plans, tool usage, or thinking process) will be discarded, so only the text inside these tags will be posted to the chat channel.\n"
            f"For example:\n"
            f"<response>Hey mate! I'll get on it.</response>"
        )
        response_text = run_agy(prompt)
        print(f"[AI Runner] Raw response from {speaker}:\n{response_text}")

        # Extract content inside <response>...</response>
        clean_text = ""
        match_resp = re.search(r'<response>(.*?)</response>', response_text, re.DOTALL)
        if match_resp:
            clean_text = match_resp.group(1).strip()
        else:
            clean_text = response_text

        return {
            "character": speaker,
            "text": clean_text,
            "target_channel": default_target
        }

    speakers = router_result.get("speakers", [])
    if speakers:
        print(f"[AI Runner] Generating responses for speakers sequentially: {speakers}")
        active_history = history
        for speaker in speakers:
            res = process_speaker(speaker, active_history)
            if res and res.get("text"):
                final_responses.append(res)
                
                # Append this response to active history so the next speaker has immediate context
                new_msg = {
                    "subtype": "bot_message",
                    "text": res["text"],
                    "username": speaker,
                    "type": "message",
                    "source": "slack"
                }
                active_history += "\n" + json.dumps(new_msg)

    # 4. Write to outbox
    if final_responses:
        os.makedirs(os.path.dirname(OUTBOX_FILE), exist_ok=True)
        with open(OUTBOX_FILE, "w", encoding="utf-8") as f:
            json.dump(final_responses, f, indent=2)
        print(f"[AI Runner] Pipeline finished. Saved {len(final_responses)} responses to outbox.")
    else:
        print("[AI Runner] No responses generated.")

if __name__ == "__main__":
    main()
