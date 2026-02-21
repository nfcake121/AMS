"""Cylindrical legs strategy."""

from __future__ import annotations

from src.builders.blender.plan_types import Primitive


def build_leg_cylindrical_strategy(
    plan,
    *,
    name: str,
    dimensions_mm: tuple[float, float, float],
    location_mm: tuple[float, float, float],
) -> None:
    plan.primitives.append(
        Primitive(
            name=name,
            shape="cylindrical",
            dimensions_mm=dimensions_mm,
            location_mm=location_mm,
        )
    )
