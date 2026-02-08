"""Rule-based IR autofixes for debug validator problems."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _ensure_dict(root: dict[str, Any], key: str) -> dict[str, Any]:
    current = root.get(key)
    if isinstance(current, dict):
        return current
    root[key] = {}
    return root[key]


def _set_patch(target: dict[str, Any], path: str, value: Any, patch_list: list[dict[str, Any]]) -> bool:
    keys = path.split(".")
    if not keys:
        return False

    node: dict[str, Any] = target
    for key in keys[:-1]:
        next_node = node.get(key)
        if not isinstance(next_node, dict):
            next_node = {}
            node[key] = next_node
        node = next_node

    leaf = keys[-1]
    old_value = node.get(leaf)
    if old_value == value:
        return False
    node[leaf] = value
    patch_list.append({"path": path, "old": old_value, "new": value})
    return True


def _fix_intersection_slats_arms(ir: dict[str, Any], patch_list: list[dict[str, Any]]) -> None:
    slats = _ensure_dict(ir, "slats")
    old_margin = _as_float(slats.get("margin_x_mm", 40.0), 40.0)
    margin_step = 10.0
    if _set_patch(ir, "slats.margin_x_mm", old_margin + margin_step, patch_list):
        return

    old_count = max(1, _as_int(slats.get("count", 14), 14))
    if old_count > 1:
        _set_patch(ir, "slats.count", old_count - 1, patch_list)


def _fix_slats_not_bent(ir: dict[str, Any], patch_list: list[dict[str, Any]]) -> None:
    slats = _ensure_dict(ir, "slats")
    old_arc = _as_float(slats.get("arc_height_mm", 0.0), 0.0)

    seat_depth = _as_float(ir.get("seat_depth_mm", 0.0), 0.0)
    margin_y = _as_float(slats.get("margin_y_mm", 0.0), 0.0)
    length_mm = max(0.0, seat_depth - (2.0 * margin_y))
    arc_limit = length_mm / 2.0 if length_mm > 0.0 else old_arc + 5.0

    new_arc = min(old_arc + 5.0, arc_limit)
    if new_arc > old_arc:
        _set_patch(ir, "slats.arc_height_mm", new_arc, patch_list)


def _fix_missing_arms(ir: dict[str, Any], patch_list: list[dict[str, Any]]) -> None:
    arms = _ensure_dict(ir, "arms")
    arm_type = str(arms.get("type", "none")).strip().lower()
    if arm_type == "none":
        return
    _set_patch(ir, "arms.width_mm", 120, patch_list)
    _set_patch(ir, "arms.profile", "box", patch_list)


def fix_ir(ir: dict[str, Any], problems: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Apply rule-based IR patches and return (new_ir, patch_list)."""
    patched = deepcopy(ir)
    patch_list: list[dict[str, Any]] = []
    applied_codes: set[str] = set()

    for problem in problems:
        if not isinstance(problem, dict):
            continue
        code = str(problem.get("code", "")).strip().upper()
        if not code or code in applied_codes:
            continue

        if code == "INTERSECTION_SLATS_ARMS":
            _fix_intersection_slats_arms(patched, patch_list)
            applied_codes.add(code)
            continue
        if code == "SLATS_NOT_BENT":
            _fix_slats_not_bent(patched, patch_list)
            applied_codes.add(code)
            continue
        if code == "MISSING_ARMS":
            _fix_missing_arms(patched, patch_list)
            applied_codes.add(code)

    return patched, patch_list

