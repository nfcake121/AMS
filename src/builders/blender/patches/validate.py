"""Validation and normalization for patch operations."""

from __future__ import annotations

import os
from typing import Any

from src.builders.blender.diagnostics import Severity, emit_simple
from src.builders.blender.patches.types import PatchOp
from src.builders.blender.patches.whitelist import PATCH_PATH_RULES


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    return max(1, value)


def _path_depth(path: str) -> int:
    return len([part for part in str(path).split(".") if part])


def _match_rule(path: str) -> dict[str, Any] | None:
    if path in PATCH_PATH_RULES:
        return PATCH_PATH_RULES[path]
    for pattern, rule in PATCH_PATH_RULES.items():
        if "*" not in pattern:
            continue
        prefix, suffix = pattern.split("*", 1)
        if path.startswith(prefix) and path.endswith(suffix):
            return rule
    return None


def _reject(patch: PatchOp, code: str, reason: str) -> dict[str, Any]:
    return {"patch": patch.to_dict(), "code": code, "reason": reason}


def validate_patch_ops(
    ops: list[PatchOp],
    *,
    diag_sink=None,
    run_id: str = "",
) -> tuple[list[PatchOp], list[dict[str, Any]]]:
    max_ops = _env_int("AMS_PATCH_MAX_OPS", 10)
    max_depth = _env_int("AMS_PATCH_MAX_DEPTH", 6)
    valid_ops: list[PatchOp] = []
    rejected: list[dict[str, Any]] = []

    for index, patch in enumerate(list(ops)):
        if index >= max_ops:
            rejected.append(_reject(patch, "PATCH_MAX_OPS", f"max ops limit exceeded ({max_ops})"))
            continue

        depth = _path_depth(patch.path)
        if depth > max_depth:
            rejected.append(_reject(patch, "PATCH_PATH_DEPTH", f"path depth {depth} > {max_depth}"))
            continue

        if patch.op not in {"set", "inc"}:
            rejected.append(_reject(patch, "PATCH_OP_UNSUPPORTED", f"unsupported op: {patch.op}"))
            continue

        rule = _match_rule(patch.path)
        if rule is None:
            rejected.append(_reject(patch, "PATCH_PATH_NOT_ALLOWED", "path not in whitelist"))
            continue

        rule_type = str(rule.get("type", ""))
        allowed = rule.get("allowed")
        min_value = rule.get("min")
        max_value = rule.get("max")

        if patch.op == "inc" and rule_type not in {"number", "integer"}:
            rejected.append(_reject(patch, "PATCH_INC_TYPE", "inc requires numeric whitelist path"))
            continue

        if patch.op == "set":
            raw_value = patch.value
        else:
            raw_value = patch.delta

        normalized_value = raw_value
        if rule_type == "bool":
            if not isinstance(raw_value, bool):
                rejected.append(_reject(patch, "PATCH_TYPE_MISMATCH", "expected bool"))
                continue
        elif rule_type == "string":
            if not isinstance(raw_value, str):
                rejected.append(_reject(patch, "PATCH_TYPE_MISMATCH", "expected string"))
                continue
        elif rule_type == "enum":
            if not isinstance(raw_value, str):
                rejected.append(_reject(patch, "PATCH_TYPE_MISMATCH", "expected enum string"))
                continue
            if isinstance(allowed, list) and raw_value not in allowed:
                rejected.append(_reject(patch, "PATCH_ENUM_NOT_ALLOWED", f"value not allowed: {raw_value}"))
                continue
        elif rule_type == "integer":
            if not isinstance(raw_value, int):
                rejected.append(_reject(patch, "PATCH_TYPE_MISMATCH", "expected integer"))
                continue
            normalized_value = int(raw_value)
        elif rule_type == "number":
            if not isinstance(raw_value, (int, float)):
                rejected.append(_reject(patch, "PATCH_TYPE_MISMATCH", "expected number"))
                continue
            normalized_value = float(raw_value)
        else:
            rejected.append(_reject(patch, "PATCH_RULE_INVALID", "unknown whitelist rule type"))
            continue

        if isinstance(normalized_value, (int, float)):
            clamped_value = normalized_value
            if isinstance(min_value, (int, float)) and clamped_value < float(min_value):
                clamped_value = float(min_value)
            if isinstance(max_value, (int, float)) and clamped_value > float(max_value):
                clamped_value = float(max_value)
            if clamped_value != normalized_value:
                if diag_sink is not None:
                    emit_simple(
                        diag_sink,
                        run_id=run_id,
                        stage="debug",
                        component="builder",
                        code="PATCH_CLAMP",
                        severity=Severity.WARN,
                        path=patch.path,
                        source="computed",
                        input_value=normalized_value,
                        resolved_value=clamped_value,
                        reason="patch value clamped to whitelist bounds",
                        meta={"min": min_value, "max": max_value},
                    )
                normalized_value = clamped_value
            if rule_type == "integer":
                normalized_value = int(round(float(normalized_value)))

        if patch.op == "set":
            valid_ops.append(
                PatchOp(
                    op="set",
                    path=patch.path,
                    value=normalized_value,
                    meta=dict(patch.meta),
                )
            )
        else:
            valid_ops.append(
                PatchOp(
                    op="inc",
                    path=patch.path,
                    delta=normalized_value,
                    meta=dict(patch.meta),
                )
            )

    return valid_ops, rejected
