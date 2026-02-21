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
from src.builders.blender.geom_utils import primitives_union_bbox


CASES = [
    {
        "path": "data/examples/sofa_ir.json",
        "rail_names": ["rail_left", "rail_right"],
        "slat_names": [
            "slat_1",
            "slat_2",
            "slat_3",
            "slat_4",
            "slat_5",
            "slat_6",
            "slat_7",
            "slat_8",
            "slat_9",
            "slat_10",
            "slat_11",
            "slat_12",
            "slat_13",
            "slat_14",
            "slat_15",
            "slat_16",
        ],
        "rail_count": 2,
        "slat_count": 16,
        "non_slat_rail_count": 34,
        "rail_bbox_min": (-857.0, -242.0, 381.0),
        "rail_bbox_max": (857.0, 242.0, 411.0),
        "slat_bbox_min": (-860.0, -205.0, 418.0),
        "slat_bbox_max": (860.0, 205.0, 430.0),
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json",
        "rail_names": ["rail_left", "rail_right"],
        "slat_names": [
            "slat_1",
            "slat_2",
            "slat_3",
            "slat_4",
            "slat_5",
            "slat_6",
            "slat_7",
            "slat_8",
            "slat_9",
            "slat_10",
            "slat_11",
            "slat_12",
            "slat_13",
            "slat_14",
            "slat_15",
            "slat_16",
        ],
        "rail_count": 2,
        "slat_count": 16,
        "non_slat_rail_count": 34,
        "rail_bbox_min": (-857.0, -242.0, 381.0),
        "rail_bbox_max": (857.0, 242.0, 411.0),
        "slat_bbox_min": (-860.0, -205.0, 418.0),
        "slat_bbox_max": (860.0, 205.0, 430.0),
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v04.json",
        "rail_names": ["rail_left", "rail_right"],
        "slat_names": [
            "slat_1",
            "slat_2",
            "slat_3",
            "slat_4",
            "slat_5",
            "slat_6",
            "slat_7",
            "slat_8",
            "slat_9",
            "slat_10",
            "slat_11",
            "slat_12",
            "slat_13",
            "slat_14",
            "slat_15",
            "slat_16",
        ],
        "rail_count": 2,
        "slat_count": 16,
        "non_slat_rail_count": 34,
        "rail_bbox_min": (-857.0, -242.0, 381.0),
        "rail_bbox_max": (857.0, 242.0, 411.0),
        "slat_bbox_min": (-860.0, -205.0, 418.0),
        "slat_bbox_max": (860.0, 205.0, 430.0),
    },
]


def _build_plan_silent(ir: dict):
    with redirect_stdout(io.StringIO()):
        return build_plan_from_ir(ir)


def _assert_close_tuple(actual, expected, eps=2.0):
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert abs(float(actual_value) - float(expected_value)) <= eps


def test_seat_slats_regression():
    for case in CASES:
        ir = json.loads(Path(case["path"]).read_text(encoding="utf-8"))
        plan = _build_plan_silent(ir)
        rail_primitives = [p for p in plan.primitives if p.name.startswith("rail_")]
        slat_primitives = [p for p in plan.primitives if p.name.startswith("slat_")]
        non_target_primitives = [
            p for p in plan.primitives if not (p.name.startswith("rail_") or p.name.startswith("slat_"))
        ]

        assert [p.name for p in rail_primitives] == case["rail_names"]
        assert [p.name for p in slat_primitives] == case["slat_names"]

        assert len(rail_primitives) == case["rail_count"]
        assert len(slat_primitives) == case["slat_count"]
        assert len(non_target_primitives) == case["non_slat_rail_count"]

        rail_bbox = primitives_union_bbox(rail_primitives)
        slat_bbox = primitives_union_bbox(slat_primitives)

        _assert_close_tuple(rail_bbox["min"], case["rail_bbox_min"])
        _assert_close_tuple(rail_bbox["max"], case["rail_bbox_max"])
        _assert_close_tuple(slat_bbox["min"], case["slat_bbox_min"])
        _assert_close_tuple(slat_bbox["max"], case["slat_bbox_max"])
