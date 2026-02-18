"""Validation rules and scoring for Blender debug metrics."""

from __future__ import annotations

import json
import os
import sys
from typing import Any


DEFAULT_OVERLAP_EPS = 1e-8
BEND_MOD_ANGLE_EPS = 1e-6


def _read_env_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _read_env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return int(default)


BEND_EPS_M = _read_env_float("DEBUG_BEND_EPS_M", 0.002)
CLEARANCE_EPS_M = _read_env_float("DEBUG_CLEARANCE_EPS_M", 0.003)
JOINT_OVERLAP_ALLOWANCE_MM = _read_env_float("DEBUG_JOINT_OVERLAP_ALLOWANCE_MM", 2.0)
MOD_EFFECT_EPS_M = _read_env_float("DEBUG_MOD_EFFECT_EPS_M", 0.001)
MOD_EFFECT_VERTS_EPS = _read_env_int("DEBUG_MOD_EFFECT_VERTS_EPS", 4)


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


def _looks_like_metrics(payload: Any) -> bool:
    return isinstance(payload, dict) and any(k in payload for k in ("objects", "groups", "overlaps"))


def _looks_like_ir(payload: Any) -> bool:
    return isinstance(payload, dict) and any(k in payload for k in ("slats", "back_support", "seat_width_mm"))


def _normalize_validate_args(first: dict[str, Any], second: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Allow both validate(ir, metrics) and legacy validate(metrics, ir)."""
    if _looks_like_metrics(first) and _looks_like_ir(second):
        return second, first
    return first, second


def _objects_by_prefix(metrics: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    objects = metrics.get("objects", [])
    if not isinstance(objects, list):
        return []
    lowered = prefix.lower()
    return [
        obj
        for obj in objects
        if isinstance(obj, dict) and str(obj.get("name", "")).lower().startswith(lowered)
    ]


def _mesh_objects_by_prefix(metrics: dict[str, Any], prefix: str) -> list[dict[str, Any]]:
    return [
        obj
        for obj in _objects_by_prefix(metrics, prefix)
        if str(obj.get("type", "")).strip().upper() == "MESH"
    ]


def _bend_mod_summary(obj: dict[str, Any]) -> tuple[bool, float]:
    """Return (has_bend_modifier, max_abs_bend_angle)."""
    max_abs_angle = 0.0
    has_bend_modifier = False
    modifiers = obj.get("modifiers", [])
    if not isinstance(modifiers, list):
        return has_bend_modifier, max_abs_angle
    for modifier in modifiers:
        if not isinstance(modifier, dict):
            continue
        if str(modifier.get("type", "")).upper() != "SIMPLE_DEFORM":
            continue
        if str(modifier.get("deform_method", "")).upper() == "BEND":
            has_bend_modifier = True
            angle = abs(_as_float(modifier.get("angle", 0.0), 0.0))
            if angle > max_abs_angle:
                max_abs_angle = angle
    return has_bend_modifier, float(max_abs_angle)


def _bbox_delta_axis(obj: dict[str, Any], axis: str) -> float:
    bbox_delta = obj.get("bbox_delta", {})
    if not isinstance(bbox_delta, dict):
        return 0.0
    return abs(_as_float(bbox_delta.get(axis, 0.0), 0.0))


def _bbox_delta_abs_xyz(obj: dict[str, Any]) -> dict[str, float]:
    return {
        "x": _bbox_delta_axis(obj, "x"),
        "y": _bbox_delta_axis(obj, "y"),
        "z": _bbox_delta_axis(obj, "z"),
    }


def _bbox_delta_xyz(obj: dict[str, Any]) -> dict[str, float]:
    bbox_delta = obj.get("bbox_delta", {})
    if not isinstance(bbox_delta, dict):
        return {"x": 0.0, "y": 0.0, "z": 0.0}
    return {
        "x": _as_float(bbox_delta.get("x", 0.0), 0.0),
        "y": _as_float(bbox_delta.get("y", 0.0), 0.0),
        "z": _as_float(bbox_delta.get("z", 0.0), 0.0),
    }


def _max_bbox_delta_abs(obj: dict[str, Any]) -> float:
    deltas = _bbox_delta_abs_xyz(obj)
    return max(deltas["x"], deltas["y"], deltas["z"])


def _bent_stats_for_prefix(
    metrics: dict[str, Any],
    prefix: str,
    bend_eps_m: float,
) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    count_bent = 0
    for obj in _objects_by_prefix(metrics, prefix):
        bbox_delta = _bbox_delta_xyz(obj)
        deltas = _bbox_delta_abs_xyz(obj)
        max_delta = _max_bbox_delta_abs(obj)
        has_bend_mod, bend_angle = _bend_mod_summary(obj)
        bent = (max_delta >= bend_eps_m) or (has_bend_mod and bend_angle > BEND_MOD_ANGLE_EPS)
        if bent:
            count_bent += 1
        diagnostics.append(
            {
                "name": str(obj.get("name", "")),
                "bbox_delta": bbox_delta,
                "max_delta": float(max_delta),
                "has_bend_mod": bool(has_bend_mod),
                "bend_angle": float(bend_angle),
            }
        )
    top5 = sorted(diagnostics, key=lambda item: float(item.get("max_delta", 0.0)), reverse=True)[:5]
    return {
        "count_total": len(diagnostics),
        "count_bent": int(count_bent),
        "eps_m": float(bend_eps_m),
        "top5": top5,
    }


def _overlap_total(metrics: dict[str, Any], key: str) -> float:
    overlaps = metrics.get("overlaps", {})
    if not isinstance(overlaps, dict):
        return 0.0
    overlap = overlaps.get(key, {})
    if not isinstance(overlap, dict):
        return 0.0
    return _as_float(overlap.get("total_volume", 0.0), 0.0)


def _group_count(metrics: dict[str, Any], key: str) -> int:
    groups = metrics.get("groups", {})
    if not isinstance(groups, dict):
        return 0
    payload = groups.get(key, {})
    if not isinstance(payload, dict):
        return 0
    return _as_int(payload.get("count", 0), 0)


def _overlap_entry(metrics: dict[str, Any], key: str) -> dict[str, Any]:
    overlaps = metrics.get("overlaps", {})
    if not isinstance(overlaps, dict):
        return {}
    entry = overlaps.get(key, {})
    if not isinstance(entry, dict):
        return {}
    return entry


def _overlap_pairs(metrics: dict[str, Any], key: str) -> list[dict[str, Any]]:
    entry = _overlap_entry(metrics, key)
    pairs = entry.get("pairs", [])
    if not isinstance(pairs, list):
        return []
    return [pair for pair in pairs if isinstance(pair, dict)]


def _pair_spans(pair: dict[str, Any]) -> dict[str, float]:
    bbox = pair.get("bbox_world", {})
    if not isinstance(bbox, dict):
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    min_corner = bbox.get("min", [])
    max_corner = bbox.get("max", [])
    if not isinstance(min_corner, list) or not isinstance(max_corner, list):
        return {"x": 0.0, "y": 0.0, "z": 0.0}
    if len(min_corner) < 3 or len(max_corner) < 3:
        return {"x": 0.0, "y": 0.0, "z": 0.0}

    return {
        "x": max(0.0, _as_float(max_corner[0], 0.0) - _as_float(min_corner[0], 0.0)),
        "y": max(0.0, _as_float(max_corner[1], 0.0) - _as_float(min_corner[1], 0.0)),
        "z": max(0.0, _as_float(max_corner[2], 0.0) - _as_float(min_corner[2], 0.0)),
    }


def _pair_min_span(pair: dict[str, Any]) -> float:
    spans = _pair_spans(pair)
    return min(float(spans["x"]), float(spans["y"]), float(spans["z"]))


def _is_expected_slats_frame_joint_overlap(ir: dict[str, Any], pair: dict[str, Any]) -> bool:
    right_name = str(pair.get("right", "")).strip().lower()
    if not right_name:
        return False

    if right_name.startswith("rail_") or right_name.startswith("beam_cross_"):
        slats = ir.get("slats", {})
        if not isinstance(slats, dict):
            return False
        allowance_mm = (
            _as_float(slats.get("clearance_mm", 0.0), 0.0)
            + _as_float(slats.get("mount_offset_mm", 0.0), 0.0)
            + JOINT_OVERLAP_ALLOWANCE_MM
        )
        allowance_m = max(0.0, allowance_mm / 1000.0)
        return _pair_min_span(pair) <= allowance_m
    return False


def _is_expected_back_slats_frame_joint_overlap(ir: dict[str, Any], pair: dict[str, Any]) -> bool:
    right_name = str(pair.get("right", "")).strip().lower()
    if right_name not in {"back_rail_left", "back_rail_right"}:
        return False

    back_support = ir.get("back_support", {})
    frame = ir.get("frame", {})
    if not isinstance(back_support, dict) or not isinstance(frame, dict):
        return False

    back_depth_mm = _as_float(back_support.get("thickness_mm", 0.0), 0.0)
    frame_depth_mm = _as_float(frame.get("thickness_mm", 0.0), 0.0)
    allowance_mm = max(0.0, back_depth_mm - frame_depth_mm) + JOINT_OVERLAP_ALLOWANCE_MM
    allowance_m = max(0.0, allowance_mm / 1000.0)
    return _pair_min_span(pair) <= allowance_m


def _split_overlap_pairs(
    ir: dict[str, Any],
    metrics: dict[str, Any],
    key: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    all_pairs = _overlap_pairs(metrics, key)
    hard_pairs: list[dict[str, Any]] = []
    allowed_joint_pairs: list[dict[str, Any]] = []

    for pair in all_pairs:
        if key == "slats_vs_frame" and _is_expected_slats_frame_joint_overlap(ir, pair):
            allowed_joint_pairs.append(pair)
            continue
        if key == "back_slats_vs_frame" and _is_expected_back_slats_frame_joint_overlap(ir, pair):
            allowed_joint_pairs.append(pair)
            continue
        hard_pairs.append(pair)

    return hard_pairs, allowed_joint_pairs


def _pairs_total_volume(pairs: list[dict[str, Any]]) -> float:
    total = 0.0
    for pair in pairs:
        total += _as_float(pair.get("volume", 0.0), 0.0)
    return float(total)


def _overlap_pairs_top(metrics: dict[str, Any], key: str, limit: int = 10) -> list[dict[str, Any]]:
    pairs = _overlap_pairs(metrics, key)
    return _pairs_top_from_list(pairs, limit=limit)


def _pairs_top_from_list(pairs: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    typed_pairs = [pair for pair in pairs if isinstance(pair, dict)]

    def _pair_volume(pair: dict[str, Any]) -> float:
        return _as_float(pair.get("volume", 0.0), 0.0)

    sorted_pairs = sorted(typed_pairs, key=_pair_volume, reverse=True)[: max(0, int(limit))]
    result: list[dict[str, Any]] = []
    for pair in sorted_pairs:
        result.append(
            {
                "left": str(pair.get("left", "")),
                "right": str(pair.get("right", "")),
                "volume": float(_as_float(pair.get("volume", 0.0), 0.0)),
                "bbox_world": pair.get("bbox_world"),
            }
        )
    return result


def _offenders_from_pairs_top(pairs_top: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names: set[str] = set()
    for pair in pairs_top:
        if not isinstance(pair, dict):
            continue
        left_name = str(pair.get("left", "")).strip()
        right_name = str(pair.get("right", "")).strip()
        if left_name:
            names.add(left_name)
        if right_name:
            names.add(right_name)
    return [{"name": name} for name in sorted(names)]


def _overlap_unique_counts(metrics: dict[str, Any], key: str) -> tuple[int, int]:
    pairs = _overlap_pairs(metrics, key)
    left_names = {str(pair.get("left", "")) for pair in pairs if str(pair.get("left", "")).strip()}
    right_names = {str(pair.get("right", "")) for pair in pairs if str(pair.get("right", "")).strip()}
    return len(left_names), len(right_names)


def _overlap_problem_details(metrics: dict[str, Any], key: str, total_volume: float, overlap_eps: float) -> dict[str, Any]:
    unique_left_count, unique_right_count = _overlap_unique_counts(metrics, key)
    pairs_top = _overlap_pairs_top(metrics, key, limit=10)
    return {
        "total_volume_m3": float(total_volume),
        "eps_m3": float(overlap_eps),
        "pairs_top": pairs_top,
        "offenders": _offenders_from_pairs_top(pairs_top),
        "unique_left_count": int(unique_left_count),
        "unique_right_count": int(unique_right_count),
    }


def _overlap_problem_details_from_pairs(
    metrics: dict[str, Any],
    key: str,
    *,
    overlap_eps: float,
    hard_pairs: list[dict[str, Any]],
    joint_pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    hard_pairs_top = _pairs_top_from_list(hard_pairs, limit=10)
    joint_pairs_top = _pairs_top_from_list(joint_pairs, limit=10)
    offender_pairs_top = hard_pairs_top if hard_pairs_top else joint_pairs_top

    hard_left = {str(pair.get("left", "")) for pair in hard_pairs if str(pair.get("left", "")).strip()}
    hard_right = {str(pair.get("right", "")) for pair in hard_pairs if str(pair.get("right", "")).strip()}

    return {
        "total_volume_m3": float(_overlap_total(metrics, key)),
        "effective_total_volume_m3": float(_pairs_total_volume(hard_pairs)),
        "joint_only_volume_m3": float(_pairs_total_volume(joint_pairs)),
        "eps_m3": float(overlap_eps),
        "pairs_top": hard_pairs_top,
        "joint_pairs_top": joint_pairs_top,
        "offenders": _offenders_from_pairs_top(offender_pairs_top),
        "unique_left_count": int(len(hard_left)),
        "unique_right_count": int(len(hard_right)),
        "joint_pairs_count": int(len(joint_pairs)),
        "joint_allowance_mm": float(JOINT_OVERLAP_ALLOWANCE_MM),
    }


def _group_bbox_world(metrics: dict[str, Any], group_key: str) -> dict[str, Any] | None:
    groups = metrics.get("groups", {})
    if not isinstance(groups, dict):
        return None
    group_payload = groups.get(group_key, {})
    if not isinstance(group_payload, dict):
        return None
    bbox = group_payload.get("bbox_world")
    if not isinstance(bbox, dict):
        return None
    min_corner = bbox.get("min")
    max_corner = bbox.get("max")
    if not isinstance(min_corner, list) or not isinstance(max_corner, list):
        return None
    if len(min_corner) < 3 or len(max_corner) < 3:
        return None
    return bbox


def _z_clearance_between_bboxes(
    first_bbox: dict[str, Any] | None,
    second_bbox: dict[str, Any] | None,
) -> float | None:
    if not first_bbox or not second_bbox:
        return None
    first_min = _as_float(first_bbox.get("min", [0.0, 0.0, 0.0])[2], 0.0)
    first_max = _as_float(first_bbox.get("max", [0.0, 0.0, 0.0])[2], 0.0)
    second_min = _as_float(second_bbox.get("min", [0.0, 0.0, 0.0])[2], 0.0)
    second_max = _as_float(second_bbox.get("max", [0.0, 0.0, 0.0])[2], 0.0)

    if first_max < second_min:
        return float(second_min - first_max)
    if second_max < first_min:
        return float(first_min - second_max)
    return 0.0


def _problem(code: str, severity: int, message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": code,
        "severity": int(severity),
        "message": message,
        "details": details,
    }


def _should_check_slats_overlap(ir: dict[str, Any], metrics: dict[str, Any]) -> bool:
    slats = ir.get("slats", {})
    if isinstance(slats, dict) and "enabled" in slats:
        return bool(slats.get("enabled", False))
    return _group_count(metrics, "slat_") > 0


def _should_check_back_slats_overlap(ir: dict[str, Any], metrics: dict[str, Any]) -> bool:
    back_support = ir.get("back_support", {})
    if isinstance(back_support, dict) and "mode" in back_support:
        return str(back_support.get("mode", "")).strip().lower() == "slats"
    return _group_count(metrics, "back_slat_") > 0


def _normalize_modifier_key(key: Any) -> str:
    raw = str(key).strip().upper()
    if not raw:
        return ""
    raw = raw.replace(" ", "")
    if ":" in raw:
        left, right = raw.split(":", 1)
        if right:
            return f"{left}:{right}"
        return left
    return raw


def _expected_modifiers_map(ir: dict[str, Any]) -> dict[str, list[str]]:
    debug_payload = ir.get("debug", {})
    if not isinstance(debug_payload, dict):
        return {}
    expected_payload = debug_payload.get("expect_modifiers", {})
    if not isinstance(expected_payload, dict):
        return {}

    result: dict[str, list[str]] = {}
    for group_key, expected in expected_payload.items():
        if not isinstance(expected, list):
            continue
        normalized: list[str] = []
        for item in expected:
            key = _normalize_modifier_key(item)
            if key and key not in normalized:
                normalized.append(key)
        if normalized:
            result[str(group_key)] = normalized
    return result


def _modifier_key_from_payload(modifier: dict[str, Any]) -> str:
    mod_type = _normalize_modifier_key(modifier.get("type", ""))
    if mod_type != "SIMPLE_DEFORM":
        return mod_type
    deform_method = _normalize_modifier_key(modifier.get("deform_method", ""))
    if deform_method:
        return f"SIMPLE_DEFORM:{deform_method}"
    return "SIMPLE_DEFORM"


def _object_modifier_keys(obj: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    raw_keys = obj.get("modifier_keys", [])
    if isinstance(raw_keys, list):
        for item in raw_keys:
            key = _normalize_modifier_key(item)
            if key:
                keys.add(key)

    if keys:
        return keys

    modifiers = obj.get("modifiers", [])
    if not isinstance(modifiers, list):
        return keys
    for modifier in modifiers:
        if not isinstance(modifier, dict):
            continue
        key = _modifier_key_from_payload(modifier)
        if key:
            keys.add(key)
    return keys


def _has_expected_modifier(present_keys: set[str], expected_key: str) -> bool:
    normalized_expected = _normalize_modifier_key(expected_key)
    if not normalized_expected:
        return False
    if normalized_expected in present_keys:
        return True

    if ":" in normalized_expected:
        mod_type = normalized_expected.split(":", 1)[0]
        return mod_type in present_keys

    prefix = f"{normalized_expected}:"
    if normalized_expected in present_keys:
        return True
    return any(key.startswith(prefix) for key in present_keys)


def _object_counts(obj: dict[str, Any]) -> tuple[int, int | None, int, int | None]:
    verts = _as_int(obj.get("verts", 0), 0)
    polys = _as_int(obj.get("polys", 0), 0)

    verts_base_raw = obj.get("verts_base")
    verts_base = _as_int(verts_base_raw, 0) if isinstance(verts_base_raw, (int, float)) else None
    polys_base_raw = obj.get("polys_base")
    polys_base = _as_int(polys_base_raw, 0) if isinstance(polys_base_raw, (int, float)) else None
    return verts, verts_base, polys, polys_base


def _verts_delta_abs(obj: dict[str, Any]) -> int | None:
    verts, verts_base, _, _ = _object_counts(obj)
    if verts_base is None:
        return None
    return abs(int(verts - verts_base))


def _modifier_no_effect_for_object(
    obj: dict[str, Any],
    expected_modifier: str,
    *,
    eps_m: float,
    verts_eps: int,
) -> tuple[bool, int, str, float]:
    mod_key = _normalize_modifier_key(expected_modifier)
    mod_type = mod_key.split(":", 1)[0]
    max_delta = _max_bbox_delta_abs(obj)
    verts_delta = _verts_delta_abs(obj)
    has_geom_delta = max_delta >= eps_m
    has_verts_delta = (verts_delta is not None) and (verts_delta > int(verts_eps))

    if mod_key == "SIMPLE_DEFORM:BEND":
        has_bend_mod, bend_angle = _bend_mod_summary(obj)
        if has_geom_delta or (has_bend_mod and bend_angle > BEND_MOD_ANGLE_EPS):
            return False, 0, "", float(bend_angle)
        if bend_angle > BEND_MOD_ANGLE_EPS:
            return False, 0, "", float(bend_angle)
        return True, 2, "bbox_delta too small", float(bend_angle)

    if mod_type == "ARRAY":
        if has_geom_delta or has_verts_delta:
            return False, 0, "", 0.0
        if verts_delta is None:
            return True, 2, "bbox_delta too small", 0.0
        return True, 2, "bbox_delta and verts delta too small", 0.0

    if mod_type == "MIRROR":
        if verts_delta is None:
            return False, 0, "verts_base unavailable", 0.0
        if verts_delta > int(verts_eps):
            return False, 0, "", 0.0
        return True, 2, "verts did not increase versus base mesh", 0.0

    if mod_type == "SOLIDIFY":
        if verts_delta is None:
            return False, 0, "verts_base unavailable", 0.0
        if (max_delta < eps_m) and (verts_delta <= int(verts_eps)):
            return True, 2, "bbox_delta and verts delta too small", 0.0
        return False, 0, "", 0.0

    warn_types = {"BEVEL", "SUBSURF", "WEIGHTED_NORMAL", "BOOLEAN", "SHRINKWRAP", "CURVE", "LATTICE"}
    if mod_type in warn_types:
        if verts_delta is None:
            return False, 0, "verts_base unavailable", 0.0
        if (max_delta < eps_m) and (verts_delta <= int(verts_eps)):
            return True, 1, "bbox_delta and verts delta too small", 0.0
        return False, 0, "", 0.0

    if has_geom_delta or has_verts_delta:
        return False, 0, "", 0.0
    return True, 1, "bbox_delta and verts delta too small", 0.0


def _validate_modifier_expectation_missing(ir: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    expected_map = _expected_modifiers_map(ir)
    if not expected_map:
        return []

    problems: list[dict[str, Any]] = []
    for group_key, expected in expected_map.items():
        objects = _mesh_objects_by_prefix(metrics, group_key)
        if not objects:
            continue

        missing_by_object: list[dict[str, Any]] = []
        for obj in objects:
            present_keys = _object_modifier_keys(obj)
            missing = [key for key in expected if not _has_expected_modifier(present_keys, key)]
            if missing:
                missing_by_object.append(
                    {
                        "name": str(obj.get("name", "")),
                        "missing": missing,
                    }
                )

        if not missing_by_object:
            continue

        problems.append(
            _problem(
                code="MOD_EXPECTATION_MISSING",
                severity=2,
                message=f"Expected modifiers are missing for group '{group_key}'.",
                details={
                    "group_key": group_key,
                    "expected": expected,
                    "missing_by_object": missing_by_object,
                    "counts": {
                        "objects": len(objects),
                        "objects_with_missing": len(missing_by_object),
                    },
                },
            )
        )
    return problems


def _validate_modifier_expectation_no_effect(
    ir: dict[str, Any],
    metrics: dict[str, Any],
    *,
    effect_eps_m: float,
    effect_verts_eps: int,
) -> list[dict[str, Any]]:
    expected_map = _expected_modifiers_map(ir)
    if not expected_map:
        return []

    problems: list[dict[str, Any]] = []
    for group_key, expected in expected_map.items():
        objects = _mesh_objects_by_prefix(metrics, group_key)
        for obj in objects:
            present_keys = _object_modifier_keys(obj)
            if not present_keys:
                continue

            for expected_key in expected:
                if not _has_expected_modifier(present_keys, expected_key):
                    continue

                no_effect, severity, reason, bend_angle = _modifier_no_effect_for_object(
                    obj,
                    expected_modifier=expected_key,
                    eps_m=effect_eps_m,
                    verts_eps=effect_verts_eps,
                )
                if not no_effect or severity <= 0:
                    continue

                verts, verts_base, polys, polys_base = _object_counts(obj)
                details: dict[str, Any] = {
                    "group_key": group_key,
                    "name": str(obj.get("name", "")),
                    "modifier": _normalize_modifier_key(expected_key),
                    "reason": reason,
                    "bbox_delta": _bbox_delta_xyz(obj),
                    "verts": int(verts),
                    "verts_base": verts_base,
                    "polys": int(polys),
                    "polys_base": polys_base,
                    "eps_m": float(effect_eps_m),
                    "verts_eps": int(effect_verts_eps),
                }
                if _normalize_modifier_key(expected_key) == "SIMPLE_DEFORM:BEND":
                    details["bend_angle"] = float(bend_angle)

                problems.append(
                    _problem(
                        code="MOD_EXPECTATION_NO_EFFECT",
                        severity=int(severity),
                        message=f"Modifier {_normalize_modifier_key(expected_key)} has no observable effect.",
                        details=details,
                    )
                )
    return problems


def _validate_slats_not_bent(
    ir: dict[str, Any],
    metrics: dict[str, Any],
    bend_eps_m: float,
) -> list[dict[str, Any]]:
    slats = ir.get("slats", {})
    if not isinstance(slats, dict):
        return []
    if not bool(slats.get("enabled", False)):
        return []
    if _as_float(slats.get("arc_height_mm", 0.0), 0.0) <= 0.0:
        return []

    stats = _bent_stats_for_prefix(metrics, "slat_", bend_eps_m=bend_eps_m)
    if int(stats.get("count_bent", 0)) > 0:
        return []

    details = {
        "count_total": int(stats.get("count_total", 0)),
        "count_bent": int(stats.get("count_bent", 0)),
        "eps_m": float(stats.get("eps_m", bend_eps_m)),
        "top5": stats.get("top5", []),
    }
    if int(stats.get("count_total", 0)) == 0:
        details["note"] = "no objects found"

    return [
        _problem(
            code="SLATS_NOT_BENT",
            severity=2,
            message="Seat slats are expected to be bent but bend evidence is missing.",
            details=details,
        )
    ]


def _validate_back_slats_not_bent(
    ir: dict[str, Any],
    metrics: dict[str, Any],
    bend_eps_m: float,
) -> list[dict[str, Any]]:
    back_support = ir.get("back_support", {})
    if not isinstance(back_support, dict):
        return []
    mode = str(back_support.get("mode", "")).strip().lower()
    if mode != "slats":
        return []
    back_slats = back_support.get("slats", {})
    if not isinstance(back_slats, dict):
        return []
    if _as_float(back_slats.get("arc_height_mm", 0.0), 0.0) <= 0.0:
        return []

    stats = _bent_stats_for_prefix(metrics, "back_slat_", bend_eps_m=bend_eps_m)
    if int(stats.get("count_bent", 0)) > 0:
        return []

    details = {
        "count_total": int(stats.get("count_total", 0)),
        "count_bent": int(stats.get("count_bent", 0)),
        "eps_m": float(stats.get("eps_m", bend_eps_m)),
        "top5": stats.get("top5", []),
    }
    if int(stats.get("count_total", 0)) == 0:
        details["note"] = "no objects found"

    return [
        _problem(
            code="BACK_SLATS_NOT_BENT",
            severity=2,
            message="Back slats are expected to be bent but bend evidence is missing.",
            details=details,
        )
    ]


def _validate_overlap_slats_frame(ir: dict[str, Any], metrics: dict[str, Any], overlap_eps: float) -> list[dict[str, Any]]:
    if not _should_check_slats_overlap(ir, metrics):
        return []

    hard_pairs, joint_pairs = _split_overlap_pairs(ir, metrics, "slats_vs_frame")
    effective_volume = _pairs_total_volume(hard_pairs)
    total_volume = _overlap_total(metrics, "slats_vs_frame")

    if effective_volume <= overlap_eps:
        if total_volume <= overlap_eps or len(joint_pairs) == 0:
            return []
        details = _overlap_problem_details_from_pairs(
            metrics,
            "slats_vs_frame",
            overlap_eps=overlap_eps,
            hard_pairs=hard_pairs,
            joint_pairs=joint_pairs,
        )
        return [
            _problem(
                code="OVERLAP_SLATS_FRAME",
                severity=1,
                message="Seat slats have only expected joint-contact overlaps with frame.",
                details=details,
            )
        ]

    details = _overlap_problem_details_from_pairs(
        metrics,
        "slats_vs_frame",
        overlap_eps=overlap_eps,
        hard_pairs=hard_pairs,
        joint_pairs=joint_pairs,
    )
    if details.get("unique_left_count", 0) == 0:
        unique_left_count, unique_right_count = _overlap_unique_counts(metrics, "slats_vs_frame")
        details["unique_left_count"] = int(unique_left_count)
        details["unique_right_count"] = int(unique_right_count)

    return [
        _problem(
            code="OVERLAP_SLATS_FRAME",
            severity=2,
            message="Seat slats overlap frame geometry.",
            details=details,
        )
    ]


def _validate_overlap_slats_arms(ir: dict[str, Any], metrics: dict[str, Any], overlap_eps: float) -> list[dict[str, Any]]:
    if not _should_check_slats_overlap(ir, metrics):
        return []
    volume = _overlap_total(metrics, "slats_vs_arms")
    if volume <= overlap_eps:
        return []

    return [
        _problem(
            code="OVERLAP_SLATS_ARMS",
            severity=2,
            message="Seat slats overlap arm geometry.",
            details=_overlap_problem_details(metrics, "slats_vs_arms", volume, overlap_eps),
        )
    ]


def _validate_overlap_back_slats_frame(ir: dict[str, Any], metrics: dict[str, Any], overlap_eps: float) -> list[dict[str, Any]]:
    if not _should_check_back_slats_overlap(ir, metrics):
        return []

    hard_pairs, joint_pairs = _split_overlap_pairs(ir, metrics, "back_slats_vs_frame")
    effective_volume = _pairs_total_volume(hard_pairs)
    total_volume = _overlap_total(metrics, "back_slats_vs_frame")

    if effective_volume <= overlap_eps:
        if total_volume <= overlap_eps or len(joint_pairs) == 0:
            return []
        details = _overlap_problem_details_from_pairs(
            metrics,
            "back_slats_vs_frame",
            overlap_eps=overlap_eps,
            hard_pairs=hard_pairs,
            joint_pairs=joint_pairs,
        )
        return [
            _problem(
                code="OVERLAP_BACK_SLATS_FRAME",
                severity=1,
                message="Back slats have only expected joint-contact overlaps with frame.",
                details=details,
            )
        ]

    details = _overlap_problem_details_from_pairs(
        metrics,
        "back_slats_vs_frame",
        overlap_eps=overlap_eps,
        hard_pairs=hard_pairs,
        joint_pairs=joint_pairs,
    )
    if details.get("unique_left_count", 0) == 0:
        unique_left_count, unique_right_count = _overlap_unique_counts(metrics, "back_slats_vs_frame")
        details["unique_left_count"] = int(unique_left_count)
        details["unique_right_count"] = int(unique_right_count)

    return [
        _problem(
            code="OVERLAP_BACK_SLATS_FRAME",
            severity=2,
            message="Back slats overlap frame geometry.",
            details=details,
        )
    ]


def _validate_low_clearance_slats_frame(metrics: dict[str, Any], clearance_eps: float) -> list[dict[str, Any]]:
    overlap_volume = _overlap_total(metrics, "slats_vs_frame")
    if overlap_volume > 0.0:
        return []

    slat_bbox = _group_bbox_world(metrics, "slat_")
    frame_bbox = _group_bbox_world(metrics, "frame_")
    min_clearance_z = _z_clearance_between_bboxes(slat_bbox, frame_bbox)
    if min_clearance_z is None:
        return []
    if min_clearance_z >= clearance_eps:
        return []

    return [
        _problem(
            code="LOW_CLEARANCE_SLATS_FRAME",
            severity=1,
            message="Seat slats and frame have very low Z clearance.",
            details={
                "min_clearance_z_m": float(min_clearance_z),
                "eps_m": float(clearance_eps),
            },
        )
    ]


def validate(
    ir: dict[str, Any],
    metrics: dict[str, Any],
    overlap_eps: float = DEFAULT_OVERLAP_EPS,
    bend_delta_eps: float | None = None,
    clearance_eps_m: float | None = None,
) -> dict[str, Any]:
    """Validate IR against metrics and return score payload."""
    ir, metrics = _normalize_validate_args(ir, metrics)
    overlap_eps = float(_read_env_float("DEBUG_OVERLAP_EPS_M3", overlap_eps))
    bent_eps = float(BEND_EPS_M if bend_delta_eps is None else bend_delta_eps)
    clearance_eps = float(CLEARANCE_EPS_M if clearance_eps_m is None else clearance_eps_m)
    mod_effect_eps_m = float(_read_env_float("DEBUG_MOD_EFFECT_EPS_M", MOD_EFFECT_EPS_M))
    mod_effect_verts_eps = int(_read_env_int("DEBUG_MOD_EFFECT_VERTS_EPS", MOD_EFFECT_VERTS_EPS))

    problems: list[dict[str, Any]] = []
    problems.extend(_validate_modifier_expectation_missing(ir, metrics))
    problems.extend(
        _validate_modifier_expectation_no_effect(
            ir,
            metrics,
            effect_eps_m=mod_effect_eps_m,
            effect_verts_eps=mod_effect_verts_eps,
        )
    )
    problems.extend(_validate_slats_not_bent(ir, metrics, bend_eps_m=bent_eps))
    problems.extend(_validate_back_slats_not_bent(ir, metrics, bend_eps_m=bent_eps))
    problems.extend(_validate_overlap_slats_frame(ir, metrics, overlap_eps=overlap_eps))
    problems.extend(_validate_overlap_slats_arms(ir, metrics, overlap_eps=overlap_eps))
    problems.extend(_validate_overlap_back_slats_frame(ir, metrics, overlap_eps=overlap_eps))
    problems.extend(_validate_low_clearance_slats_frame(metrics, clearance_eps=clearance_eps))

    def _severity_weight(severity: int) -> float:
        if severity >= 3:
            return 0.30
        if severity == 2:
            return 0.10
        if severity == 1:
            return 0.02
        return 0.0

    severity_sum = sum(_as_int(problem.get("severity", 0), 0) for problem in problems)
    severity_max = max((_as_int(problem.get("severity", 0), 0) for problem in problems), default=0)
    penalty = min(1.0, sum(_severity_weight(_as_int(problem.get("severity", 0), 0)) for problem in problems))
    score = max(0.0, 1.0 - penalty)

    return {
        "score": float(round(score, 6)),
        "problems": problems,
        "problem_count": len(problems),
        "severity_max": int(severity_max),
        "penalty": float(round(penalty, 6)),
    }


def _load_json_object(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}, got {type(payload).__name__}")
    return payload


def _resolve_input_path(base_path: str, candidate: str) -> str:
    if not candidate:
        return ""
    if os.path.isabs(candidate):
        return candidate
    return os.path.abspath(os.path.join(os.path.dirname(base_path), candidate))


def _infer_payload_kind(payload: dict[str, Any]) -> tuple[str, str]:
    kind_raw = str(payload.get("kind", "")).strip().lower()
    if kind_raw == "run":
        return "run", "kind_run"
    if kind_raw == "metrics":
        return "metrics", "kind_metrics"

    if (
        "validation" in payload
        or "patches_applied" in payload
        or "ir_in_path" in payload
        or ("metrics" in payload and ("status" in payload or "run_id" in payload))
    ):
        return "run", "heuristic_run"

    if (
        "validation" not in payload
        and "objects" in payload
        and "groups" in payload
        and "overlaps" in payload
    ):
        return "metrics", "heuristic_metrics"

    return "metrics", "heuristic_fallback_metrics"


def _extract_metrics_from_metrics_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nested_metrics = payload.get("metrics")
    if isinstance(nested_metrics, dict) and not _looks_like_metrics(payload):
        return nested_metrics
    return payload


def _extract_ir_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    embedded_ir = payload.get("ir")
    if isinstance(embedded_ir, dict):
        return embedded_ir
    kind, _ = _infer_payload_kind(payload)
    if kind == "run":
        return {}
    return payload


def load_debug_payload(path: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load debug input payload and return (ir, metrics, meta)."""
    input_path = os.path.abspath(path)
    payload = _load_json_object(input_path)
    kind, payload_format = _infer_payload_kind(payload)

    meta: dict[str, Any] = {
        "kind": kind,
        "format": payload_format,
        "input_path": input_path,
        "metrics_source": "none",
        "ir_source": "none",
        "metrics_error": None,
    }

    metrics_payload: dict[str, Any] = {}
    ir_payload: dict[str, Any] = {}

    if kind == "run":
        embedded_metrics = payload.get("metrics")
        if isinstance(embedded_metrics, dict):
            metrics_payload = embedded_metrics
            meta["metrics_source"] = "embedded"
        else:
            metrics_path_raw = str(payload.get("metrics_path", "")).strip()
            if metrics_path_raw:
                metrics_path = _resolve_input_path(input_path, metrics_path_raw)
                try:
                    loaded_metrics_payload = _load_json_object(metrics_path)
                    metrics_payload = _extract_metrics_from_metrics_payload(loaded_metrics_payload)
                    meta["metrics_source"] = "metrics_path"
                    meta["metrics_path"] = metrics_path
                except Exception as exc:
                    meta["metrics_error"] = f"failed to load metrics_path: {exc}"
            else:
                meta["metrics_error"] = "run payload has no embedded metrics and no metrics_path"

        env_ir_path = str(os.getenv("DEBUG_IR_JSON", "")).strip()
        if env_ir_path:
            loaded_ir_payload = _load_json_object(env_ir_path)
            ir_payload = _extract_ir_from_payload(loaded_ir_payload)
            meta["ir_source"] = "env_debug_ir_json"
        elif isinstance(payload.get("ir"), dict):
            ir_payload = payload["ir"]
            meta["ir_source"] = "embedded_ir"
        else:
            ir_in_path_raw = str(payload.get("ir_in_path", "")).strip()
            if ir_in_path_raw:
                ir_in_path = _resolve_input_path(input_path, ir_in_path_raw)
                if os.path.exists(ir_in_path):
                    try:
                        ir_payload = _load_json_object(ir_in_path)
                        meta["ir_source"] = "ir_in_path"
                        meta["ir_in_path"] = ir_in_path
                    except Exception:
                        ir_payload = {}
                        meta["ir_source"] = "ir_in_path_unreadable"
    else:
        metrics_payload = _extract_metrics_from_metrics_payload(payload)
        meta["metrics_source"] = "input_file"

        env_ir_path = str(os.getenv("DEBUG_IR_JSON", "")).strip()
        if env_ir_path:
            loaded_ir_payload = _load_json_object(env_ir_path)
            ir_payload = _extract_ir_from_payload(loaded_ir_payload)
            meta["ir_source"] = "env_debug_ir_json"

    return ir_payload, metrics_payload, meta


def _self_check_joint_only_overlap_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    ir_payload: dict[str, Any] = {
        "back_support": {
            "mode": "slats",
            "thickness_mm": 60.0,
        },
        "frame": {
            "thickness_mm": 58.0,
        },
    }
    metrics_payload: dict[str, Any] = {
        "kind": "metrics",
        "groups": {
            "back_slat_": {"count": 1},
            "frame_": {"count": 1},
        },
        "overlaps": {
            "back_slats_vs_frame": {
                "total_volume": 3.2e-5,
                "pairs": [
                    {
                        "left": "back_slat_1",
                        "right": "back_rail_left",
                        "volume": 3.2e-5,
                        "bbox_world": {
                            "min": [0.0, 0.0, 0.0],
                            "max": [0.0015, 0.0010, 0.0040],
                        },
                    }
                ],
            },
            "slats_vs_frame": {"total_volume": 0.0, "pairs": []},
            "slats_vs_arms": {"total_volume": 0.0, "pairs": []},
        },
    }
    return ir_payload, metrics_payload


if __name__ == "__main__":
    input_path = str(os.getenv("DEBUG_INPUT_JSON", "")).strip()
    if not input_path:
        input_path = str(os.getenv("DEBUG_METRICS_JSON", "")).strip()

    if not input_path:
        print("validators: running built-in joint-only overlap self-check", file=sys.stderr)
        ir_payload, metrics_payload = _self_check_joint_only_overlap_payload()
        result = validate(ir_payload, metrics_payload)
        print(json.dumps(result, ensure_ascii=False, indent=2))

        joint_top_found = False
        joint_top_len = 0
        hard_top_len = 0
        offenders_len = 0
        problems = result.get("problems", [])
        if isinstance(problems, list):
            for problem in problems:
                if not isinstance(problem, dict):
                    continue
                code = str(problem.get("code", "")).strip().upper()
                if code != "OVERLAP_BACK_SLATS_FRAME":
                    continue
                details = problem.get("details", {})
                if not isinstance(details, dict):
                    continue
                joint_pairs_top = details.get("joint_pairs_top", [])
                pairs_top = details.get("pairs_top", [])
                offenders = details.get("offenders", [])
                joint_top_found = isinstance(joint_pairs_top, list) and len(joint_pairs_top) > 0
                joint_top_len = len(joint_pairs_top) if isinstance(joint_pairs_top, list) else 0
                hard_top_len = len(pairs_top) if isinstance(pairs_top, list) else 0
                offenders_len = len(offenders) if isinstance(offenders, list) else 0
                break
        print(
            f"validators: self_check joint_pairs_top_found={joint_top_found} "
            f"joint_pairs_top_len={joint_top_len} hard_pairs_top_len={hard_top_len} "
            f"offenders_len={offenders_len}",
            file=sys.stderr,
        )
        raise SystemExit(0)

    try:
        ir_payload, metrics_payload, meta = load_debug_payload(input_path)
    except Exception as exc:
        print(f"validators: failed to load input: {exc}", file=sys.stderr)
        raise SystemExit(2)

    print(
        f"validators: loaded input kind={meta.get('kind')} format={meta.get('format')}",
        file=sys.stderr,
    )

    if meta.get("kind") == "run" and (not _looks_like_metrics(metrics_payload)):
        error_text = str(meta.get("metrics_error") or "run input metrics not found or unreadable")
        print(f"validators: {error_text}", file=sys.stderr)
        raise SystemExit(2)

    result = validate(ir_payload, metrics_payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        f"validators: kind={meta.get('kind')} problems={int(result.get('problem_count', 0))}",
        file=sys.stderr,
    )
