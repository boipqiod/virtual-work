"""
Virtual Office — Main Entry Point
A slow, realistic remote team simulation for English practice and dev learning.
"""

import os
import time
import signal
import sys

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv()

from agents.orchestrator import Orchestrator


# Global shutdown flag
_shutting_down = False


def main():
    global _shutting_down
    office = Orchestrator()
    
    def shutdown(sig, frame):
        global _shutting_down
        if _shutting_down:
            # Second signal = force quit
            print("\nForce quit.")
            os._exit(1)
        _shutting_down = True
        print("\nShutting down gracefully... (press again to force)")
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    print("=" * 50)
    print("Virtual Office started.")
    print("Agents: Liam (PM), Aiden (Tech Lead), Sarah (CEO), Chloe (Sales)")
    print("Press Ctrl+C to stop.")
    print("=" * 50)
    
    while not _shutting_down:
        office.tick()
        # Sleep in 1-second intervals so we respond to Ctrl+C quickly
        loop_interval = int(os.environ.get("LOOP_INTERVAL", "30"))
        for _ in range(loop_interval):
            if _shutting_down:
                break
            time.sleep(1)
    
    print("Virtual Office stopped. See you mate.")


if __name__ == "__main__":
    main()
