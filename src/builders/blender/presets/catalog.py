"""Style preset catalog for Blender builder resolver."""

from __future__ import annotations

from copy import deepcopy


_GLOBAL_DEFAULTS = {
    "arms": {
        "width_mm": 120.0,
        "profile": "box",
    },
    "back": {
        "mode": "panel",
        "frame": {
            "offset_y_mm": 0.0,
            "margin_x_mm": 40.0,
            "margin_z_mm": 30.0,
            "rail_inset_mm": 0.0,
            "rail_width_mm": 35.0,
            "rail_depth_mm": 35.0,
            "rail_height_mm": 35.0,
            "bottom_rail_split": False,
            "bottom_rail_gap_mm": 60.0,
            "split_center": False,
            "frame_layout": "single",
            "bottom_rail_attach_mode": "seat_rear_beam",
            "bottom_rail_height_mm": 18.0,
            "center_post_width_mm": None,
            "center_post": {
                "enabled": False,
                "thickness_mm": 35.0,
                "inset_y_mm": 0.0,
            },
        },
        "slats": {
            "orientation": "vertical",
            "layout": "full",
            "count": 10,
            "width_mm": 35.0,
            "thickness_mm": 10.0,
            "arc_height_mm": 0.0,
            "arc_sign": -1.0,
            "gap_mm": 0.0,
            "center_gap_mm": 0.0,
        },
        "straps": {
            "count": 6,
            "width_mm": 30.0,
            "thickness_mm": 6.0,
        },
    },
}

_STYLE_PRESETS = {
    "scandi": {
        "scandi_straight_v1": {
            "back": {
                "mode": "slats",
                "frame": {
                    "frame_layout": "split_2",
                    "split_center": True,
                },
                "slats": {
                    "orientation": "horizontal",
                    "layout": "split_center",
                },
            }
        }
    }
}

_DEFAULT_PRESET_BY_STYLE = {
    "scandi": "scandi_straight_v1",
}


def _deep_merge(base: dict, patch: dict) -> dict:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def default_preset_id(style: str) -> str:
    normalized_style = str(style or "").strip().lower() or "default"
    return _DEFAULT_PRESET_BY_STYLE.get(normalized_style, "default")


def get_preset(style: str, preset_id: str) -> dict:
    """Return merged preset defaults for style/preset_id."""
    normalized_style = str(style or "").strip().lower() or "default"
    normalized_preset_id = str(preset_id or "").strip() or default_preset_id(normalized_style)

    merged = deepcopy(_GLOBAL_DEFAULTS)

    style_catalog = _STYLE_PRESETS.get(normalized_style, {})
    preset = style_catalog.get(normalized_preset_id)
    if preset is None and normalized_preset_id != "default":
        preset = style_catalog.get(default_preset_id(normalized_style))
    if preset is None:
        preset = {}

    merged = _deep_merge(merged, preset)

    return merged
