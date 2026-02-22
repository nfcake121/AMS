from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.naming import PREFIXES, arm_name, leg_name, leg_point_name, slat_name


def _load_snapshot(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_naming_policy_contains_required_prefixes() -> None:
    required = {
        "arm_",
        "arm_main_left_",
        "arm_main_right_",
        "arm_chaise_free_end_",
        "back_",
        "back_main_",
        "back_chaise_",
        "back_rail_",
        "back_slat_",
        "beam_",
        "beam_chaise_",
        "beam_cross_chaise_",
        "leg_",
        "leg_chaise_",
        "leg_point_",
        "rail_",
        "rail_chaise_",
        "slat_",
        "slat_chaise_",
    }
    assert required.issubset(set(PREFIXES.values()))
    assert arm_name("left", "cap") == "arm_left_cap"
    assert slat_name(3) == "slat_3"
    assert leg_name(4) == "leg_4"
    assert leg_point_name(2) == "leg_point_2"


def test_golden_snapshots_keep_expected_name_prefixes() -> None:
    snapshots = [
        _load_snapshot("tests/golden/sofa_ir.plan.json"),
        _load_snapshot("tests/golden/sofa_ir_scandi_back_split2_hslats_v03_armframe.plan.json"),
    ]
    guard_prefixes = ["arm_", "back_", "back_rail_", "back_slat_", "beam_", "leg_", "rail_", "slat_"]
    for snapshot in snapshots:
        primitive_names = [item["name"] for item in snapshot["primitives"]]
        for prefix in guard_prefixes:
            assert any(name.startswith(prefix) for name in primitive_names), prefix
        anchor_names = [item["name"] for item in snapshot["anchors"]]
        assert any(name.startswith("leg_point_") for name in anchor_names)
