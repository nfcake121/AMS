"""Layout computation helpers for Blender builder."""

from __future__ import annotations

from src.builders.blender.diagnostics import Severity, emit_simple
from src.builders.blender.geom_utils import ir_value
from src.builders.blender.spec.types import (
    Layout,
    LayoutJoin,
    LayoutSegment,
    LayoutSlot,
    ResolvedSpec,
)


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


def _emit_corner_layout_events(
    *,
    diag_sink,
    run_id: str,
    chaise_side: str,
    chaise_width_mm: float,
    chaise_depth_mm: float,
    corner_gap_mm: float,
    segments_count: int,
    arm_slots_count: int,
    back_slots_count: int,
) -> None:
    emit_simple(
        diag_sink,
        run_id=run_id,
        stage="layout",
        component="layout",
        code="LAYOUT_KIND_CORNER_SELECTED",
        severity=Severity.INFO,
        path="layout",
        source="computed",
        reason="corner layout selected",
        resolved_value="corner",
    )
    emit_simple(
        diag_sink,
        run_id=run_id,
        stage="layout",
        component="layout",
        code="CORNER_DIMENSIONS_COMPUTED",
        severity=Severity.INFO,
        path="corner",
        source="computed",
        reason="corner dimensions computed",
        meta={
            "side": chaise_side,
            "chaise_width_mm": float(chaise_width_mm),
            "chaise_depth_mm": float(chaise_depth_mm),
            "gap": float(corner_gap_mm),
        },
    )
    emit_simple(
        diag_sink,
        run_id=run_id,
        stage="layout",
        component="layout",
        code="LAYOUT_TOPOLOGY_COMPUTED",
        severity=Severity.INFO,
        path="layout.topology",
        source="computed",
        reason="corner topology computed",
        meta={
            "segments": int(segments_count),
            "arm_slots": int(arm_slots_count),
            "back_slots": int(back_slots_count),
        },
    )


def compute_layout(
    ir: dict,
    spec: ResolvedSpec,
    *,
    diag_sink=None,
    run_id: str = "",
) -> Layout:
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
    floor_z = 0.0
    seat_main_min_z = floor_z
    seat_main_max_z = seat_support_top_z

    if spec.corner is None:
        segments = (
            LayoutSegment(
                name="main",
                min_x=seat_min_x,
                max_x=seat_max_x,
                min_y=seat_min_y,
                max_y=seat_max_y,
                min_z=seat_main_min_z,
                max_z=seat_main_max_z,
                back_plane_y=back_plane_y,
            ),
        )
        arm_slots = (
            LayoutSlot(
                name="main_left",
                segment="main",
                kind="arm",
                allowed=True,
                min_x=seat_min_x,
                max_x=seat_min_x + frame_thickness_mm,
                min_y=seat_min_y,
                max_y=seat_max_y,
                min_z=seat_main_min_z,
                max_z=seat_main_max_z,
            ),
            LayoutSlot(
                name="main_right",
                segment="main",
                kind="arm",
                allowed=True,
                min_x=seat_max_x - frame_thickness_mm,
                max_x=seat_max_x,
                min_y=seat_min_y,
                max_y=seat_max_y,
                min_z=seat_main_min_z,
                max_z=seat_main_max_z,
            ),
        )
        back_slots = (
            LayoutSlot(
                name="main_back",
                segment="main",
                kind="back",
                allowed=True,
                min_x=seat_min_x,
                max_x=seat_max_x,
                min_y=seat_min_y,
                max_y=seat_min_y + frame_thickness_mm,
                min_z=seat_main_min_z,
                max_z=seat_main_max_z,
            ),
        )
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
            floor_z=floor_z,
            seat_support_center_z=seat_support_center_z,
            seat_support_top_z=seat_support_top_z,
            base_frame_top_z=base_frame_top_z,
            base_frame_center_z=base_frame_center_z,
            back_base_y=back_base_y,
            back_plane_y=back_plane_y,
            kind="straight",
            seat_main_min_x=seat_min_x,
            seat_main_max_x=seat_max_x,
            seat_main_min_y=seat_min_y,
            seat_main_max_y=seat_max_y,
            seat_main_min_z=seat_main_min_z,
            seat_main_max_z=seat_main_max_z,
            seat_chaise_min_x=None,
            seat_chaise_max_x=None,
            seat_chaise_min_y=None,
            seat_chaise_max_y=None,
            seat_chaise_min_z=None,
            seat_chaise_max_z=None,
            corner_join_x=None,
            corner_side=None,
            corner_join_mode=None,
            corner_gap_mm=0.0,
            chaise_width_mm=None,
            chaise_depth_mm=None,
            overall_min_x=seat_min_x,
            overall_max_x=seat_max_x,
            overall_min_y=seat_min_y,
            overall_max_y=seat_max_y,
            overall_min_z=seat_main_min_z,
            overall_max_z=seat_main_max_z,
            segments=segments,
            arm_slots=arm_slots,
            back_slots=back_slots,
            join=None,
            corner_topology={},
        )

    corner = spec.corner
    chaise_side = corner.chaise_side if corner.chaise_side in {"left", "right"} else "right"
    corner_gap_mm = max(0.0, float(corner.corner_gap_mm))
    chaise_extra_depth_mm = max(0.0, float(corner.chaise_extra_depth_mm))
    chaise_width_mm = max((seat_width_mm / 2.0), 550.0)
    chaise_width_mm = max(450.0, min(900.0, chaise_width_mm))
    chaise_depth_mm = seat_depth_mm + chaise_extra_depth_mm

    if chaise_side == "right":
        corner_join_x = seat_max_x
        seat_chaise_min_x = corner_join_x + corner_gap_mm
        seat_chaise_max_x = seat_chaise_min_x + chaise_width_mm
    else:
        corner_join_x = seat_min_x
        seat_chaise_max_x = corner_join_x - corner_gap_mm
        seat_chaise_min_x = seat_chaise_max_x - chaise_width_mm

    seat_chaise_min_y = seat_min_y
    seat_chaise_max_y = seat_min_y + chaise_depth_mm
    seat_chaise_min_z = floor_z
    seat_chaise_max_z = seat_support_top_z

    overall_min_x = min(seat_min_x, seat_chaise_min_x)
    overall_max_x = max(seat_max_x, seat_chaise_max_x)
    overall_min_y = min(seat_min_y, seat_chaise_min_y)
    overall_max_y = max(seat_max_y, seat_chaise_max_y)
    overall_min_z = min(seat_main_min_z, seat_chaise_min_z)
    overall_max_z = max(seat_main_max_z, seat_chaise_max_z)

    if chaise_side == "right":
        join_ref_x = seat_chaise_min_x
        chaise_free_min_x = seat_chaise_max_x - frame_thickness_mm
        chaise_free_max_x = seat_chaise_max_x
        main_right_allowed = False
    else:
        join_ref_x = seat_chaise_max_x
        chaise_free_min_x = seat_chaise_min_x
        chaise_free_max_x = seat_chaise_min_x + frame_thickness_mm
        main_right_allowed = True

    segments = (
        LayoutSegment(
            name="main",
            min_x=seat_min_x,
            max_x=seat_max_x,
            min_y=seat_min_y,
            max_y=seat_max_y,
            min_z=seat_main_min_z,
            max_z=seat_main_max_z,
            back_plane_y=back_plane_y,
        ),
        LayoutSegment(
            name="chaise",
            min_x=seat_chaise_min_x,
            max_x=seat_chaise_max_x,
            min_y=seat_chaise_min_y,
            max_y=seat_chaise_max_y,
            min_z=seat_chaise_min_z,
            max_z=seat_chaise_max_z,
            back_plane_y=seat_chaise_min_y + (frame_thickness_mm / 2.0),
        ),
    )

    join_min_x = min(corner_join_x, join_ref_x) - (frame_thickness_mm / 2.0)
    join_max_x = max(corner_join_x, join_ref_x) + (frame_thickness_mm / 2.0)
    join_min_y = seat_min_y
    join_max_y = seat_min_y + frame_thickness_mm
    join_min_z = floor_z
    join_max_z = seat_support_top_z
    join = LayoutJoin(
        join_mode=str(corner.join_mode),
        min_x=join_min_x,
        max_x=join_max_x,
        min_y=join_min_y,
        max_y=join_max_y,
        min_z=join_min_z,
        max_z=join_max_z,
    )

    arm_slots = (
        LayoutSlot(
            name="main_left",
            segment="main",
            kind="arm",
            allowed=True,
            min_x=seat_min_x,
            max_x=seat_min_x + frame_thickness_mm,
            min_y=seat_min_y,
            max_y=seat_max_y,
            min_z=seat_main_min_z,
            max_z=seat_main_max_z,
        ),
        LayoutSlot(
            name="main_right",
            segment="main",
            kind="arm",
            allowed=main_right_allowed,
            min_x=seat_max_x - frame_thickness_mm,
            max_x=seat_max_x,
            min_y=seat_min_y,
            max_y=seat_max_y,
            min_z=seat_main_min_z,
            max_z=seat_main_max_z,
        ),
        LayoutSlot(
            name="chaise_free_end",
            segment="chaise",
            kind="arm",
            allowed=True,
            min_x=chaise_free_min_x,
            max_x=chaise_free_max_x,
            min_y=seat_chaise_min_y,
            max_y=seat_chaise_max_y,
            min_z=seat_chaise_min_z,
            max_z=seat_chaise_max_z,
        ),
        LayoutSlot(
            name="join_blocked",
            segment="join",
            kind="arm",
            allowed=False,
            min_x=join.min_x,
            max_x=join.max_x,
            min_y=join.min_y,
            max_y=join.max_y,
            min_z=join.min_z,
            max_z=join.max_z,
        ),
    )

    back_slots = (
        LayoutSlot(
            name="main_back",
            segment="main",
            kind="back",
            allowed=True,
            min_x=seat_min_x,
            max_x=seat_max_x,
            min_y=seat_min_y,
            max_y=seat_min_y + frame_thickness_mm,
            min_z=seat_main_min_z,
            max_z=seat_main_max_z,
        ),
        LayoutSlot(
            name="chaise_back",
            segment="chaise",
            kind="back",
            allowed=True,
            min_x=seat_chaise_min_x,
            max_x=seat_chaise_max_x,
            min_y=seat_chaise_min_y,
            max_y=seat_chaise_min_y + frame_thickness_mm,
            min_z=seat_chaise_min_z,
            max_z=seat_chaise_max_z,
        ),
    )

    corner_topology = {
        "main_left_allowed": bool(any(slot.name == "main_left" and slot.allowed for slot in arm_slots)),
        "main_right_allowed": bool(any(slot.name == "main_right" and slot.allowed for slot in arm_slots)),
        "chaise_free_end_allowed": bool(any(slot.name == "chaise_free_end" and slot.allowed for slot in arm_slots)),
        "join_blocked": bool(any(slot.name == "join_blocked" and (not slot.allowed) for slot in arm_slots)),
        "main_back_allowed": bool(any(slot.name == "main_back" and slot.allowed for slot in back_slots)),
        "chaise_back_allowed": bool(any(slot.name == "chaise_back" and slot.allowed for slot in back_slots)),
    }

    if diag_sink is not None:
        _emit_corner_layout_events(
            diag_sink=diag_sink,
            run_id=run_id,
            chaise_side=chaise_side,
            chaise_width_mm=chaise_width_mm,
            chaise_depth_mm=chaise_depth_mm,
            corner_gap_mm=corner_gap_mm,
            segments_count=len(segments),
            arm_slots_count=len(arm_slots),
            back_slots_count=len(back_slots),
        )

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
        floor_z=floor_z,
        seat_support_center_z=seat_support_center_z,
        seat_support_top_z=seat_support_top_z,
        base_frame_top_z=base_frame_top_z,
        base_frame_center_z=base_frame_center_z,
        back_base_y=back_base_y,
        back_plane_y=back_plane_y,
        kind="corner",
        seat_main_min_x=seat_min_x,
        seat_main_max_x=seat_max_x,
        seat_main_min_y=seat_min_y,
        seat_main_max_y=seat_max_y,
        seat_main_min_z=seat_main_min_z,
        seat_main_max_z=seat_main_max_z,
        seat_chaise_min_x=seat_chaise_min_x,
        seat_chaise_max_x=seat_chaise_max_x,
        seat_chaise_min_y=seat_chaise_min_y,
        seat_chaise_max_y=seat_chaise_max_y,
        seat_chaise_min_z=seat_chaise_min_z,
        seat_chaise_max_z=seat_chaise_max_z,
        corner_join_x=corner_join_x,
        corner_side=chaise_side,
        corner_join_mode=corner.join_mode,
        corner_gap_mm=corner_gap_mm,
        chaise_width_mm=chaise_width_mm,
        chaise_depth_mm=chaise_depth_mm,
        overall_min_x=overall_min_x,
        overall_max_x=overall_max_x,
        overall_min_y=overall_min_y,
        overall_max_y=overall_max_y,
        overall_min_z=overall_min_z,
        overall_max_z=overall_max_z,
        segments=segments,
        arm_slots=arm_slots,
        back_slots=back_slots,
        join=join,
        corner_topology=corner_topology,
    )
