"""Generate a geometry plan and anchors for Blender builds."""

import os
import uuid

from src.builders.blender.diagnostics import Severity, make_event
from src.builders.blender.geom_utils import ir_value as _ir_value
from src.builders.blender.plan_types import Anchor, BuildPlan


def _ir_bool(ir: dict, key: str, default: bool) -> bool:
    # Shared tolerant bool parser kept for compatibility with older helpers.
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


def _debug_env_enabled() -> bool:
    # Any non-falsey DEBUG* env variable enables debug-mode prints.
    falsey = {"", "0", "false", "off", "no", "none"}
    for key, value in os.environ.items():
        if not key.startswith("DEBUG"):
            continue
        if str(value).strip().lower() not in falsey:
            return True
    return False


def _diag_sink_from_env():
    # Diagnostics are opt-in: JSONL sink only when AMS_DIAG_JSONL is set.
    from src.builders.blender.diagnostics import JsonlDiagnosticsSink, NoopDiagnosticsSink

    path = os.environ.get("AMS_DIAG_JSONL", "")
    if isinstance(path, str) and path.strip():
        return JsonlDiagnosticsSink(path.strip())
    return NoopDiagnosticsSink()


def build_plan_from_ir(ir: dict) -> BuildPlan:
    """Create a sofa-frame geometry plan from resolved IR.

    Coordinate system: X is width (left/right), Y is depth (front/back),
    Z is up. seat_height_mm defines the top of the seat support board.
    """
    from src.builders.blender.layout import compute_layout
    from src.builders.blender.spec.resolve import resolve
    from src.builders.blender.spec.types import (
        ArmsInputs,
        BackInputs,
        BuildContext,
        LegsInputs,
        SeatFrameInputs,
        SeatSlatsInputs,
    )

    # 1) Resolve IR + preset defaults, then compute shared layout scalars.
    resolved_spec, resolve_diagnostics = resolve(ir, preset_id=ir.get("preset_id"))
    layout = compute_layout(ir, resolved_spec)

    # 2) Collect/normalize raw config values still needed by component inputs.
    arms = ir.get("arms", {}) if isinstance(ir.get("arms"), dict) else {}
    arms_type = _canon_arms_type(resolved_spec.arms.type)
    arms_width_mm = max(0.0, float(resolved_spec.arms.width_mm))
    arms_profile = str(resolved_spec.arms.profile)
    arms_style_raw = arms.get("style", arms_profile)
    if isinstance(arms_style_raw, str):
        arms_style = arms_style_raw.strip().lower()
    else:
        arms_style = str(arms_profile)
    frame = ir.get("frame", {}) if isinstance(ir.get("frame"), dict) else {}
    frame_thickness_mm = _ir_value(frame, "thickness_mm", 35.0)
    back_height_mm = _ir_value(frame, "back_height_above_seat_mm", 420.0)

    legs_family = (
        resolved_spec.legs.family
        if isinstance(resolved_spec.legs.family, str) and resolved_spec.legs.family
        else "block"
    )

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

    # 3) Initialize plan metadata used by debug/tools.
    plan = BuildPlan(metadata={
        "seat_count": str(layout.seat_count),
        "legs_family": str(legs_family),
        "arms_type": str(arms_type),
        "arms_profile": str(arms_profile),
        "arms_style": str(arms_style),
        "seat_total_width_mm": str(layout.seat_total_width_mm),
        "total_width_mm": str(layout.total_width_mm),
    })

    # 4) Build runtime context (debug + diagnostics sink).
    build_ctx = BuildContext(
        run_id=uuid.uuid4().hex,
        debug=_debug_env_enabled(),
        diag=_diag_sink_from_env(),
    )
    # Structured lifecycle event for external logging/analysis.
    build_ctx.diag.emit(
        make_event(
            run_id=build_ctx.run_id,
            stage="build",
            component="builder",
            code="BUILD_START",
            severity=Severity.INFO,
            source="computed",
            reason="build pipeline start",
            resolved_value={
                "ir_id": ir.get("id"),
                "preset_id": ir.get("preset_id"),
                "style": resolved_spec.style,
            },
        )
    )
    for event in resolve_diagnostics.warnings:
        build_ctx.diag.emit(
            make_event(
                ts=event.ts,
                run_id=build_ctx.run_id,
                stage=event.stage,
                component=event.component,
                code=event.code,
                severity=event.severity,
                path=event.path,
                source=event.source,
                input_value=event.input_value,
                resolved_value=event.resolved_value,
                reason=event.reason,
                meta=event.meta,
            )
        )
    # 5) Materialize per-component input objects (no geometry logic here).
    seat_frame_inputs = SeatFrameInputs(
        seat_count=layout.seat_count,
        total_width_mm=layout.total_width_mm,
        seat_depth_mm=layout.seat_depth_mm,
        frame_thickness_mm=layout.frame_thickness_mm,
        base_frame_center_z=layout.base_frame_center_z,
        slats_enabled=slats_enabled,
        seat_total_width_mm=layout.seat_total_width_mm,
        seat_support_center_z=layout.seat_support_center_z,
    )
    seat_slats_inputs = SeatSlatsInputs(
        slats_enabled=slats_enabled,
        seat_depth_mm=layout.seat_depth_mm,
        seat_total_width_mm=layout.seat_total_width_mm,
        slat_count=slat_count,
        slat_width_mm=slat_width_mm,
        slat_thickness_mm=slat_thickness_mm,
        slat_arc_height_mm=slat_arc_height_mm,
        slat_arc_sign=slat_arc_sign,
        slat_margin_x_mm=slat_margin_x_mm,
        slat_margin_y_mm=slat_margin_y_mm,
        slat_clearance_mm=slat_clearance_mm,
        slat_mount_mode=slat_mount_mode,
        slat_mount_offset_mm=slat_mount_offset_mm,
        slat_rail_inset_mm=slat_rail_inset_mm,
        slat_rail_height_mm=slat_rail_height_mm,
        slat_rail_width_mm=slat_rail_width_mm,
        slat_rail_inset_y_mm=slat_rail_inset_y_mm,
        base_frame_top_z=layout.base_frame_top_z,
        seat_support_top_z=layout.seat_support_top_z,
    )
    back_inputs = BackInputs(
        back=resolved_spec.back,
        seat_total_width_mm=layout.seat_total_width_mm,
        total_width_mm=layout.total_width_mm,
        seat_depth_mm=layout.seat_depth_mm,
        frame_thickness_mm=layout.frame_thickness_mm,
        seat_support_top_z=layout.seat_support_top_z,
        base_frame_top_z=layout.base_frame_top_z,
        base_frame_center_z=layout.base_frame_center_z,
        back_plane_y=layout.back_plane_y,
    )
    arms_inputs = ArmsInputs(
        arms_type=arms_type,
        arms_width_mm=arms_width_mm,
        profile=arms_profile,
        seat_width_mm=layout.seat_width_mm,
        seat_depth_mm=layout.seat_depth_mm,
        seat_height_mm=layout.seat_height_mm,
        seat_count=layout.seat_count,
        frame_thickness_mm=layout.frame_thickness_mm,
        back_height_mm=back_height_mm,
        arms_config=arms,
        back_support_config=(
            ir.get("back_support", {})
            if isinstance(ir.get("back_support"), dict)
            else {}
        ),
    )
    legs_inputs = LegsInputs(
        family=resolved_spec.legs.family,
        height_mm=resolved_spec.legs.height_mm,
        total_width_mm=layout.total_width_mm,
        frame_thickness_mm=layout.frame_thickness_mm,
        seat_depth_mm=layout.seat_depth_mm,
        base_frame_top_z=layout.base_frame_top_z,
    )

    # 6) Build components in stable order; order is regression-sensitive.
    from src.builders.blender.components.seat_frame import build_seat_frame

    build_seat_frame(
        plan=plan,
        inputs=seat_frame_inputs,
        ctx=build_ctx,
    )

    from src.builders.blender.components.seat_slats import build_seat_slats

    build_seat_slats(
        plan=plan,
        inputs=seat_slats_inputs,
        ctx=build_ctx,
    )

    from src.builders.blender.components.back import build_back

    build_back(plan=plan, inputs=back_inputs, ctx=build_ctx)

    # Arms/legs are also delegated via thin seams.
    from src.builders.blender.components.arms import build_arms
    from src.builders.blender.components.legs import build_legs

    build_arms(plan=plan, inputs=arms_inputs, ctx=build_ctx)

    build_legs(
        plan=plan,
        inputs=legs_inputs,
        ctx=build_ctx,
    )

    # Keep legacy seat zone anchor for downstream tools/validators.
    plan.anchors.append(Anchor(name="seat_zone", location_mm=(0.0, 0.0, layout.seat_support_center_z)))
    # Structured lifecycle event with resulting plan sizes.
    build_ctx.diag.emit(
        make_event(
            run_id=build_ctx.run_id,
            stage="build",
            component="builder",
            code="BUILD_DONE",
            severity=Severity.INFO,
            source="computed",
            reason="build pipeline done",
            resolved_value={
                "ir_id": ir.get("id"),
                "primitives_count": len(plan.primitives),
                "anchors_count": len(plan.anchors),
            },
        )
    )

    return plan
