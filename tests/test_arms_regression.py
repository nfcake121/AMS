from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.builder_v01 import build_plan_from_ir


CASES = [
    {
        "path": "data/examples/sofa_ir.json",
        "count": 10,
        "bbox_min": (-1018.0, -249.0, 411.0),
        "bbox_max": (1018.0, 234.0, 613.0),
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json",
        "count": 10,
        "bbox_min": (-1018.0, -249.0, 411.0),
        "bbox_max": (1018.0, 234.0, 613.0),
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v04.json",
        "count": 10,
        "bbox_min": (-1018.0, -248.5, 411.0),
        "bbox_max": (1018.0, 233.5, 620.0),
    },
]


def _arm_primitives(plan):
    return [primitive for primitive in plan.primitives if primitive.name.startswith("arm_")]


def _bbox(primitives):
    min_x = min(p.location_mm[0] - (p.dimensions_mm[0] / 2.0) for p in primitives)
    min_y = min(p.location_mm[1] - (p.dimensions_mm[1] / 2.0) for p in primitives)
    min_z = min(p.location_mm[2] - (p.dimensions_mm[2] / 2.0) for p in primitives)
    max_x = max(p.location_mm[0] + (p.dimensions_mm[0] / 2.0) for p in primitives)
    max_y = max(p.location_mm[1] + (p.dimensions_mm[1] / 2.0) for p in primitives)
    max_z = max(p.location_mm[2] + (p.dimensions_mm[2] / 2.0) for p in primitives)
    return (min_x, min_y, min_z), (max_x, max_y, max_z)


def _assert_close_tuple(actual, expected, eps=1e-6):
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert abs(float(actual_value) - float(expected_value)) <= eps


def test_arms_regression_counts_and_bbox():
    for case in CASES:
        ir = json.loads(Path(case["path"]).read_text(encoding="utf-8"))
        plan = build_plan_from_ir(ir)
        arm_primitives = _arm_primitives(plan)

        assert len(arm_primitives) == case["count"]
        bbox_min, bbox_max = _bbox(arm_primitives)
        _assert_close_tuple(bbox_min, case["bbox_min"])
        _assert_close_tuple(bbox_max, case["bbox_max"])
