"""Generate a geometry plan and anchors for Blender builds."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Primitive:
    """Represents a basic geometry primitive."""

    name: str
    shape: str
    dimensions_mm: Tuple[float, float, float]
    location_mm: Tuple[float, float, float]
    rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class Anchor:
    """Named anchor or empty location."""

    name: str
    location_mm: Tuple[float, float, float]


@dataclass
class BuildPlan:
    """Container for primitives and anchors to build a sofa frame."""

    primitives: List[Primitive] = field(default_factory=list)
    anchors: List[Anchor] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


def _ir_value(ir: dict, key: str, default: float) -> float:
    """Helper to fetch numeric values from IR with defaults."""
    value = ir.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def build_plan_from_ir(ir: dict) -> BuildPlan:
    """Create a minimal geometry plan from resolved IR."""
    seat_width_mm = _ir_value(ir, "seat_width_mm", 2000.0)
    seat_depth_mm = _ir_value(ir, "seat_depth_mm", 900.0)
    seat_height_mm = _ir_value(ir, "seat_height_mm", 450.0)
    seat_count = int(_ir_value(ir, "seat_count", 3))
    back_height_mm = _ir_value(ir, "back_height_above_seat_mm", 450.0)
    frame = ir.get("frame", {}) if isinstance(ir.get("frame"), dict) else {}
    frame_thickness_mm = _ir_value(frame, "thickness_mm", 40.0)

    arms = ir.get("arms", {}) if isinstance(ir.get("arms"), dict) else {}
    arms_type = arms.get("type", "block")
    arms_width_mm = _ir_value(arms, "width_mm", 120.0)

    legs = ir.get("legs", {}) if isinstance(ir.get("legs"), dict) else {}
    legs_height_mm = _ir_value(legs, "height_mm", 120.0)
    legs_family = legs.get("family", "block")

    plan = BuildPlan(metadata={
        "seat_count": str(seat_count),
        "legs_family": str(legs_family),
    })

    seat_location = (0.0, 0.0, seat_height_mm / 2.0)
    plan.primitives.append(
        Primitive(
            name="seat_base",
            shape="cube",
            dimensions_mm=(seat_width_mm, seat_depth_mm, seat_height_mm),
            location_mm=seat_location,
        )
    )

    back_location = (
        0.0,
        -(seat_depth_mm / 2.0) + (frame_thickness_mm / 2.0),
        seat_height_mm + (back_height_mm / 2.0),
    )
    plan.primitives.append(
        Primitive(
            name="backrest",
            shape="cube",
            dimensions_mm=(seat_width_mm, frame_thickness_mm, back_height_mm),
            location_mm=back_location,
        )
    )

    if arms_type != "none":
        arm_height_mm = seat_height_mm + (back_height_mm * 0.35)
        arm_depth_mm = seat_depth_mm * 0.9
        arm_y = 0.0
        arm_z = arm_height_mm / 2.0
        arm_offset_x = (seat_width_mm / 2.0) - (arms_width_mm / 2.0)
        plan.primitives.append(
            Primitive(
                name="arm_left",
                shape="cube",
                dimensions_mm=(arms_width_mm, arm_depth_mm, arm_height_mm),
                location_mm=(-arm_offset_x, arm_y, arm_z),
            )
        )
        plan.primitives.append(
            Primitive(
                name="arm_right",
                shape="cube",
                dimensions_mm=(arms_width_mm, arm_depth_mm, arm_height_mm),
                location_mm=(arm_offset_x, arm_y, arm_z),
            )
        )

    leg_offset_x = (seat_width_mm / 2.0) - (frame_thickness_mm * 1.5)
    leg_offset_y = (seat_depth_mm / 2.0) - (frame_thickness_mm * 1.5)
    leg_points = [
        (-leg_offset_x, -leg_offset_y, legs_height_mm / 2.0),
        (leg_offset_x, -leg_offset_y, legs_height_mm / 2.0),
        (-leg_offset_x, leg_offset_y, legs_height_mm / 2.0),
        (leg_offset_x, leg_offset_y, legs_height_mm / 2.0),
    ]

    for index, point in enumerate(leg_points, start=1):
        plan.anchors.append(Anchor(name=f"leg_point_{index}", location_mm=point))
        plan.primitives.append(
            Primitive(
                name=f"leg_{index}",
                shape=legs_family,
                dimensions_mm=(frame_thickness_mm, frame_thickness_mm, legs_height_mm),
                location_mm=point,
            )
        )

    plan.anchors.extend(
        [
            Anchor(name="seat_zone", location_mm=seat_location),
            Anchor(name="back_zone", location_mm=back_location),
            Anchor(name="arm_left_zone", location_mm=(-leg_offset_x, 0.0, seat_height_mm)),
            Anchor(name="arm_right_zone", location_mm=(leg_offset_x, 0.0, seat_height_mm)),
        ]
    )

    return plan
