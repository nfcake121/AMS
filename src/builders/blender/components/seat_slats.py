"""Seat slats component for Blender builder plan generation."""

from __future__ import annotations

from collections.abc import Callable

from src.builders.blender.diagnostics import Severity, emit_simple
from src.builders.blender.plan_types import Anchor, Primitive
from src.builders.blender.spec.types import BuildContext, SeatSlatsInputs


def select_seat_slats_strategy(inputs: SeatSlatsInputs) -> str:
    del inputs
    return "default"


def _build_seat_slats_default(plan, inputs: SeatSlatsInputs) -> None:
    if not inputs.slats_enabled:
        return

    slat_length_mm = max(1.0, inputs.seat_depth_mm - (2.0 * inputs.slat_margin_y_mm))
    rail_length_mm = max(1.0, inputs.seat_depth_mm - (2.0 * inputs.slat_rail_inset_y_mm))
    usable_width_mm = max(1.0, inputs.seat_total_width_mm - (2.0 * inputs.slat_margin_x_mm))
    if inputs.slat_count == 1:
        slat_centers_x = [0.0]
    else:
        span_mm = max(0.0, usable_width_mm - inputs.slat_width_mm)
        step_mm = span_mm / (inputs.slat_count - 1)
        start_x = -(usable_width_mm / 2.0) + (inputs.slat_width_mm / 2.0)
        slat_centers_x = [start_x + (step_mm * i) for i in range(inputs.slat_count)]

    # Slats mount to the base frame top plane unless explicitly centered.
    slat_plane_z_mm = inputs.base_frame_top_z
    if inputs.slat_mount_mode == "centered":
        slat_center_z = inputs.seat_support_top_z - (inputs.slat_thickness_mm / 2.0) + inputs.slat_clearance_mm
    else:
        slat_center_z = (
            slat_plane_z_mm
            + inputs.slat_mount_offset_mm
            + inputs.slat_clearance_mm
            + (inputs.slat_thickness_mm / 2.0)
        )

    min_x = min(slat_centers_x) - (inputs.slat_width_mm / 2.0)
    max_x = max(slat_centers_x) + (inputs.slat_width_mm / 2.0)
    rail_height_mm = inputs.slat_rail_height_mm
    rail_width_mm = inputs.slat_rail_width_mm
    rail_depth_mm = rail_length_mm
    rail_top_z = slat_plane_z_mm
    rail_center_z = rail_top_z - (rail_height_mm / 2.0)
    rail_left_x = min_x + (rail_width_mm / 2.0) + inputs.slat_rail_inset_mm
    rail_right_x = max_x - (rail_width_mm / 2.0) - inputs.slat_rail_inset_mm
    if rail_left_x < rail_right_x:
        plan.primitives.append(
            Primitive(
                name="rail_left",
                shape="beam",
                dimensions_mm=(rail_width_mm, rail_depth_mm, rail_height_mm),
                location_mm=(rail_left_x, 0.0, rail_center_z),
            )
        )
        plan.primitives.append(
            Primitive(
                name="rail_right",
                shape="beam",
                dimensions_mm=(rail_width_mm, rail_depth_mm, rail_height_mm),
                location_mm=(rail_right_x, 0.0, rail_center_z),
            )
        )
        plan.anchors.append(
            Anchor(name="rail_left", location_mm=(rail_left_x, 0.0, rail_center_z))
        )
        plan.anchors.append(
            Anchor(name="rail_right", location_mm=(rail_right_x, 0.0, rail_center_z))
        )

    plan.anchors.append(Anchor(name="slat_plane_z", location_mm=(0.0, 0.0, slat_plane_z_mm)))
    plan.anchors.append(Anchor(name="slat_area_center", location_mm=(0.0, 0.0, slat_center_z)))
    for i, x in enumerate(slat_centers_x, start=1):
        plan.primitives.append(
            Primitive(
                name=f"slat_{i}",
                shape="slat",
                dimensions_mm=(inputs.slat_width_mm, slat_length_mm, inputs.slat_thickness_mm),
                location_mm=(x, 0.0, slat_center_z),
                params={
                    "arc_height_mm": inputs.slat_arc_height_mm,
                    "arc_sign": inputs.slat_arc_sign,
                    "orientation": "horizontal",
                    "mount_mode": inputs.slat_mount_mode,
                    "mount_offset_mm": inputs.slat_mount_offset_mm,
                    "clearance_mm": inputs.slat_clearance_mm,
                },
            )
        )


SEAT_SLATS_STRATEGIES: dict[str, Callable] = {
    "default": _build_seat_slats_default,
}


def build_seat_slats(plan, inputs: SeatSlatsInputs, ctx: BuildContext) -> None:
    strategy_id = select_seat_slats_strategy(inputs)
    strategy = SEAT_SLATS_STRATEGIES.get(strategy_id, SEAT_SLATS_STRATEGIES["default"])
    emit_simple(
        ctx.diag,
        run_id=ctx.run_id,
        stage="build",
        component="seat_slats",
        code="STRATEGY_SELECTED",
        severity=Severity.INFO,
        path="seat_slats.strategy",
        source="computed",
        reason="seat slats strategy selected",
        payload={
            "strategy": strategy_id,
            "handler": strategy.__name__.removeprefix("_build_seat_slats_"),
        },
    )
    strategy(plan, inputs)
