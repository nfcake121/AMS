"""Arms component for Blender builder plan generation."""

from __future__ import annotations

from typing import List, Tuple

from src.builders.blender import builder_v01 as builder
from src.builders.blender.spec.types import BuildContext, ResolvedSpec

Primitive = builder.Primitive
Anchor = builder.Anchor


def _canon_arms_type(value: str) -> str:
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower()
    if normalized in {"none", "left", "right", "both"}:
        return normalized
    return "none"


def _add_primitive(plan, primitive: Primitive, primitives_out: list) -> None:
    plan.primitives.append(primitive)
    primitives_out.append(primitive)


def _log_arms_build(side: str, profile: str, arms_width_mm: float, arm_primitives: List[Primitive], arm_depth_mm_local: float, arm_height_mm_local: float) -> None:
    arm_bbox = builder._primitives_union_bbox(arm_primitives)
    primitive_names = ",".join(p.name for p in arm_primitives)
    center_x = 0.5 * (arm_bbox["min"][0] + arm_bbox["max"][0])
    center_y = 0.5 * (arm_bbox["min"][1] + arm_bbox["max"][1])
    center_z = 0.5 * (arm_bbox["min"][2] + arm_bbox["max"][2])
    print(
        "ARMS_BUILD "
        f"profile={profile} "
        f"side={side} "
        f"dims_mm=(w={arms_width_mm:.3f},h={arm_height_mm_local:.3f},depth={arm_depth_mm_local:.3f}) "
        f"pos_mm=({center_x:.3f},{center_y:.3f},{center_z:.3f}) "
        f"bbox_min={arm_bbox['min']} "
        f"bbox_max={arm_bbox['max']} "
        f"primitives=[{primitive_names}]"
    )


def build_arm_box(plan, side: str, seat_total_width_mm: float, arms_width_mm: float, seat_depth_mm: float, seat_height_mm: float, frame_thickness_mm: float, base_frame_top_z: float, primitives_out: list) -> None:
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


def build_arm_frame_open(plan, side: str, arms_width_mm: float, seat_total_width_mm: float, seat_depth_mm: float, seat_height_mm: float, frame_thickness_mm: float, back_height_mm: float, ir: dict, primitives_out: list) -> None:
    arms = ir.get("arms", {}) if isinstance(ir.get("arms"), dict) else {}
    back_support_for_arms = ir.get("back_support", {}) if isinstance(ir.get("back_support"), dict) else {}

    arm_back_height_source = builder._ir_value(back_support_for_arms, "height_above_seat_mm", back_height_mm)
    arm_height_mm = max(1.0, builder._ir_value(arms, "height_mm", seat_height_mm + (arm_back_height_source * 0.35)))

    arm_length_y_mode_raw = arms.get("length_y_mode", "match_seat")
    if isinstance(arm_length_y_mode_raw, str):
        arm_length_y_mode = arm_length_y_mode_raw.strip().lower()
    else:
        arm_length_y_mode = "match_seat"
    if arm_length_y_mode not in {"match_seat", "custom"}:
        arm_length_y_mode = "match_seat"

    arm_length_y_custom_mm = max(1.0, builder._ir_value(arms, "length_y_mm", seat_depth_mm))
    arm_inset_y_front_mm = max(0.0, builder._ir_value(arms, "inset_y_front_mm", 25.0))
    arm_inset_y_back_mm = max(0.0, builder._ir_value(arms, "inset_y_back_mm", 10.0))
    arm_clearance_to_seat_mm = builder._clamp(builder._ir_value(arms, "clearance_to_seat_mm", 2.0), 0.0, 30.0)
    arm_thickness_mm = builder._clamp(builder._ir_value(arms, "thickness_mm", frame_thickness_mm), 18.0, 30.0)
    arm_inner_clearance_mm = builder._clamp(builder._ir_value(arms, "inner_clearance_mm", 8.0), 6.0, 12.0)
    arm_cap_overhang_mm = builder._clamp(builder._ir_value(arms, "cap_overhang_mm", builder._ir_value(arms, "top_overhang_mm", 8.0)), 5.0, 15.0)
    arm_outer_rail_width_mm = builder._clamp(builder._ir_value(arms, "outer_rail_width_mm", 56.0), 40.0, 80.0)

    seat_support_top_z = seat_height_mm
    base_frame_top_z = seat_support_top_z - frame_thickness_mm
    seat_front_outer_y = seat_depth_mm / 2.0
    seat_back_outer_y = -(seat_depth_mm / 2.0)

    is_left = side == "left"
    side_sign = -1.0 if is_left else 1.0
    side_prefix = f"arm_{side}"

    inner_face_x = side_sign * (seat_total_width_mm / 2.0)
    outer_face_x = side_sign * ((seat_total_width_mm / 2.0) + arms_width_mm)

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

    y_clearance_mm = builder._clamp(arm_clearance_to_seat_mm, 2.0, 5.0)
    frame_min_y += (y_clearance_mm / 2.0)
    frame_max_y -= (y_clearance_mm / 2.0)
    if frame_max_y <= frame_min_y:
        frame_min_y = frame_center_y - (arm_span_y / 2.0)
        frame_max_y = frame_center_y + (arm_span_y / 2.0)

    arm_span_y = max(1.0, frame_max_y - frame_min_y)
    frame_center_y = 0.5 * (frame_min_y + frame_max_y)

    arm_bottom_z = base_frame_top_z
    arm_top_z = max(arm_bottom_z + (2.0 * arm_thickness_mm), arm_height_mm)
    arm_span_z = max(1.0, arm_top_z - arm_bottom_z)

    post_thickness_x = builder._clamp(arm_thickness_mm, 12.0, max(12.0, arms_width_mm - 6.0))
    post_depth_y = builder._clamp(arm_thickness_mm, 12.0, max(12.0, arm_span_y * 0.45))
    cap_thickness_z = builder._clamp(arm_thickness_mm, 12.0, max(12.0, arm_span_z * 0.45))
    top_rail_thickness_z = builder._clamp(arm_thickness_mm, 12.0, max(12.0, arm_span_z * 0.35))

    structure_top_z = arm_top_z - cap_thickness_z
    structure_span_z = max(1.0, structure_top_z - arm_bottom_z)
    structure_center_z = arm_bottom_z + (structure_span_z / 2.0)
    top_rail_thickness_z = min(top_rail_thickness_z, structure_span_z)
    top_rail_center_z = structure_top_z - (top_rail_thickness_z / 2.0)

    inner_dist_min = (post_thickness_x / 2.0) + 1.0
    inner_dist_max = max(inner_dist_min, arms_width_mm - (post_thickness_x / 2.0) - 1.0)
    inner_post_center_dist = builder._clamp(
        arm_inner_clearance_mm + (post_thickness_x / 2.0),
        inner_dist_min,
        inner_dist_max,
    )
    inner_post_center_x = inner_face_x + (side_sign * inner_post_center_dist)

    back_dist_min = inner_post_center_dist + (post_thickness_x * 0.5)
    back_dist_max = max(back_dist_min, arms_width_mm - (post_thickness_x / 2.0) - 1.0)
    back_post_center_dist = builder._clamp(
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

    arm_primitives = [
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
        _add_primitive(plan, primitive, primitives_out)
        plan.anchors.append(Anchor(name=primitive.name, location_mm=primitive.location_mm))

    arm_center_x = 0.5 * (inner_face_x + outer_face_x)
    arm_center_z = arm_bottom_z + (arm_span_z / 2.0)
    plan.anchors.append(Anchor(name=f"arm_frame_{side}", location_mm=(arm_center_x, frame_center_y, arm_center_z)))
    plan.anchors.append(Anchor(name=f"{side_prefix}_zone", location_mm=(arm_center_x, frame_center_y, seat_height_mm)))

    _log_arms_build(
        side=side,
        profile="frame_box_open",
        arms_width_mm=arms_width_mm,
        arm_primitives=arm_primitives,
        arm_depth_mm_local=arm_span_y,
        arm_height_mm_local=arm_span_z,
    )


def build_arms(plan, spec: ResolvedSpec, ctx: BuildContext, ir: dict, primitives_out: list) -> None:
    del ctx
    seat_width_mm = builder._ir_value(ir, "seat_width_mm", 600.0)
    seat_depth_mm = builder._ir_value(ir, "seat_depth_mm", 600.0)
    seat_height_mm = builder._ir_value(ir, "seat_height_mm", 440.0)
    seat_count = max(1, int(builder._ir_value(ir, "seat_count", 3)))
    seat_total_width_mm = seat_width_mm * seat_count

    frame = ir.get("frame", {}) if isinstance(ir.get("frame"), dict) else {}
    frame_thickness_mm = builder._ir_value(frame, "thickness_mm", 35.0)
    back_height_mm = builder._ir_value(frame, "back_height_above_seat_mm", 420.0)

    arms_type = _canon_arms_type(spec.arms.type)
    arms_width_mm = max(0.0, float(spec.arms.width_mm))
    profile = str(spec.arms.profile or "box")

    if profile not in {"box", "frame_box_open"}:
        print(
            "RESOLVE_WARNING "
            "code=PROFILE_FALLBACK_TO_BOX "
            f"message=unsupported arms profile '{profile}' -> 'box'"
        )
        profile = "box"

    if arms_type in {"both", "left"}:
        if profile == "frame_box_open":
            build_arm_frame_open(
                plan=plan,
                side="left",
                arms_width_mm=arms_width_mm,
                seat_total_width_mm=seat_total_width_mm,
                seat_depth_mm=seat_depth_mm,
                seat_height_mm=seat_height_mm,
                frame_thickness_mm=frame_thickness_mm,
                back_height_mm=back_height_mm,
                ir=ir,
                primitives_out=primitives_out,
            )
        else:
            base_frame_top_z = seat_height_mm - frame_thickness_mm
            build_arm_box(
                plan=plan,
                side="left",
                seat_total_width_mm=seat_total_width_mm,
                arms_width_mm=arms_width_mm,
                seat_depth_mm=seat_depth_mm,
                seat_height_mm=seat_height_mm,
                frame_thickness_mm=frame_thickness_mm,
                base_frame_top_z=base_frame_top_z,
                primitives_out=primitives_out,
            )

    if arms_type in {"both", "right"}:
        if profile == "frame_box_open":
            build_arm_frame_open(
                plan=plan,
                side="right",
                arms_width_mm=arms_width_mm,
                seat_total_width_mm=seat_total_width_mm,
                seat_depth_mm=seat_depth_mm,
                seat_height_mm=seat_height_mm,
                frame_thickness_mm=frame_thickness_mm,
                back_height_mm=back_height_mm,
                ir=ir,
                primitives_out=primitives_out,
            )
        else:
            base_frame_top_z = seat_height_mm - frame_thickness_mm
            build_arm_box(
                plan=plan,
                side="right",
                seat_total_width_mm=seat_total_width_mm,
                arms_width_mm=arms_width_mm,
                seat_depth_mm=seat_depth_mm,
                seat_height_mm=seat_height_mm,
                frame_thickness_mm=frame_thickness_mm,
                base_frame_top_z=base_frame_top_z,
                primitives_out=primitives_out,
            )
