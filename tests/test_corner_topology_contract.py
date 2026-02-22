from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.builders.blender.builder_v01 as builder_mod
from src.builders.blender.layout import compute_layout
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


def test_corner_topology_slots_and_builder_events() -> None:
    ir = _load_ir("data/examples/sofa_ir_corner_right_v01.json")
    sink = ListDiagnosticsSink()
    ctx = BuildContext(run_id="corner-topology-contract", debug=False, diag=sink)
    normalized_ir = validate_and_normalize_ir(ir, ctx)
    resolved_spec, _resolve_diagnostics = resolve(normalized_ir, preset_id=normalized_ir.get("preset_id"))
    layout = compute_layout(normalized_ir, resolved_spec, diag_sink=sink, run_id=ctx.run_id)
    assert layout.kind == "corner"

    (
        _seat_frame_inputs,
        _seat_slats_inputs,
        back_inputs,
        arms_inputs,
        _legs_inputs,
        _metadata,
    ) = builder_mod._make_component_inputs(normalized_ir, resolved_spec, layout, build_ctx=ctx)

    arm_requests = {request.slot_name: request for request in arms_inputs.requests}
    assert "join_blocked" in arm_requests
    assert arm_requests["join_blocked"].allowed is False
    assert "chaise_free_end" in arm_requests
    assert arm_requests["chaise_free_end"].allowed is True

    back_requests = {request.slot_name: request for request in back_inputs.requests}
    assert "chaise_back" in back_requests
    assert back_requests["chaise_back"].allowed is True

    codes = [event.code for event in sink.events]
    assert "LAYOUT_KIND_CORNER_SELECTED" in codes
    assert "LAYOUT_TOPOLOGY_COMPUTED" in codes
    assert "TOPOLOGY_ARM_SLOTS_RECEIVED" in codes
    assert "TOPOLOGY_BACK_SLOTS_RECEIVED" in codes

