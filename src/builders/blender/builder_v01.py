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

    from src.builders.blender.spec.resolve import resolve
    from src.builders.blender.spec.types import BuildContext

    resolved_spec, resolve_diagnostics = resolve(ir, preset_id=ir.get("preset_id"))

    arms = ir.get("arms", {}) if isinstance(ir.get("arms"), dict) else {}
    arms_type = _canon_arms_type(resolved_spec.arms.type)
    arms_width_mm = max(0.0, float(resolved_spec.arms.width_mm))
    arms_profile = str(resolved_spec.arms.profile)
    arms_style_raw = arms.get("style", arms_profile)
    if isinstance(arms_style_raw, str):
        arms_style = arms_style_raw.strip().lower()
    else:
        arms_style = str(arms_profile)
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

    back_spec = resolved_spec.back

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

    from src.builders.blender.components.back import BackBuildHelpers, build_back

    build_ctx = BuildContext(run_id=None, debug=_debug_env_enabled())
    if build_ctx.debug:
        for warning in resolve_diagnostics.warnings:
            print(
                "RESOLVE_WARNING "
                f"code={warning.get('code', '')} "
                f"path={warning.get('path', '')} "
                f"old={warning.get('old', '')} "
                f"new={warning.get('new', '')} "
                f"source={warning.get('source', '')}"
            )

    back_result = build_back(
        plan=plan,
        spec=back_spec,
        ctx=build_ctx,
        ir=ir,
        helpers=BackBuildHelpers(
            seat_total_width_mm=seat_total_width_mm,
            total_width_mm=total_width_mm,
            seat_depth_mm=seat_depth_mm,
            frame_thickness_mm=frame_thickness_mm,
            seat_support_top_z=seat_support_top_z,
            base_frame_top_z=base_frame_top_z,
            base_frame_center_z=base_frame_center_z,
            back_y=back_y,
        ),
    )

    # Arms: delegated to component (thin seam).
    from src.builders.blender.components.arms import build_arms

    arms_primitives_out: List[Primitive] = []
    build_arms(
        plan=plan,
        spec=resolved_spec,
        ctx=build_ctx,
        ir=ir,
        primitives_out=arms_primitives_out,
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
    back_anchor_y = back_result.back_anchor_y
    back_bottom_z = back_result.back_bottom_z
    back_top_z = back_result.back_top_z
    back_inner_center = back_result.back_inner_center
    left_back_corner = (-(seat_total_width_mm / 2.0), back_anchor_y, back_bottom_z)
    right_back_corner = ((seat_total_width_mm / 2.0), back_anchor_y, back_bottom_z)

    plan.anchors.extend(
        [
            Anchor(name="seat_zone", location_mm=(0.0, 0.0, seat_support_center_z)),
            Anchor(name="back_zone", location_mm=back_result.back_panel_center),
            Anchor(name="seat_rear_rail", location_mm=back_result.seat_rear_rail_center),
            Anchor(
                name="seat_back_rail_center_y",
                location_mm=(0.0, back_result.seat_back_rail_center_y, base_frame_center_z),
            ),
            Anchor(
                name="seat_back_rail_outer_face_y",
                location_mm=(0.0, back_result.seat_back_rail_outer_face_y, base_frame_center_z),
            ),
            Anchor(name="y_back_seat", location_mm=(0.0, back_result.y_back_seat, base_frame_center_z)),
            Anchor(name="seat_back_plane", location_mm=(0.0, back_result.seat_back_rail_outer_face_y, back_bottom_z)),
            Anchor(name="back_frame_origin", location_mm=back_result.back_frame_origin),
            Anchor(name="back_bottom_edge_center", location_mm=(0.0, back_anchor_y, back_bottom_z)),
            Anchor(name="back_top_edge_center", location_mm=(0.0, back_anchor_y, back_top_z)),
            Anchor(name="back_inner_plane_center", location_mm=back_inner_center),
            Anchor(name="left_back_corner", location_mm=left_back_corner),
            Anchor(name="right_back_corner", location_mm=right_back_corner),
        ]
    )

    return plan
