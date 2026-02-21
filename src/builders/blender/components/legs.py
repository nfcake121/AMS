"""Legs component for Blender builder plan generation."""

from __future__ import annotations

from src.builders.blender.components.legs_strategies import (
    build_leg_block_strategy,
    build_leg_cylindrical_strategy,
    build_leg_passthrough_strategy,
    build_leg_tapered_cone_strategy,
)
from src.builders.blender.diagnostics import Severity, emit_simple
from src.builders.blender.plan_types import Anchor
from src.builders.blender.spec.types import BuildContext, LegsInputs


def _legs_family(inputs: LegsInputs) -> str:
    family = inputs.family
    if isinstance(family, str) and family:
        return family
    return "block"


def _legs_height_mm(inputs: LegsInputs) -> float:
    height = inputs.height_mm
    if height is None:
        return 160.0
    return float(height)


def build_legs(plan, inputs: LegsInputs, ctx: BuildContext) -> None:
    legs_family = _legs_family(inputs)
    legs_height_mm = _legs_height_mm(inputs)

    strategy_dispatch = {
        "block": ("leg_block", build_leg_block_strategy),
        "tapered_cone": ("leg_tapered_cone", build_leg_tapered_cone_strategy),
        "cylindrical": ("leg_cylindrical", build_leg_cylindrical_strategy),
    }
    handler_name, handler = strategy_dispatch.get(
        legs_family,
        ("leg_passthrough", build_leg_passthrough_strategy),
    )

    emit_simple(
        ctx.diag,
        run_id=ctx.run_id,
        stage="build",
        component="legs",
        code="STRATEGY_SELECTED",
        severity=Severity.INFO,
        path="legs.family",
        source="computed",
        payload={
            "key": {"family": legs_family},
            "handler": handler_name,
        },
        resolved_value={"family": legs_family},
        reason="dispatch legs build strategy",
    )

    leg_offset_x = (inputs.total_width_mm / 2.0) - (inputs.frame_thickness_mm / 2.0)
    leg_offset_y = (inputs.seat_depth_mm / 2.0) - (inputs.frame_thickness_mm / 2.0)
    base_frame_bottom_z = inputs.base_frame_top_z - inputs.frame_thickness_mm
    legs_center_z = base_frame_bottom_z - (legs_height_mm / 2.0)
    leg_points = [
        (-leg_offset_x, -leg_offset_y, legs_center_z),
        (leg_offset_x, -leg_offset_y, legs_center_z),
        (-leg_offset_x, leg_offset_y, legs_center_z),
        (leg_offset_x, leg_offset_y, legs_center_z),
    ]

    for index, point in enumerate(leg_points, start=1):
        plan.anchors.append(Anchor(name=f"leg_point_{index}", location_mm=point))
        primitive_name = f"leg_{index}"
        primitive_dimensions = (
            float(inputs.frame_thickness_mm),
            float(inputs.frame_thickness_mm),
            float(legs_height_mm),
        )
        if handler_name == "leg_passthrough":
            build_leg_passthrough_strategy(
                plan=plan,
                family=legs_family,
                name=primitive_name,
                dimensions_mm=primitive_dimensions,
                location_mm=point,
            )
        else:
            handler(
                plan=plan,
                name=primitive_name,
                dimensions_mm=primitive_dimensions,
                location_mm=point,
            )
