from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.builder_v01 import build_plan_from_ir


CASES = [
    {
        "path": "data/examples/sofa_ir.json",
        "back_count": 13,
        "rail_count": 5,
        "slat_count": 8,
        "bbox": (-900.0, -282.0, 411.0, 900.0, -248.0, 925.0),
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json",
        "back_count": 13,
        "rail_count": 5,
        "slat_count": 8,
        "bbox": (-900.0, -282.0, 411.0, 900.0, -248.0, 925.0),
    },
]


def _build_plan_silent(ir: dict):
    with redirect_stdout(io.StringIO()):
        return build_plan_from_ir(ir)


def _back_primitives(plan):
    return [primitive for primitive in plan.primitives if primitive.name.startswith("back_")]


def _bbox(primitives):
    min_x = min(p.location_mm[0] - (p.dimensions_mm[0] / 2.0) for p in primitives)
    min_y = min(p.location_mm[1] - (p.dimensions_mm[1] / 2.0) for p in primitives)
    min_z = min(p.location_mm[2] - (p.dimensions_mm[2] / 2.0) for p in primitives)
    max_x = max(p.location_mm[0] + (p.dimensions_mm[0] / 2.0) for p in primitives)
    max_y = max(p.location_mm[1] + (p.dimensions_mm[1] / 2.0) for p in primitives)
    max_z = max(p.location_mm[2] + (p.dimensions_mm[2] / 2.0) for p in primitives)
    return (min_x, min_y, min_z, max_x, max_y, max_z)


def _assert_close_tuple(actual, expected, eps=1e-6):
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert abs(float(actual_value) - float(expected_value)) <= eps


def test_back_horizontal_split_regression():
    for case in CASES:
        ir = json.loads(Path(case["path"]).read_text(encoding="utf-8"))
        plan = _build_plan_silent(ir)

        back_primitives = _back_primitives(plan)
        rails = [p for p in back_primitives if p.name.startswith("back_rail_")]
        slats = [p for p in back_primitives if p.name.startswith("back_slat_")]

        assert len(back_primitives) == case["back_count"]
        assert len(rails) == case["rail_count"]
        assert len(slats) == case["slat_count"]
        assert any(p.name == "back_rail_center" for p in rails)

        split_slats = [p for p in slats if "_left_" in p.name or "_right_" in p.name]
        assert len(split_slats) > 0
        for slat in split_slats:
            min_x = slat.location_mm[0] - (slat.dimensions_mm[0] / 2.0)
            max_x = slat.location_mm[0] + (slat.dimensions_mm[0] / 2.0)
            assert max_x <= 0.0 or min_x >= 0.0

        bbox = _bbox(back_primitives)
        _assert_close_tuple(bbox, case["bbox"])


def test_back_vertical_slats_variant():
    ir = json.loads(Path("data/examples/sofa_ir.json").read_text(encoding="utf-8"))
    back_support = ir.setdefault("back_support", {})
    slats = back_support.setdefault("slats", {})
    slats["orientation"] = "vertical"
    slats["layout"] = "full"

    plan = _build_plan_silent(ir)
    back_primitives = _back_primitives(plan)
    rails = [p for p in back_primitives if p.name.startswith("back_rail_")]
    slats = [p for p in back_primitives if p.name.startswith("back_slat_")]

    assert len(back_primitives) == 12
    assert len(rails) == 5
    assert len(slats) == 7
    assert all(p.shape == "slat" for p in slats)
    assert all("_left_" not in p.name and "_right_" not in p.name for p in slats)
    assert any(p.name == "back_rail_center" for p in rails)

    bbox = _bbox(back_primitives)
    _assert_close_tuple(bbox, (-900.0, -282.0, 411.0, 900.0, -248.0, 925.0))
