from __future__ import annotations

import io
import json
import math
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.builders.blender.builder_v01 import build_plan_from_ir


def _load_ir(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_corner_geometry_smoke() -> None:
    for ir_path in (
        "data/examples/sofa_ir_corner_right_v01.json",
        "data/examples/sofa_ir_corner_left_v01.json",
    ):
        ir = _load_ir(ir_path)
        with redirect_stdout(io.StringIO()):
            plan = build_plan_from_ir(ir)

        primitive_names = [primitive.name for primitive in plan.primitives]
        assert any(name.startswith("back_main_") for name in primitive_names)
        assert any(name.startswith("back_chaise_") for name in primitive_names)
        assert any(name.startswith("arm_main_left_") or name.startswith("arm_main_right_") for name in primitive_names)
        assert any(name.startswith("arm_chaise_free_end_") for name in primitive_names)
        assert not any(name.startswith("arm_join_") or name.startswith("arm_join_blocked_") for name in primitive_names)

        for primitive in plan.primitives:
            assert all(math.isfinite(float(value)) for value in primitive.dimensions_mm)
            assert all(float(value) > 0.0 for value in primitive.dimensions_mm)
