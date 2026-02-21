"""Back straps strategy."""

from __future__ import annotations

from src.builders.blender.plan_types import Primitive


def build_back_straps_strategy(
    plan,
    *,
    back_strap_count: int,
    back_strap_width_mm: float,
    back_strap_thickness_mm: float,
    back_frame_height_mm: float,
    back_frame_member_mm: float,
    back_margin_z_mm: float,
    seat_total_width_mm: float,
    back_frame_base_z: float,
    back_frame_center_y: float,
) -> None:
    strap_center_x = 0.0
    strap_span_z_mm = max(1.0, (back_frame_height_mm - back_frame_member_mm) - (2.0 * back_margin_z_mm))
    effective_back_strap_count = max(1, int(back_strap_count))
    if effective_back_strap_count == 1:
        strap_centers_z = [back_frame_base_z + ((back_frame_height_mm - back_frame_member_mm) / 2.0)]
    else:
        step_mm = strap_span_z_mm / (effective_back_strap_count - 1)
        start_z = back_frame_base_z + back_margin_z_mm
        strap_centers_z = [start_z + (step_mm * i) for i in range(effective_back_strap_count)]

    for i, z in enumerate(strap_centers_z, start=1):
        plan.primitives.append(
            Primitive(
                name=f"back_strap_{i}",
                shape="board",
                dimensions_mm=(seat_total_width_mm, back_strap_thickness_mm, back_strap_width_mm),
                location_mm=(strap_center_x, back_frame_center_y, z),
            )
        )
