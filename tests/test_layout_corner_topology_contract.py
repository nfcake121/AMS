from __future__ import annotations

import math
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


def _assert_finite_positive_span(min_v: float, max_v: float) -> None:
    assert math.isfinite(float(min_v))
    assert math.isfinite(float(max_v))
    assert float(max_v) > float(min_v)


def test_layout_corner_topology_contract() -> None:
    ir = {
        "version": "0.1",
        "style": "scandi",
        "layout": "corner",
        "seat_count": 2,
        "seat_width_mm": 900.0,
        "seat_depth_mm": 520.0,
        "seat_height_mm": 445.0,
        "frame": {"thickness_mm": 34.0},
        "legs": {},
        "arms": {"type": "both", "width_mm": 110.0, "profile": "box"},
        "slats": {"enabled": True, "count": 16},
        "back_support": {"mode": "slats"},
        "corner": {
            "chaise_side": "right",
            "chaise_extra_depth_mm": 320.0,
            "corner_gap_mm": 0.0,
            "join_mode": "shared_corner_post",
        },
    }
    sink = ListDiagnosticsSink()
    ctx = BuildContext(run_id="layout-corner-topology", debug=False, diag=sink)
    normalized = validate_and_normalize_ir(ir, ctx)
    spec, _resolve_diagnostics = resolve(normalized, preset_id=normalized.get("preset_id"))
    layout = compute_layout(
        normalized,
        spec,
        diag_sink=sink,
        run_id=ctx.run_id,
    )

    assert layout.kind == "corner"
    segment_by_name = {segment.name: segment for segment in layout.segments}
    assert {"main", "chaise"}.issubset(set(segment_by_name))

    main_segment = segment_by_name["main"]
    chaise_segment = segment_by_name["chaise"]
    _assert_finite_positive_span(main_segment.min_x, main_segment.max_x)
    _assert_finite_positive_span(main_segment.min_y, main_segment.max_y)
    _assert_finite_positive_span(main_segment.min_z, main_segment.max_z)
    _assert_finite_positive_span(chaise_segment.min_x, chaise_segment.max_x)
    _assert_finite_positive_span(chaise_segment.min_y, chaise_segment.max_y)
    _assert_finite_positive_span(chaise_segment.min_z, chaise_segment.max_z)

    arm_slot_by_name = {slot.name: slot for slot in layout.arm_slots}
    assert {"main_left", "main_right", "chaise_free_end", "join_blocked"}.issubset(set(arm_slot_by_name))
    assert arm_slot_by_name["join_blocked"].allowed is False

    back_slot_by_name = {slot.name: slot for slot in layout.back_slots}
    assert {"main_back", "chaise_back"}.issubset(set(back_slot_by_name))

    assert layout.join is not None
    assert layout.join.join_mode == "shared_corner_post"
    _assert_finite_positive_span(layout.join.min_x, layout.join.max_x)
    _assert_finite_positive_span(layout.join.min_y, layout.join.max_y)
    _assert_finite_positive_span(layout.join.min_z, layout.join.max_z)

    layout_codes = {event.code for event in sink.events if event.stage == "layout"}
    assert "LAYOUT_KIND_CORNER_SELECTED" in layout_codes
    assert "LAYOUT_TOPOLOGY_COMPUTED" in layout_codes

