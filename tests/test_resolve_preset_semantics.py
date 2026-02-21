from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.presets.catalog import get_preset
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
