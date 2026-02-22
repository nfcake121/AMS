from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.spec.ir_schema import validate_and_normalize_ir
from src.builders.blender.spec.types import BuildContext


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


def test_validate_and_normalize_ir_coerces_numeric_string_and_emits_event() -> None:
    sink = ListDiagnosticsSink()
    ctx = BuildContext(run_id="run-ir-schema-1", debug=False, diag=sink)
    normalized = validate_and_normalize_ir(
        {
            "version": "0.1",
            "style": "default",
            "layout": "straight",
            "seat_count": "445",
            "seat_depth_mm": 610.0,
            "seat_height_mm": 440.0,
            "frame": {},
            "legs": {},
            "arms": {},
            "slats": {},
            "back_support": {},
        },
        ctx,
    )
    assert normalized["seat_count"] == 445
    assert normalized["seat_width_mm"] == 600.0
    code_path = {(event.code, event.path) for event in sink.events}
    assert ("IR_SCHEMA_TYPE_COERCE", "seat_count") in code_path
    assert ("IR_SCHEMA_MISSING_REQUIRED", "seat_width_mm") in code_path
    assert ("IR_SCHEMA_DEFAULT_APPLIED", "seat_width_mm") in code_path


def test_validate_and_normalize_ir_handles_missing_required_without_crash() -> None:
    sink = ListDiagnosticsSink()
    ctx = BuildContext(run_id="run-ir-schema-2", debug=False, diag=sink)
    normalized = validate_and_normalize_ir({"style": "scandi"}, ctx)
    assert isinstance(normalized, dict)
    assert normalized["style"] == "scandi"
    assert normalized["seat_count"] == 3
    assert normalized["seat_width_mm"] == 600.0
    assert any(event.code == "IR_SCHEMA_MISSING_REQUIRED" for event in sink.events)

