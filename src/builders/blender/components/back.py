"""Back support component for Blender builder plan generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from src.builders.blender.builder_v01 import Anchor, Primitive
from src.builders.blender.geom_utils import clamp, primitive_bbox_world
from src.builders.blender.spec.types import BackSpec, BuildContext, LayoutContext, ResolvedSpec


@dataclass(frozen=True)
class BackBuildHelpers:
    seat_total_width_mm: float
    total_width_mm: float
    seat_depth_mm: float
    frame_thickness_mm: float
    seat_support_top_z: float
    base_frame_top_z: float
    base_frame_center_z: float
    back_y: float


@dataclass(frozen=True)
class BackBuildResult:
    has_back_support: bool
    back_panel_center: Tuple[float, float, float]
    seat_rear_rail_center: Tuple[float, float, float]
    seat_back_rail_center_y: float
    seat_back_rail_outer_face_y: float
    y_back_seat: float
    back_frame_origin: Tuple[float, float, float]
    back_anchor_y: float
    back_bottom_z: float
    back_top_z: float
    back_inner_center: Tuple[float, float, float]


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


def build_back_frame_full() -> float:
    return 0.0


def build_back_frame_split2(
    plan,
    *,
    center_post_width_mm: float,
    back_rail_depth_mm: float,
    inner_bottom_frame_z: float,
    inner_top_frame_z: float,
    back_frame_center_y: float,
    inset_x_mm: float,
    back_frame_debug_primitives: list,
) -> float:
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
    return (center_post_width_mm / 2.0) + inset_x_mm


def build_back_horizontal_slats(
    plan,
    *,
    back_slat_width_mm: float,
    back_slat_thickness_mm: float,
    back_slat_count: int,
    has_back_slat_gap: bool,
    back_slat_gap_mm: float,
    split_center_layout: bool,
    inner_bottom_z: float,
    inner_top_z: float,
    inner_min_x: float,
    inner_max_x: float,
    center_split_gap_half_x: float,
    back_slat_center_y: float,
    back_slat_layout: str,
    frame_layout: str,
    center_post_width_mm: float,
    center_gap_mm_effective: float,
    bottom_rail_split: bool,
    bottom_rail_gap_mm: float,
    back_slat_debug_primitives: list,
) -> str:
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
        f"orientation=horizontal "
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

    return back_slats_bbox_inner_text


def build_back_vertical_slats(
    plan,
    *,
    back_slat_width_mm: float,
    back_slat_thickness_mm: float,
    back_slat_arc_height_mm: float,
    back_slat_arc_sign: float,
    back_slat_count: int,
    split_center_layout: bool,
    inner_min_x: float,
    inner_max_x: float,
    inner_bottom_z: float,
    inner_top_z: float,
    center_split_gap_half_x: float,
    back_slat_center_y: float,
    back_slat_center_z: float,
    back_slat_layout: str,
    frame_layout: str,
    center_post_width_mm: float,
    center_gap_mm_effective: float,
    bottom_rail_split: bool,
    bottom_rail_gap_mm: float,
    back_slat_debug_primitives: list,
) -> str:
    slat_height_mm = max(1.0, inner_top_z - inner_bottom_z)
    left_window_mm = max(0.0, inner_max_x - inner_min_x)
    right_window_mm = 0.0
    effective_slat_count = max(1, int(back_slat_count))
    if split_center_layout:
        left_min_x = inner_min_x
        left_max_x = min(inner_max_x, -center_split_gap_half_x)
        right_min_x = max(inner_min_x, center_split_gap_half_x)
        right_max_x = inner_max_x
        left_window_mm = max(0.0, left_max_x - left_min_x)
        right_window_mm = max(0.0, right_max_x - right_min_x)
        left_valid = (left_max_x - left_min_x) >= 1.0
        right_valid = (right_max_x - right_min_x) >= 1.0
        left_count = (effective_slat_count + 1) // 2
        right_count = effective_slat_count // 2
        if not left_valid and not right_valid:
            slat_centers_x = _centers_for_range(inner_min_x, inner_max_x, effective_slat_count, back_slat_width_mm)
        elif not left_valid:
            slat_centers_x = _centers_for_range(right_min_x, right_max_x, effective_slat_count, back_slat_width_mm)
        elif not right_valid:
            slat_centers_x = _centers_for_range(left_min_x, left_max_x, effective_slat_count, back_slat_width_mm)
        else:
            slat_centers_x = _centers_for_range(left_min_x, left_max_x, left_count, back_slat_width_mm)
            slat_centers_x.extend(_centers_for_range(right_min_x, right_max_x, right_count, back_slat_width_mm))
    else:
        slat_centers_x = _centers_for_range(inner_min_x, inner_max_x, effective_slat_count, back_slat_width_mm)

    back_slats_bbox_inner_text = (
        f"orientation=vertical "
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

    return back_slats_bbox_inner_text


def _build_back_from_spec(plan, spec: BackSpec, ctx: BuildContext, helpers: BackBuildHelpers) -> BackBuildResult:
    has_back_support = bool(spec.has_back_support)
    back_support_mode = str(spec.mode or "panel")

    back_height_mm = float(spec.frame.height_above_seat_mm)
    back_thickness_mm = float(spec.frame.thickness_mm)
    back_offset_y_mm = float(spec.frame.offset_y_mm)
    back_margin_x_mm = float(spec.frame.margin_x_mm)
    back_margin_z_mm = float(spec.frame.margin_z_mm)
    back_rail_inset_mm = float(spec.frame.rail_inset_mm)
    back_rail_width_mm = float(spec.frame.rail_width_mm)
    back_rail_depth_mm = float(spec.frame.rail_depth_mm)
    back_rail_height_mm = float(spec.frame.rail_height_mm)
    bottom_rail_split = bool(spec.frame.bottom_rail_split)
    bottom_rail_gap_mm = float(spec.frame.bottom_rail_gap_mm)
    frame_layout = str(spec.frame.frame_layout or "single")
    bottom_rail_attach_mode = str(spec.frame.bottom_rail_attach_mode or "seat_rear_beam")
    bottom_rail_height_mm = float(spec.frame.bottom_rail_height_mm)
    center_post_width_mm = float(spec.frame.center_post.width_mm)
    center_post_enabled = bool(spec.frame.center_post.enabled)

    back_slat_count = int(spec.slats.count)
    back_slat_width_mm = float(spec.slats.width_mm)
    back_slat_thickness_mm = float(spec.slats.thickness_mm)
    back_slat_arc_height_mm = float(spec.slats.arc_height_mm)
    back_slat_arc_sign = float(spec.slats.arc_sign)
    back_slat_orientation = str(spec.slats.orientation or "vertical")
    back_slat_layout = str(spec.slats.layout or "full")
    has_back_slat_gap = bool(spec.slats.has_gap_mm)
    back_slat_gap_mm = float(spec.slats.gap_mm)
    back_slat_center_gap_mm = float(spec.slats.center_gap_mm)

    back_strap_count = int(spec.straps.count)
    back_strap_width_mm = float(spec.straps.width_mm)
    back_strap_thickness_mm = float(spec.straps.thickness_mm)

    seat_support_top_z = helpers.seat_support_top_z
    seat_depth_mm = helpers.seat_depth_mm
    back_y = helpers.back_y
    frame_thickness_mm = helpers.frame_thickness_mm
    seat_total_width_mm = helpers.seat_total_width_mm
    total_width_mm = helpers.total_width_mm
    base_frame_top_z = helpers.base_frame_top_z
    base_frame_center_z = helpers.base_frame_center_z

    # Back support uses a frame tied directly to the rear seat rail.
    back_offset_y_micro_mm = clamp(back_offset_y_mm, -80.0, 80.0)
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

        plan.primitives.extend([back_rail_bottom, back_rail_top])
        back_frame_debug_primitives.extend([back_rail_bottom, back_rail_top])
        plan.anchors.extend(
            [
                Anchor(name="back_rail_bottom", location_mm=back_rail_bottom.location_mm),
                Anchor(name="back_rail_top", location_mm=back_rail_top.location_mm),
            ]
        )

        if frame_layout == "split_2":
            center_gap_half_x = build_back_frame_split2(
                plan=plan,
                center_post_width_mm=center_post_width_mm,
                back_rail_depth_mm=back_rail_depth_mm,
                inner_bottom_frame_z=inner_bottom_frame_z,
                inner_top_frame_z=inner_top_frame_z,
                back_frame_center_y=back_frame_center_y,
                inset_x_mm=inset_x_mm,
                back_frame_debug_primitives=back_frame_debug_primitives,
            )
        else:
            center_gap_half_x = build_back_frame_full()

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

        plan.anchors.append(Anchor(name="back_slat_plane_y", location_mm=(0.0, back_slat_plane_y, 0.0)))
        plan.anchors.append(Anchor(name="back_slat_center_z", location_mm=(0.0, 0.0, back_slat_center_z)))
        plan.anchors.append(
            Anchor(name="back_frame_inner_rect_min", location_mm=(inner_min_x, back_frame_center_y, inner_bottom_z))
        )
        plan.anchors.append(
            Anchor(name="back_frame_inner_rect_max", location_mm=(inner_max_x, back_frame_center_y, inner_top_z))
        )

        if back_slat_orientation == "horizontal":
            back_slats_bbox_inner_text = build_back_horizontal_slats(
                plan=plan,
                back_slat_width_mm=back_slat_width_mm,
                back_slat_thickness_mm=back_slat_thickness_mm,
                back_slat_count=back_slat_count,
                has_back_slat_gap=has_back_slat_gap,
                back_slat_gap_mm=back_slat_gap_mm,
                split_center_layout=split_center_layout,
                inner_bottom_z=inner_bottom_z,
                inner_top_z=inner_top_z,
                inner_min_x=inner_min_x,
                inner_max_x=inner_max_x,
                center_split_gap_half_x=center_split_gap_half_x,
                back_slat_center_y=back_slat_center_y,
                back_slat_layout=back_slat_layout,
                frame_layout=frame_layout,
                center_post_width_mm=center_post_width_mm,
                center_gap_mm_effective=center_gap_mm_effective,
                bottom_rail_split=bottom_rail_split,
                bottom_rail_gap_mm=bottom_rail_gap_mm,
                back_slat_debug_primitives=back_slat_debug_primitives,
            )
        else:
            back_slats_bbox_inner_text = build_back_vertical_slats(
                plan=plan,
                back_slat_width_mm=back_slat_width_mm,
                back_slat_thickness_mm=back_slat_thickness_mm,
                back_slat_arc_height_mm=back_slat_arc_height_mm,
                back_slat_arc_sign=back_slat_arc_sign,
                back_slat_count=back_slat_count,
                split_center_layout=split_center_layout,
                inner_min_x=inner_min_x,
                inner_max_x=inner_max_x,
                inner_bottom_z=inner_bottom_z,
                inner_top_z=inner_top_z,
                center_split_gap_half_x=center_split_gap_half_x,
                back_slat_center_y=back_slat_center_y,
                back_slat_center_z=back_slat_center_z,
                back_slat_layout=back_slat_layout,
                frame_layout=frame_layout,
                center_post_width_mm=center_post_width_mm,
                center_gap_mm_effective=center_gap_mm_effective,
                bottom_rail_split=bottom_rail_split,
                bottom_rail_gap_mm=bottom_rail_gap_mm,
                back_slat_debug_primitives=back_slat_debug_primitives,
            )
    elif back_support_mode == "straps":
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
            bbox = primitive_bbox_world(primitive)
            print(
                "[builder_v01] back_frame "
                f"{primitive.name} bbox_world.min={bbox['min']} bbox_world.max={bbox['max']}"
            )
        for primitive in back_slat_debug_primitives:
            bbox = primitive_bbox_world(primitive)
            print(
                "[builder_v01] back_frame "
                f"{primitive.name} bbox_world.min={bbox['min']} bbox_world.max={bbox['max']}"
            )

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

    if ctx.debug and center_post_enabled and frame_layout != "split_2":
        print("BACK_BUILD debug=center_post_enabled_but_frame_not_split2")

    return BackBuildResult(
        has_back_support=has_back_support,
        back_panel_center=back_panel_center,
        seat_rear_rail_center=seat_rear_rail_center,
        seat_back_rail_center_y=seat_back_rail_center_y,
        seat_back_rail_outer_face_y=seat_back_rail_outer_face_y,
        y_back_seat=y_back_seat,
        back_frame_origin=back_frame_origin,
        back_anchor_y=back_anchor_y,
        back_bottom_z=back_bottom_z,
        back_top_z=back_top_z,
        back_inner_center=back_inner_center,
    )


def _coerce_back_helpers(layout: LayoutContext) -> BackBuildHelpers:
    return BackBuildHelpers(
        seat_total_width_mm=float(layout.seat_total_width_mm),
        total_width_mm=float(layout.total_width_mm),
        seat_depth_mm=float(layout.seat_depth_mm),
        frame_thickness_mm=float(layout.frame_thickness_mm),
        seat_support_top_z=float(layout.seat_support_top_z),
        base_frame_top_z=float(layout.base_frame_top_z),
        base_frame_center_z=float(layout.base_frame_center_z),
        back_y=float(layout.back_y),
    )


def _append_back_zone_anchors(plan, back_result: BackBuildResult, helpers: BackBuildHelpers) -> None:
    seat_total_width_mm = helpers.seat_total_width_mm
    base_frame_center_z = helpers.base_frame_center_z

    back_anchor_y = back_result.back_anchor_y
    back_bottom_z = back_result.back_bottom_z
    back_top_z = back_result.back_top_z
    back_inner_center = back_result.back_inner_center
    left_back_corner = (-(seat_total_width_mm / 2.0), back_anchor_y, back_bottom_z)
    right_back_corner = ((seat_total_width_mm / 2.0), back_anchor_y, back_bottom_z)

    plan.anchors.extend(
        [
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


def build_back(plan, spec: ResolvedSpec, ctx: BuildContext, layout: LayoutContext) -> None:
    helpers = _coerce_back_helpers(layout)
    back_result = _build_back_from_spec(plan=plan, spec=spec.back, ctx=ctx, helpers=helpers)
    _append_back_zone_anchors(plan=plan, back_result=back_result, helpers=helpers)
