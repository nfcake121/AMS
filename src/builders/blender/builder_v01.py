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
    params: Dict[str, float] = field(default_factory=dict)


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


def _canon_arms_type(value: str) -> str:
    """Normalize arms type to one of: none, left, right, both."""
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower()
    if normalized in {"left", "right", "both", "none"}:
        return normalized
    return "none"


def _arms_count(arms_type: str) -> int:
    """Return number of arm blocks for a canonical arms_type."""
    if arms_type == "both":
        return 2
    if arms_type in {"left", "right"}:
        return 1
    return 0


def build_plan_from_ir(ir: dict) -> BuildPlan:
    """Create a sofa-frame geometry plan from resolved IR.

    Coordinate system: X is width (left/right), Y is depth (front/back),
    Z is up. seat_height_mm defines the top of the seat support board.
    """
    seat_width_mm = _ir_value(ir, "seat_width_mm", 600.0)
    seat_depth_mm = _ir_value(ir, "seat_depth_mm", 600.0)
    seat_height_mm = _ir_value(ir, "seat_height_mm", 440.0)
    seat_count = max(1, int(_ir_value(ir, "seat_count", 3)))
    seat_total_width_mm = seat_width_mm * seat_count

    frame = ir.get("frame", {}) if isinstance(ir.get("frame"), dict) else {}
    frame_thickness_mm = _ir_value(frame, "thickness_mm", 35.0)
    back_height_mm = _ir_value(frame, "back_height_above_seat_mm", 420.0)
    back_thickness_mm = _ir_value(frame, "back_thickness_mm", 90.0)

    arms = ir.get("arms", {}) if isinstance(ir.get("arms"), dict) else {}
    arms_type = _canon_arms_type(arms.get("type", "none"))
    arms_width_mm = _ir_value(arms, "width_mm", 120.0)
    arms_total_mm = arms_width_mm * _arms_count(arms_type)
    total_width_mm = seat_total_width_mm + arms_total_mm

    legs = ir.get("legs", {}) if isinstance(ir.get("legs"), dict) else {}
    legs_height_mm = _ir_value(legs, "height_mm", 160.0)
    legs_family = legs.get("family", "block")

    seat_support_thickness_mm = frame_thickness_mm

    slats = ir.get("slats", {}) if isinstance(ir.get("slats"), dict) else {}
    slats_enabled = bool(slats.get("enabled", False))
    slat_count = max(1, int(_ir_value(slats, "count", 14)))
    slat_width_mm = _ir_value(slats, "width_mm", 55.0)
    slat_thickness_mm = _ir_value(slats, "thickness_mm", 10.0)
    slat_arc_height_mm = _ir_value(slats, "arc_height_mm", 0.0)
    slat_arc_sign = _ir_value(slats, "arc_sign", -1.0)
    slat_margin_x_mm = _ir_value(slats, "margin_x_mm", 40.0)
    slat_margin_y_mm = _ir_value(slats, "margin_y_mm", 60.0)
    slat_clearance_mm = _ir_value(slats, "clearance_mm", 0.0)
    slat_mount_mode = slats.get("mount_mode", "rests_on_plane")
    if not isinstance(slat_mount_mode, str):
        slat_mount_mode = "rests_on_plane"
    slat_mount_mode = slat_mount_mode.strip().lower()
    if slat_mount_mode not in {"rests_on_plane", "centered"}:
        slat_mount_mode = "rests_on_plane"
    slat_mount_offset_mm = _ir_value(slats, "mount_offset_mm", 0.0)
    slat_rail_inset_mm = _ir_value(slats, "rail_inset_mm", 0.0)
    slat_rail_height_mm = _ir_value(slats, "rail_height_mm", frame_thickness_mm)
    slat_rail_width_mm = _ir_value(slats, "rail_width_mm", frame_thickness_mm)
    slat_rail_inset_y_mm = _ir_value(slats, "rail_inset_y_mm", slat_margin_y_mm)

    has_back_support = "back_support" in ir
    back_support = ir.get("back_support", {}) if isinstance(ir.get("back_support"), dict) else {}
    back_support_mode = back_support.get("mode", "panel")
    if not isinstance(back_support_mode, str):
        back_support_mode = "panel"
    back_support_mode = back_support_mode.strip().lower()
    if back_support_mode not in {"panel", "slats", "straps"}:
        back_support_mode = "panel"

    back_height_mm = _ir_value(back_support, "height_above_seat_mm", back_height_mm)
    back_thickness_mm = _ir_value(back_support, "thickness_mm", back_thickness_mm)
    back_offset_y_mm = _ir_value(back_support, "offset_y_mm", 0.0)
    back_margin_x_mm = _ir_value(back_support, "margin_x_mm", 40.0)
    back_margin_z_mm = _ir_value(back_support, "margin_z_mm", 30.0)

    back_slats = back_support.get("slats", {}) if isinstance(back_support.get("slats"), dict) else {}
    back_slat_count = max(1, int(_ir_value(back_slats, "count", 10)))
    back_slat_width_mm = _ir_value(back_slats, "width_mm", 35.0)
    back_slat_thickness_mm = _ir_value(back_slats, "thickness_mm", 10.0)
    back_slat_arc_height_mm = _ir_value(back_slats, "arc_height_mm", 0.0)
    back_slat_arc_sign = _ir_value(back_slats, "arc_sign", -1.0)

    back_straps = back_support.get("straps", {}) if isinstance(back_support.get("straps"), dict) else {}
    back_strap_count = max(1, int(_ir_value(back_straps, "count", 6)))
    back_strap_width_mm = _ir_value(back_straps, "width_mm", 30.0)
    back_strap_thickness_mm = _ir_value(back_straps, "thickness_mm", 6.0)

    # Z placement stack: legs -> base frame -> seat support -> back frame -> arms.
    # Seat support top aligns to seat_height_mm.
    seat_support_top_z = seat_height_mm
    seat_support_center_z = seat_support_top_z - (seat_support_thickness_mm / 2.0)
    base_frame_top_z = seat_support_top_z - seat_support_thickness_mm
    base_frame_center_z = base_frame_top_z - (frame_thickness_mm / 2.0)
    base_frame_bottom_z = base_frame_top_z - frame_thickness_mm
    legs_center_z = base_frame_bottom_z - (legs_height_mm / 2.0)

    plan = BuildPlan(metadata={
        "seat_count": str(seat_count),
        "legs_family": str(legs_family),
        "arms_type": str(arms_type),
        "seat_total_width_mm": str(seat_total_width_mm),
        "total_width_mm": str(total_width_mm),
    })

    # Base frame beams (outer perimeter of total frame).
    front_y = (seat_depth_mm / 2.0) - (frame_thickness_mm / 2.0)
    back_y = -(seat_depth_mm / 2.0) + (frame_thickness_mm / 2.0)
    left_x = -(total_width_mm / 2.0) + (frame_thickness_mm / 2.0)
    right_x = (total_width_mm / 2.0) - (frame_thickness_mm / 2.0)

    plan.primitives.extend(
        [
            Primitive(
                name="beam_front",
                shape="beam",
                dimensions_mm=(total_width_mm, frame_thickness_mm, frame_thickness_mm),
                location_mm=(0.0, front_y, base_frame_center_z),
            ),
            Primitive(
                name="beam_back",
                shape="beam",
                dimensions_mm=(total_width_mm, frame_thickness_mm, frame_thickness_mm),
                location_mm=(0.0, back_y, base_frame_center_z),
            ),
            Primitive(
                name="beam_left",
                shape="beam",
                dimensions_mm=(frame_thickness_mm, seat_depth_mm, frame_thickness_mm),
                location_mm=(left_x, 0.0, base_frame_center_z),
            ),
            Primitive(
                name="beam_right",
                shape="beam",
                dimensions_mm=(frame_thickness_mm, seat_depth_mm, frame_thickness_mm),
                location_mm=(right_x, 0.0, base_frame_center_z),
            ),
        ]
    )

    # Cross beams across depth (along Y), evenly spaced along X.
    cross_count = max(2, min(4, seat_count + 1))
    inner_width_mm = max(1.0, total_width_mm - (2.0 * frame_thickness_mm))
    cross_spacing_mm = inner_width_mm / (cross_count + 1)
    for i in range(cross_count):
        x = -(inner_width_mm / 2.0) + cross_spacing_mm * (i + 1)
        plan.primitives.append(
            Primitive(
                name=f"beam_cross_{i + 1}",
                shape="beam",
                dimensions_mm=(frame_thickness_mm, seat_depth_mm - (2.0 * frame_thickness_mm), frame_thickness_mm),
                location_mm=(x, 0.0, base_frame_center_z),
            )
        )

    # Seat support board (seat area only) on top of base frame.
    if not slats_enabled:
        plan.primitives.append(
            Primitive(
                name="seat_support",
                shape="board",
                dimensions_mm=(seat_total_width_mm, seat_depth_mm, seat_support_thickness_mm),
                location_mm=(0.0, 0.0, seat_support_center_z),
            )
        )

    # Slats (lamellas) across X, running along Y with front/back margins.
    if slats_enabled:
        slat_length_mm = max(1.0, seat_depth_mm - (2.0 * slat_margin_y_mm))
        rail_length_mm = max(1.0, seat_depth_mm - (2.0 * slat_rail_inset_y_mm))
        usable_width_mm = max(1.0, seat_total_width_mm - (2.0 * slat_margin_x_mm))
        if slat_count == 1:
            slat_centers_x = [0.0]
        else:
            span_mm = max(0.0, usable_width_mm - slat_width_mm)
            step_mm = span_mm / (slat_count - 1)
            start_x = -(usable_width_mm / 2.0) + (slat_width_mm / 2.0)
            slat_centers_x = [start_x + (step_mm * i) for i in range(slat_count)]

        # Slats mount to the base frame top plane unless explicitly centered.
        slat_plane_z_mm = base_frame_top_z
        if slat_mount_mode == "centered":
            slat_center_z = seat_support_top_z - (slat_thickness_mm / 2.0) + slat_clearance_mm
        else:
            slat_center_z = (
                slat_plane_z_mm
                + slat_mount_offset_mm
                + slat_clearance_mm
                + (slat_thickness_mm / 2.0)
            )

        min_x = min(slat_centers_x) - (slat_width_mm / 2.0)
        max_x = max(slat_centers_x) + (slat_width_mm / 2.0)
        rail_height_mm = slat_rail_height_mm
        rail_width_mm = slat_rail_width_mm
        rail_depth_mm = rail_length_mm
        rail_top_z = slat_plane_z_mm
        rail_center_z = rail_top_z - (rail_height_mm / 2.0)
        rail_left_x = min_x + (rail_width_mm / 2.0) + slat_rail_inset_mm
        rail_right_x = max_x - (rail_width_mm / 2.0) - slat_rail_inset_mm
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
                    dimensions_mm=(slat_width_mm, slat_length_mm, slat_thickness_mm),
                    location_mm=(x, 0.0, slat_center_z),
                    params={
                        "arc_height_mm": slat_arc_height_mm,
                        "arc_sign": slat_arc_sign,
                        "orientation": "horizontal",
                        "mount_mode": slat_mount_mode,
                        "mount_offset_mm": slat_mount_offset_mm,
                        "clearance_mm": slat_clearance_mm,
                    },
                )
            )

    # Back support (panel/slats/straps) at rear edge.
    back_frame_plane_y = -(seat_depth_mm / 2.0)
    back_plane_y = back_frame_plane_y - (back_thickness_mm / 2.0) + back_offset_y_mm
    back_center_z = seat_support_top_z + (back_height_mm / 2.0)
    back_panel_center = (0.0, back_plane_y, back_center_z)

    if not has_back_support:
        # Backward-compatible panel using frame.back_* dimensions.
        plan.primitives.append(
            Primitive(
                name="back_frame",
                shape="board",
                dimensions_mm=(total_width_mm, back_thickness_mm, back_height_mm),
                location_mm=back_panel_center,
            )
        )
    elif back_support_mode == "panel":
        plan.primitives.append(
            Primitive(
                name="back_panel",
                shape="board",
                dimensions_mm=(total_width_mm, back_thickness_mm, back_height_mm),
                location_mm=back_panel_center,
            )
        )
    elif back_support_mode == "slats":
        slat_height_mm = max(1.0, back_height_mm - (2.0 * back_margin_z_mm))
        back_slat_center_z = seat_support_top_z + back_margin_z_mm + (slat_height_mm / 2.0)
        back_slat_plane_y = back_frame_plane_y + back_offset_y_mm
        back_slat_center_y = back_slat_plane_y - (back_slat_thickness_mm / 2.0)
        usable_width_mm = max(1.0, seat_total_width_mm - (2.0 * back_margin_x_mm))
        if back_slat_count == 1:
            slat_centers_x = [0.0]
        else:
            span_mm = max(0.0, usable_width_mm - back_slat_width_mm)
            step_mm = span_mm / (back_slat_count - 1)
            start_x = -(usable_width_mm / 2.0) + (back_slat_width_mm / 2.0)
            slat_centers_x = [start_x + (step_mm * i) for i in range(back_slat_count)]

        plan.anchors.append(Anchor(name="back_slat_plane_y", location_mm=(0.0, back_slat_plane_y, 0.0)))
        plan.anchors.append(Anchor(name="back_slat_center_z", location_mm=(0.0, 0.0, back_slat_center_z)))

        min_x = min(slat_centers_x) - (back_slat_width_mm / 2.0)
        max_x = max(slat_centers_x) + (back_slat_width_mm / 2.0)
        back_rail_inset_mm = _ir_value(back_support, "rail_inset_mm", 0.0)
        back_rail_width_mm = _ir_value(back_support, "rail_width_mm", frame_thickness_mm)
        back_rail_depth_mm = _ir_value(back_support, "rail_depth_mm", back_thickness_mm)
        back_rail_height_mm = _ir_value(back_support, "rail_height_mm", slat_height_mm)
        rail_left_x = min_x + (back_rail_width_mm / 2.0) + back_rail_inset_mm
        rail_right_x = max_x - (back_rail_width_mm / 2.0) - back_rail_inset_mm
        if (
            back_rail_width_mm > 0.0
            and back_rail_depth_mm > 0.0
            and back_rail_height_mm > 0.0
            and rail_left_x < rail_right_x
        ):
            plan.primitives.append(
                Primitive(
                    name="back_rail_left",
                    shape="beam",
                    dimensions_mm=(back_rail_width_mm, back_rail_depth_mm, back_rail_height_mm),
                    location_mm=(rail_left_x, back_slat_center_y, back_slat_center_z),
                )
            )
            plan.primitives.append(
                Primitive(
                    name="back_rail_right",
                    shape="beam",
                    dimensions_mm=(back_rail_width_mm, back_rail_depth_mm, back_rail_height_mm),
                    location_mm=(rail_right_x, back_slat_center_y, back_slat_center_z),
                )
            )
            plan.anchors.append(
                Anchor(name="back_rail_left", location_mm=(rail_left_x, back_slat_center_y, back_slat_center_z))
            )
            plan.anchors.append(
                Anchor(name="back_rail_right", location_mm=(rail_right_x, back_slat_center_y, back_slat_center_z))
            )

        for i, x in enumerate(slat_centers_x, start=1):
            plan.primitives.append(
                Primitive(
                    name=f"back_slat_{i}",
                    shape="slat",
                    dimensions_mm=(back_slat_width_mm, back_slat_thickness_mm, slat_height_mm),
                    location_mm=(x, back_slat_center_y, back_slat_center_z),
                    params={
                        "arc_height_mm": back_slat_arc_height_mm,
                        "arc_sign": back_slat_arc_sign,
                        "orientation": "vertical",
                    },
                )
            )
            plan.anchors.append(
                Anchor(name=f"back_slat_{i}", location_mm=(x, back_slat_center_y, back_slat_center_z))
            )
    elif back_support_mode == "straps":
        strap_center_x = 0.0
        strap_span_z_mm = max(1.0, back_height_mm - (2.0 * back_margin_z_mm))
        if back_strap_count == 1:
            strap_centers_z = [seat_support_top_z + (back_height_mm / 2.0)]
        else:
            step_mm = strap_span_z_mm / (back_strap_count - 1)
            start_z = seat_support_top_z + back_margin_z_mm
            strap_centers_z = [start_z + (step_mm * i) for i in range(back_strap_count)]

        for i, z in enumerate(strap_centers_z, start=1):
            plan.primitives.append(
                Primitive(
                    name=f"back_strap_{i}",
                    shape="board",
                    dimensions_mm=(seat_total_width_mm, back_strap_thickness_mm, back_strap_width_mm),
                    location_mm=(strap_center_x, back_plane_y, z),
                )
            )

    # Simple arm frames as boards when present.
    # Arms sit outside the seat area in X, and their bottoms align to the base frame top.
    arm_height_mm = max(frame_thickness_mm * 2.0, seat_height_mm * 0.65)
    arm_center_z = base_frame_top_z + (arm_height_mm / 2.0)
    if arms_type in {"both", "left"}:
        left_arm_center_x = -(seat_total_width_mm / 2.0) - (arms_width_mm / 2.0)
        plan.primitives.append(
            Primitive(
                name="left_arm_frame",
                shape="board",
                dimensions_mm=(arms_width_mm, seat_depth_mm, arm_height_mm),
                location_mm=(left_arm_center_x, 0.0, arm_center_z),
            )
        )
        plan.anchors.append(
            Anchor(name="arm_left_zone", location_mm=(left_arm_center_x, 0.0, seat_height_mm))
        )
    if arms_type in {"both", "right"}:
        right_arm_center_x = (seat_total_width_mm / 2.0) + (arms_width_mm / 2.0)
        plan.primitives.append(
            Primitive(
                name="right_arm_frame",
                shape="board",
                dimensions_mm=(arms_width_mm, seat_depth_mm, arm_height_mm),
                location_mm=(right_arm_center_x, 0.0, arm_center_z),
            )
        )
        plan.anchors.append(
            Anchor(name="arm_right_zone", location_mm=(right_arm_center_x, 0.0, seat_height_mm))
        )

    # Leg anchors and leg primitives at corners.
    leg_offset_x = (total_width_mm / 2.0) - (frame_thickness_mm / 2.0)
    leg_offset_y = (seat_depth_mm / 2.0) - (frame_thickness_mm / 2.0)
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
                dimensions_mm=(frame_thickness_mm, frame_thickness_mm, legs_height_mm),
                location_mm=point,
            )
        )

    # Anchors for zones.
    back_bottom_z = seat_support_top_z
    back_top_z = seat_support_top_z + back_height_mm
    back_inner_center = (0.0, back_plane_y, seat_support_top_z + (back_height_mm / 2.0))
    left_back_corner = (-(seat_total_width_mm / 2.0), back_plane_y, back_bottom_z)
    right_back_corner = ((seat_total_width_mm / 2.0), back_plane_y, back_bottom_z)

    plan.anchors.extend(
        [
            Anchor(name="seat_zone", location_mm=(0.0, 0.0, seat_support_center_z)),
            Anchor(name="back_zone", location_mm=back_panel_center),
            Anchor(name="back_bottom_edge_center", location_mm=(0.0, back_plane_y, back_bottom_z)),
            Anchor(name="back_top_edge_center", location_mm=(0.0, back_plane_y, back_top_z)),
            Anchor(name="back_inner_plane_center", location_mm=back_inner_center),
            Anchor(name="left_back_corner", location_mm=left_back_corner),
            Anchor(name="right_back_corner", location_mm=right_back_corner),
        ]
    )

    return plan
