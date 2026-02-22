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


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


def _load_ir(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_corner_seat_frame_join_smoke(monkeypatch) -> None:
    import src.builders.blender.builder_v01 as builder_mod

    cases = (
        ("data/examples/sofa_ir_corner_right_v01.json", "right"),
        ("data/examples/sofa_ir_corner_left_v01.json", "left"),
    )
    for ir_path, side in cases:
        sink = ListDiagnosticsSink()
        monkeypatch.setattr(builder_mod, "_diag_sink_from_env", lambda sink=sink: sink)
        with redirect_stdout(io.StringIO()):
            plan = build_plan_from_ir(_load_ir(ir_path))

        beam_names = [primitive.name for primitive in plan.primitives if primitive.name.startswith("beam_")]
        assert any(name.startswith("beam_main_") for name in beam_names)
        assert any(name.startswith("beam_chaise_") for name in beam_names)
        assert any(name.startswith("beam_corner_") for name in beam_names)

        if side == "right":
            assert "beam_right" not in beam_names
            assert "beam_chaise_left" not in beam_names
        else:
            assert "beam_left" not in beam_names
            assert "beam_chaise_right" not in beam_names

        seat_frame_events = [
            event
            for event in sink.events
            if event.stage == "build" and event.component == "seat_frame" and event.code == "STRATEGY_SELECTED"
        ]
        assert seat_frame_events
        payload = seat_frame_events[-1].meta.get("payload", {})
        assert payload.get("strategy") == "corner_shared_corner_post"
        assert payload.get("layout_kind") == "corner"
        assert payload.get("join_mode") == "shared_corner_post"

