"""
cortex
------
Standalone Emotiv Cortex API integration module for MasterHub.

This package connects to a real Emotiv EPOC X headset via the local
Cortex WebSocket service and produces live mental-command predictions
in the same normalized format already used elsewhere in this project
(emotiv_bci_predictions.json / simulator/prediction_reader.py):

    {"command": "push", "confidence": 0.94, "timestamp": "2026-08-03T12:45:10"}

It does NOT call MasterHub's Flask API, FSM, Router, or domain
handlers directly, and it does NOT modify any existing MasterHub
component. It only produces predictions -- wiring those predictions
into MasterHub (e.g. via the existing simulator/sender.py) is a
separate integration step outside this module.

Quick start:
    python -m cortex.run_live

See README.md for full setup instructions (Cortex credentials,
pairing the EPOC X, starting the Cortex service, troubleshooting).
"""

__version__ = "1.0.0"
