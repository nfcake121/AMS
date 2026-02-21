"""Stable serialization of build plans for regression snapshots."""

from __future__ import annotations

from typing import Any

from src.builders.blender.plan_types import BuildPlan


def _round_value(value: Any):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    if isinstance(value, (list, tuple)):
        return [_round_value(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key in sorted(value):
            normalized[str(key)] = _round_value(value[key])
        return normalized
    return value


def plan_to_snapshot(plan: BuildPlan) -> dict[str, Any]:
    primitives: list[dict[str, Any]] = []
    for primitive in plan.primitives:
        item: dict[str, Any] = {
            "name": primitive.name,
            "shape": primitive.shape,
            "dimensions_mm": _round_value(primitive.dimensions_mm),
            "location_mm": _round_value(primitive.location_mm),
        }
        if hasattr(primitive, "rotation_deg"):
            item["rotation_deg"] = _round_value(primitive.rotation_deg)
        if hasattr(primitive, "params"):
            item["params"] = _round_value(primitive.params)
        primitives.append(item)

    anchors: list[dict[str, Any]] = []
    for anchor in plan.anchors:
        anchors.append(
            {
                "name": anchor.name,
                "location_mm": _round_value(anchor.location_mm),
            }
        )

    return {
        "primitives": primitives,
        "anchors": anchors,
    }
