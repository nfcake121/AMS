"""Rule-based IR autofixes for debug validator problems."""

from __future__ import annotations

import json
import math
import os
from copy import deepcopy
from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def read_env_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def bbox_spans_m(bbox_world: Any) -> tuple[float, float, float]:
    if not isinstance(bbox_world, dict):
        return 0.0, 0.0, 0.0

    min_corner = bbox_world.get("min", [])
    max_corner = bbox_world.get("max", [])
    if not isinstance(min_corner, list) or not isinstance(max_corner, list):
        return 0.0, 0.0, 0.0
    if len(min_corner) < 3 or len(max_corner) < 3:
        return 0.0, 0.0, 0.0

    sx = max(0.0, _as_float(max_corner[0], 0.0) - _as_float(min_corner[0], 0.0))
    sy = max(0.0, _as_float(max_corner[1], 0.0) - _as_float(min_corner[1], 0.0))
    sz = max(0.0, _as_float(max_corner[2], 0.0) - _as_float(min_corner[2], 0.0))
    return float(sx), float(sy), float(sz)


def bbox_min_span_axis(bbox_world: Any) -> tuple[str, float]:
    sx, sy, sz = bbox_spans_m(bbox_world)
    axis, span = min(
        (("x", sx), ("y", sy), ("z", sz)),
        key=lambda item: float(item[1]),
    )
    return str(axis), float(span)


def mm_from_m(m: float) -> int:
    return int(math.ceil(max(0.0, float(m)) * 1000.0))


def _clamp(value: float, min_value: float | None = None, max_value: float | None = None) -> float:
    result = float(value)
    if min_value is not None:
        result = max(float(min_value), result)
    if max_value is not None:
        result = min(float(max_value), result)
    return result


def _verbose_enabled() -> bool:
    raw = str(os.getenv("DEBUG_AUTOFIX_VERBOSE", "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _vprint(enabled: bool, message: str) -> None:
    if enabled:
        print(message)


def _get_path(root: dict[str, Any], path: str) -> tuple[bool, Any]:
    keys = [k for k in path.split(".") if k]
    if not keys:
        return False, None

    node: Any = root
    for key in keys[:-1]:
        if not isinstance(node, dict):
            return False, None
        node = node.get(key)
        if node is None:
            return False, None

    if not isinstance(node, dict):
        return False, None
    leaf = keys[-1]
    if leaf not in node:
        return False, None
    return True, node.get(leaf)


def _set_path(root: dict[str, Any], path: str, new_value: Any, patches: list[dict[str, Any]]) -> bool:
    keys = [k for k in path.split(".") if k]
    if not keys:
        return False

    node: dict[str, Any] = root
    for key in keys[:-1]:
        next_node = node.get(key)
        if not isinstance(next_node, dict):
            next_node = {}
            node[key] = next_node
        node = next_node

    leaf = keys[-1]
    old_value = node.get(leaf)
    if old_value == new_value:
        return False

    node[leaf] = new_value
    patches.append({"path": path, "old": old_value, "new": new_value})
    return True


def _coerce_numeric(value: float, old_value: Any) -> int | float:
    if isinstance(old_value, bool):
        return int(round(value))
    if isinstance(old_value, int):
        return int(round(value))
    if isinstance(old_value, float):
        return float(value)
    rounded = round(float(value))
    if abs(float(value) - float(rounded)) < 1e-9:
        return int(rounded)
    return float(value)


def _inc_path_clamped(
    ir: dict[str, Any],
    path: str,
    delta: float,
    min_value: float,
    max_value: float,
    patches: list[dict[str, Any]],
) -> tuple[bool, int | float, Any]:
    exists, old_value = _get_path(ir, path)
    base_value = _as_float(old_value, 0.0) if exists else 0.0
    new_numeric = _clamp(base_value + float(delta), min_value=min_value, max_value=max_value)
    new_value = _coerce_numeric(new_numeric, old_value)
    changed = _set_path(ir, path, new_value, patches)
    return changed, new_value, old_value


def _log_pair_context(
    *,
    verbose: bool,
    code: str,
    pair: dict[str, Any] | None,
    axis: str,
    span_m: float,
    delta_mm: int,
    safety_mm: int,
) -> None:
    if not verbose:
        return
    left_name = str((pair or {}).get("left", ""))
    right_name = str((pair or {}).get("right", ""))
    _vprint(
        True,
        (
            f"[autofix] code={code} "
            f"pair={left_name}->{right_name} "
            f"axis={axis} span_m={span_m:.6g} "
            f"delta_mm={delta_mm} safety_mm={safety_mm}"
        ),
    )


def _log_patch_change(
    *,
    verbose: bool,
    code: str,
    path: str,
    old_value: Any,
    new_value: Any,
) -> None:
    if not verbose:
        return
    _vprint(True, f"[autofix] code={code} patch {path}: {old_value} -> {new_value}")


def _normalize_code(code: str) -> str:
    normalized = code.strip().upper()
    aliases = {
        "INTERSECTION_SLATS_FRAME": "OVERLAP_SLATS_FRAME",
        "INTERSECTION_SLATS_ARMS": "OVERLAP_SLATS_ARMS",
    }
    return aliases.get(normalized, normalized)


def _problem_details(problem: dict[str, Any]) -> dict[str, Any]:
    details = problem.get("details", {})
    if isinstance(details, dict):
        return details
    return {}


def _problem_total_volume(problem: dict[str, Any]) -> float:
    details = _problem_details(problem)
    for key in ("total_volume_m3", "volume_m3", "total_volume"):
        if key in details:
            return _as_float(details.get(key), 0.0)
    return 0.0


def _problem_pairs_top(problem: dict[str, Any]) -> list[dict[str, Any]]:
    details = _problem_details(problem)
    pairs = details.get("pairs_top", [])
    if not isinstance(pairs, list):
        return []
    return [pair for pair in pairs if isinstance(pair, dict)]


def get_top_pair(problem: dict[str, Any]) -> dict[str, Any] | None:
    pairs = _problem_pairs_top(problem)
    if not pairs:
        return None
    return pairs[0]


def _top_pair(problem: dict[str, Any], metrics: dict[str, Any] | None, overlap_key: str) -> dict[str, Any] | None:
    from_problem = get_top_pair(problem)
    if from_problem is not None:
        return from_problem

    pairs = _overlap_pairs(metrics, overlap_key)
    if not pairs:
        return None
    return max(pairs, key=lambda pair: _as_float(pair.get("volume", 0.0), 0.0))


def _safety_mm() -> int:
    return max(0, int(math.ceil(read_env_float("DEBUG_AUTOFIX_SAFETY_MM", 2.0))))


def _delta_from_pair(pair: dict[str, Any] | None, safety_mm: int) -> tuple[str, float, int]:
    if not isinstance(pair, dict):
        return "x", 0.0, 2
    axis, span_m = bbox_min_span_axis(pair.get("bbox_world"))
    if span_m <= 0.0:
        return axis, 0.0, 2
    delta_mm = mm_from_m(span_m) + int(max(0, safety_mm))
    return axis, float(span_m), int(max(1, delta_mm))


def _overlap_total_m3(metrics: dict[str, Any] | None, key: str) -> float | None:
    if not isinstance(metrics, dict):
        return None
    overlaps = metrics.get("overlaps", {})
    if not isinstance(overlaps, dict):
        return None
    entry = overlaps.get(key, {})
    if not isinstance(entry, dict):
        return None
    return float(_as_float(entry.get("total_volume", 0.0), 0.0))


def is_effective(
    prev_metrics: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    key: str,
    eps_m3: float | None = None,
) -> bool:
    eps = float(read_env_float("DEBUG_AUTOFIX_EFFECT_EPS_M3", 1e-8) if eps_m3 is None else eps_m3)
    raw_prev = _overlap_total_m3(prev_metrics, key)
    raw_new = _overlap_total_m3(metrics, key)
    if (raw_prev is None) and (raw_new is None):
        return False
    prev_overlap, new_overlap = _resolved_overlap_pair_m3(prev_metrics, metrics, key)
    if float(new_overlap) <= eps:
        return True
    return (float(prev_overlap) - float(new_overlap)) >= eps


def _format_overlap(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.6g}"


def _resolved_overlap_pair_m3(
    prev_metrics: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    key: str,
) -> tuple[float, float]:
    prev_overlap = _overlap_total_m3(prev_metrics, key)
    new_overlap = _overlap_total_m3(metrics, key)
    if prev_overlap is None and new_overlap is None:
        return 0.0, 0.0
    if prev_overlap is None:
        prev_overlap = float(_as_float(new_overlap, 0.0))
    if new_overlap is None:
        new_overlap = float(_as_float(prev_overlap, 0.0))
    return float(prev_overlap), float(new_overlap)


def _log_effect_decision(
    *,
    verbose: bool,
    code: str,
    key: str,
    prev_metrics: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    eps_m3: float,
) -> tuple[bool, float, float, float]:
    prev_overlap, new_overlap = _resolved_overlap_pair_m3(prev_metrics, metrics, key)
    delta_overlap = float(prev_overlap - new_overlap)
    effective = is_effective(prev_metrics, metrics, key, eps_m3=eps_m3)
    if verbose:
        _vprint(
            True,
            (
                f"[autofix] code={code} overlap_key={key} "
                f"prev_overlap={_format_overlap(prev_overlap)} "
                f"new_overlap={_format_overlap(new_overlap)} "
                f"delta_overlap={delta_overlap:.6g} "
                f"effect_eps_m3={float(eps_m3):.6g} "
                f"effective={effective}"
            ),
        )
    return effective, prev_overlap, new_overlap, delta_overlap


def _overlap_entry(metrics: dict[str, Any] | None, key: str) -> dict[str, Any]:
    if not isinstance(metrics, dict):
        return {}
    overlaps = metrics.get("overlaps", {})
    if not isinstance(overlaps, dict):
        return {}
    entry = overlaps.get(key, {})
    if not isinstance(entry, dict):
        return {}
    return entry


def _overlap_pairs(metrics: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    entry = _overlap_entry(metrics, key)
    pairs = entry.get("pairs", [])
    if not isinstance(pairs, list):
        return []
    return [pair for pair in pairs if isinstance(pair, dict)]


def _overlap_total(metrics: dict[str, Any] | None, key: str, problem: dict[str, Any]) -> float:
    entry = _overlap_entry(metrics, key)
    total = _as_float(entry.get("total_volume", 0.0), 0.0)
    if total > 0.0:
        return total
    return _problem_total_volume(problem)


def _fix_slats_not_bent(ir: dict[str, Any], patches: list[dict[str, Any]]) -> None:
    slats = ir.get("slats", {})
    if not isinstance(slats, dict):
        slats = {}
        ir["slats"] = slats

    old_arc = _as_float(slats.get("arc_height_mm", 0.0), 0.0)
    new_arc = _clamp(old_arc + 5.0, max_value=60.0)
    _set_path(ir, "slats.arc_height_mm", new_arc, patches)

    if "subdiv_cuts" in slats:
        old_cuts = _as_int(slats.get("subdiv_cuts", 0), 0)
        new_cuts = int(_clamp(float(old_cuts + 8), min_value=0.0, max_value=256.0))
        _set_path(ir, "slats.subdiv_cuts", new_cuts, patches)


def _fix_back_slats_not_bent(ir: dict[str, Any], patches: list[dict[str, Any]]) -> None:
    back_support = ir.get("back_support", {})
    if not isinstance(back_support, dict):
        back_support = {}
        ir["back_support"] = back_support
    slats = back_support.get("slats", {})
    if not isinstance(slats, dict):
        slats = {}
        back_support["slats"] = slats

    old_arc = _as_float(slats.get("arc_height_mm", 0.0), 0.0)
    new_arc = _clamp(old_arc + 3.0, max_value=40.0)
    _set_path(ir, "back_support.slats.arc_height_mm", new_arc, patches)


def _fix_overlap_slats_frame(
    ir: dict[str, Any],
    patches: list[dict[str, Any]],
    metrics: dict[str, Any] | None,
    prev_metrics: dict[str, Any] | None,
    problem: dict[str, Any],
    verbose: bool,
) -> None:
    code = "OVERLAP_SLATS_FRAME"
    overlap_key = "slats_vs_frame"
    pair = _top_pair(problem, metrics, "slats_vs_frame")
    right_name = str((pair or {}).get("right", "")).lower()
    safety_mm = _safety_mm()
    axis, span_m, delta_mm = _delta_from_pair(pair, safety_mm=safety_mm)
    effect_eps_m3 = read_env_float("DEBUG_AUTOFIX_EFFECT_EPS_M3", 1e-8)
    _log_pair_context(
        verbose=verbose,
        code=code,
        pair=pair,
        axis=axis,
        span_m=span_m,
        delta_mm=delta_mm,
        safety_mm=safety_mm,
    )
    effective, _, _, _ = _log_effect_decision(
        verbose=verbose,
        code=code,
        key=overlap_key,
        prev_metrics=prev_metrics,
        metrics=metrics,
        eps_m3=effect_eps_m3,
    )

    has_mount_offset, _ = _get_path(ir, "slats.mount_offset_mm")
    has_rail_inset, _ = _get_path(ir, "slats.rail_inset_mm")

    clearance_delta = float(max(1, int(math.ceil(float(delta_mm) / 4.0))))
    mount_delta = float(max(1, int(math.ceil(float(delta_mm) / 2.0))))
    rail_inset_delta = float(max(1, int(math.ceil(float(delta_mm) / 2.0))))
    safe_fallback_clearance = float(2 if int(delta_mm) >= 4 else 1)

    Strategy = tuple[str, str, float, float, float, bool]

    def _apply_strategy(strategy: Strategy, step: str) -> bool:
        strategy_name, path, delta, min_value, max_value, require_existing = strategy
        if require_existing:
            exists, _ = _get_path(ir, path)
            if not exists:
                if verbose:
                    _vprint(
                        True,
                        f"[autofix] code={code} skip_strategy={strategy_name} reason=missing_path path={path}",
                    )
                return False
        changed, new_value, old_value = _inc_path_clamped(
            ir,
            path,
            float(delta),
            float(min_value),
            float(max_value),
            patches,
        )
        if changed:
            _log_patch_change(
                verbose=verbose,
                code=code,
                path=path,
                old_value=old_value,
                new_value=new_value,
            )
        if verbose:
            _vprint(
                True,
                f"[autofix] code={code} chosen_strategy={strategy_name} chosen_param={path} step={step}",
            )
        return True

    group = "other"
    if right_name.startswith("rail_") or ("rail_left" in right_name) or ("rail_right" in right_name):
        group = "rail"
    elif right_name.startswith("beam_cross_"):
        group = "beam"

    primary: Strategy
    secondary: Strategy | None = None
    fallback: Strategy = (
        "safe_fallback_clearance",
        "slats.clearance_mm",
        safe_fallback_clearance,
        0.0,
        12.0,
        False,
    )

    if group == "rail":
        if axis == "x":
            primary = ("rail_axis_x_margin_x", "slats.margin_x_mm", float(delta_mm), 0.0, 80.0, False)
            secondary = ("rail_axis_x_rail_inset", "slats.rail_inset_mm", rail_inset_delta, 0.0, 20.0, True)
        elif axis == "y":
            primary = ("rail_axis_y_margin_y", "slats.margin_y_mm", float(delta_mm), 0.0, 120.0, False)
        else:  # axis == "z"
            if has_mount_offset:
                primary = ("rail_axis_z_mount_offset", "slats.mount_offset_mm", mount_delta, 0.0, 80.0, True)
                secondary = ("rail_axis_z_clearance", "slats.clearance_mm", clearance_delta, 0.0, 12.0, False)
            else:
                primary = ("rail_axis_z_clearance", "slats.clearance_mm", clearance_delta, 0.0, 12.0, False)

    elif group == "beam":
        if axis == "y":
            primary = ("beam_axis_y_margin_y", "slats.margin_y_mm", float(delta_mm), 0.0, 120.0, False)
        elif axis == "z":
            if has_mount_offset:
                primary = ("beam_axis_z_mount_offset", "slats.mount_offset_mm", mount_delta, 0.0, 80.0, True)
                secondary = ("beam_axis_z_clearance", "slats.clearance_mm", clearance_delta, 0.0, 12.0, False)
            else:
                primary = ("beam_axis_z_clearance", "slats.clearance_mm", clearance_delta, 0.0, 12.0, False)
        else:  # axis == "x"
            primary = ("beam_axis_x_margin_x_fallback", "slats.margin_x_mm", float(delta_mm), 0.0, 80.0, False)

    else:
        primary = ("other_axis_clearance", "slats.clearance_mm", clearance_delta, 0.0, 12.0, False)

    _apply_strategy(primary, step="primary")
    if effective:
        return

    if verbose:
        _vprint(True, f"[autofix] code={code} no_effect_after_primary effective=False")
    secondary_applied = _apply_strategy(secondary, step="secondary") if secondary is not None else False
    if verbose and (secondary is None):
        _vprint(True, f"[autofix] code={code} secondary_strategy=none")
    if not secondary_applied and (secondary is not None) and verbose:
        _vprint(True, f"[autofix] code={code} secondary_strategy_skipped")

    if verbose:
        _vprint(True, f"[autofix] code={code} no_effect_after_secondary effective=False fallback=true")
    _apply_strategy(fallback, step="fallback")


def _fix_overlap_back_slats_frame(
    ir: dict[str, Any],
    patches: list[dict[str, Any]],
    metrics: dict[str, Any] | None,
    prev_metrics: dict[str, Any] | None,
    problem: dict[str, Any],
    context: dict[str, Any] | None,
    verbose: bool,
) -> None:
    del context
    code = "OVERLAP_BACK_SLATS_FRAME"
    overlap_key = "back_slats_vs_frame"
    pair = _top_pair(problem, metrics, "back_slats_vs_frame")
    right_name = str((pair or {}).get("right", "")).lower()
    left_name = str((pair or {}).get("left", ""))
    safety_mm = _safety_mm()
    axis, span_m, delta_mm = _delta_from_pair(pair, safety_mm=safety_mm)
    effect_eps_m3 = read_env_float("DEBUG_AUTOFIX_EFFECT_EPS_M3", 1e-8)
    _log_pair_context(
        verbose=verbose,
        code=code,
        pair=pair,
        axis=axis,
        span_m=span_m,
        delta_mm=delta_mm,
        safety_mm=safety_mm,
    )
    effective, _, _, _ = _log_effect_decision(
        verbose=verbose,
        code=code,
        key=overlap_key,
        prev_metrics=prev_metrics,
        metrics=metrics,
        eps_m3=effect_eps_m3,
    )

    Strategy = tuple[str, str, float, float, float, bool]

    def _apply_strategy(strategy: Strategy, step: str) -> bool:
        strategy_name, path, delta, min_value, max_value, require_existing = strategy
        if require_existing:
            exists, _ = _get_path(ir, path)
            if not exists:
                if verbose:
                    _vprint(
                        True,
                        f"[autofix] code={code} skip_strategy={strategy_name} reason=missing_path path={path}",
                    )
                return False
        changed, new_value, old_value = _inc_path_clamped(
            ir,
            path,
            float(delta),
            float(min_value),
            float(max_value),
            patches,
        )
        if changed:
            _log_patch_change(
                verbose=verbose,
                code=code,
                path=path,
                old_value=old_value,
                new_value=new_value,
            )
        if verbose:
            _vprint(
                True,
                (
                    f"[autofix] code={code} chosen_strategy={strategy_name} "
                    f"chosen_param={path} step={step} pair={left_name}->{right_name}"
                ),
            )
        return True

    offset_delta = float(max(1, int(math.ceil(float(delta_mm) / 2.0))))
    has_offset_y, _ = _get_path(ir, "back_support.offset_y_mm")

    primary: Strategy
    secondary: Strategy | None = None

    if axis == "y":
        if has_offset_y:
            primary = ("axis_y_offset_y_primary", "back_support.offset_y_mm", offset_delta, -50.0, 80.0, True)
        else:
            primary = ("axis_y_margin_z_primary_no_offset", "back_support.margin_z_mm", float(delta_mm), 0.0, 120.0, False)
        secondary = ("axis_y_margin_x_fallback", "back_support.margin_x_mm", float(delta_mm), 0.0, 80.0, False)
    elif axis == "z":
        primary = ("axis_z_margin_z_primary", "back_support.margin_z_mm", float(delta_mm), 0.0, 80.0, False)
        secondary = ("axis_z_offset_y_secondary", "back_support.offset_y_mm", offset_delta, -50.0, 80.0, True)
    else:  # axis == "x"
        primary = ("axis_x_margin_x_primary", "back_support.margin_x_mm", float(delta_mm), 0.0, 80.0, False)
        secondary = ("axis_x_margin_z_secondary", "back_support.margin_z_mm", float(delta_mm), 0.0, 120.0, False)

    _apply_strategy(primary, step="primary")
    if effective:
        return

    if verbose:
        _vprint(True, f"[autofix] code={code} no_effect_after_primary effective=False")
    if secondary is None:
        if verbose:
            _vprint(True, f"[autofix] code={code} secondary_strategy=none")
        return
    secondary_applied = _apply_strategy(secondary, step="secondary")
    if not secondary_applied and verbose:
        _vprint(True, f"[autofix] code={code} secondary_strategy_skipped")


def _fix_overlap_slats_arms(ir: dict[str, Any], patches: list[dict[str, Any]]) -> None:
    _inc_path_clamped(ir, "slats.margin_x_mm", 5.0, 0.0, 200.0, patches)


def _resolve_problems(
    problems: list[dict[str, Any]] | None,
    validation: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if isinstance(problems, list):
        return [item for item in problems if isinstance(item, dict)]
    if isinstance(validation, dict):
        candidate = validation.get("problems", [])
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def fix_ir(
    ir: dict[str, Any],
    problems: list[dict[str, Any]] | None = None,
    *,
    metrics: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    prev_metrics: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply MVP debug autofixes and return (new_ir, patches_applied)."""
    patched = deepcopy(ir)
    patches_applied: list[dict[str, Any]] = []
    handled_codes: set[str] = set()
    resolved_problems = _resolve_problems(problems, validation)
    verbose = _verbose_enabled()

    for problem in resolved_problems:
        code = _normalize_code(str(problem.get("code", "")))
        if not code or code in handled_codes:
            continue

        if code == "SLATS_NOT_BENT":
            _fix_slats_not_bent(patched, patches_applied)
            handled_codes.add(code)
            continue

        if code == "BACK_SLATS_NOT_BENT":
            _fix_back_slats_not_bent(patched, patches_applied)
            handled_codes.add(code)
            continue

        if code == "OVERLAP_SLATS_FRAME":
            _fix_overlap_slats_frame(
                patched,
                patches_applied,
                metrics=metrics,
                prev_metrics=prev_metrics,
                problem=problem,
                verbose=verbose,
            )
            handled_codes.add(code)
            continue

        if code == "OVERLAP_BACK_SLATS_FRAME":
            _fix_overlap_back_slats_frame(
                patched,
                patches_applied,
                metrics=metrics,
                prev_metrics=prev_metrics,
                problem=problem,
                context=context,
                verbose=verbose,
            )
            handled_codes.add(code)
            continue

        if code == "OVERLAP_SLATS_ARMS":
            _fix_overlap_slats_arms(patched, patches_applied)
            handled_codes.add(code)

    return patched, patches_applied


if __name__ == "__main__":
    os.environ["DEBUG_AUTOFIX_SAFETY_MM"] = str(_as_int(os.getenv("DEBUG_AUTOFIX_SAFETY_MM", 2), 2))
    os.environ["DEBUG_AUTOFIX_EFFECT_EPS_M3"] = str(read_env_float("DEBUG_AUTOFIX_EFFECT_EPS_M3", 1e-8))

    ir_base: dict[str, Any] = {
        "slats": {
            "margin_x_mm": 40,
            "margin_y_mm": 55,
            "clearance_mm": 4,
            "mount_offset_mm": 3,
            "rail_inset_mm": 3,
        }
    }

    problem_axis_z = {
        "code": "OVERLAP_SLATS_FRAME",
        "details": {
            "pairs_top": [
                {
                    "left": "slat_1",
                    "right": "rail_left",
                    "volume": 1.0e-4,
                    "bbox_world": {
                        "min": [0.0, 0.0, 0.0],
                        "max": [0.010, 0.008, 0.001],
                    },
                }
            ]
        },
    }
    pair_z = get_top_pair(problem_axis_z)
    axis_z, span_z, delta_z = _delta_from_pair(pair_z, safety_mm=_safety_mm())
    before_margin_x_z = _as_int(ir_base["slats"]["margin_x_mm"], 0)
    before_clearance_z = _as_int(ir_base["slats"]["clearance_mm"], 0)
    before_mount_z = _as_int(ir_base["slats"]["mount_offset_mm"], 0)
    fixed_ir_z, patches_z = fix_ir(
        ir_base,
        problems=[problem_axis_z],
        metrics={"overlaps": {"slats_vs_frame": {"total_volume": 1.0e-3}}},
        prev_metrics=None,
        context=None,
        validation=None,
    )
    after_margin_x_z = _as_int(fixed_ir_z.get("slats", {}).get("margin_x_mm", 0), 0)
    after_clearance_z = _as_int(fixed_ir_z.get("slats", {}).get("clearance_mm", 0), 0)
    after_mount_z = _as_int(fixed_ir_z.get("slats", {}).get("mount_offset_mm", 0), 0)
    primary_path_z = str((patches_z[0] if patches_z else {}).get("path", ""))
    ok_axis_z = bool(
        (axis_z == "z")
        and (primary_path_z in {"slats.clearance_mm", "slats.mount_offset_mm"})
        and (after_margin_x_z == before_margin_x_z)
        and ((after_clearance_z > before_clearance_z) or (after_mount_z > before_mount_z))
    )

    print(f"SELF_TEST_SLATS_RAIL_AXIS_Z axis={axis_z} span_m={span_z:.6g} delta_mm={delta_z}")
    print(
        "SELF_TEST_SLATS_RAIL_AXIS_Z "
        f"margin_x before={before_margin_x_z} after={after_margin_x_z} "
        f"clearance before={before_clearance_z} after={after_clearance_z} "
        f"mount_offset before={before_mount_z} after={after_mount_z}"
    )
    print(f"SELF_TEST_SLATS_RAIL_AXIS_Z primary_patch={primary_path_z} ok={ok_axis_z}")
    print(json.dumps(patches_z, ensure_ascii=False, indent=2))

    problem_axis_x = {
        "code": "OVERLAP_SLATS_FRAME",
        "details": {
            "pairs_top": [
                {
                    "left": "slat_2",
                    "right": "rail_right",
                    "volume": 1.0e-4,
                    "bbox_world": {
                        "min": [0.0, 0.0, 0.0],
                        "max": [0.001, 0.010, 0.020],
                    },
                }
            ]
        },
    }
    pair_x = get_top_pair(problem_axis_x)
    axis_x, span_x, delta_x = _delta_from_pair(pair_x, safety_mm=_safety_mm())
    before_margin_x = _as_int(ir_base["slats"]["margin_x_mm"], 0)
    fixed_ir_x, patches_x = fix_ir(
        ir_base,
        problems=[problem_axis_x],
        metrics={"overlaps": {"slats_vs_frame": {"total_volume": 1.0e-3}}},
        prev_metrics=None,
        context=None,
        validation=None,
    )
    after_margin_x = _as_int(fixed_ir_x.get("slats", {}).get("margin_x_mm", 0), 0)
    primary_path_x = str((patches_x[0] if patches_x else {}).get("path", ""))
    ok_axis_x = bool((axis_x == "x") and (primary_path_x == "slats.margin_x_mm") and (after_margin_x > before_margin_x))

    print(f"SELF_TEST_SLATS_RAIL_AXIS_X axis={axis_x} span_m={span_x:.6g} delta_mm={delta_x}")
    print(f"SELF_TEST_SLATS_RAIL_AXIS_X margin_x before={before_margin_x} after={after_margin_x}")
    print(f"SELF_TEST_SLATS_RAIL_AXIS_X primary_patch={primary_path_x} ok={ok_axis_x}")
    print(json.dumps(patches_x, ensure_ascii=False, indent=2))
