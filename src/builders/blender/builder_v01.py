"""Generate a geometry plan and anchors for Blender builds."""

import math
import os
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


def _ir_bool(ir: dict, key: str, default: bool) -> bool:
    value = ir.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(default)


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


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, float(value)))


def _primitive_bbox_world(primitive: Primitive) -> Dict[str, Tuple[float, float, float]]:
    """Axis-aligned bbox for a primitive in world coordinates (plan space)."""
    dx, dy, dz = primitive.dimensions_mm
    cx, cy, cz = primitive.location_mm
    half_x = float(dx) / 2.0
    half_y = float(dy) / 2.0
    half_z = float(dz) / 2.0
    try:
        rx_deg, ry_deg, rz_deg = primitive.rotation_deg
    except (TypeError, ValueError):
        rx_deg, ry_deg, rz_deg = (0.0, 0.0, 0.0)
    if rx_deg == 0.0 and ry_deg == 0.0 and rz_deg == 0.0:
        world_half_x = half_x
        world_half_y = half_y
        world_half_z = half_z
    else:
        rx = math.radians(float(rx_deg))
        ry = math.radians(float(ry_deg))
        rz = math.radians(float(rz_deg))
        cxr, sxr = math.cos(rx), math.sin(rx)
        cyr, syr = math.cos(ry), math.sin(ry)
        czr, szr = math.cos(rz), math.sin(rz)

        # Blender default Euler order is XYZ.
        r00 = cyr * czr
        r01 = -cyr * szr
        r02 = syr
        r10 = sxr * syr * czr + cxr * szr
        r11 = -sxr * syr * szr + cxr * czr
        r12 = -sxr * cyr
        r20 = -cxr * syr * czr + sxr * szr
        r21 = cxr * syr * szr + sxr * czr
        r22 = cxr * cyr

        world_half_x = abs(r00) * half_x + abs(r01) * half_y + abs(r02) * half_z
        world_half_y = abs(r10) * half_x + abs(r11) * half_y + abs(r12) * half_z
        world_half_z = abs(r20) * half_x + abs(r21) * half_y + abs(r22) * half_z
    return {
        "min": (cx - world_half_x, cy - world_half_y, cz - world_half_z),
        "max": (cx + world_half_x, cy + world_half_y, cz + world_half_z),
    }


def _primitives_union_bbox(primitives: List[Primitive]) -> Dict[str, Tuple[float, float, float]]:
    if not primitives:
        return {
            "min": (0.0, 0.0, 0.0),
            "max": (0.0, 0.0, 0.0),
        }
    min_x = float("inf")
    min_y = float("inf")
    min_z = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")
    max_z = float("-inf")
    for primitive in primitives:
        bbox = _primitive_bbox_world(primitive)
        bmin = bbox["min"]
        bmax = bbox["max"]
        min_x = min(min_x, bmin[0])
        min_y = min(min_y, bmin[1])
        min_z = min(min_z, bmin[2])
        max_x = max(max_x, bmax[0])
        max_y = max(max_y, bmax[1])
        max_z = max(max_z, bmax[2])
    return {
        "min": (min_x, min_y, min_z),
        "max": (max_x, max_y, max_z),
    }


def _debug_env_enabled() -> bool:
    falsey = {"", "0", "false", "off", "no", "none"}
    for key, value in os.environ.items():
        if not key.startswith("DEBUG"):
            continue
        if str(value).strip().lower() not in falsey:
            return True
    return False


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
    arms_profile_raw = arms.get("profile", "")
    if isinstance(arms_profile_raw, str):
        arms_profile_candidate = arms_profile_raw.strip().lower()
    else:
        arms_profile_candidate = ""
    arms_style_raw = arms.get("style", "box")
    if isinstance(arms_style_raw, str):
        arms_style = arms_style_raw.strip().lower()
    else:
        arms_style = "box"
    if arms_style not in {"box", "scandi_frame", "frame_box_open", "scandi_open_frame"}:
        arms_style = "box"
    if arms_profile_candidate not in {"box", "scandi_frame", "frame_box_open", "scandi_open_frame"}:
        arms_profile_candidate = ""
    if arms_profile_candidate in {"scandi_frame", "frame_box_open", "scandi_open_frame"}:
        arms_profile = "frame_box_open"
    elif arms_profile_candidate == "box":
        # Backward compatibility with style-driven scandi IRs.
        if arms_style in {"scandi_frame", "frame_box_open", "scandi_open_frame"}:
            arms_profile = "frame_box_open"
        else:
            arms_profile = "box"
    else:
        arms_profile = "frame_box_open" if arms_style in {"scandi_frame", "frame_box_open", "scandi_open_frame"} else "box"

    arm_back_height_source = back_height_mm
    back_support_for_arms = ir.get("back_support", {}) if isinstance(ir.get("back_support"), dict) else {}
    arm_back_height_source = _ir_value(back_support_for_arms, "height_above_seat_mm", arm_back_height_source)
    arm_height_mm = max(1.0, _ir_value(arms, "height_mm", seat_height_mm + (arm_back_height_source * 0.35)))

    arm_length_y_mode_raw = arms.get("length_y_mode", "match_seat")
    if isinstance(arm_length_y_mode_raw, str):
        arm_length_y_mode = arm_length_y_mode_raw.strip().lower()
    else:
        arm_length_y_mode = "match_seat"
    if arm_length_y_mode not in {"match_seat", "custom"}:
        arm_length_y_mode = "match_seat"
    arm_length_y_custom_mm = max(1.0, _ir_value(arms, "length_y_mm", seat_depth_mm))
    arm_inset_y_front_mm = max(0.0, _ir_value(arms, "inset_y_front_mm", 25.0))
    arm_inset_y_back_mm = max(0.0, _ir_value(arms, "inset_y_back_mm", 10.0))
    arm_clearance_to_seat_mm = _clamp(_ir_value(arms, "clearance_to_seat_mm", 2.0), 0.0, 30.0)
    arm_thickness_mm = _ir_value(arms, "thickness_mm", frame_thickness_mm)
    arm_thickness_mm = _clamp(arm_thickness_mm, 18.0, 30.0)
    arm_inner_clearance_mm = _clamp(_ir_value(arms, "inner_clearance_mm", 8.0), 6.0, 12.0)
    arm_cap_overhang_mm = _clamp(_ir_value(arms, "cap_overhang_mm", _ir_value(arms, "top_overhang_mm", 8.0)), 5.0, 15.0)
    arm_outer_rail_width_mm = _clamp(_ir_value(arms, "outer_rail_width_mm", 56.0), 40.0, 80.0)
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
    back_rail_inset_mm = _ir_value(back_support, "rail_inset_mm", 0.0)
    back_rail_width_mm = _ir_value(back_support, "rail_width_mm", frame_thickness_mm)
    back_rail_depth_mm = _ir_value(back_support, "rail_depth_mm", frame_thickness_mm)
    back_rail_height_mm = _ir_value(back_support, "rail_height_mm", back_rail_width_mm)
    bottom_rail_split = _ir_bool(back_support, "bottom_rail_split", False)
    bottom_rail_gap_mm = _ir_value(back_support, "bottom_rail_gap_mm", 60.0)
    split_center_requested = _ir_bool(back_support, "split_center", False)
    bottom_rail_attach_mode = str(back_support.get("bottom_rail_attach_mode", "seat_rear_beam")).strip().lower()
    if bottom_rail_attach_mode not in {"seat_rear_beam", "none"}:
        bottom_rail_attach_mode = "seat_rear_beam"
    raw_frame_layout = back_support.get("frame_layout")
    if isinstance(raw_frame_layout, str):
        frame_layout = raw_frame_layout.strip().lower()
    else:
        frame_layout = "split_2" if bottom_rail_split else "single"
    if frame_layout not in {"single", "split_2"}:
        frame_layout = "single"
    center_post = back_support.get("center_post", {}) if isinstance(back_support.get("center_post"), dict) else {}
    center_post_enabled = _ir_bool(center_post, "enabled", False)
    center_post_thickness_mm = _ir_value(center_post, "thickness_mm", back_rail_width_mm)
    if "center_post_width_mm" in back_support:
        center_post_width_mm = _ir_value(back_support, "center_post_width_mm", back_rail_width_mm)
    elif center_post_enabled or "thickness_mm" in center_post:
        center_post_width_mm = center_post_thickness_mm
    else:
        center_post_width_mm = back_rail_width_mm
    default_bottom_rail_height_mm = max(10.0, round(back_rail_height_mm * 0.5))
    has_bottom_rail_height = "bottom_rail_height_mm" in back_support
    has_legacy_bottom_rail_thickness = "bottom_rail_thickness_mm" in back_support
    if has_bottom_rail_height:
        bottom_rail_height_mm = _ir_value(back_support, "bottom_rail_height_mm", default_bottom_rail_height_mm)
    elif has_legacy_bottom_rail_thickness:
        legacy_value = _ir_value(back_support, "bottom_rail_thickness_mm", default_bottom_rail_height_mm)
        if legacy_value < back_rail_height_mm:
            bottom_rail_height_mm = legacy_value
        else:
            bottom_rail_height_mm = default_bottom_rail_height_mm
    else:
        bottom_rail_height_mm = default_bottom_rail_height_mm

    back_slats = back_support.get("slats", {}) if isinstance(back_support.get("slats"), dict) else {}
    back_slat_count = max(1, int(_ir_value(back_slats, "count", 10)))
    back_slat_width_mm = _ir_value(back_slats, "width_mm", 35.0)
    back_slat_thickness_mm = _ir_value(back_slats, "thickness_mm", 10.0)
    back_slat_arc_height_mm = _ir_value(back_slats, "arc_height_mm", 0.0)
    back_slat_arc_sign = _ir_value(back_slats, "arc_sign", -1.0)
    back_slat_orientation_raw = back_slats.get("orientation", "vertical")
    if isinstance(back_slat_orientation_raw, str):
        back_slat_orientation = back_slat_orientation_raw.strip().lower()
    else:
        back_slat_orientation = "vertical"
    if back_slat_orientation not in {"vertical", "horizontal"}:
        back_slat_orientation = "vertical"
    back_slat_layout_raw = back_slats.get("layout", "full")
    if isinstance(back_slat_layout_raw, str):
        back_slat_layout = back_slat_layout_raw.strip().lower()
    else:
        back_slat_layout = "full"
    if back_slat_layout not in {"full", "split_center"}:
        back_slat_layout = "full"
    has_back_slat_gap = "gap_mm" in back_slats
    back_slat_gap_mm = max(0.0, _ir_value(back_slats, "gap_mm", 0.0))
    back_slat_center_gap_mm = max(0.0, _ir_value(back_slats, "center_gap_mm", 0.0))
    if back_slat_layout == "split_center":
        split_center_requested = True
    if center_post_enabled:
        split_center_requested = True
    if split_center_requested:
        frame_layout = "split_2"

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
        "arms_profile": str(arms_profile),
        "arms_style": str(arms_style),
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

    # Back support uses a frame tied directly to the rear seat rail.
    back_offset_y_micro_mm = _clamp(back_offset_y_mm, -80.0, 80.0)
    seat_back_rail_center_y = back_y
    seat_back_rail_outer_face_y = seat_back_rail_center_y - (frame_thickness_mm / 2.0)
    y_back_seat = seat_back_rail_outer_face_y
    seat_rear_rail_center = (0.0, seat_back_rail_center_y, base_frame_center_z)
    seat_rear_rail_top_z = base_frame_top_z

    back_rail_width_mm = max(1.0, back_rail_width_mm)
    back_rail_depth_mm = max(1.0, back_rail_depth_mm)
    back_rail_height_mm = max(1.0, back_rail_height_mm)
    back_frame_member_mm = max(1.0, back_thickness_mm)
    bottom_rail_height_mm = max(10.0, bottom_rail_height_mm)
    center_post_width_mm = max(1.0, center_post_width_mm)

    if bottom_rail_attach_mode == "seat_rear_beam":
        back_frame_plane_y = y_back_seat + back_offset_y_micro_mm
    else:
        back_frame_plane_y = (-(seat_depth_mm / 2.0)) + back_offset_y_mm
    back_frame_base_z = seat_rear_rail_top_z
    back_frame_top_z = max(back_frame_base_z + 1.0, seat_support_top_z + back_height_mm)
    back_frame_height_mm = back_frame_top_z - back_frame_base_z
    back_frame_center_y = back_frame_plane_y - (back_rail_depth_mm / 2.0)
    back_frame_origin = (0.0, back_frame_plane_y, back_frame_base_z)
    back_center_z = back_frame_base_z + (back_frame_height_mm / 2.0)
    back_panel_center = (0.0, back_frame_center_y, back_center_z)
    rail_left_x = -(seat_total_width_mm / 2.0) + (back_rail_width_mm / 2.0)
    rail_right_x = (seat_total_width_mm / 2.0) - (back_rail_width_mm / 2.0)

    back_frame_debug_primitives: List[Primitive] = []
    back_slat_debug_primitives: List[Primitive] = []
    back_slats_bbox_inner_text = "n/a"

    if has_back_support:
        back_upright_center_z = back_frame_base_z + (back_frame_height_mm / 2.0)

        back_rail_left = Primitive(
            name="back_rail_left",
            shape="beam",
            dimensions_mm=(back_rail_width_mm, back_rail_depth_mm, back_frame_height_mm),
            location_mm=(rail_left_x, back_frame_center_y, back_upright_center_z),
        )
        back_rail_right = Primitive(
            name="back_rail_right",
            shape="beam",
            dimensions_mm=(back_rail_width_mm, back_rail_depth_mm, back_frame_height_mm),
            location_mm=(rail_right_x, back_frame_center_y, back_upright_center_z),
        )
        plan.primitives.extend([back_rail_left, back_rail_right])
        back_frame_debug_primitives.extend([back_rail_left, back_rail_right])
        plan.anchors.extend(
            [
                Anchor(name="back_rail_left", location_mm=back_rail_left.location_mm),
                Anchor(name="back_rail_right", location_mm=back_rail_right.location_mm),
            ]
        )

    if not has_back_support:
        # Backward-compatible panel using frame.back_* dimensions.
        legacy_back_plane_y = seat_back_rail_outer_face_y - (back_thickness_mm / 2.0) + back_offset_y_mm
        legacy_back_center_z = seat_support_top_z + (back_height_mm / 2.0)
        plan.primitives.append(
            Primitive(
                name="back_frame",
                shape="board",
                dimensions_mm=(total_width_mm, back_thickness_mm, back_height_mm),
                location_mm=(0.0, legacy_back_plane_y, legacy_back_center_z),
            )
        )
    elif back_support_mode == "panel":
        plan.primitives.append(
            Primitive(
                name="back_panel",
                shape="board",
                dimensions_mm=(seat_total_width_mm, back_frame_member_mm, back_frame_height_mm),
                location_mm=back_panel_center,
            )
        )
    elif back_support_mode == "slats":
        inset_x_mm = max(3.0, back_rail_inset_mm)
        inset_z_mm = max(3.0, back_rail_inset_mm)
        margin_x_mm = max(0.0, back_margin_x_mm)
        margin_z_mm = max(0.0, back_margin_z_mm)

        frame_inner_min_x = rail_left_x + (back_rail_width_mm / 2.0)
        frame_inner_max_x = rail_right_x - (back_rail_width_mm / 2.0)
        frame_inner_width_mm = max(1.0, frame_inner_max_x - frame_inner_min_x)

        bottom_rail_center_z = back_frame_base_z + (bottom_rail_height_mm / 2.0)
        top_rail_center_z = back_frame_top_z - (back_rail_height_mm / 2.0)

        back_rail_bottom = Primitive(
            name="back_rail_bottom",
            shape="beam",
            dimensions_mm=(frame_inner_width_mm, back_rail_depth_mm, bottom_rail_height_mm),
            location_mm=(0.0, back_frame_center_y, bottom_rail_center_z),
        )
        back_rail_top = Primitive(
            name="back_rail_top",
            shape="beam",
            dimensions_mm=(frame_inner_width_mm, back_rail_depth_mm, back_rail_height_mm),
            location_mm=(0.0, back_frame_center_y, top_rail_center_z),
        )
        inner_bottom_frame_z = bottom_rail_center_z + (bottom_rail_height_mm / 2.0)
        inner_top_frame_z = top_rail_center_z - (back_rail_height_mm / 2.0)
        center_gap_half_x = 0.0

        plan.primitives.extend([back_rail_bottom, back_rail_top])
        back_frame_debug_primitives.extend([back_rail_bottom, back_rail_top])
        plan.anchors.extend(
            [
                Anchor(name="back_rail_bottom", location_mm=back_rail_bottom.location_mm),
                Anchor(name="back_rail_top", location_mm=back_rail_top.location_mm),
            ]
        )

        if frame_layout == "split_2":
            center_post_height_mm = max(1.0, inner_top_frame_z - inner_bottom_frame_z)
            center_post_center_z = inner_bottom_frame_z + (center_post_height_mm / 2.0)
            back_rail_center = Primitive(
                name="back_rail_center",
                shape="beam",
                dimensions_mm=(center_post_width_mm, back_rail_depth_mm, center_post_height_mm),
                location_mm=(0.0, back_frame_center_y, center_post_center_z),
            )
            plan.primitives.append(back_rail_center)
            back_frame_debug_primitives.append(back_rail_center)
            plan.anchors.append(Anchor(name="back_rail_center", location_mm=back_rail_center.location_mm))
            center_gap_half_x = (center_post_width_mm / 2.0) + inset_x_mm

        inner_min_x = frame_inner_min_x + inset_x_mm + margin_x_mm
        inner_max_x = frame_inner_max_x - inset_x_mm - margin_x_mm
        if inner_max_x <= inner_min_x:
            inner_min_x = frame_inner_min_x + inset_x_mm
            inner_max_x = frame_inner_max_x - inset_x_mm
        inner_bottom_z = inner_bottom_frame_z + inset_z_mm + margin_z_mm
        inner_top_z = inner_top_frame_z - inset_z_mm - margin_z_mm
        if inner_top_z <= inner_bottom_z:
            inner_bottom_z = inner_bottom_frame_z + inset_z_mm
            inner_top_z = inner_top_frame_z - inset_z_mm
        if inner_top_z <= inner_bottom_z:
            inner_top_z = inner_bottom_z + 1.0

        slat_span_z_mm = max(1.0, inner_top_z - inner_bottom_z)
        back_slat_center_z = inner_bottom_z + (slat_span_z_mm / 2.0)
        y_slat_inset_max = max(0.0, ((back_rail_depth_mm - back_slat_thickness_mm) / 2.0) - 0.5)
        y_slat_inset_mm = min(2.0, y_slat_inset_max)
        back_slat_center_y = back_frame_center_y - y_slat_inset_mm
        back_slat_plane_y = back_slat_center_y + (back_slat_thickness_mm / 2.0)
        split_center_layout = (frame_layout == "split_2") or (back_slat_layout == "split_center")
        center_gap_mm_effective = max(0.0, back_slat_center_gap_mm)
        center_split_gap_half_x = max(
            center_gap_half_x,
            (center_post_width_mm / 2.0)
            + max(2.0, center_gap_mm_effective),
        )

        def _centers_for_range(
            axis_min: float,
            axis_max: float,
            count: int,
            item_size_mm: float,
            gap_mm=None,
        ) -> List[float]:
            if count <= 0:
                return []
            range_min = min(float(axis_min), float(axis_max))
            range_max = max(float(axis_min), float(axis_max))
            if count == 1:
                return [0.5 * (range_min + range_max)]
            item_size_mm = max(1.0, float(item_size_mm))
            span_mm = max(0.0, range_max - range_min)
            if gap_mm is not None and float(gap_mm) > 0.0:
                required_span_mm = (item_size_mm * count) + (float(gap_mm) * float(count - 1))
                if required_span_mm <= span_mm:
                    start_axis = range_min + ((span_mm - required_span_mm) / 2.0) + (item_size_mm / 2.0)
                    step_axis = item_size_mm + float(gap_mm)
                    return [start_axis + (step_axis * i) for i in range(count)]

            free_span_mm = max(0.0, span_mm - item_size_mm)
            step_axis = free_span_mm / float(count - 1)
            start_axis = range_min + (item_size_mm / 2.0)
            return [start_axis + (step_axis * i) for i in range(count)]

        plan.anchors.append(Anchor(name="back_slat_plane_y", location_mm=(0.0, back_slat_plane_y, 0.0)))
        plan.anchors.append(Anchor(name="back_slat_center_z", location_mm=(0.0, 0.0, back_slat_center_z)))
        plan.anchors.append(
            Anchor(name="back_frame_inner_rect_min", location_mm=(inner_min_x, back_frame_center_y, inner_bottom_z))
        )
        plan.anchors.append(
            Anchor(name="back_frame_inner_rect_max", location_mm=(inner_max_x, back_frame_center_y, inner_top_z))
        )

        if back_slat_orientation == "horizontal":
            row_height_mm = max(1.0, back_slat_width_mm)
            if has_back_slat_gap and back_slat_gap_mm > 0.0:
                row_gap_mm = back_slat_gap_mm
            else:
                row_gap_mm = 35.0
            effective_row_count = max(1, int(back_slat_count))
            inner_height_mm = max(1.0, inner_top_z - inner_bottom_z)
            packed_height_mm = (effective_row_count * row_height_mm) + ((effective_row_count - 1) * row_gap_mm)
            if packed_height_mm > (inner_height_mm + 1e-6):
                denom_mm = row_height_mm + row_gap_mm
                if denom_mm > 0.0:
                    max_rows_fit = int((inner_height_mm + row_gap_mm) // denom_mm)
                else:
                    max_rows_fit = 2
                max_rows_fit = max(2, max_rows_fit)
                effective_row_count = max(2, min(effective_row_count, max_rows_fit))

            row_centers_z = _centers_for_range(
                inner_bottom_z,
                inner_top_z,
                effective_row_count,
                row_height_mm,
                gap_mm=row_gap_mm,
            )

            segments: List[Tuple[str, float, float]] = []
            left_window_mm = 0.0
            right_window_mm = 0.0
            if split_center_layout:
                left_min_x = inner_min_x
                left_max_x = min(inner_max_x, -center_split_gap_half_x)
                right_min_x = max(inner_min_x, center_split_gap_half_x)
                right_max_x = inner_max_x
                left_window_mm = max(0.0, left_max_x - left_min_x)
                right_window_mm = max(0.0, right_max_x - right_min_x)
                if left_window_mm >= 1.0:
                    segments.append(("left", left_min_x, left_max_x))
                if right_window_mm >= 1.0:
                    segments.append(("right", right_min_x, right_max_x))
            if not segments:
                left_window_mm = max(0.0, inner_max_x - inner_min_x)
                right_window_mm = 0.0
                segments.append(("full", inner_min_x, inner_max_x))

            back_slats_bbox_inner_text = (
                f"orientation={back_slat_orientation} "
                f"layout={back_slat_layout} "
                f"frame_layout={frame_layout} "
                f"center_post_width_mm={center_post_width_mm:.3f} "
                f"center_gap_mm={center_gap_mm_effective:.3f} "
                f"count={effective_row_count} "
                f"gap_mm={row_gap_mm:.3f} "
                f"left_window_mm={left_window_mm:.3f} "
                f"right_window_mm={right_window_mm:.3f} "
                f"bottom_split={int(bool(bottom_rail_split))} "
                f"bottom_gap_mm={float(bottom_rail_gap_mm):.3f} "
                f"min=({inner_min_x:.3f},{inner_bottom_z:.3f}) "
                f"max=({inner_max_x:.3f},{inner_top_z:.3f}) y={back_slat_center_y:.3f} "
                f"center_gap_half={center_split_gap_half_x:.3f}"
            )

            next_full_index = 1
            for row_idx, z in enumerate(row_centers_z, start=1):
                for segment_name, segment_min_x, segment_max_x in segments:
                    segment_len_x = max(1.0, segment_max_x - segment_min_x)
                    segment_center_x = segment_min_x + (segment_len_x / 2.0)
                    if segment_name == "full":
                        slat_name = f"back_slat_{next_full_index}"
                        next_full_index += 1
                    else:
                        slat_name = f"back_slat_{segment_name}_{row_idx}"
                    back_slat = Primitive(
                        name=slat_name,
                        shape="beam",
                        dimensions_mm=(segment_len_x, back_slat_thickness_mm, row_height_mm),
                        location_mm=(segment_center_x, back_slat_center_y, z),
                        params={
                            "orientation": "horizontal",
                            "layout": "split_center" if split_center_layout else "full",
                            "row_index": float(row_idx),
                            "segment": segment_name,
                        },
                    )
                    plan.primitives.append(back_slat)
                    if len(back_slat_debug_primitives) < 2:
                        back_slat_debug_primitives.append(back_slat)
                    plan.anchors.append(
                        Anchor(name=slat_name, location_mm=(segment_center_x, back_slat_center_y, z))
                    )
        else:
            slat_height_mm = slat_span_z_mm
            left_window_mm = max(0.0, inner_max_x - inner_min_x)
            right_window_mm = 0.0
            if split_center_layout:
                left_min_x = inner_min_x
                left_max_x = min(inner_max_x, -center_split_gap_half_x)
                right_min_x = max(inner_min_x, center_split_gap_half_x)
                right_max_x = inner_max_x
                left_window_mm = max(0.0, left_max_x - left_min_x)
                right_window_mm = max(0.0, right_max_x - right_min_x)
                left_valid = (left_max_x - left_min_x) >= 1.0
                right_valid = (right_max_x - right_min_x) >= 1.0
                left_count = (back_slat_count + 1) // 2
                right_count = back_slat_count // 2
                if not left_valid and not right_valid:
                    slat_centers_x = _centers_for_range(inner_min_x, inner_max_x, back_slat_count, back_slat_width_mm)
                elif not left_valid:
                    slat_centers_x = _centers_for_range(right_min_x, right_max_x, back_slat_count, back_slat_width_mm)
                elif not right_valid:
                    slat_centers_x = _centers_for_range(left_min_x, left_max_x, back_slat_count, back_slat_width_mm)
                else:
                    slat_centers_x = _centers_for_range(left_min_x, left_max_x, left_count, back_slat_width_mm)
                    slat_centers_x.extend(_centers_for_range(right_min_x, right_max_x, right_count, back_slat_width_mm))
            else:
                slat_centers_x = _centers_for_range(inner_min_x, inner_max_x, back_slat_count, back_slat_width_mm)

            back_slats_bbox_inner_text = (
                f"orientation={back_slat_orientation} "
                f"layout={back_slat_layout} "
                f"frame_layout={frame_layout} "
                f"center_post_width_mm={center_post_width_mm:.3f} "
                f"center_gap_mm={center_gap_mm_effective:.3f} "
                f"count={len(slat_centers_x)} "
                f"gap_mm=0.000 "
                f"left_window_mm={left_window_mm:.3f} "
                f"right_window_mm={right_window_mm:.3f} "
                f"bottom_split={int(bool(bottom_rail_split))} "
                f"bottom_gap_mm={float(bottom_rail_gap_mm):.3f} "
                f"min=({inner_min_x:.3f},{inner_bottom_z:.3f}) "
                f"max=({inner_max_x:.3f},{inner_top_z:.3f}) y={back_slat_center_y:.3f} "
                f"center_gap_half={center_split_gap_half_x:.3f}"
            )

            for i, x in enumerate(slat_centers_x, start=1):
                back_slat = Primitive(
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
                plan.primitives.append(back_slat)
                if i <= 2:
                    back_slat_debug_primitives.append(back_slat)
                plan.anchors.append(
                    Anchor(name=f"back_slat_{i}", location_mm=(x, back_slat_center_y, back_slat_center_z))
                )
    elif back_support_mode == "straps":
        strap_center_x = 0.0
        strap_span_z_mm = max(1.0, (back_frame_height_mm - back_frame_member_mm) - (2.0 * back_margin_z_mm))
        if back_strap_count == 1:
            strap_centers_z = [back_frame_base_z + ((back_frame_height_mm - back_frame_member_mm) / 2.0)]
        else:
            step_mm = strap_span_z_mm / (back_strap_count - 1)
            start_z = back_frame_base_z + back_margin_z_mm
            strap_centers_z = [start_z + (step_mm * i) for i in range(back_strap_count)]

        for i, z in enumerate(strap_centers_z, start=1):
            plan.primitives.append(
                Primitive(
                    name=f"back_strap_{i}",
                    shape="board",
                    dimensions_mm=(seat_total_width_mm, back_strap_thickness_mm, back_strap_width_mm),
                    location_mm=(strap_center_x, back_frame_center_y, z),
                )
            )

    if has_back_support:
        print(f"BACK_ANCHOR y_back_seat={y_back_seat:.3f}")
        print(
            "BACK_FRAME "
            f"y={back_frame_center_y:.3f} "
            f"plane_y={back_frame_plane_y:.3f} "
            f"attach_mode={bottom_rail_attach_mode}"
        )
        print(f"BACK_SLATS bbox_inner={back_slats_bbox_inner_text}")
        print(f"[builder_v01] back_frame back_frame_origin={back_frame_origin}")
        for primitive in back_frame_debug_primitives:
            bbox = _primitive_bbox_world(primitive)
            print(
                "[builder_v01] back_frame "
                f"{primitive.name} bbox_world.min={bbox['min']} bbox_world.max={bbox['max']}"
            )
        for primitive in back_slat_debug_primitives:
            bbox = _primitive_bbox_world(primitive)
            print(
                "[builder_v01] back_frame "
                f"{primitive.name} bbox_world.min={bbox['min']} bbox_world.max={bbox['max']}"
            )

    # Arms: legacy box or open-frame scandi arm.
    legacy_arm_height_mm = max(frame_thickness_mm * 2.0, seat_height_mm * 0.65)
    legacy_arm_center_z = base_frame_top_z + (legacy_arm_height_mm / 2.0)
    seat_front_outer_y = seat_depth_mm / 2.0
    seat_back_outer_y = -(seat_depth_mm / 2.0)

    def _arm_y_bounds() -> Tuple[float, float, float, float]:
        usable_min_y = seat_back_outer_y + arm_inset_y_back_mm
        usable_max_y = seat_front_outer_y - arm_inset_y_front_mm
        if usable_max_y <= usable_min_y:
            usable_min_y = seat_back_outer_y + 5.0
            usable_max_y = seat_front_outer_y - 5.0
        usable_span_y = max(1.0, usable_max_y - usable_min_y)

        if arm_length_y_mode == "custom":
            arm_span_y = min(max(1.0, arm_length_y_custom_mm), usable_span_y)
        else:
            arm_span_y = usable_span_y
        frame_center_y = 0.5 * (usable_min_y + usable_max_y)
        frame_min_y = frame_center_y - (arm_span_y / 2.0)
        frame_max_y = frame_center_y + (arm_span_y / 2.0)
        return frame_min_y, frame_max_y, arm_span_y, frame_center_y

    def _log_arms_build(side: str, arm_primitives: List[Primitive], arm_depth_mm_local: float, arm_height_mm_local: float) -> None:
        arm_bbox = _primitives_union_bbox(arm_primitives)
        primitive_names = ",".join(p.name for p in arm_primitives)
        center_x = 0.5 * (arm_bbox["min"][0] + arm_bbox["max"][0])
        center_y = 0.5 * (arm_bbox["min"][1] + arm_bbox["max"][1])
        center_z = 0.5 * (arm_bbox["min"][2] + arm_bbox["max"][2])
        print(
            "ARMS_BUILD "
            f"profile={arms_profile} "
            f"side={side} "
            f"dims_mm=(w={arms_width_mm:.3f},h={arm_height_mm_local:.3f},depth={arm_depth_mm_local:.3f}) "
            f"pos_mm=({center_x:.3f},{center_y:.3f},{center_z:.3f}) "
            f"bbox_min={arm_bbox['min']} "
            f"bbox_max={arm_bbox['max']} "
            f"primitives=[{primitive_names}]"
        )

    def _add_legacy_arm(side: str) -> None:
        is_left = side == "left"
        side_sign = -1.0 if is_left else 1.0
        arm_center_x = side_sign * ((seat_total_width_mm / 2.0) + (arms_width_mm / 2.0))
        plan.primitives.append(
            Primitive(
                name=f"{side}_arm_frame",
                shape="board",
                dimensions_mm=(arms_width_mm, seat_depth_mm, legacy_arm_height_mm),
                location_mm=(arm_center_x, 0.0, legacy_arm_center_z),
            )
        )
        plan.anchors.append(Anchor(name=f"arm_{side}_zone", location_mm=(arm_center_x, 0.0, seat_height_mm)))

    def build_arm_frame_open(side: str) -> None:
        is_left = side == "left"
        side_sign = -1.0 if is_left else 1.0
        side_prefix = f"arm_{side}"
        inner_face_x = side_sign * (seat_total_width_mm / 2.0)
        outer_face_x = side_sign * ((seat_total_width_mm / 2.0) + arms_width_mm)

        frame_min_y, frame_max_y, arm_span_y, frame_center_y = _arm_y_bounds()
        y_clearance_mm = _clamp(arm_clearance_to_seat_mm, 2.0, 5.0)
        frame_min_y += (y_clearance_mm / 2.0)
        frame_max_y -= (y_clearance_mm / 2.0)
        if frame_max_y <= frame_min_y:
            frame_min_y, frame_max_y, arm_span_y, frame_center_y = _arm_y_bounds()
        arm_span_y = max(1.0, frame_max_y - frame_min_y)
        frame_center_y = 0.5 * (frame_min_y + frame_max_y)

        arm_bottom_z = base_frame_top_z
        arm_top_z = max(arm_bottom_z + (2.0 * arm_thickness_mm), arm_height_mm)
        arm_span_z = max(1.0, arm_top_z - arm_bottom_z)

        post_thickness_x = _clamp(arm_thickness_mm, 12.0, max(12.0, arms_width_mm - 6.0))
        post_depth_y = _clamp(arm_thickness_mm, 12.0, max(12.0, arm_span_y * 0.45))
        cap_thickness_z = _clamp(arm_thickness_mm, 12.0, max(12.0, arm_span_z * 0.45))
        top_rail_thickness_z = _clamp(arm_thickness_mm, 12.0, max(12.0, arm_span_z * 0.35))

        structure_top_z = arm_top_z - cap_thickness_z
        structure_span_z = max(1.0, structure_top_z - arm_bottom_z)
        structure_center_z = arm_bottom_z + (structure_span_z / 2.0)
        top_rail_thickness_z = min(top_rail_thickness_z, structure_span_z)
        top_rail_center_z = structure_top_z - (top_rail_thickness_z / 2.0)

        inner_dist_min = (post_thickness_x / 2.0) + 1.0
        inner_dist_max = max(inner_dist_min, arms_width_mm - (post_thickness_x / 2.0) - 1.0)
        inner_post_center_dist = _clamp(
            arm_inner_clearance_mm + (post_thickness_x / 2.0),
            inner_dist_min,
            inner_dist_max,
        )
        inner_post_center_x = inner_face_x + (side_sign * inner_post_center_dist)

        back_dist_min = inner_post_center_dist + (post_thickness_x * 0.5)
        back_dist_max = max(back_dist_min, arms_width_mm - (post_thickness_x / 2.0) - 1.0)
        back_post_center_dist = _clamp(
            arms_width_mm - (post_thickness_x / 2.0) - 1.0,
            back_dist_min,
            back_dist_max,
        )
        back_post_center_x = inner_face_x + (side_sign * back_post_center_dist)
        top_rail_span_x = max(post_thickness_x, abs(back_post_center_x - inner_post_center_x) + post_thickness_x)
        top_rail_center_x = 0.5 * (inner_post_center_x + back_post_center_x)

        inner_post_center_y = frame_max_y - (post_depth_y / 2.0)
        back_post_center_y = frame_min_y + (post_depth_y / 2.0)

        outer_rail_width_x = min(arm_outer_rail_width_mm, max(20.0, arms_width_mm - 2.0))
        outer_rail_depth_y = post_depth_y
        outer_rail_center_x = outer_face_x - (side_sign * (outer_rail_width_x / 2.0))
        outer_rail_center_y = frame_max_y - (outer_rail_depth_y / 2.0)
        outer_rail_center_z = arm_bottom_z + (arm_span_z / 2.0)

        cap_inner_inset_mm = max(0.0, arm_inner_clearance_mm - 2.0)
        cap_span_x = max(
            arm_thickness_mm,
            min(arms_width_mm + arm_cap_overhang_mm + 2.0, (arms_width_mm - cap_inner_inset_mm) + arm_cap_overhang_mm),
        )
        cap_center_dist = cap_inner_inset_mm + (cap_span_x / 2.0)
        cap_center_x = inner_face_x + (side_sign * cap_center_dist)
        cap_center_y = frame_center_y
        cap_center_z = arm_top_z - (cap_thickness_z / 2.0)

        arm_primitives: List[Primitive] = [
            Primitive(
                name=f"{side_prefix}_inner_post",
                shape="beam",
                dimensions_mm=(post_thickness_x, post_depth_y, structure_span_z),
                location_mm=(inner_post_center_x, inner_post_center_y, structure_center_z),
            ),
            Primitive(
                name=f"{side_prefix}_back_post",
                shape="beam",
                dimensions_mm=(post_thickness_x, post_depth_y, structure_span_z),
                location_mm=(back_post_center_x, back_post_center_y, structure_center_z),
            ),
            Primitive(
                name=f"{side_prefix}_top_rail",
                shape="beam",
                dimensions_mm=(top_rail_span_x, arm_span_y, top_rail_thickness_z),
                location_mm=(top_rail_center_x, frame_center_y, top_rail_center_z),
            ),
            Primitive(
                name=f"{side_prefix}_cap",
                shape="board",
                dimensions_mm=(cap_span_x, arm_span_y, cap_thickness_z),
                location_mm=(cap_center_x, cap_center_y, cap_center_z),
            ),
            Primitive(
                name=f"{side_prefix}_outer_rail",
                shape="board",
                dimensions_mm=(outer_rail_width_x, outer_rail_depth_y, arm_span_z),
                location_mm=(outer_rail_center_x, outer_rail_center_y, outer_rail_center_z),
            ),
        ]

        for primitive in arm_primitives:
            plan.primitives.append(primitive)
            plan.anchors.append(Anchor(name=primitive.name, location_mm=primitive.location_mm))

        arm_center_x = 0.5 * (inner_face_x + outer_face_x)
        arm_center_z = arm_bottom_z + (arm_span_z / 2.0)
        plan.anchors.append(Anchor(name=f"arm_frame_{side}", location_mm=(arm_center_x, frame_center_y, arm_center_z)))
        plan.anchors.append(Anchor(name=f"{side_prefix}_zone", location_mm=(arm_center_x, frame_center_y, seat_height_mm)))
        _log_arms_build(side=side, arm_primitives=arm_primitives, arm_depth_mm_local=arm_span_y, arm_height_mm_local=arm_span_z)

    def _add_arm(side: str) -> None:
        if arms_profile == "frame_box_open":
            build_arm_frame_open(side)
        else:
            _add_legacy_arm(side)

    if arms_type in {"both", "left"}:
        _add_arm("left")
    if arms_type in {"both", "right"}:
        _add_arm("right")

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
    if has_back_support:
        back_anchor_y = back_frame_center_y
        back_bottom_z = back_frame_base_z
        back_top_z = back_frame_top_z
        back_inner_center = (0.0, back_frame_center_y, back_center_z)
    else:
        back_anchor_y = seat_back_rail_outer_face_y - (back_thickness_mm / 2.0) + back_offset_y_mm
        back_bottom_z = seat_support_top_z
        back_top_z = seat_support_top_z + back_height_mm
        back_inner_center = (0.0, back_anchor_y, seat_support_top_z + (back_height_mm / 2.0))
    left_back_corner = (-(seat_total_width_mm / 2.0), back_anchor_y, back_bottom_z)
    right_back_corner = ((seat_total_width_mm / 2.0), back_anchor_y, back_bottom_z)

    plan.anchors.extend(
        [
            Anchor(name="seat_zone", location_mm=(0.0, 0.0, seat_support_center_z)),
            Anchor(name="back_zone", location_mm=back_panel_center),
            Anchor(name="seat_rear_rail", location_mm=seat_rear_rail_center),
            Anchor(
                name="seat_back_rail_center_y",
                location_mm=(0.0, seat_back_rail_center_y, base_frame_center_z),
            ),
            Anchor(
                name="seat_back_rail_outer_face_y",
                location_mm=(0.0, seat_back_rail_outer_face_y, base_frame_center_z),
            ),
            Anchor(name="y_back_seat", location_mm=(0.0, y_back_seat, base_frame_center_z)),
            Anchor(name="seat_back_plane", location_mm=(0.0, seat_back_rail_outer_face_y, back_bottom_z)),
            Anchor(name="back_frame_origin", location_mm=back_frame_origin),
            Anchor(name="back_bottom_edge_center", location_mm=(0.0, back_anchor_y, back_bottom_z)),
            Anchor(name="back_top_edge_center", location_mm=(0.0, back_anchor_y, back_top_z)),
            Anchor(name="back_inner_plane_center", location_mm=back_inner_center),
            Anchor(name="left_back_corner", location_mm=left_back_corner),
            Anchor(name="right_back_corner", location_mm=right_back_corner),
        ]
    )

    return plan
