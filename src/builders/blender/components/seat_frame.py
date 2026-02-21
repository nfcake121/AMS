"""Seat frame component for Blender builder plan generation."""

from __future__ import annotations

from collections.abc import Callable

from src.builders.blender.diagnostics import Severity, emit_simple
from src.builders.blender.plan_types import Primitive
from src.builders.blender.spec.types import BuildContext, SeatFrameInputs


def select_seat_frame_strategy(inputs: SeatFrameInputs) -> str:
    del inputs
    return "default"


def _build_seat_frame_default(plan, inputs: SeatFrameInputs) -> None:
    front_y = (inputs.seat_depth_mm / 2.0) - (inputs.frame_thickness_mm / 2.0)
    back_y = -(inputs.seat_depth_mm / 2.0) + (inputs.frame_thickness_mm / 2.0)
    left_x = -(inputs.total_width_mm / 2.0) + (inputs.frame_thickness_mm / 2.0)
    right_x = (inputs.total_width_mm / 2.0) - (inputs.frame_thickness_mm / 2.0)

    plan.primitives.extend(
        [
            Primitive(
                name="beam_front",
                shape="beam",
                dimensions_mm=(inputs.total_width_mm, inputs.frame_thickness_mm, inputs.frame_thickness_mm),
                location_mm=(0.0, front_y, inputs.base_frame_center_z),
            ),
            Primitive(
                name="beam_back",
                shape="beam",
                dimensions_mm=(inputs.total_width_mm, inputs.frame_thickness_mm, inputs.frame_thickness_mm),
                location_mm=(0.0, back_y, inputs.base_frame_center_z),
            ),
            Primitive(
                name="beam_left",
                shape="beam",
                dimensions_mm=(inputs.frame_thickness_mm, inputs.seat_depth_mm, inputs.frame_thickness_mm),
                location_mm=(left_x, 0.0, inputs.base_frame_center_z),
            ),
            Primitive(
                name="beam_right",
                shape="beam",
                dimensions_mm=(inputs.frame_thickness_mm, inputs.seat_depth_mm, inputs.frame_thickness_mm),
                location_mm=(right_x, 0.0, inputs.base_frame_center_z),
            ),
        ]
    )

    cross_count = max(2, min(4, inputs.seat_count + 1))
    inner_width_mm = max(1.0, inputs.total_width_mm - (2.0 * inputs.frame_thickness_mm))
    cross_spacing_mm = inner_width_mm / (cross_count + 1)
    for i in range(cross_count):
        x = -(inner_width_mm / 2.0) + cross_spacing_mm * (i + 1)
        plan.primitives.append(
            Primitive(
                name=f"beam_cross_{i + 1}",
                shape="beam",
                dimensions_mm=(
                    inputs.frame_thickness_mm,
                    inputs.seat_depth_mm - (2.0 * inputs.frame_thickness_mm),
                    inputs.frame_thickness_mm,
                ),
                location_mm=(x, 0.0, inputs.base_frame_center_z),
            )
        )

    if not inputs.slats_enabled:
        plan.primitives.append(
            Primitive(
                name="seat_support",
                shape="board",
                dimensions_mm=(inputs.seat_total_width_mm, inputs.seat_depth_mm, inputs.frame_thickness_mm),
                location_mm=(0.0, 0.0, inputs.seat_support_center_z),
            )
        )


SEAT_FRAME_STRATEGIES: dict[str, Callable] = {
    "default": _build_seat_frame_default,
}


def build_seat_frame(plan, inputs: SeatFrameInputs, ctx: BuildContext) -> None:
    strategy_id = select_seat_frame_strategy(inputs)
    strategy = SEAT_FRAME_STRATEGIES.get(strategy_id, SEAT_FRAME_STRATEGIES["default"])
    emit_simple(
        ctx.diag,
        run_id=ctx.run_id,
        stage="build",
        component="seat_frame",
        code="STRATEGY_SELECTED",
        severity=Severity.INFO,
        path="seat_frame.strategy",
        source="computed",
        reason="seat frame strategy selected",
        payload={
            "strategy": strategy_id,
            "handler": strategy.__name__.removeprefix("_build_seat_frame_"),
        },
    )
    strategy(plan, inputs)
