"""Passthrough legs strategy for compatibility with unknown families."""

from __future__ import annotations

from src.builders.blender.plan_types import Primitive


def build_leg_passthrough_strategy(
    plan,
    *,
    family: str,
    name: str,
    dimensions_mm: tuple[float, float, float],
    location_mm: tuple[float, float, float],
) -> None:
    plan.primitives.append(
        Primitive(
            name=name,
            shape=family,
            dimensions_mm=dimensions_mm,
            location_mm=location_mm,
        )
    )
