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
from src.builders.blender.spec.resolve import resolve


CASES = [
    "data/examples/sofa_ir.json",
    "data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json",
    "data/examples/sofa_ir_scandi_back_split2_hslats_v04.json",
]


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


def _expected_strategy_handlers(ir: dict) -> tuple[str, str]:
    resolved, _ = resolve(ir, preset_id=ir.get("preset_id"))

    arms_profile = str(resolved.arms.profile or "box")
    if arms_profile not in {"box", "frame_box_open"}:
        arms_profile = "box"
    arms_handler = "arm_frame_box_open" if arms_profile == "frame_box_open" else "arm_box"

    if not bool(resolved.back.has_back_support):
        back_handler = "legacy_back_frame"
    else:
        back_mode = str(resolved.back.mode or "panel")
        if back_mode == "slats":
            back_handler = "back_slats"
        elif back_mode == "straps":
            back_handler = "back_straps"
        elif back_mode == "panel":
            back_handler = "back_panel"
        else:
            back_handler = "back_noop"

    return back_handler, arms_handler


def test_strategy_selection_smoke(monkeypatch):
    import src.builders.blender.builder_v01 as builder_mod

    for case in CASES:
        ir = json.loads(Path(case).read_text(encoding="utf-8"))
        expected_back_handler, expected_arms_handler = _expected_strategy_handlers(ir)

        sink = ListDiagnosticsSink()
        monkeypatch.setattr(builder_mod, "_diag_sink_from_env", lambda: sink)

        buf = io.StringIO()
        with redirect_stdout(buf):
            plan = build_plan_from_ir(ir)
        assert plan.primitives
        assert buf.getvalue() == ""

        strategy_events = [
            event
            for event in sink.events
            if event.code == "STRATEGY_SELECTED" and event.stage == "build"
        ]

        back_events = [event for event in strategy_events if event.component == "back"]
        arms_events = [event for event in strategy_events if event.component == "arms"]
        assert back_events, f"Missing back strategy event for {case}"
        assert arms_events, f"Missing arms strategy event for {case}"

        back_handler = back_events[-1].meta.get("payload", {}).get("handler")
        arms_handler = arms_events[-1].meta.get("payload", {}).get("handler")
        assert back_handler == expected_back_handler, (
            f"Unexpected back handler for {case}: {back_handler} != {expected_back_handler}"
        )
        assert arms_handler == expected_arms_handler, (
            f"Unexpected arms handler for {case}: {arms_handler} != {expected_arms_handler}"
        )
