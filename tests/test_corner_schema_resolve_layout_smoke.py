from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.layout import compute_layout
from src.builders.blender.spec.ir_schema import validate_and_normalize_ir
from src.builders.blender.spec.resolve import resolve
from src.builders.blender.spec.types import BuildContext


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


def test_corner_schema_resolve_layout_smoke() -> None:
    schema_sink = ListDiagnosticsSink()
    schema_ctx = BuildContext(run_id="corner-schema", debug=False, diag=schema_sink)
    raw_ir = {
        "version": "0.1",
        "style": "scandi",
        "layout": "corner",
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
            "chaise_side": "unsupported_side",
            "chaise_extra_depth_mm": 5000.0,
            "corner_gap_mm": -12.0,
            "join_mode": "butt_joint",
        },
    }
    normalized_ir = validate_and_normalize_ir(raw_ir, schema_ctx)
    assert normalized_ir["layout"] == "corner"
    assert isinstance(normalized_ir.get("corner"), dict)

    resolved_spec, resolve_diagnostics = resolve(normalized_ir, preset_id=normalized_ir.get("preset_id"))
    assert resolved_spec.corner is not None
    assert resolved_spec.corner.chaise_side == "right"
    assert resolved_spec.corner.join_mode == "shared_corner_post"
    assert float(resolved_spec.corner.chaise_extra_depth_mm) == 1200.0
    assert float(resolved_spec.corner.corner_gap_mm) == 0.0

    resolve_events = resolve_diagnostics.warnings
    assert any(
        event.code == "RESOLVE_ENUM_FALLBACK" and event.path == "corner.chaise_side"
        for event in resolve_events
    )
    assert any(
        event.code == "RESOLVE_ENUM_FALLBACK" and event.path == "corner.join_mode"
        for event in resolve_events
    )
    assert any(
        event.code == "RESOLVE_CLAMP_APPLIED" and event.path == "corner.chaise_extra_depth_mm"
        for event in resolve_events
    )
    assert any(
        event.code == "RESOLVE_CLAMP_APPLIED" and event.path == "corner.corner_gap_mm"
        for event in resolve_events
    )

    layout_sink = ListDiagnosticsSink()
    layout = compute_layout(
        normalized_ir,
        resolved_spec,
        diag_sink=layout_sink,
        run_id="corner-layout",
    )
    assert layout.kind == "corner"
    assert layout.chaise_width_mm is not None and layout.chaise_width_mm > 0.0
    assert layout.chaise_depth_mm is not None
    assert float(layout.chaise_depth_mm) == float(layout.seat_depth_mm) + float(
        resolved_spec.corner.chaise_extra_depth_mm
    )
    layout_codes = {event.code for event in layout_sink.events}
    assert "LAYOUT_KIND_CORNER_SELECTED" in layout_codes
    assert "CORNER_DIMENSIONS_COMPUTED" in layout_codes

