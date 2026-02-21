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
from src.builders.blender.plan_snapshot import plan_to_snapshot


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


def _load_ir(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _build_silent(ir: dict):
    with redirect_stdout(io.StringIO()):
        return build_plan_from_ir(ir)


def test_arms_strategy_smoke(monkeypatch):
    import src.builders.blender.builder_v01 as builder_mod

    cases = [
        ("data/examples/sofa_ir_scandi_back_split2_hslats_v03_arms_box.json", "box"),
        ("data/examples/sofa_ir_scandi_back_split2_hslats_v03_arms_frame_open.json", "frame_box_open"),
    ]
    for path, expected_strategy in cases:
        sink = ListDiagnosticsSink()
        monkeypatch.setattr(builder_mod, "_diag_sink_from_env", lambda sink=sink: sink)
        ir = _load_ir(path)
        plan = _build_silent(ir)

        arm_primitives = [primitive for primitive in plan.primitives if primitive.name.startswith("arm_")]
        assert arm_primitives, f"arm_* primitives must be present for {path}"
        strategy_events = [
            event
            for event in sink.events
            if event.stage == "build" and event.component == "arms" and event.code == "STRATEGY_SELECTED"
        ]
        assert strategy_events, f"missing STRATEGY_SELECTED for {path}"
        payload = strategy_events[-1].meta.get("payload", {})
        assert payload.get("strategy") == expected_strategy


def test_existing_sofa_ir_snapshot_unchanged():
    ir = _load_ir("data/examples/sofa_ir.json")
    snapshot = plan_to_snapshot(_build_silent(ir))
    golden_path = Path("tests/golden/sofa_ir.plan.json")
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert snapshot == expected
