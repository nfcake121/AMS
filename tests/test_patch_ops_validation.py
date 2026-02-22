from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.patches.types import PatchOp
from src.builders.blender.patches.validate import validate_patch_ops


class ListDiagnosticsSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


def test_validate_patch_ops_accepts_whitelisted_patch() -> None:
    valid, rejected = validate_patch_ops([PatchOp(op="set", path="arms.width_mm", value=180.0)])
    assert len(valid) == 1
    assert valid[0].value == 180.0
    assert rejected == []


def test_validate_patch_ops_rejects_non_whitelisted_path() -> None:
    valid, rejected = validate_patch_ops([PatchOp(op="set", path="unknown.path", value=1)])
    assert valid == []
    assert len(rejected) == 1
    assert rejected[0]["code"] == "PATCH_PATH_NOT_ALLOWED"


def test_validate_patch_ops_rejects_type_mismatch() -> None:
    valid, rejected = validate_patch_ops([PatchOp(op="set", path="arms.width_mm", value="wide")])
    assert valid == []
    assert len(rejected) == 1
    assert rejected[0]["code"] == "PATCH_TYPE_MISMATCH"


def test_validate_patch_ops_clamps_and_emits_warning() -> None:
    sink = ListDiagnosticsSink()
    valid, rejected = validate_patch_ops(
        [PatchOp(op="set", path="legs.height_mm", value=9999.0)],
        diag_sink=sink,
        run_id="test-run",
    )
    assert rejected == []
    assert len(valid) == 1
    assert float(valid[0].value) == 500.0
    clamp_codes = [event.code for event in sink.events]
    assert "PATCH_CLAMP" in clamp_codes
    clamp_event = next(event for event in sink.events if event.code == "PATCH_CLAMP")
    assert clamp_event.path == "legs.height_mm"
    assert clamp_event.resolved_value == 500.0


def test_validate_patch_ops_honors_max_ops_limit(monkeypatch) -> None:
    monkeypatch.setenv("AMS_PATCH_MAX_OPS", "1")
    ops = [
        PatchOp(op="set", path="arms.width_mm", value=110.0),
        PatchOp(op="set", path="legs.height_mm", value=170.0),
    ]
    valid, rejected = validate_patch_ops(ops)
    assert len(valid) == 1
    assert len(rejected) == 1
    assert rejected[0]["code"] == "PATCH_MAX_OPS"

