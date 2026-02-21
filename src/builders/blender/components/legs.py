"""Legs component for Blender builder plan generation."""

from __future__ import annotations

from src.builders.blender.plan_types import Anchor, Primitive
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
    del ctx

    legs_family = _legs_family(inputs)
    legs_height_mm = _legs_height_mm(inputs)

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
        plan.primitives.append(
            Primitive(
                name=f"leg_{index}",
                shape=legs_family,
                dimensions_mm=(inputs.frame_thickness_mm, inputs.frame_thickness_mm, legs_height_mm),
                location_mm=point,
            )
        )
