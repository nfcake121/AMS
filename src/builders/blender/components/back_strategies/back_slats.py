"""Back slats strategy."""

from __future__ import annotations

from typing import Callable

from src.builders.blender.plan_types import Anchor, Primitive


def build_back_slats_strategy(
    plan,
    *,
    back_slat_count: int,
    back_slat_width_mm: float,
    back_slat_thickness_mm: float,
    back_slat_arc_height_mm: float,
    back_slat_arc_sign: float,
    back_slat_orientation: str,
    back_slat_layout: str,
    has_back_slat_gap: bool,
    back_slat_gap_mm: float,
    back_slat_center_gap_mm: float,
    back_rail_inset_mm: float,
    back_margin_x_mm: float,
    back_margin_z_mm: float,
    back_rail_width_mm: float,
    back_rail_depth_mm: float,
    back_rail_height_mm: float,
    bottom_rail_height_mm: float,
    bottom_rail_split: bool,
    bottom_rail_gap_mm: float,
    frame_layout: str,
    center_post_width_mm: float,
    rail_left_x: float,
    rail_right_x: float,
    back_frame_base_z: float,
    back_frame_top_z: float,
    back_frame_center_y: float,
    back_frame_debug_primitives: list,
    back_slat_debug_primitives: list,
    build_back_frame_split2_fn: Callable[..., float],
    build_back_frame_full_fn: Callable[[], float],
    build_back_horizontal_slats_fn: Callable[..., str],
    build_back_vertical_slats_fn: Callable[..., str],
) -> str:
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
        center_gap_half_x = build_back_frame_split2_fn(
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
        center_gap_half_x = build_back_frame_full_fn()

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

    def _build_slats_horizontal() -> str:
        return build_back_horizontal_slats_fn(
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

    def _build_slats_vertical() -> str:
        return build_back_vertical_slats_fn(
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

    slat_orientation_key = "horizontal" if back_slat_orientation == "horizontal" else "vertical"
    slat_layout_key = "split_center" if back_slat_layout == "split_center" else "full"
    slats_dispatch = {
        ("slats", "horizontal", "full"): _build_slats_horizontal,
        ("slats", "horizontal", "split_center"): _build_slats_horizontal,
        ("slats", "vertical", "full"): _build_slats_vertical,
        ("slats", "vertical", "split_center"): _build_slats_vertical,
    }
    return slats_dispatch[("slats", slat_orientation_key, slat_layout_key)]()
