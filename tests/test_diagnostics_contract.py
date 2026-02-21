from __future__ import annotations

import io
import json
import sys
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.builder_v01 import build_plan_from_ir
from src.builders.blender.diagnostics import (
    Event,
    Severity,
    VALID_COMPONENTS,
    VALID_SEVERITIES,
    VALID_SOURCES,
    VALID_STAGES,
    emit_simple,
)


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)


def _load_ir(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_build_pipeline_is_stdout_silent(monkeypatch):
    sink = ListDiagnosticsSink()
    import src.builders.blender.builder_v01 as builder_mod

    monkeypatch.setattr(builder_mod, "_diag_sink_from_env", lambda: sink)
    ir = _load_ir("data/examples/sofa_ir.json")

    buf = io.StringIO()
    with redirect_stdout(buf):
        plan = build_plan_from_ir(ir)
    assert plan.primitives
    assert buf.getvalue() == ""


def test_diagnostics_event_contract_and_stability(monkeypatch):
    sink = ListDiagnosticsSink()
    import src.builders.blender.builder_v01 as builder_mod

    monkeypatch.setattr(builder_mod, "_diag_sink_from_env", lambda: sink)
    ir = _load_ir("data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json")
    # Force at least one resolve warning event.
    ir.setdefault("arms", {})["width_mm"] = -10

    buf = io.StringIO()
    with redirect_stdout(buf):
        build_plan_from_ir(ir)
    assert buf.getvalue() == ""

    assert sink.events
    required_keys = {
        "ts",
        "run_id",
        "stage",
        "component",
        "code",
        "severity",
        "path",
        "source",
        "input_value",
        "resolved_value",
        "reason",
        "meta",
    }
    signatures: list[tuple[str, str, str, int]] = []
    for event in sink.events:
        payload = event.to_dict()
        assert set(payload.keys()) == required_keys
        assert isinstance(payload["run_id"], str)
        assert payload["severity"] in VALID_SEVERITIES
        assert payload["stage"] in VALID_STAGES
        assert payload["source"] in VALID_SOURCES
        assert payload["component"] in VALID_COMPONENTS
        assert isinstance(payload["code"], str) and payload["code"]
        if payload["path"] == "":
            assert payload["code"] in {"BUILD_START", "BUILD_DONE"}
            assert payload["reason"] or payload["meta"]
        signatures.append(
            (
                payload["stage"],
                payload["component"],
                payload["code"],
                int(payload["severity"]),
            )
        )

    counts = Counter(signatures)
    assert counts[("build", "builder", "BUILD_START", int(Severity.INFO))] == 1
    assert counts[("build", "builder", "BUILD_DONE", int(Severity.INFO))] == 1
    assert any(stage == "resolve" for stage, _component, _code, _severity in signatures)


def test_emit_simple_contract_and_normalization() -> None:
    sink = ListDiagnosticsSink()
    event = emit_simple(
        sink,
        run_id="run-1",
        stage="debug",
        component="builder",
        code="UNIT_EVENT",
        path="arms.width_mm",
        payload={"min": 0, "max": 120},
        severity=Severity.WARN,
        iter_index=2,
        source="computed",
        reason="unit test",
        input_value=-10,
        resolved_value=0.0,
        meta={"hint": "clamp"},
    )
    assert sink.events and sink.events[-1] is event
    event_payload = event.to_dict()
    assert event_payload["stage"] == "debug"
    assert event_payload["component"] == "builder"
    assert event_payload["source"] == "computed"
    assert event_payload["meta"]["iter_index"] == 2
    assert event_payload["meta"]["payload"] == {"min": 0, "max": 120}
    assert event_payload["meta"]["hint"] == "clamp"

    normalized = emit_simple(
        sink,
        code="UNIT_EVENT_NORMALIZE",
        stage="unknown_stage",
        component="unknown_component",
        source="unknown_source",
    )
    assert normalized.stage == "build"
    assert normalized.component == "builder"
    assert normalized.source == "computed"
