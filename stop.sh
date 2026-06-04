#!/usr/bin/env bash
# =============================================================================
# Virtual Office — Graceful Shutdown Script
# Finds the running main.py process and shuts it down gracefully.
# =============================================================================

# Find the PID of python3 main.py running in the virtual-office directory
PID=$(ps aux | grep "[m]ain.py" | awk '{print $2}')

if [ -n "$PID" ]; then
    echo "Found Virtual Office running with PID: $PID"
    echo "Sending SIGINT (Ctrl+C signal) to trigger graceful shutdown..."
    kill -2 "$PID" # kill -2 is SIGINT, triggers the signal handler in main.py
    
    # Wait up to 5 seconds for the process to terminate gracefully
    for i in {1..5}; do
        if ! ps -p "$PID" > /dev/null; then
            echo "Virtual Office stopped successfully. See you mate!"
            exit 0
        fi
        echo "Waiting for process to exit ($i/5)..."
        sleep 1
    done
    
    echo "Process did not exit. Sending SIGKILL to force quit..."
    kill -9 "$PID"
    echo "Virtual Office force quit."
else
    echo "Virtual Office is not currently running."
fi
