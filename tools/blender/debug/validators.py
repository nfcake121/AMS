"""Validation rules and scoring for debug metrics."""

from __future__ import annotations

from typing import Any


DEFAULT_OVERLAP_EPS = 1e-9
DEFAULT_BEND_DELTA_EPS = 1e-5
DEFAULT_OVERLAP_K = 100.0


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _group_count(metrics: dict[str, Any], key: str) -> int:
    groups = metrics.get("groups", {})
    group = groups.get(key, {})
    return _as_int(group.get("count", 0), 0)


def _overlap_total(metrics: dict[str, Any], key: str) -> float:
    overlaps = metrics.get("overlaps", {})
    entry = overlaps.get(key, {})
    return _as_float(entry.get("total_volume", 0.0), 0.0)


def _canonical_arms_type(ir: dict[str, Any]) -> str:
    arms = ir.get("arms", {})
    if not isinstance(arms, dict):
        return "none"
    value = arms.get("type", "none")
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower()
    if normalized in {"none", "left", "right", "both"}:
        return normalized
    return "none"


def _slats_not_bent(
    metrics: dict[str, Any],
    bend_delta_eps: float,
) -> list[dict[str, Any]]:
    offenders: list[dict[str, Any]] = []
    for obj in metrics.get("objects", []):
        if not isinstance(obj, dict):
            continue
        name = str(obj.get("name", ""))
        if not name.startswith("slat_"):
            continue

        modifiers = obj.get("modifiers", [])
        if not isinstance(modifiers, list):
            continue
        bend_modifiers = [
            mod
            for mod in modifiers
            if isinstance(mod, dict)
            and str(mod.get("type", "")) == "SIMPLE_DEFORM"
            and str(mod.get("deform_method", "")).upper() == "BEND"
        ]
        if not bend_modifiers:
            continue

        bbox_delta = obj.get("bbox_delta", {})
        if not isinstance(bbox_delta, dict):
            bbox_delta = {}

        for mod in bend_modifiers:
            axis = str(mod.get("axis", "Z")).lower()
            if axis not in {"x", "y", "z"}:
                axis = "z"
            delta = abs(_as_float(bbox_delta.get(axis, 0.0), 0.0))
            if delta <= bend_delta_eps:
                offenders.append(
                    {
                        "object": name,
                        "axis": axis.upper(),
                        "delta_m": delta,
                        "angle_rad": _as_float(mod.get("angle", 0.0), 0.0),
                    }
                )
                break
    return offenders


def validate(
    metrics: dict[str, Any],
    ir: dict[str, Any],
    overlap_eps: float = DEFAULT_OVERLAP_EPS,
    bend_delta_eps: float = DEFAULT_BEND_DELTA_EPS,
    overlap_k: float = DEFAULT_OVERLAP_K,
) -> dict[str, Any]:
    """Validate build metrics against IR expectations and return score."""
    problems: list[dict[str, Any]] = []

    arms_type = _canonical_arms_type(ir)
    arm_count = _group_count(metrics, "arm_")
    if arms_type != "none" and arm_count == 0:
        problems.append(
            {
                "code": "MISSING_ARMS",
                "severity": 3,
                "details": {"arms_type": arms_type, "arm_objects": arm_count},
            }
        )

    slats = ir.get("slats", {})
    slats_enabled = bool(slats.get("enabled", False)) if isinstance(slats, dict) else False
    expected_slats = _as_int(slats.get("count", 14), 14) if isinstance(slats, dict) else 14
    actual_slats = _group_count(metrics, "slat_")
    if slats_enabled and expected_slats != actual_slats:
        problems.append(
            {
                "code": "SLATS_COUNT_MISMATCH",
                "severity": 2,
                "details": {"expected": expected_slats, "actual": actual_slats},
            }
        )

    not_bent = _slats_not_bent(metrics, bend_delta_eps=bend_delta_eps)
    if not_bent:
        problems.append(
            {
                "code": "SLATS_NOT_BENT",
                "severity": 2,
                "details": {"objects": not_bent, "bend_delta_eps_m": bend_delta_eps},
            }
        )

    overlap_slats_arms = _overlap_total(metrics, "slats_vs_arms")
    if overlap_slats_arms > overlap_eps:
        problems.append(
            {
                "code": "INTERSECTION_SLATS_ARMS",
                "severity": 3,
                "details": {
                    "volume_m3": overlap_slats_arms,
                    "eps_m3": overlap_eps,
                },
            }
        )

    overlap_slats_frame = _overlap_total(metrics, "slats_vs_frame")
    if overlap_slats_frame > overlap_eps:
        problems.append(
            {
                "code": "INTERSECTION_SLATS_FRAME",
                "severity": 3,
                "details": {
                    "volume_m3": overlap_slats_frame,
                    "eps_m3": overlap_eps,
                },
            }
        )

    back_support = ir.get("back_support", {})
    back_mode = ""
    if isinstance(back_support, dict):
        mode = back_support.get("mode", "")
        if isinstance(mode, str):
            back_mode = mode.strip().lower()

    if back_mode:
        objects = metrics.get("objects", [])
        back_pref_count = 0
        if isinstance(objects, list):
            back_pref_count = sum(
                1
                for obj in objects
                if isinstance(obj, dict) and str(obj.get("name", "")).startswith("back_")
            )
        back_slat_count = _group_count(metrics, "back_slat_")
        if back_slat_count == 0 and back_pref_count == 0:
            problems.append(
                {
                    "code": "BACK_NOT_PRESENT",
                    "severity": 2,
                    "details": {"mode": back_mode, "back_pref_count": back_pref_count},
                }
            )

    overlap_back_slats_frame = _overlap_total(metrics, "back_slats_vs_frame")
    severity_sum = sum(_as_int(problem.get("severity", 1), 1) for problem in problems)
    overlap_sum = overlap_slats_arms + overlap_slats_frame + overlap_back_slats_frame
    penalty = min(1.0, (severity_sum * 0.1) + (overlap_sum * overlap_k))
    score = 1.0 - penalty

    return {
        "score": float(max(0.0, round(score, 6))),
        "penalty": {
            "severity_sum": severity_sum,
            "overlap_sum_m3": float(overlap_sum),
            "overlap_k": float(overlap_k),
            "value": float(round(penalty, 6)),
        },
        "problem_count": len(problems),
        "problems": problems,
    }

