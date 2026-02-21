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
        "leg_names": ["leg_1", "leg_2", "leg_3", "leg_4"],
        "anchor_names": ["leg_point_1", "leg_point_2", "leg_point_3", "leg_point_4"],
        "leg_dimensions_mm": [
            (34.0, 34.0, 150.0),
            (34.0, 34.0, 150.0),
            (34.0, 34.0, 150.0),
            (34.0, 34.0, 150.0),
        ],
        "leg_locations_mm": [
            (-993.0, -243.0, 302.0),
            (993.0, -243.0, 302.0),
            (-993.0, 243.0, 302.0),
            (993.0, 243.0, 302.0),
        ],
        "leg_count": 4,
        "anchor_count": 4,
        "non_leg_count": 48,
        "bbox_min": (-1010.0, -260.0, 227.0),
        "bbox_max": (1010.0, 260.0, 377.0),
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json",
        "leg_names": ["leg_1", "leg_2", "leg_3", "leg_4"],
        "anchor_names": ["leg_point_1", "leg_point_2", "leg_point_3", "leg_point_4"],
        "leg_dimensions_mm": [
            (34.0, 34.0, 150.0),
            (34.0, 34.0, 150.0),
            (34.0, 34.0, 150.0),
            (34.0, 34.0, 150.0),
        ],
        "leg_locations_mm": [
            (-993.0, -243.0, 302.0),
            (993.0, -243.0, 302.0),
            (-993.0, 243.0, 302.0),
            (993.0, 243.0, 302.0),
        ],
        "leg_count": 4,
        "anchor_count": 4,
        "non_leg_count": 48,
        "bbox_min": (-1010.0, -260.0, 227.0),
        "bbox_max": (1010.0, 260.0, 377.0),
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v04.json",
        "leg_names": ["leg_1", "leg_2", "leg_3", "leg_4"],
        "anchor_names": ["leg_point_1", "leg_point_2", "leg_point_3", "leg_point_4"],
        "leg_dimensions_mm": [
            (34.0, 34.0, 150.0),
            (34.0, 34.0, 150.0),
            (34.0, 34.0, 150.0),
            (34.0, 34.0, 150.0),
        ],
        "leg_locations_mm": [
            (-993.0, -243.0, 302.0),
            (993.0, -243.0, 302.0),
            (-993.0, 243.0, 302.0),
            (993.0, 243.0, 302.0),
        ],
        "leg_count": 4,
        "anchor_count": 4,
        "non_leg_count": 48,
        "bbox_min": (-1010.0, -260.0, 227.0),
        "bbox_max": (1010.0, 260.0, 377.0),
    },
]


def _build_plan_silent(ir: dict):
    with redirect_stdout(io.StringIO()):
        return build_plan_from_ir(ir)


def _assert_close_tuple(actual, expected, eps=2.0):
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        assert abs(float(actual_value) - float(expected_value)) <= eps


def test_legs_regression_counts_names_and_bbox():
    for case in CASES:
        ir = json.loads(Path(case["path"]).read_text(encoding="utf-8"))
        plan = _build_plan_silent(ir)
        leg_primitives = [primitive for primitive in plan.primitives if primitive.name.startswith("leg_")]
        leg_anchors = [anchor for anchor in plan.anchors if anchor.name.startswith("leg_point_")]
        non_leg_primitives = [primitive for primitive in plan.primitives if not primitive.name.startswith("leg_")]

        assert [primitive.name for primitive in leg_primitives] == case["leg_names"]
        assert [anchor.name for anchor in leg_anchors] == case["anchor_names"]
        assert len(leg_primitives) == case["leg_count"]
        assert len(leg_anchors) == case["anchor_count"]
        assert len(non_leg_primitives) == case["non_leg_count"]
        for actual, expected in zip(
            [primitive.dimensions_mm for primitive in leg_primitives],
            case["leg_dimensions_mm"],
        ):
            _assert_close_tuple(actual, expected, eps=0.001)
        for actual, expected in zip(
            [primitive.location_mm for primitive in leg_primitives],
            case["leg_locations_mm"],
        ):
            _assert_close_tuple(actual, expected, eps=0.001)
        for actual, expected in zip(
            [anchor.location_mm for anchor in leg_anchors],
            case["leg_locations_mm"],
        ):
            _assert_close_tuple(actual, expected, eps=0.001)

        bbox = primitives_union_bbox(leg_primitives)
        _assert_close_tuple(bbox["min"], case["bbox_min"])
        _assert_close_tuple(bbox["max"], case["bbox_max"])
