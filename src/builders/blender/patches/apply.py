"""Apply validated patch operations to IR payloads."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.builders.blender.patches.types import PatchOp, PatchResult
from src.builders.blender.patches.whitelist import KNOWN_OBJECT_PATHS


def _reject(patch: PatchOp, code: str, reason: str) -> dict[str, Any]:
    return {"patch": patch.to_dict(), "code": code, "reason": reason}


def _set_by_path(root: dict[str, Any], path: str, value: Any) -> tuple[bool, Any]:
    parts = [part for part in path.split(".") if part]
    node: Any = root
    current_path = ""
    for key in parts[:-1]:
        current_path = key if not current_path else f"{current_path}.{key}"
        if not isinstance(node, dict):
            return False, None
        if key not in node:
            if current_path in KNOWN_OBJECT_PATHS:
                node[key] = {}
            else:
                return False, None
        node = node.get(key)
    if not isinstance(node, dict):
        return False, None
    leaf = parts[-1]
    if leaf not in node:
        return False, None
    old_value = node.get(leaf)
    node[leaf] = value
    return True, old_value


def _inc_by_path(root: dict[str, Any], path: str, delta: float | int) -> tuple[bool, Any, Any]:
    parts = [part for part in path.split(".") if part]
    node: Any = root
    for key in parts[:-1]:
        if not isinstance(node, dict) or key not in node:
            return False, None, None
        node = node.get(key)
    if not isinstance(node, dict):
        return False, None, None
    leaf = parts[-1]
    if leaf not in node:
        return False, None, None
    current = node.get(leaf)
    if not isinstance(current, (int, float)):
        return False, current, None
    new_value = float(current) + float(delta)
    if isinstance(current, int) and isinstance(delta, int):
        new_value = int(new_value)
    node[leaf] = new_value
    return True, current, new_value


def apply_patch_ops(ir: dict[str, Any], ops: list[PatchOp]) -> tuple[dict[str, Any], PatchResult]:
    patched_ir = deepcopy(ir)
    applied: list[PatchOp] = []
    rejected: list[dict[str, Any]] = []

    for patch in list(ops):
        if patch.op == "set":
            ok, _old = _set_by_path(patched_ir, patch.path, patch.value)
            if not ok:
                rejected.append(_reject(patch, "PATCH_SET_FAILED", "path missing or branch unavailable"))
                continue
            applied.append(patch)
            continue

        if patch.op == "inc":
            if patch.delta is None:
                rejected.append(_reject(patch, "PATCH_INC_FAILED", "delta is required for inc"))
                continue
            ok, current, _new = _inc_by_path(patched_ir, patch.path, patch.delta)
            if not ok:
                if current is not None and not isinstance(current, (int, float)):
                    rejected.append(_reject(patch, "PATCH_INC_FAILED", "target is not numeric"))
                else:
                    rejected.append(_reject(patch, "PATCH_INC_FAILED", "path missing or branch unavailable"))
                continue
            applied.append(patch)
            continue

        rejected.append(_reject(patch, "PATCH_OP_UNSUPPORTED", f"unsupported op: {patch.op}"))

    return patched_ir, PatchResult(applied=applied, rejected=rejected, changed=bool(applied))
