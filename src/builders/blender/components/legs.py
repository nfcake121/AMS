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


def _append_leg_with_handler(
    *,
    plan,
    handler,
    handler_name: str,
    family: str,
    name: str,
    dimensions_mm: tuple[float, float, float],
    location_mm: tuple[float, float, float],
) -> None:
    if handler_name == "leg_passthrough":
        build_leg_passthrough_strategy(
            plan=plan,
            family=family,
            name=name,
            dimensions_mm=dimensions_mm,
            location_mm=location_mm,
        )
        return
    handler(
        plan=plan,
        name=name,
        dimensions_mm=dimensions_mm,
        location_mm=location_mm,
    )


def build_legs(plan, inputs: LegsInputs, ctx: BuildContext) -> None:
    legs_family = _legs_family(inputs)
    legs_height_mm = _legs_height_mm(inputs)
    layout_kind = str(inputs.layout_kind or "straight")

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
            "strategy": "corner" if layout_kind == "corner" else "straight",
            "key": {"family": legs_family, "layout_kind": layout_kind},
            "handler": handler_name,
        },
        resolved_value={"family": legs_family, "layout_kind": layout_kind},
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
        _append_leg_with_handler(
            plan=plan,
            handler=handler,
            handler_name=handler_name,
            family=legs_family,
            name=primitive_name,
            dimensions_mm=primitive_dimensions,
            location_mm=point,
        )

    if (
        layout_kind == "corner"
        and inputs.seat_chaise_min_x is not None
        and inputs.seat_chaise_max_x is not None
        and inputs.seat_chaise_min_y is not None
        and inputs.seat_chaise_max_y is not None
    ):
        chaise_min_x = float(inputs.seat_chaise_min_x)
        chaise_max_x = float(inputs.seat_chaise_max_x)
        chaise_min_y = float(inputs.seat_chaise_min_y)
        chaise_max_y = float(inputs.seat_chaise_max_y)
        side = str(inputs.corner_side or "right")
        if side == "left":
            outer_x = chaise_min_x + (inputs.frame_thickness_mm / 2.0)
        else:
            outer_x = chaise_max_x - (inputs.frame_thickness_mm / 2.0)
        back_y = chaise_min_y + (inputs.frame_thickness_mm / 2.0)
        front_y = chaise_max_y - (inputs.frame_thickness_mm / 2.0)
        chaise_leg_points = [
            (outer_x, back_y, legs_center_z),
            (outer_x, front_y, legs_center_z),
        ]
        primitive_dimensions = (
            float(inputs.frame_thickness_mm),
            float(inputs.frame_thickness_mm),
            float(legs_height_mm),
        )
        for index, point in enumerate(chaise_leg_points, start=1):
            plan.anchors.append(Anchor(name=f"leg_chaise_point_{index}", location_mm=point))
            _append_leg_with_handler(
                plan=plan,
                handler=handler,
                handler_name=handler_name,
                family=legs_family,
                name=f"leg_chaise_{index}",
                dimensions_mm=primitive_dimensions,
                location_mm=point,
            )
