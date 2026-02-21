from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.layout import compute_layout
from src.builders.blender.spec.resolve import resolve


CASES = [
    {
        "path": "data/examples/sofa_ir.json",
        "seat_top_z": 445.0,
        "seat_min_x": -900.0,
        "seat_max_x": 900.0,
        "seat_min_y": -260.0,
        "seat_max_y": 260.0,
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json",
        "seat_top_z": 445.0,
        "seat_min_x": -900.0,
        "seat_max_x": 900.0,
        "seat_min_y": -260.0,
        "seat_max_y": 260.0,
    },
    {
        "path": "data/examples/sofa_ir_scandi_back_split2_hslats_v04.json",
        "seat_top_z": 445.0,
        "seat_min_x": -900.0,
        "seat_max_x": 900.0,
        "seat_min_y": -260.0,
        "seat_max_y": 260.0,
    },
]


def _assert_close(actual: float, expected: float, eps: float = 1e-6) -> None:
    assert abs(float(actual) - float(expected)) <= eps


def test_compute_layout_regression():
    for case in CASES:
        ir = json.loads(Path(case["path"]).read_text(encoding="utf-8"))
        spec, _diagnostics = resolve(ir, preset_id=ir.get("preset_id"))
        layout = compute_layout(ir, spec)

        _assert_close(layout.seat_top_z, case["seat_top_z"])
        _assert_close(layout.seat_min_x, case["seat_min_x"])
        _assert_close(layout.seat_max_x, case["seat_max_x"])
        _assert_close(layout.seat_min_y, case["seat_min_y"])
        _assert_close(layout.seat_max_y, case["seat_max_y"])
