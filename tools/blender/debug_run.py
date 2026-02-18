"""Blender-level debug run orchestrator for sofa IR.

Usage:
  blender --background --python tools/blender/debug_run.py -- path/to/sofa_ir.json
"""

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
from tools.blender.debug.io import (  # noqa: E402
    ensure_dir,
    make_run_id,
    make_run_tag,
    save_json,
    sha256_file,
    sha256_json,
)
from tools.blender.debug.metrics import collect_scene_metrics  # noqa: E402
from tools.blender.debug.validators import validate  # noqa: E402
from tools.blender.run_builder_v01 import (  # noqa: E402
    _clear_scene,
    _create_anchor,
    _create_primitive,
    _ensure_mm_units,
)


def _read_ir_path() -> str:
    """Resolve IR path from argv after '--', then from IR_PATH env."""
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if len(sys.argv) > idx + 1:
            candidate = str(sys.argv[idx + 1]).strip()
            if candidate:
                return candidate

    env_candidate = str(os.environ.get("IR_PATH", "")).strip()
    if env_candidate:
        return env_candidate

    if len(sys.argv) > 1:
        fallback = str(sys.argv[-1]).strip()
        if fallback and fallback != "--":
            return fallback
    return ""


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    return max(int(min_value), value)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _resolve_out_dir(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(REPO_ROOT, path))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _problem_count(validation: dict[str, Any]) -> int:
    problems = validation.get("problems", [])
    if isinstance(problems, list):
        return len(problems)
    return 0


def _top_overlap_offender_pair(validation: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_volume = -1.0

    problems = validation.get("problems", [])
    if isinstance(problems, list):
        for problem in problems:
            if not isinstance(problem, dict):
                continue
            code = str(problem.get("code", "")).strip().upper()
            if not code.startswith("OVERLAP_"):
                continue
            details = problem.get("details", {})
            if not isinstance(details, dict):
                continue
            pairs = details.get("pairs_top", [])
            if not isinstance(pairs, list) or len(pairs) == 0:
                pairs = details.get("joint_pairs_top", [])
            if not isinstance(pairs, list):
                continue
            for pair in pairs:
                if not isinstance(pair, dict):
                    continue
                volume = _safe_float(pair.get("volume", 0.0), 0.0)
                if volume > best_volume:
                    best_volume = volume
                    best = {
                        "source": code,
                        "left": str(pair.get("left", "")),
                        "right": str(pair.get("right", "")),
                        "volume": float(volume),
                    }

    if best is not None:
        return best

    overlaps = metrics.get("overlaps", {})
    if not isinstance(overlaps, dict):
        return None

    for overlap_key, payload in overlaps.items():
        if not isinstance(payload, dict):
            continue
        pairs = payload.get("pairs", [])
        if not isinstance(pairs, list):
            continue
        for pair in pairs:
            if not isinstance(pair, dict):
                continue
            volume = _safe_float(pair.get("volume", 0.0), 0.0)
            if volume > best_volume:
                best_volume = volume
                best = {
                    "source": str(overlap_key),
                    "left": str(pair.get("left", "")),
                    "right": str(pair.get("right", "")),
                    "volume": float(volume),
                }
    return best


def _top_fixes_payload(patches_applied: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for patch in patches_applied[: max(0, int(limit))]:
        if not isinstance(patch, dict):
            continue
        payload.append(
            {
                "path": str(patch.get("path", "")),
                "new": patch.get("new"),
            }
        )
    return payload


def _has_severity_ge3(validation: dict[str, Any]) -> bool:
    problems = validation.get("problems", [])
    if not isinstance(problems, list):
        return False
    for problem in problems:
        if not isinstance(problem, dict):
            continue
        if int(_safe_float(problem.get("severity", 0), 0.0)) >= 3:
            return True
    return False


def _extract_build_counts(metrics: dict[str, Any]) -> dict[str, Any]:
    object_count = 0
    if isinstance(metrics.get("object_count"), int):
        object_count = int(metrics["object_count"])
    elif isinstance(metrics.get("objects"), list):
        object_count = len(metrics["objects"])

    group_counts: dict[str, int] = {}
    top_group_counts = metrics.get("group_counts", {})
    if isinstance(top_group_counts, dict):
        for key, value in top_group_counts.items():
            group_counts[str(key)] = int(_safe_float(value, 0.0))
    else:
        groups = metrics.get("groups", {})
        if isinstance(groups, dict):
            for key, value in groups.items():
                if isinstance(value, dict):
                    group_counts[str(key)] = int(_safe_float(value.get("count", 0), 0.0))

    return {
        "object_count": int(object_count),
        "group_counts": group_counts,
    }


def _build_scene_from_ir(ir: dict[str, Any]) -> dict[str, int]:
    """Build scene from IR using the existing builder primitive functions."""
    import bpy  # type: ignore

    _clear_scene()
    _ensure_mm_units()

    plan = build_plan_from_ir(ir)
    legs = ir.get("legs", {}) if isinstance(ir.get("legs"), dict) else {}
    legs_params = legs.get("params", {}) if isinstance(legs.get("params"), dict) else None

    for primitive in plan.primitives:
        _create_primitive(primitive, legs_params=legs_params)

    for anchor in plan.anchors:
        _create_anchor(anchor.name, anchor.location_mm)

    bpy.context.view_layer.update()
    return {"primitives": len(plan.primitives), "anchors": len(plan.anchors)}


def main() -> int:
    run_id = make_run_id()
    run_tag = make_run_tag(run_id=run_id)
    out_dir = _resolve_out_dir(os.environ.get("DEBUG_OUT_DIR", "out/logs/runs"))
    ensure_dir(out_dir)

    debug_iters = _env_int("DEBUG_ITERS", 1, min_value=1)
    debug_autofix = _env_flag("DEBUG_AUTOFIX", default=False)
    debug_visualize = _env_flag("DEBUG_VISUALIZE", default=False)

    ir_source_path = ""
    ir_in_path = ""
    ir_out_path = ""
    ir_sha256_in = ""
    ir_sha256_out = ""
    metrics_log_path = ""
    metrics_sha256 = ""
    validation_log_path = ""

    source_ir: dict[str, Any] = {}
    current_ir: dict[str, Any] = {}
    iter_index = 0
    iterations: list[dict[str, Any]] = []
    patches_applied: list[dict[str, Any]] = []

    final_metrics: dict[str, Any] = {}
    final_validation: dict[str, Any] = {
        "score": 0.0,
        "penalty": 1.0,
        "problem_count": 0,
        "problems": [],
    }
    final_build_counts: dict[str, Any] = {"object_count": 0, "group_counts": {}}
    final_top_offender_pair: dict[str, Any] | None = None
    prev_metrics: dict[str, Any] | None = None
    autofix_context: dict[str, Any] = {}

    status = "error"
    error_text: str | None = None
    snapshot_blend_saved = "N/A"
    snapshot_png_saved = "N/A"
    debug_offenders_count = 0
    hard_offenders_count = 0
    joint_offenders_count = 0

    try:
        ir_path = _read_ir_path()
        if not ir_path:
            raise RuntimeError("IR path is required. Pass it after '--' or set IR_PATH.")

        ir_source_path = os.path.abspath(ir_path)
        with open(ir_source_path, "r", encoding="utf-8") as handle:
            loaded_ir = json.load(handle)
        if not isinstance(loaded_ir, dict):
            raise RuntimeError(f"Expected IR JSON object, got {type(loaded_ir).__name__}")

        source_ir = loaded_ir
        current_ir = deepcopy(source_ir)

        ir_in_path = save_json(os.path.join(out_dir, f"{run_tag}.ir_in.json"), source_ir)
        ir_sha256_in = sha256_json(source_ir)

        try:
            import bpy  # type: ignore  # noqa: F401
        except Exception as exc:
            raise RuntimeError("Blender Python runtime is required (module bpy is unavailable).") from exc

        for idx in range(1, debug_iters + 1):
            iter_index = idx
            plan_counts = _build_scene_from_ir(current_ir)
            metrics = collect_scene_metrics()
            validation_payload = validate(current_ir, metrics)
            build_counts = _extract_build_counts(metrics)

            iteration_patches: list[dict[str, Any]] = []
            if debug_autofix and idx < debug_iters:
                problems = validation_payload.get("problems", [])
                if not isinstance(problems, list):
                    problems = []
                updated_ir, iteration_patches = fix_ir(
                    current_ir,
                    problems,
                    metrics=metrics,
                    validation=validation_payload,
                    prev_metrics=prev_metrics,
                    context=autofix_context,
                )
                current_ir = updated_ir
                patches_applied.extend(iteration_patches)

            iterations.append(
                {
                    "iter_index": idx,
                    "plan_counts": plan_counts,
                    "build_counts": build_counts,
                    "validation": validation_payload,
                    "patches_applied": iteration_patches,
                }
            )
            final_metrics = metrics
            final_validation = validation_payload
            final_build_counts = build_counts
            prev_metrics = metrics

        final_top_offender_pair = _top_overlap_offender_pair(final_validation, final_metrics)
        if final_top_offender_pair and isinstance(final_metrics, dict):
            final_metrics["top_offender_pair"] = final_top_offender_pair

        if debug_visualize:
            try:
                from tools.blender.debug.visualize import apply_debug_visualization  # noqa: E402

                vis_payload = apply_debug_visualization(
                    validation=final_validation,
                    metrics=final_metrics,
                    snapshot_blend_path=str(os.environ.get("DEBUG_SNAPSHOT_BLEND", "")).strip() or None,
                    snapshot_png_path=str(os.environ.get("DEBUG_SNAPSHOT_PNG", "")).strip() or None,
                    camera_lens_mm=_safe_float(os.environ.get("DEBUG_SNAPSHOT_LENS_MM", "50"), 50.0),
                )
                debug_offenders_count = int(_safe_float(vis_payload.get("offender_count", 0), 0.0))
                hard_offenders_count = int(_safe_float(vis_payload.get("hard_offender_count", 0), 0.0))
                joint_offenders_count = int(_safe_float(vis_payload.get("joint_offender_count", 0), 0.0))
                snapshot_blend_saved = str(vis_payload.get("snapshot_blend_path", "")).strip() or "N/A"
                snapshot_png_saved = str(vis_payload.get("snapshot_png_path", "")).strip() or "N/A"
            except Exception as exc:
                print(f"DEBUG_VISUALIZE_ERROR:{exc}")

        score = _safe_float(final_validation.get("score", 0.0), 0.0)
        pass_result = score >= 0.95 and (not _has_severity_ge3(final_validation))
        status = "ok" if pass_result else "fail"

    except Exception as exc:
        status = "error"
        error_text = str(exc)

    ir_in_payload = source_ir if isinstance(source_ir, dict) else {}
    if not ir_in_path:
        ir_in_path = save_json(os.path.join(out_dir, f"{run_tag}.ir_in.json"), ir_in_payload)
    if not ir_sha256_in:
        ir_sha256_in = sha256_json(ir_in_payload)

    if not current_ir and isinstance(source_ir, dict):
        current_ir = deepcopy(source_ir)
    ir_out_payload = current_ir if isinstance(current_ir, dict) else {}
    ir_out_path = save_json(os.path.join(out_dir, f"{run_tag}.ir_out.json"), ir_out_payload)
    ir_sha256_out = sha256_json(ir_out_payload)

    metrics_log_payload: dict[str, Any] = {"kind": "metrics"}
    if isinstance(final_metrics, dict):
        metrics_log_payload.update(final_metrics)
    else:
        metrics_log_payload["metrics"] = final_metrics
    metrics_log_path = os.path.abspath(save_json(os.path.join(out_dir, f"{run_tag}.metrics.json"), metrics_log_payload))
    metrics_sha256 = sha256_file(metrics_log_path)
    validation_log_path = os.path.abspath(
        save_json(os.path.join(out_dir, f"{run_tag}.validation.json"), final_validation)
    )

    log_payload: dict[str, Any] = {
        "kind": "run",
        "status": status,
        "error": error_text,
        "run_id": run_id,
        "iter_index": int(iter_index),
        "ir_source_path": ir_source_path,
        "ir_in_path": ir_in_path,
        "ir_out_path": ir_out_path,
        "ir_sha256_in": ir_sha256_in,
        "ir_sha256_out": ir_sha256_out,
        "metrics_path": metrics_log_path,
        "metrics_sha256": metrics_sha256,
        "validation_path": validation_log_path,
        "build_counts": final_build_counts,
        "metrics": final_metrics,
        "validation": final_validation,
        "patches_applied": patches_applied,
        "iterations": iterations,
        "debug_autofix": bool(debug_autofix),
        "debug_iters": int(debug_iters),
        "debug_offenders_count": int(debug_offenders_count),
        "hard_offenders_count": int(hard_offenders_count),
        "joint_offenders_count": int(joint_offenders_count),
    }

    log_path = os.path.abspath(save_json(os.path.join(out_dir, f"{run_tag}.json"), log_payload))

    score = _safe_float(final_validation.get("score", 0.0), 0.0)
    problems = _problem_count(final_validation)
    top_pair = final_top_offender_pair or _top_overlap_offender_pair(final_validation, final_metrics)
    top_fixes = _top_fixes_payload(patches_applied, limit=5)
    ir_in_debug = os.path.abspath(ir_in_path) if ir_in_path else "N/A"
    ir_out_debug = os.path.abspath(ir_out_path) if ir_out_path else "N/A"
    metrics_debug = metrics_log_path if metrics_log_path else "N/A"

    print(f"status: {status}")
    print(f"iterations: {iter_index}")
    if top_pair:
        print(
            "top_offender_pair: "
            f"{top_pair.get('left')} vs {top_pair.get('right')} "
            f"volume_m3={_safe_float(top_pair.get('volume', 0.0), 0.0):.6g} "
            f"source={top_pair.get('source')}"
        )
    else:
        print("top_offender_pair: none")

    print(f"DEBUG_RUN_ID:{run_id}")
    print(f"DEBUG_RUN_LOG:{log_path}")
    print(f"DEBUG_RUN_METRICS:{metrics_debug}")
    print(f"DEBUG_IR_IN:{ir_in_debug}")
    print(f"DEBUG_IR_OUT:{ir_out_debug}")
    print(f"DEBUG_SCORE:{score:.6f}")
    print(f"DEBUG_PROBLEMS:{problems}")
    print(f"DEBUG_TOP_FIXES:{json.dumps(top_fixes, ensure_ascii=False)}")
    print(f"DEBUG_SNAPSHOT_BLEND_SAVED:{snapshot_blend_saved}")
    print(f"DEBUG_SNAPSHOT_PNG_SAVED:{snapshot_png_saved}")
    print(f"DEBUG_OFFENDERS_COUNT:{debug_offenders_count}")
    print(f"DEBUG_HARD_OFFENDERS_COUNT:{hard_offenders_count}")
    print(f"DEBUG_JOINT_OFFENDERS_COUNT:{joint_offenders_count}")

    if status == "error":
        return 3
    if score >= 0.95 and (not _has_severity_ge3(final_validation)):
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
