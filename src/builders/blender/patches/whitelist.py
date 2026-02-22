"""Whitelisted IR patch paths and constraints.

This module intentionally contains only data.
"""

from __future__ import annotations

from typing import Any


PATCH_PATH_RULES: dict[str, dict[str, Any]] = {
    # arms.*
    "arms.type": {"type": "enum", "allowed": ["none", "left", "right", "both"]},
    "arms.width_mm": {"type": "number", "min": 0.0, "max": 600.0},
    "arms.profile": {"type": "enum", "allowed": ["box", "frame_box_open", "scandi_frame"]},
    "arms.style": {"type": "string"},
    "arms.height_mm": {"type": "number", "min": 80.0, "max": 1400.0},
    "arms.length_y_mode": {"type": "enum", "allowed": ["match_seat", "custom"]},
    "arms.length_y_mm": {"type": "number", "min": 80.0, "max": 3000.0},
    "arms.inset_y_front_mm": {"type": "number", "min": 0.0, "max": 500.0},
    "arms.inset_y_back_mm": {"type": "number", "min": 0.0, "max": 500.0},
    "arms.frame_thickness_mm": {"type": "number", "min": 8.0, "max": 120.0},
    "arms.post_thickness_mm": {"type": "number", "min": 8.0, "max": 120.0},
    "arms.clearance_to_seat_mm": {"type": "number", "min": 0.0, "max": 100.0},
    "arms.thickness_mm": {"type": "number", "min": 8.0, "max": 120.0},
    "arms.inner_clearance_mm": {"type": "number", "min": 0.0, "max": 120.0},
    "arms.cap_overhang_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "arms.outer_rail_width_mm": {"type": "number", "min": 0.0, "max": 200.0},
    # legs.*
    "legs.family": {"type": "enum", "allowed": ["block", "tapered_cone", "cylindrical"]},
    "legs.height_mm": {"type": "number", "min": 0.0, "max": 500.0},
    "legs.enabled": {"type": "bool"},
    "legs.params.*": {"type": "number", "min": -2000.0, "max": 2000.0},
    # frame.*
    "frame.thickness_mm": {"type": "number", "min": 1.0, "max": 200.0},
    "frame.back_thickness_mm": {"type": "number", "min": 1.0, "max": 600.0},
    "frame.back_height_above_seat_mm": {"type": "number", "min": 1.0, "max": 2000.0},
    # slats.*
    "slats.count": {"type": "integer", "min": 1, "max": 256},
    "slats.width_mm": {"type": "number", "min": 1.0, "max": 500.0},
    "slats.thickness_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "slats.arc_height_mm": {"type": "number", "min": 0.0, "max": 500.0},
    "slats.arc_sign": {"type": "number", "min": -1.0, "max": 1.0},
    "slats.margin_x_mm": {"type": "number", "min": 0.0, "max": 600.0},
    "slats.margin_y_mm": {"type": "number", "min": 0.0, "max": 600.0},
    "slats.clearance_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "slats.mount_offset_mm": {"type": "number", "min": -200.0, "max": 200.0},
    "slats.rail_inset_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "slats.rail_inset_y_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "slats.rail_height_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "slats.rail_width_mm": {"type": "number", "min": 0.0, "max": 200.0},
    # back_support.*
    "back_support.mode": {"type": "enum", "allowed": ["panel", "slats", "straps"]},
    "back_support.height_above_seat_mm": {"type": "number", "min": 0.0, "max": 2000.0},
    "back_support.thickness_mm": {"type": "number", "min": 0.0, "max": 600.0},
    "back_support.offset_y_mm": {"type": "number", "min": -300.0, "max": 400.0},
    "back_support.margin_x_mm": {"type": "number", "min": 0.0, "max": 600.0},
    "back_support.margin_z_mm": {"type": "number", "min": 0.0, "max": 600.0},
    "back_support.split_center": {"type": "bool"},
    "back_support.frame_layout": {"type": "enum", "allowed": ["single", "split_2", "full"]},
    "back_support.rail_inset_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "back_support.rail_width_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "back_support.rail_depth_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "back_support.rail_height_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "back_support.bottom_rail_height_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "back_support.bottom_rail_gap_mm": {"type": "number", "min": 0.0, "max": 400.0},
    "back_support.bottom_rail_split": {"type": "bool"},
    "back_support.center_post.enabled": {"type": "bool"},
    "back_support.center_post.thickness_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "back_support.center_post.inset_y_mm": {"type": "number", "min": -200.0, "max": 200.0},
    "back_support.center_post_width_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "back_support.slats.orientation": {"type": "enum", "allowed": ["vertical", "horizontal"]},
    "back_support.slats.layout": {"type": "enum", "allowed": ["full", "split_center"]},
    "back_support.slats.count": {"type": "integer", "min": 0, "max": 256},
    "back_support.slats.width_mm": {"type": "number", "min": 0.0, "max": 400.0},
    "back_support.slats.thickness_mm": {"type": "number", "min": 0.0, "max": 200.0},
    "back_support.slats.gap_mm": {"type": "number", "min": 0.0, "max": 400.0},
    "back_support.slats.center_gap_mm": {"type": "number", "min": 0.0, "max": 400.0},
    "back_support.slats.arc_height_mm": {"type": "number", "min": 0.0, "max": 400.0},
    "back_support.slats.arc_sign": {"type": "number", "min": -1.0, "max": 1.0},
}

# Intermediate object paths that can be created during apply for known branches.
KNOWN_OBJECT_PATHS = {
    "arms",
    "legs",
    "legs.params",
    "frame",
    "slats",
    "back_support",
    "back_support.center_post",
    "back_support.slats",
}
