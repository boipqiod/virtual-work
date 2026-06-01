#!/bin/bash
# ==============================================================================
# Virtual Office Master Runner (start.sh)
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================="
echo "Starting Aussie Startup Virtual Office..."
echo "Press [CTRL+C] to stop all processes gracefully."
echo "=================================================="

# 1. Response Monitor Loop (10s intervals for incoming Slack messages)
bash "$SCRIPT_DIR/app/main.sh" &
MAIN_PID=$!
echo "-> Response Monitor (main.sh) started (PID: $MAIN_PID)"

# 2. Proactive Conversation Loop (1-2 hour intervals)
bash "$SCRIPT_DIR/app/active_loop.sh" &
ACTIVE_PID=$!
echo "-> Proactive Checker (active_loop.sh) started (PID: $ACTIVE_PID)"

# 2.5. Discussion Loop (30 min intervals)
bash "$SCRIPT_DIR/app/discussion_loop.sh" &
DISCUSSION_PID=$!
echo "-> Discussion Engine (discussion_loop.sh) started (PID: $DISCUSSION_PID)"

# 3. Web Dashboard Server (Port 8000)
python3 "$SCRIPT_DIR/app/dashboard.py" &
DASHBOARD_PID=$!
echo "-> Interactive Web Dashboard started at http://localhost:8000 (PID: $DASHBOARD_PID)"
echo "=================================================="

# Cleanup block to kill background jobs upon Ctrl+C
cleanup() {
  echo -e "\nStopping all Virtual Office processes..."
  kill $MAIN_PID $ACTIVE_PID $DISCUSSION_PID $DASHBOARD_PID 2>/dev/null
  echo "All processes stopped. See you mate!"
  exit 0
}

trap cleanup INT TERM

# Wait for background jobs
wait
