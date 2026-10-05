"""
simulator/sender.py
---------------------
Compatibility wrapper around the shared prediction pipeline package.
"""

from __future__ import annotations

from prediction_pipeline import CommandSender, SendResult

__all__ = ["CommandSender", "SendResult"]
