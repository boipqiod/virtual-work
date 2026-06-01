#!/bin/bash
# ==============================================================================
# Daily Midnight Log Compressor & Folder Rollover Script
# ==============================================================================
# This script:
# 1. Reads the current day's raw_history.jsonl file.
# 2. Generates a daily summary utilizing an AI model (simulated).
# 3. Writes daily_summary.md to the current day's memory directory.
# 4. Prepares the next day's memory directory.
# ==============================================================================

# Verify python3 presence
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required to run daily_compressor.sh." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"

# Robustly load env
load_env() {
  local env_file="$1"
  if [ -f "$env_file" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      if [[ ! "$line" =~ ^[[:space:]]*# ]] && [[ "$line" =~ [[:space:]]*=[[:space:]]* ]]; then
        local key=$(echo "$line" | cut -d'=' -f1 | xargs)
        local val=$(echo "$line" | cut -d'=' -f2- | xargs)
        val="${val%\"}"
        val="${val#\"}"
        val="${val%\'}"
        val="${val#\'}"
        export "$key"="$val"
      fi
    done < "$env_file"
  fi
}

load_env "$WORKSPACE_DIR/.env"

TODAY=$(date +"%Y-%m-%d")
NEXT_DAY=$(date -v+1d +"%Y-%m-%d" 2>/dev/null || date -d "+1 day" +"%Y-%m-%d" 2>/dev/null)

TODAY_DIR="$WORKSPACE_DIR/agent_io/memory/$TODAY"
NEXT_DAY_DIR="$WORKSPACE_DIR/agent_io/memory/$NEXT_DAY"
RAW_HISTORY="$TODAY_DIR/raw_history.jsonl"
SUMMARY_FILE="$TODAY_DIR/daily_summary.md"

echo "=== Running Daily Log Compressor for $TODAY ==="

# 1. Ensure today's directory exists
if [ ! -d "$TODAY_DIR" ]; then
  echo "Today's memory directory $TODAY_DIR does not exist. Creating it..."
  mkdir -p "$TODAY_DIR"
fi

# 2. If raw history exists, perform compression/summary
if [ -f "$RAW_HISTORY" ]; then
  echo "Found raw history at $RAW_HISTORY. Summarizing..."
  
  # AI Simulation: In a real environment, this calls:
  # agy run --prompt "Summarize these events: $(cat $RAW_HISTORY)"
  # Here we simulate using a Python script that reads the JSONL and generates a structured summary.
  export RAW_HISTORY_PATH="$RAW_HISTORY"
  export SUMMARY_PATH="$SUMMARY_FILE"
  export TODAY_DATE="$TODAY"
  
  python3 -c '
import os
import json

raw_history_path = os.environ.get("RAW_HISTORY_PATH")
summary_path = os.environ.get("SUMMARY_PATH")
today_date = os.environ.get("TODAY_DATE")

print(f"Reading events from {raw_history_path}...")
events_count = 0
messages = []

try:
    with open(raw_history_path, "r") as f:
        for line in f:
            if line.strip():
                try:
                    event = json.loads(line)
                    events_count += 1
                    user = event.get("user", "Unknown")
                    text = event.get("text", "")
                    ts = event.get("ts", "")
                    messages.append(f"- [{ts}] {user}: {text}")
                except Exception as e:
                    print(f"Warning: failed to parse JSON line: {e}")
except Exception as e:
    print(f"Error opening history: {e}")
    exit(1)

# Generate formatted messages list outside f-string to avoid backslash SyntaxError in Python < 3.12
formatted_msgs = "\n".join(messages) if messages else "- No events recorded today."

# Generate a mock AI markdown summary of the logs
summary_content = f"""# Daily Summary for {today_date}

## Statistics
- **Total Events Processed**: {events_count}

## Raw History Events log
{formatted_msgs}

## AI Analysis
*This section simulates the output of the AI summarizer (`agy`).*
- The team was active.
- Key discussion points centered around system state and updates.
"""

with open(summary_path, "w") as f:
    f.write(summary_content)

print(f"Summary written to {summary_path}")
'
else
  echo "No raw history found for today ($TODAY). Creating empty daily summary..."
  echo -e "# Daily Summary for $TODAY\n\nNo events were recorded today." > "$SUMMARY_FILE"
fi

# 2.5. Archive completed tasks from agent_tasks.json
echo "Archiving completed tasks for $TODAY..."
export SCRIPT_DIR
export TODAY_DIR
python3 -c '
import os
import sys
import json

script_dir = os.environ.get("SCRIPT_DIR", "")
sys.path.insert(0, script_dir)
try:
    import task_manager
    today_dir = os.environ.get("TODAY_DIR", "")
    completed = task_manager.archive_completed_tasks()
    if completed:
        archive_path = os.path.join(today_dir, "completed_tasks.json")
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(completed, f, indent=2, ensure_ascii=False)
        print(f"Archived {len(completed)} completed tasks to {archive_path}")
    else:
        print("No completed tasks to archive.")
except Exception as e:
    print(f"Error archiving tasks: {e}")
'

# 3. Prepare the next day's directory
echo "Preparing next day directory at $NEXT_DAY_DIR..."
mkdir -p "$NEXT_DAY_DIR"
touch "$NEXT_DAY_DIR/.gitkeep"

echo "=== Rollover and compression completed successfully ==="
