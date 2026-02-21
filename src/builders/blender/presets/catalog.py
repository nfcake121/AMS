"""Style preset catalog for Blender builder resolver.

Merge precedence (low -> high):
1) global defaults
2) style base overrides
3) preset overrides
4) optional preset variant overrides

Resolver IR values remain the highest-precedence layer and are applied later.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

PresetDict = dict[str, Any]


@dataclass(frozen=True)
class PresetDefinition:
    base: Mapping[str, Any] = field(default_factory=dict)
    variants: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class StyleDefinition:
    default_preset_id: str = "default"
    base: Mapping[str, Any] = field(default_factory=dict)
    presets: Mapping[str, PresetDefinition] = field(default_factory=dict)


@dataclass(frozen=True)
class PresetLayer:
    layer_id: str
    values: Mapping[str, Any]


_GLOBAL_DEFAULTS: PresetDict = {
    "arms": {
        "width_mm": 120.0,
        "profile": "box",
    },
    "legs": {
        "family": "block",
        "height_mm": 160.0,
        "params": {},
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

_STYLE_DEFINITIONS: dict[str, StyleDefinition] = {
    "scandi": StyleDefinition(
        default_preset_id="scandi_straight_v1",
        presets={
            "scandi_straight_v1": PresetDefinition(
                base={
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
            )
        },
    ),
}


def _deep_merge(base: Mapping[str, Any], patch: Mapping[str, Any]) -> PresetDict:
    merged: PresetDict = deepcopy(dict(base))
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _normalize_style(style: str) -> str:
    normalized_style = str(style or "").strip().lower()
    return normalized_style or "default"


def _normalize_preset_id(style: str, preset_id: str | None) -> str:
    normalized = str(preset_id or "").strip()
    if normalized:
        return normalized
    return default_preset_id(style)


def default_preset_id(style: str) -> str:
    normalized_style = _normalize_style(style)
    style_definition = _STYLE_DEFINITIONS.get(normalized_style)
    if style_definition is None:
        return "default"
    default_id = str(style_definition.default_preset_id or "").strip()
    return default_id or "default"


def get_preset_layers(
    style: str,
    preset_id: str | None,
    variant_id: str | None = None,
) -> tuple[PresetLayer, ...]:
    normalized_style = _normalize_style(style)
    normalized_preset_id = _normalize_preset_id(normalized_style, preset_id)
    normalized_variant_id = str(variant_id or "").strip()

    layers: list[PresetLayer] = [PresetLayer(layer_id="global", values=_GLOBAL_DEFAULTS)]

    style_definition = _STYLE_DEFINITIONS.get(normalized_style)
    if style_definition is None:
        return tuple(layers)

    if style_definition.base:
        layers.append(PresetLayer(layer_id=f"style:{normalized_style}", values=style_definition.base))

    selected_preset_id = normalized_preset_id
    selected_preset = style_definition.presets.get(selected_preset_id)
    if selected_preset is None and normalized_preset_id != "default":
        selected_preset_id = default_preset_id(normalized_style)
        selected_preset = style_definition.presets.get(selected_preset_id)

    if selected_preset is None:
        return tuple(layers)

    if selected_preset.base:
        layers.append(PresetLayer(layer_id=f"preset:{selected_preset_id}", values=selected_preset.base))

    if normalized_variant_id:
        variant_patch = selected_preset.variants.get(normalized_variant_id)
        if variant_patch:
            layers.append(
                PresetLayer(
                    layer_id=f"variant:{selected_preset_id}:{normalized_variant_id}",
                    values=variant_patch,
                )
            )

    return tuple(layers)


def get_preset(style: str, preset_id: str | None, variant_id: str | None = None) -> PresetDict:
    """Return merged preset defaults for style/preset_id."""
    layers = get_preset_layers(style=style, preset_id=preset_id, variant_id=variant_id)
    merged: PresetDict = {}
    for layer in layers:
        merged = _deep_merge(merged, layer.values)
    return merged
