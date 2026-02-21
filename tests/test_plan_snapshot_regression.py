from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.builder_v01 import build_plan_from_ir
from src.builders.blender.plan_snapshot import plan_to_snapshot


CASES = [
    "data/examples/sofa_ir.json",
    "data/examples/sofa_ir_scandi_back_split2_hslats_v03_armframe.json",
    "data/examples/sofa_ir_scandi_back_split2_hslats_v04.json",
]

GOLDEN_DIR = Path("tests/golden")


def _update_golden_enabled() -> bool:
    value = os.environ.get("UPDATE_GOLDEN", "")
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _golden_path(ir_path: str) -> Path:
    basename = Path(ir_path).stem
    return GOLDEN_DIR / f"{basename}.plan.json"


def _build_plan_silent(ir: dict):
    with redirect_stdout(io.StringIO()):
        return build_plan_from_ir(ir)


def test_plan_snapshot_regression():
    update = _update_golden_enabled()
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

    for ir_path in CASES:
        ir = json.loads(Path(ir_path).read_text(encoding="utf-8"))
        plan = _build_plan_silent(ir)
        snapshot = plan_to_snapshot(plan)
        golden_path = _golden_path(ir_path)

        if update:
            golden_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
            continue

        assert golden_path.exists(), (
            f"Golden snapshot not found: {golden_path}. "
            "Run with UPDATE_GOLDEN=1 to generate."
        )
        expected = json.loads(golden_path.read_text(encoding="utf-8"))
        assert snapshot == expected
