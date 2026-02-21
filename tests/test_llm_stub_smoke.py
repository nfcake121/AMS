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
from src.builders.blender.diagnostics import (
    REQUIRED_BASELINE_EVENT_CODES,
    REQUIRED_BASELINE_STAGES,
    build_diagnostics_summary,
)
from src.builders.blender.plan_snapshot import plan_to_snapshot
from src.pipeline.llm_stub import maybe_generate_suggestions_from_env


def _load_ir(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _build_silent(ir: dict):
    with redirect_stdout(io.StringIO()):
        return build_plan_from_ir(ir)


def test_llm_stub_enabled_does_not_change_plan_snapshot(monkeypatch, tmp_path):
    ir = _load_ir("data/examples/sofa_ir.json")
    baseline = plan_to_snapshot(_build_silent(ir))

    out_path = tmp_path / "llm_stub_suggestions.json"
    monkeypatch.setenv("AMS_LLM_ENABLED", "1")
    monkeypatch.setenv("AMS_LLM_PATCHES_JSON", str(out_path))
    with_stub = plan_to_snapshot(_build_silent(ir))

    assert with_stub == baseline
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload.get("enabled") is True
    assert isinstance(payload.get("suggestions"), list)
    assert isinstance(payload.get("diagnostics_summary"), dict)


def test_llm_stub_summary_contains_required_build_codes():
    ir = _load_ir("data/examples/sofa_ir.json")
    suggestions = maybe_generate_suggestions_from_env(
        ir=ir,
        events=[],
        metrics=None,
        validators=None,
    )
    assert suggestions == []

    # Contract sanity: required baseline lists are explicit and non-empty.
    assert REQUIRED_BASELINE_EVENT_CODES == {"BUILD_START", "BUILD_DONE", "LAYOUT_COMPUTED"}
    assert REQUIRED_BASELINE_STAGES == {"resolve", "layout", "build"}

    # Summary helper should remain stable on empty input.
    summary = build_diagnostics_summary([])
    assert summary["total"] == 0
    assert summary["by_stage"] == {}
    assert summary["by_code"] == {}
    assert summary["by_severity"] == {}
