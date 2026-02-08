"""Blender CLI debug run for sofa builder."""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from typing import Any


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.builders.blender.builder_v01 import build_plan_from_ir  # noqa: E402
from tools.blender.debug.autofix import fix_ir  # noqa: E402
from tools.blender.debug.io import ir_sha256, make_run_id, save_run_log  # noqa: E402
from tools.blender.debug.metrics import collect_scene_metrics  # noqa: E402
from tools.blender.debug.validators import validate  # noqa: E402
from tools.blender.run_builder_v01 import (  # noqa: E402
    _clear_scene,
    _create_anchor,
    _create_primitive,
    _ensure_mm_units,
)


def _read_ir_path() -> str:
    """Resolve IR path from env or argv (after '--')."""
    if os.environ.get("IR_PATH"):
        return os.environ["IR_PATH"]
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if len(sys.argv) > idx + 1:
            return sys.argv[idx + 1]
    if len(sys.argv) > 1:
        return sys.argv[-1]
    return ""


def _read_debug_iters() -> int:
    """Resolve DEBUG_ITERS env var with default 3."""
    raw = os.environ.get("DEBUG_ITERS", "3")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 3
    return max(1, value)


def _build_scene_from_ir(ir: dict[str, Any]) -> dict[str, int]:
    """Build scene from IR and return primitive/anchor counts."""
    import bpy  # type: ignore

    _clear_scene()
    _ensure_mm_units()

    plan = build_plan_from_ir(ir)
    legs = ir.get("legs", {}) if isinstance(ir.get("legs"), dict) else {}
    legs_params = legs.get("params", {}) if isinstance(legs.get("params"), dict) else None

    for prim in plan.primitives:
        _create_primitive(prim, legs_params=legs_params)

    for anchor in plan.anchors:
        _create_anchor(anchor.name, anchor.location_mm)

    bpy.context.view_layer.update()
    return {"primitives": len(plan.primitives), "anchors": len(plan.anchors)}


def main() -> dict[str, Any]:
    """Run debug build, validate scene, and optionally apply rule-based autofix."""
    ir_path = _read_ir_path()
    if not ir_path:
        raise SystemExit("IR path is required. Pass it after '--' or set IR_PATH env var.")

    ir_path = os.path.abspath(ir_path)
    with open(ir_path, "r", encoding="utf-8") as handle:
        source_ir = json.load(handle)
    if not isinstance(source_ir, dict):
        raise SystemExit(f"Expected IR JSON object, got {type(source_ir).__name__}")

    debug_autofix = os.environ.get("DEBUG_AUTOFIX") == "1"
    max_iters = _read_debug_iters() if debug_autofix else 1
    run_id = make_run_id()

    current_ir = deepcopy(source_ir)
    iterations: list[dict[str, Any]] = []
    final_validation: dict[str, Any] = {}

    for iteration_idx in range(1, max_iters + 1):
        build_info = _build_scene_from_ir(current_ir)
        metrics = collect_scene_metrics()
        validation = validate(metrics, current_ir)
        problems = validation.get("problems", [])
        if not isinstance(problems, list):
            problems = []

        patch_list: list[dict[str, Any]] = []
        did_patch = False
        if debug_autofix and problems and iteration_idx < max_iters:
            candidate_ir, patch_list = fix_ir(current_ir, problems)
            if patch_list:
                current_ir = candidate_ir
                did_patch = True

        iterations.append(
            {
                "iteration": iteration_idx,
                "build": build_info,
                "metrics": metrics,
                "validation": validation,
                "patches": patch_list,
            }
        )
        final_validation = validation

        if not (debug_autofix and problems and did_patch and iteration_idx < max_iters):
            break

    payload: dict[str, Any] = {
        "run_id": run_id,
        "source_ir_path": ir_path,
        "source_ir_sha256": ir_sha256(source_ir),
        "autofix_enabled": debug_autofix,
        "max_iters": max_iters,
        "iterations": iterations,
        "final_ir": current_ir,
        "final_ir_sha256": ir_sha256(current_ir),
        "final_problem_count": len(final_validation.get("problems", [])),
        "final_score": final_validation.get("score"),
    }

    log_path = save_run_log(
        payload,
        out_dir=os.path.join(REPO_ROOT, "out", "logs", "runs"),
        run_id=run_id,
    )

    print(f"DEBUG_RUN_ID:{run_id}")
    print(f"DEBUG_RUN_LOG:{log_path}")
    print(f"DEBUG_AUTOFIX:{1 if debug_autofix else 0}")
    print(f"DEBUG_ITERS_EXECUTED:{len(iterations)}")

    return payload


if __name__ == "__main__":
    main()

