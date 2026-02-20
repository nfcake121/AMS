"""Compatibility layer for preset catalog access from spec package."""

from __future__ import annotations

from src.builders.blender.presets.catalog import default_preset_id, get_preset

__all__ = [
    "default_preset_id",
    "get_preset",
]
