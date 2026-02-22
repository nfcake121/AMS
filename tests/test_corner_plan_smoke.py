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


def test_corner_plan_smoke(monkeypatch) -> None:
    import src.builders.blender.builder_v01 as builder_mod

    ir_paths = [
        "data/examples/sofa_ir_corner_right_v01.json",
        "data/examples/sofa_ir_corner_left_v01.json",
    ]
    for ir_path in ir_paths:
        sink = ListDiagnosticsSink()
        monkeypatch.setattr(builder_mod, "_diag_sink_from_env", lambda sink=sink: sink)
        ir = _load_ir(ir_path)

        with redirect_stdout(io.StringIO()):
            plan = build_plan_from_ir(ir)

        primitive_names = [primitive.name for primitive in plan.primitives]
        assert any(name.startswith("beam_chaise_") for name in primitive_names)
        assert any(name.startswith("slat_chaise_") for name in primitive_names)
        assert any(name.startswith("leg_chaise_") for name in primitive_names)
        assert any(name.startswith("back_main_") for name in primitive_names)
        assert any(name.startswith("back_chaise_") for name in primitive_names)
        assert "back_corner_post" in primitive_names
        assert any(name.startswith("arm_main_left_") or name.startswith("arm_main_right_") for name in primitive_names)
        assert any(name.startswith("arm_chaise_free_end_") for name in primitive_names)
        assert not any(name.startswith("arm_join_") or name.startswith("arm_join_blocked_") for name in primitive_names)

        for primitive in plan.primitives:
            assert all(math.isfinite(float(value)) for value in primitive.dimensions_mm)
            assert all(float(value) > 0.0 for value in primitive.dimensions_mm)
            assert all(math.isfinite(float(value)) for value in primitive.location_mm)

        codes = {event.code for event in sink.events}
        assert "LAYOUT_KIND_CORNER_SELECTED" in codes
        assert "CORNER_DIMENSIONS_COMPUTED" in codes
        assert "LAYOUT_TOPOLOGY_COMPUTED" in codes

        strategy_components = {
            event.component
            for event in sink.events
            if event.code == "STRATEGY_SELECTED"
        }
        assert {"seat_frame", "seat_slats", "legs", "arms", "back"}.issubset(strategy_components)
        assert "TOPOLOGY_ARM_SLOTS_RECEIVED" in codes
        assert "TOPOLOGY_BACK_SLOTS_RECEIVED" in codes
