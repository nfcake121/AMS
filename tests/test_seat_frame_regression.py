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
        "names": [
            "beam_front",
            "beam_back",
            "beam_left",
            "beam_right",
            "beam_cross_1",
            "beam_cross_2",
            "beam_cross_3",
        ],
        "count": 7,
        "non_seat_count": 45,
        "bbox_min": (-1010.0, -260.0, 377.0),
        "bbox_max": (1010.0, 260.0, 411.0),
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json",
        "names": [
            "beam_front",
            "beam_back",
            "beam_left",
            "beam_right",
            "beam_cross_1",
            "beam_cross_2",
            "beam_cross_3",
        ],
        "count": 7,
        "non_seat_count": 45,
        "bbox_min": (-1010.0, -260.0, 377.0),
        "bbox_max": (1010.0, 260.0, 411.0),
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v04.json",
        "names": [
            "beam_front",
            "beam_back",
            "beam_left",
            "beam_right",
            "beam_cross_1",
            "beam_cross_2",
            "beam_cross_3",
        ],
        "count": 7,
        "non_seat_count": 45,
        "bbox_min": (-1010.0, -260.0, 377.0),
        "bbox_max": (1010.0, 260.0, 411.0),
    },
]


def _build_plan_silent(ir: dict):
    with redirect_stdout(io.StringIO()):
        return build_plan_from_ir(ir)


def _seat_frame_primitives(plan):
    return [p for p in plan.primitives if p.name.startswith("beam_") or p.name == "seat_support"]


def _assert_close_tuple(actual, expected, eps=2.0):
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert abs(float(actual_value) - float(expected_value)) <= eps


def test_seat_frame_regression():
    for case in CASES:
        ir = json.loads(Path(case["path"]).read_text(encoding="utf-8"))
        plan = _build_plan_silent(ir)

        seat_primitives = _seat_frame_primitives(plan)
        non_seat_primitives = [
            p for p in plan.primitives if not (p.name.startswith("beam_") or p.name == "seat_support")
        ]

        assert [p.name for p in seat_primitives] == case["names"]
        assert len(seat_primitives) == case["count"]
        assert len(non_seat_primitives) == case["non_seat_count"]

        bbox = primitives_union_bbox(seat_primitives)
        _assert_close_tuple(bbox["min"], case["bbox_min"])
        _assert_close_tuple(bbox["max"], case["bbox_max"])
