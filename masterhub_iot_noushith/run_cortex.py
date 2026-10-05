"""
run_cortex.py
-------------
Standalone entry point to run the Emotiv Cortex BCI live streaming service
independently from MasterHub.

Usage:
    python run_cortex.py

Prerequisites:
    1. EMOTIV Launcher running on this machine (listening on wss://localhost:6868).
    2. This standalone process monitors only. To control domains, start app.py
       and use its /cortex/ Connect button so the worker shares the app FSM.
    3. CORTEX_CLIENT_ID and CORTEX_CLIENT_SECRET configured in .env or environment.
"""

import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cortex.run_live import main
from cortex.logger import get_logger

log = get_logger("cortex_launcher")

if __name__ == "__main__":
    print("=" * 60)
    print("  MasterHub — Emotiv Cortex BCI Standalone Service")
    print("  Connecting to wss://localhost:6868 ...")
    print("  Press Ctrl+C at any time to disconnect and exit.")
    print("=" * 60)
    
    sys.exit(main())
