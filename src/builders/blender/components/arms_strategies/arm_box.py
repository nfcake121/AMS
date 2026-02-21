"""Box arms strategy."""

from __future__ import annotations

from src.builders.blender.plan_types import Anchor, Primitive


def _add_primitive(plan, primitive: Primitive, primitives_out: list) -> None:
    plan.primitives.append(primitive)
    primitives_out.append(primitive)


def build_arm_box_strategy(
    plan,
    *,
    side: str,
    seat_total_width_mm: float,
    arms_width_mm: float,
    seat_depth_mm: float,
    seat_height_mm: float,
    frame_thickness_mm: float,
    base_frame_top_z: float,
    primitives_out: list,
) -> None:
    is_left = side == "left"
    side_sign = -1.0 if is_left else 1.0
    legacy_arm_height_mm = max(frame_thickness_mm * 2.0, seat_height_mm * 0.65)
    legacy_arm_center_z = base_frame_top_z + (legacy_arm_height_mm / 2.0)
    arm_center_x = side_sign * ((seat_total_width_mm / 2.0) + (arms_width_mm / 2.0))

    arm_primitive = Primitive(
        name=f"{side}_arm_frame",
        shape="board",
        dimensions_mm=(arms_width_mm, seat_depth_mm, legacy_arm_height_mm),
        location_mm=(arm_center_x, 0.0, legacy_arm_center_z),
    )
    _add_primitive(plan, arm_primitive, primitives_out)
    plan.anchors.append(Anchor(name=f"arm_{side}_zone", location_mm=(arm_center_x, 0.0, seat_height_mm)))
