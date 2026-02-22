from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.patches.apply import apply_patch_ops
from src.builders.blender.patches.types import PatchOp
from src.builders.blender.patches.validate import validate_patch_ops


def test_apply_patch_ops_set_and_inc_work() -> None:
    ir = {
        "arms": {"width_mm": 120.0},
        "legs": {"height_mm": 160},
    }
    source_ir = copy.deepcopy(ir)
    ops = [
        PatchOp(op="set", path="arms.width_mm", value=150.0),
        PatchOp(op="inc", path="legs.height_mm", delta=-10),
    ]
    patched, result = apply_patch_ops(ir, ops)
    assert ir == source_ir
    assert patched["arms"]["width_mm"] == 150.0
    assert patched["legs"]["height_mm"] == 150
    assert result.changed is True
    assert len(result.applied) == 2
    assert result.rejected == []


def test_apply_patch_ops_rejects_missing_path() -> None:
    ir = {"arms": {"width_mm": 120.0}}
    patched, result = apply_patch_ops(ir, [PatchOp(op="set", path="arms.unknown", value=1.0)])
    assert patched == ir
    assert result.changed is False
    assert len(result.applied) == 0
    assert len(result.rejected) == 1
    assert result.rejected[0]["code"] == "PATCH_SET_FAILED"


def test_apply_patch_ops_rejects_inc_on_non_numeric_target() -> None:
    ir = {"arms": {"profile": "box"}}
    _patched, result = apply_patch_ops(ir, [PatchOp(op="inc", path="arms.profile", delta=1.0)])
    assert result.changed is False
    assert len(result.rejected) == 1
    assert result.rejected[0]["code"] == "PATCH_INC_FAILED"


def test_max_ops_limit_enforced_by_validation(monkeypatch) -> None:
    monkeypatch.setenv("AMS_PATCH_MAX_OPS", "1")
    valid, rejected = validate_patch_ops(
        [
            PatchOp(op="set", path="arms.width_mm", value=140.0),
            PatchOp(op="set", path="legs.height_mm", value=130.0),
        ]
    )
    assert len(valid) == 1
    assert len(rejected) == 1
    assert rejected[0]["code"] == "PATCH_MAX_OPS"

