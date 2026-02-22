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
from src.builders.blender.layout import compute_layout
from src.builders.blender.plan_snapshot import plan_to_snapshot
from src.builders.blender.spec.ir_schema import validate_and_normalize_ir
from src.builders.blender.spec.resolve import resolve
from src.builders.blender.spec.types import BuildContext


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


def _load_ir(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_corner_block_is_ignored_for_straight_layout() -> None:
    schema_sink = ListDiagnosticsSink()
    schema_ctx = BuildContext(run_id="straight-schema", debug=False, diag=schema_sink)
    raw_ir = {
        "version": "0.1",
        "style": "default",
        "layout": "straight",
        "seat_count": 3,
        "seat_width_mm": 600.0,
        "seat_depth_mm": 600.0,
        "seat_height_mm": 445.0,
        "frame": {},
        "legs": {},
        "arms": {},
        "slats": {},
        "back_support": {},
        "corner": {
            "chaise_side": "left",
            "chaise_extra_depth_mm": 900.0,
            "corner_gap_mm": 20.0,
            "join_mode": "butt_joint",
        },
    }
    normalized_ir = validate_and_normalize_ir(raw_ir, schema_ctx)
    assert normalized_ir["layout"] == "straight"
    assert normalized_ir.get("corner") == raw_ir["corner"]
    assert not any(str(event.path).startswith("corner") for event in schema_sink.events)

    resolved_spec, resolve_diagnostics = resolve(normalized_ir, preset_id=normalized_ir.get("preset_id"))
    assert resolved_spec.corner is None
    assert not any(str(event.path).startswith("corner") for event in resolve_diagnostics.warnings)

    layout_sink = ListDiagnosticsSink()
    layout = compute_layout(
        normalized_ir,
        resolved_spec,
        diag_sink=layout_sink,
        run_id="straight-layout",
    )
    assert layout.kind == "straight"
    assert not any(
        event.code in {"LAYOUT_KIND_CORNER_SELECTED", "CORNER_DIMENSIONS_COMPUTED"}
        for event in layout_sink.events
    )


def test_existing_straight_snapshot_remains_unchanged() -> None:
    ir = _load_ir("data/examples/sofa_ir.json")
    with redirect_stdout(io.StringIO()):
        plan = build_plan_from_ir(ir)
    actual_snapshot = plan_to_snapshot(plan)
    expected_snapshot = json.loads(Path("tests/golden/sofa_ir.plan.json").read_text(encoding="utf-8"))
    assert actual_snapshot == expected_snapshot

