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


def test_inputs_corner_requests_contract() -> None:
    import src.builders.blender.builder_v01 as builder_mod

    ir = _load_ir("data/examples/sofa_ir_corner_right_v01.json")
    sink = ListDiagnosticsSink()
    ctx = BuildContext(run_id="inputs-corner-contract", debug=False, diag=sink)
    normalized_ir = validate_and_normalize_ir(ir, ctx)
    resolved_spec, _resolve_diagnostics = resolve(normalized_ir, preset_id=normalized_ir.get("preset_id"))
    layout = compute_layout(normalized_ir, resolved_spec, diag_sink=sink, run_id=ctx.run_id)

    (
        _seat_frame_inputs,
        _seat_slats_inputs,
        back_inputs,
        arms_inputs,
        _legs_inputs,
        _metadata,
    ) = builder_mod._make_component_inputs(normalized_ir, resolved_spec, layout)

    assert arms_inputs.requests
    arm_slot_names = {request.slot_name for request in arms_inputs.requests}
    assert {"main_left", "main_right", "chaise_free_end", "join_blocked"}.issubset(arm_slot_names)
    join_request = next(request for request in arms_inputs.requests if request.slot_name == "join_blocked")
    assert join_request.allowed is False

    assert back_inputs.requests
    back_slot_names = {request.slot_name for request in back_inputs.requests}
    assert {"main_back", "chaise_back"}.issubset(back_slot_names)
    assert all(request.allowed for request in back_inputs.requests)


def test_straight_build_snapshots_unchanged_guard() -> None:
    ir = _load_ir("data/examples/sofa_ir.json")
    with redirect_stdout(io.StringIO()):
        plan = build_plan_from_ir(ir)
    assert plan.primitives

