"""Batch Blender debug runs for a directory of IR JSON files.

Usage:
  blender --background --python tools/blender/batch_debug_run.py -- <input_dir> <output_dir>
"""

from __future__ import annotations

import csv
import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.blender import debug_run as single_debug_run  # noqa: E402
from tools.blender.debug.autofix import fix_ir  # noqa: E402
from tools.blender.debug.io import ensure_dir, save_json  # noqa: E402
from tools.blender.debug.metrics import collect_scene_metrics  # noqa: E402
from tools.blender.debug.validators import validate  # noqa: E402
from tools.blender.debug.visualize import apply_debug_visualization  # noqa: E402


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    return max(int(min_value), int(value))


def _resolve_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(REPO_ROOT) / candidate


def _parse_args() -> tuple[Path, Path]:
    args: list[str]
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        args = [str(item).strip() for item in sys.argv[idx + 1 :]]
    else:
        args = [str(item).strip() for item in sys.argv[1:]]

    if len(args) >= 2:
        return _resolve_path(args[0]), _resolve_path(args[1])

    env_in = str(os.environ.get("DEBUG_BATCH_INPUT_DIR", "")).strip()
    env_out = str(os.environ.get("DEBUG_BATCH_OUTPUT_DIR", "")).strip()
    if env_in and env_out:
        return _resolve_path(env_in), _resolve_path(env_out)

    raise RuntimeError(
        "Usage: blender --background --python tools/blender/batch_debug_run.py -- <input_dir> <output_dir>"
    )


def _looks_like_ir(payload: Any) -> bool:
    return isinstance(payload, dict) and any(
        key in payload for key in ("slats", "back_support", "seat_width_mm", "seat_depth_mm")
    )


def _load_ir(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not _looks_like_ir(payload):
        raise ValueError(f"{path.name}: payload is not an IR JSON object")
    return payload


def _overlap_total(metrics: dict[str, Any], key: str) -> float:
    overlaps = metrics.get("overlaps", {})
    if not isinstance(overlaps, dict):
        return 0.0
    entry = overlaps.get(key, {})
    if not isinstance(entry, dict):
        return 0.0
    return float(_safe_float(entry.get("total_volume", 0.0), 0.0))


def _run_one_ir(
    ir_path: Path,
    *,
    debug_iters: int,
    debug_autofix: bool,
    snapshot_blend_dir: Path | None,
    camera_lens_mm: float,
) -> dict[str, Any]:
    source_ir = _load_ir(ir_path)
    current_ir = deepcopy(source_ir)

    prev_metrics: dict[str, Any] | None = None
    autofix_context: dict[str, Any] = {}
    patches_applied: list[dict[str, Any]] = []

    final_metrics: dict[str, Any] = {}
    final_validation: dict[str, Any] = {"score": 0.0, "problem_count": 0, "problems": []}

    for idx in range(1, debug_iters + 1):
        single_debug_run._build_scene_from_ir(current_ir)
        metrics = collect_scene_metrics()
        validation_payload = validate(current_ir, metrics)

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

        final_metrics = metrics
        final_validation = validation_payload
        prev_metrics = metrics

    top_pair = single_debug_run._top_overlap_offender_pair(final_validation, final_metrics)
    if top_pair and isinstance(final_metrics, dict):
        final_metrics["top_offender_pair"] = top_pair

    if snapshot_blend_dir is not None:
        ensure_dir(str(snapshot_blend_dir))
        blend_path = snapshot_blend_dir / f"{ir_path.stem}.blend"
        apply_debug_visualization(
            validation=final_validation,
            metrics=final_metrics,
            snapshot_blend_path=str(blend_path),
            snapshot_png_path=None,
            camera_lens_mm=float(camera_lens_mm),
        )

    return {
        "ir_path": str(ir_path),
        "ir_out": current_ir,
        "metrics": final_metrics,
        "validation": final_validation,
        "patches_applied": patches_applied,
    }


def _write_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "file_name",
        "debug_score",
        "problems_count",
        "overlaps_slats_m3",
        "overlaps_back_m3",
        "fixes_applied_count",
    ]
    ensure_dir(str(path.parent))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    try:
        import bpy  # type: ignore  # noqa: F401
    except Exception as exc:
        print(f"BATCH_DEBUG_ERROR:bpy unavailable ({exc})", file=sys.stderr)
        return 3

    try:
        input_dir, output_dir = _parse_args()
    except Exception as exc:
        print(f"BATCH_DEBUG_ERROR:{exc}", file=sys.stderr)
        return 2

    if not input_dir.exists() or not input_dir.is_dir():
        print(f"BATCH_DEBUG_ERROR: input_dir not found: {input_dir}", file=sys.stderr)
        return 2

    ensure_dir(str(output_dir))
    debug_iters = _env_int("DEBUG_ITERS", 1, min_value=1)
    debug_autofix = _env_flag("DEBUG_AUTOFIX", default=False)
    camera_lens_mm = float(_safe_float(os.environ.get("DEBUG_SNAPSHOT_LENS_MM", "50"), 50.0))

    snapshot_blend_dir_raw = str(os.environ.get("DEBUG_SNAPSHOT_BLEND_DIR", "")).strip()
    snapshot_blend_dir = _resolve_path(snapshot_blend_dir_raw) if snapshot_blend_dir_raw else None

    ir_files = sorted(input_dir.glob("*.json"))
    if not ir_files:
        print(f"BATCH_DEBUG_FILES:0")
        print(f"BATCH_DEBUG_SUMMARY:{output_dir / 'summary.csv'}")
        return 0

    summary_rows: list[dict[str, Any]] = []
    for ir_path in ir_files:
        print(f"BATCH_DEBUG_RUN:{ir_path.name}")
        try:
            result = _run_one_ir(
                ir_path,
                debug_iters=debug_iters,
                debug_autofix=debug_autofix,
                snapshot_blend_dir=snapshot_blend_dir,
                camera_lens_mm=camera_lens_mm,
            )
            metrics = result.get("metrics", {})
            validation = result.get("validation", {})
            patches_applied = result.get("patches_applied", [])

            out_prefix = output_dir / ir_path.stem
            save_json(str(out_prefix.with_suffix(".validation.json")), validation)
            save_json(str(out_prefix.with_suffix(".metrics.json")), metrics)
            save_json(str(out_prefix.with_suffix(".ir_out.json")), result.get("ir_out", {}))

            summary_rows.append(
                {
                    "file_name": ir_path.name,
                    "debug_score": f"{_safe_float(validation.get('score', 0.0), 0.0):.6f}",
                    "problems_count": int(_safe_int(validation.get("problem_count", 0), 0)),
                    "overlaps_slats_m3": f"{_overlap_total(metrics, 'slats_vs_frame'):.6g}",
                    "overlaps_back_m3": f"{_overlap_total(metrics, 'back_slats_vs_frame'):.6g}",
                    "fixes_applied_count": len(patches_applied) if isinstance(patches_applied, list) else 0,
                }
            )
        except Exception as exc:
            print(f"BATCH_DEBUG_ERROR file={ir_path.name}: {exc}", file=sys.stderr)
            summary_rows.append(
                {
                    "file_name": ir_path.name,
                    "debug_score": "0.000000",
                    "problems_count": -1,
                    "overlaps_slats_m3": "0",
                    "overlaps_back_m3": "0",
                    "fixes_applied_count": 0,
                }
            )

    summary_path = output_dir / "summary.csv"
    _write_summary_csv(summary_path, summary_rows)
    print(f"BATCH_DEBUG_FILES:{len(summary_rows)}")
    print(f"BATCH_DEBUG_SUMMARY:{summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
