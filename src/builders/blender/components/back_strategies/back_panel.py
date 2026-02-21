"""Back panel strategy."""

from __future__ import annotations

from src.builders.blender.plan_types import Primitive


def build_back_panel_strategy(
    plan,
    *,
    seat_total_width_mm: float,
    back_frame_member_mm: float,
    back_frame_height_mm: float,
    back_panel_center: tuple[float, float, float],
) -> None:
    plan.primitives.append(
        Primitive(
            name="back_panel",
            shape="board",
            dimensions_mm=(seat_total_width_mm, back_frame_member_mm, back_frame_height_mm),
            location_mm=back_panel_center,
        )
    )
