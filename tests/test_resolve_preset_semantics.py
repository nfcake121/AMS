from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.presets.catalog import get_preset, get_preset_layers
from src.builders.blender.spec.resolve import resolve


def test_scandi_preset_does_not_force_arms_type():
    preset = get_preset("scandi", "scandi_straight_v1")
    arms_preset = preset.get("arms", {})
    assert "type" not in arms_preset


def test_resolve_defaults_arms_type_when_unspecified():
    resolved, diagnostics = resolve({"style": "scandi"})
    assert resolved.arms.type == "none"
    assert diagnostics is not None


def test_resolve_respects_explicit_ir_arms_type():
    resolved, _ = resolve(
        {
            "style": "scandi",
            "arms": {
                "type": "both",
            },
        }
    )
    assert resolved.arms.type == "both"


def test_scandi_unknown_preset_falls_back_to_style_default():
    fallback_preset = get_preset("scandi", "unknown_preset")
    default_preset = get_preset("scandi", "scandi_straight_v1")
    assert fallback_preset == default_preset


def test_scandi_explicit_default_uses_global_defaults_only():
    preset = get_preset("scandi", "default")
    assert preset["back"]["mode"] == "panel"
    assert preset["back"]["slats"]["orientation"] == "vertical"
    assert preset["back"]["slats"]["layout"] == "full"


def test_preset_layers_are_stable_for_scandi_default():
    layer_ids = [layer.layer_id for layer in get_preset_layers("scandi", "scandi_straight_v1")]
    assert layer_ids == ["global", "preset:scandi_straight_v1"]


def test_unknown_variant_id_is_noop():
    baseline = get_preset("scandi", "scandi_straight_v1")
    with_unknown_variant = get_preset("scandi", "scandi_straight_v1", variant_id="missing_variant")
    assert with_unknown_variant == baseline


def test_modern_style_default_preset_is_available():
    preset = get_preset("modern", "")
    assert preset["arms"]["profile"] == "box"
    assert preset["back"]["mode"] == "panel"
