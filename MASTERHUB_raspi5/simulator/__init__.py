"""
simulator
---------
Phase 1 Emotiv Cortex integration for MasterHub.

This package does NOT talk to a real Emotiv headset. It replays a
recorded prediction JSON file (emotiv_bci_predictions.json) through the
exact same pipeline a future live Cortex WebSocket stream will use:

    JSON Prediction File
            |
            v
    Prediction Reader   (simulator/prediction_reader.py)
            |
            v
    Confidence Filter    (simulator/confidence_filter.py)
            |
            v
    Gesture Stabilizer   (simulator/stabilizer.py)
            |
            v
    API Sender           (simulator/sender.py)
            |
            v
    POST /api/command
            |
            v
    MasterHub (core/engine.py -> router -> domain handlers)

MasterHub itself (Flask API, InputProcessor, Router, StateManager,
domain handlers, mappings/*.json) is never imported or modified by this
package. All communication happens over HTTP, exactly like a real
external Cortex client would.

When the real Emotiv Cortex SDK is wired up, only prediction_reader.py
needs to be replaced with a WebSocket client that yields the same
Prediction objects -- everything downstream (filter, stabilizer,
sender, replay loop, logging) stays untouched.
"""

__version__ = "1.0.0"
