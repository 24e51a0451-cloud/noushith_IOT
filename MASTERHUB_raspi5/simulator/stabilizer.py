"""
simulator/stabilizer.py
-------------------------
Compatibility wrapper around the shared prediction pipeline package.
"""

from __future__ import annotations

from prediction_pipeline import GestureStabilizer, StabilizerResult

__all__ = ["GestureStabilizer", "StabilizerResult"]
