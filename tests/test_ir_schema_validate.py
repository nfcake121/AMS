from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.builder_v01 import build_plan_from_ir
from src.builders.blender.spec.ir_validate import ir_schema_validate


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


def test_ir_schema_validate_soft_defaults_and_type_fallbacks():
    ok, diagnostics = ir_schema_validate(
        {
            "style": 101,
            "arms": "bad",
            "seat_count": "x",
        }
    )
    assert ok is False
    assert diagnostics.normalized_ir["style"] == "default"
    assert diagnostics.normalized_ir["arms"] == {}
    assert diagnostics.normalized_ir["seat_count"] == 3
    assert diagnostics.normalized_ir["seat_width_mm"] == 600.0
    codes = {event.code for event in diagnostics.warnings}
    assert "IR_SCHEMA_TYPE_COERCE" in codes
    assert "IR_SCHEMA_DEFAULT_APPLIED" in codes
    assert all(event.stage == "ir_schema" for event in diagnostics.warnings)
    assert all(event.component == "resolver" for event in diagnostics.warnings)


def test_build_plan_from_ir_runs_with_non_dict_input(monkeypatch):
    sink = ListDiagnosticsSink()
    import src.builders.blender.builder_v01 as builder_mod

    monkeypatch.setattr(builder_mod, "_diag_sink_from_env", lambda: sink)
    with redirect_stdout(io.StringIO()):
        plan = build_plan_from_ir(["not", "dict"])  # type: ignore[arg-type]

    assert plan.primitives
    codes = {event.code for event in sink.events}
    assert "IR_SCHEMA_MISSING_REQUIRED" in codes
    assert "BUILD_START" in codes
    assert "BUILD_DONE" in codes
