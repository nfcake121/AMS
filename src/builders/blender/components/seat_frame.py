"""Seat frame component for Blender builder plan generation."""

from __future__ import annotations

from collections.abc import Callable

from src.builders.blender.diagnostics import Severity, emit_simple
from src.builders.blender.plan_types import Primitive
from src.builders.blender.spec.types import BuildContext, SeatFrameInputs


def select_seat_frame_strategy(inputs: SeatFrameInputs) -> str:
    if (
        inputs.layout_kind == "corner"
        and inputs.corner_join_mode == "shared_corner_post"
        and inputs.seat_chaise_min_x is not None
        and inputs.seat_chaise_max_x is not None
        and inputs.seat_chaise_min_y is not None
        and inputs.seat_chaise_max_y is not None
    ):
        return "corner_shared_corner_post"
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


def _append_horizontal_beam(plan, *, name: str, min_x: float, max_x: float, y: float, z: float, thickness_mm: float) -> None:
    span_x = max(1.0, float(max_x) - float(min_x))
    center_x = (float(min_x) + float(max_x)) / 2.0
    plan.primitives.append(
        Primitive(
            name=name,
            shape="beam",
            dimensions_mm=(span_x, thickness_mm, thickness_mm),
            location_mm=(center_x, float(y), float(z)),
        )
    )


def _append_vertical_beam(plan, *, name: str, x: float, min_y: float, max_y: float, z: float, thickness_mm: float) -> None:
    span_y = max(1.0, float(max_y) - float(min_y))
    center_y = (float(min_y) + float(max_y)) / 2.0
    plan.primitives.append(
        Primitive(
            name=name,
            shape="beam",
            dimensions_mm=(thickness_mm, span_y, thickness_mm),
            location_mm=(float(x), center_y, float(z)),
        )
    )


def _build_seat_frame_corner_shared_corner_post(plan, inputs: SeatFrameInputs) -> None:
    if (
        inputs.seat_chaise_min_x is None
        or inputs.seat_chaise_max_x is None
        or inputs.seat_chaise_min_y is None
        or inputs.seat_chaise_max_y is None
    ):
        return

    frame_thickness_mm = float(inputs.frame_thickness_mm)
    base_frame_center_z = float(inputs.base_frame_center_z)

    main_min_x = float(inputs.seat_main_min_x)
    main_max_x = float(inputs.seat_main_max_x)
    main_min_y = float(inputs.seat_main_min_y)
    main_max_y = float(inputs.seat_main_max_y)

    chaise_min_x = float(inputs.seat_chaise_min_x)
    chaise_max_x = float(inputs.seat_chaise_max_x)
    chaise_min_y = float(inputs.seat_chaise_min_y)
    chaise_max_y = float(inputs.seat_chaise_max_y)
    chaise_width_mm = max(1.0, chaise_max_x - chaise_min_x)
    chaise_depth_mm = max(1.0, chaise_max_y - chaise_min_y)

    main_width_mm = max(1.0, main_max_x - main_min_x)
    main_depth_mm = max(1.0, main_max_y - main_min_y)
    main_center_x = (main_min_x + main_max_x) / 2.0
    main_center_y = (main_min_y + main_max_y) / 2.0
    chaise_center_x = (chaise_min_x + chaise_max_x) / 2.0
    chaise_center_y = (chaise_min_y + chaise_max_y) / 2.0

    main_back_y = main_min_y + (frame_thickness_mm / 2.0)
    main_front_y = main_max_y - (frame_thickness_mm / 2.0)
    chaise_back_y = chaise_min_y + (frame_thickness_mm / 2.0)
    chaise_front_y = chaise_max_y - (frame_thickness_mm / 2.0)

    _append_horizontal_beam(
        plan,
        name="beam_main_back",
        min_x=main_min_x,
        max_x=main_max_x,
        y=main_back_y,
        z=base_frame_center_z,
        thickness_mm=frame_thickness_mm,
    )
    _append_horizontal_beam(
        plan,
        name="beam_main_front",
        min_x=main_min_x,
        max_x=main_max_x,
        y=main_front_y,
        z=base_frame_center_z,
        thickness_mm=frame_thickness_mm,
    )
    _append_horizontal_beam(
        plan,
        name="beam_chaise_back",
        min_x=chaise_min_x,
        max_x=chaise_max_x,
        y=chaise_back_y,
        z=base_frame_center_z,
        thickness_mm=frame_thickness_mm,
    )
    _append_horizontal_beam(
        plan,
        name="beam_chaise_front",
        min_x=chaise_min_x,
        max_x=chaise_max_x,
        y=chaise_front_y,
        z=base_frame_center_z,
        thickness_mm=frame_thickness_mm,
    )

    side = str(inputs.corner_side or ("right" if chaise_min_x >= main_max_x else "left")).strip().lower()
    if side == "left":
        main_outer_x = main_max_x - (frame_thickness_mm / 2.0)
        chaise_outer_x = chaise_min_x + (frame_thickness_mm / 2.0)
        inner_return_x = chaise_max_x - (frame_thickness_mm / 2.0)
        gap_min_x = chaise_max_x
        gap_max_x = main_min_x
    else:
        main_outer_x = main_min_x + (frame_thickness_mm / 2.0)
        chaise_outer_x = chaise_max_x - (frame_thickness_mm / 2.0)
        inner_return_x = chaise_min_x + (frame_thickness_mm / 2.0)
        gap_min_x = main_max_x
        gap_max_x = chaise_min_x

    _append_vertical_beam(
        plan,
        name="beam_main_outer",
        x=main_outer_x,
        min_y=main_min_y,
        max_y=main_max_y,
        z=base_frame_center_z,
        thickness_mm=frame_thickness_mm,
    )
    _append_vertical_beam(
        plan,
        name="beam_chaise_outer",
        x=chaise_outer_x,
        min_y=chaise_min_y,
        max_y=chaise_max_y,
        z=base_frame_center_z,
        thickness_mm=frame_thickness_mm,
    )
    if chaise_max_y > (main_max_y + 1e-6):
        _append_vertical_beam(
            plan,
            name="beam_corner_inner_return",
            x=inner_return_x,
            min_y=main_max_y,
            max_y=chaise_max_y,
            z=base_frame_center_z,
            thickness_mm=frame_thickness_mm,
        )

    join_gap_mm = max(0.0, float(gap_max_x) - float(gap_min_x))
    if join_gap_mm > 1e-6:
        _append_horizontal_beam(
            plan,
            name="beam_corner_bridge_back",
            min_x=gap_min_x,
            max_x=gap_max_x,
            y=main_back_y,
            z=base_frame_center_z,
            thickness_mm=frame_thickness_mm,
        )
        _append_horizontal_beam(
            plan,
            name="beam_corner_bridge_front",
            min_x=gap_min_x,
            max_x=gap_max_x,
            y=main_front_y,
            z=base_frame_center_z,
            thickness_mm=frame_thickness_mm,
        )

    chaise_cross_count = 2
    inner_width_mm = max(1.0, chaise_width_mm - (2.0 * frame_thickness_mm))
    cross_spacing_mm = inner_width_mm / (chaise_cross_count + 1)
    for i in range(chaise_cross_count):
        x = chaise_min_x + frame_thickness_mm + (cross_spacing_mm * (i + 1))
        plan.primitives.append(
            Primitive(
                name=f"beam_cross_chaise_{i + 1}",
                shape="beam",
                dimensions_mm=(
                    frame_thickness_mm,
                    max(1.0, chaise_depth_mm - (2.0 * frame_thickness_mm)),
                    frame_thickness_mm,
                ),
                location_mm=(x, chaise_center_y, base_frame_center_z),
            )
        )

    main_cross_count = max(2, min(4, int(inputs.seat_count) + 1))
    main_inner_width_mm = max(1.0, main_width_mm - (2.0 * frame_thickness_mm))
    main_cross_spacing_mm = main_inner_width_mm / (main_cross_count + 1)
    for i in range(main_cross_count):
        x = main_min_x + frame_thickness_mm + (main_cross_spacing_mm * (i + 1))
        plan.primitives.append(
            Primitive(
                name=f"beam_main_cross_{i + 1}",
                shape="beam",
                dimensions_mm=(
                    frame_thickness_mm,
                    max(1.0, main_depth_mm - (2.0 * frame_thickness_mm)),
                    frame_thickness_mm,
                ),
                location_mm=(x, main_center_y, base_frame_center_z),
            )
        )

    if not inputs.slats_enabled:
        plan.primitives.append(
            Primitive(
                name="seat_support",
                shape="board",
                dimensions_mm=(main_width_mm, main_depth_mm, frame_thickness_mm),
                location_mm=(main_center_x, main_center_y, inputs.seat_support_center_z),
            )
        )
        plan.primitives.append(
            Primitive(
                name="seat_support_chaise",
                shape="board",
                dimensions_mm=(chaise_width_mm, chaise_depth_mm, frame_thickness_mm),
                location_mm=(chaise_center_x, chaise_center_y, inputs.seat_support_center_z),
            )
        )

    post_x = inner_return_x
    post_y = main_max_y - (frame_thickness_mm / 2.0)
    post_z = base_frame_center_z
    plan.primitives.append(
        Primitive(
            name="beam_corner_post",
            shape="beam",
            dimensions_mm=(frame_thickness_mm, frame_thickness_mm, frame_thickness_mm),
            location_mm=(post_x, post_y, post_z),
        )
    )


SEAT_FRAME_STRATEGIES: dict[str, Callable] = {
    "default": _build_seat_frame_default,
    "corner_shared_corner_post": _build_seat_frame_corner_shared_corner_post,
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
            "layout_kind": inputs.layout_kind,
            "join_mode": inputs.corner_join_mode,
        },
    )
    strategy(plan, inputs)
