"""
simulator/confidence_filter.py
--------------------------------
Compatibility wrapper around the shared prediction pipeline package.
"""

from __future__ import annotations

from prediction_pipeline import ConfidenceFilter, FilterResult

__all__ = ["ConfidenceFilter", "FilterResult"]
