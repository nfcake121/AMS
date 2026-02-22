from __future__ import annotations

import io
import json
import math
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.builder_v01 import build_plan_from_ir


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


def _load_ir(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _assert_positive_finite_dims(plan) -> None:
    for primitive in plan.primitives:
        assert all(math.isfinite(float(v)) for v in primitive.dimensions_mm)
        assert all(float(v) > 0.0 for v in primitive.dimensions_mm)
        assert all(math.isfinite(float(v)) for v in primitive.location_mm)


def test_corner_arms_back_smoke(monkeypatch) -> None:
    import src.builders.blender.builder_v01 as builder_mod

    for ir_path in (
        "data/examples/sofa_ir_corner_right_v01.json",
        "data/examples/sofa_ir_corner_left_v01.json",
    ):
        sink = ListDiagnosticsSink()
        monkeypatch.setattr(builder_mod, "_diag_sink_from_env", lambda sink=sink: sink)

        with redirect_stdout(io.StringIO()):
            plan = build_plan_from_ir(_load_ir(ir_path))

        names = [primitive.name for primitive in plan.primitives]
        assert any(name.startswith("back_main_") for name in names)
        assert any(name.startswith("back_chaise_") for name in names)
        assert any(name.startswith("arm_chaise_free_end_") for name in names)
        assert any(name.startswith("arm_main_left_") or name.startswith("arm_main_right_") for name in names)
        assert not any(name.startswith("arm_join_") or name.startswith("arm_join_blocked_") for name in names)
        _assert_positive_finite_dims(plan)

        strategy_events = [
            event for event in sink.events if event.stage == "build" and event.code == "STRATEGY_SELECTED"
        ]
        assert any(event.component == "arms" for event in strategy_events)
        assert any(event.component == "back" for event in strategy_events)

