"""Layout computation helpers for Blender builder."""

from __future__ import annotations

from src.builders.blender.geom_utils import ir_value
from src.builders.blender.spec.types import Layout, ResolvedSpec


def _canon_arms_type(value: str) -> str:
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower()
    if normalized in {"left", "right", "both", "none"}:
        return normalized
    return "none"


def _arms_count(arms_type: str) -> int:
    if arms_type == "both":
        return 2
    if arms_type in {"left", "right"}:
        return 1
    return 0


def compute_layout(ir: dict, spec: ResolvedSpec) -> Layout:
    seat_width_mm = ir_value(ir, "seat_width_mm", 600.0)
    seat_depth_mm = ir_value(ir, "seat_depth_mm", 600.0)
    seat_height_mm = ir_value(ir, "seat_height_mm", 440.0)
    seat_count = max(1, int(ir_value(ir, "seat_count", 3)))
    seat_total_width_mm = seat_width_mm * seat_count

    frame = ir.get("frame", {}) if isinstance(ir.get("frame"), dict) else {}
    frame_thickness_mm = ir_value(frame, "thickness_mm", 35.0)

    arms_type = _canon_arms_type(spec.arms.type)
    arms_width_mm = max(0.0, float(spec.arms.width_mm))
    arms_total_mm = arms_width_mm * _arms_count(arms_type)
    total_width_mm = seat_total_width_mm + arms_total_mm

    seat_support_top_z = seat_height_mm
    seat_support_center_z = seat_support_top_z - (frame_thickness_mm / 2.0)
    base_frame_top_z = seat_support_top_z - frame_thickness_mm
    base_frame_center_z = base_frame_top_z - (frame_thickness_mm / 2.0)

    seat_min_x = -(seat_total_width_mm / 2.0)
    seat_max_x = seat_total_width_mm / 2.0
    seat_min_y = -(seat_depth_mm / 2.0)
    seat_max_y = seat_depth_mm / 2.0
    back_base_y = seat_min_y
    back_plane_y = seat_min_y + (frame_thickness_mm / 2.0)

    return Layout(
        seat_count=seat_count,
        seat_width_mm=seat_width_mm,
        seat_depth_mm=seat_depth_mm,
        seat_height_mm=seat_height_mm,
        seat_total_width_mm=seat_total_width_mm,
        total_width_mm=total_width_mm,
        frame_thickness_mm=frame_thickness_mm,
        seat_min_x=seat_min_x,
        seat_max_x=seat_max_x,
        seat_min_y=seat_min_y,
        seat_max_y=seat_max_y,
        seat_top_z=seat_support_top_z,
        floor_z=0.0,
        seat_support_center_z=seat_support_center_z,
        seat_support_top_z=seat_support_top_z,
        base_frame_top_z=base_frame_top_z,
        base_frame_center_z=base_frame_center_z,
        back_base_y=back_base_y,
        back_plane_y=back_plane_y,
    )
