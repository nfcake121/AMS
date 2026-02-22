"""Arms component for Blender builder plan generation."""

from __future__ import annotations

from src.builders.blender.components.arms_strategies import (
    build_arm_box_strategy,
    build_arm_frame_box_open_strategy,
)
from src.builders.blender.diagnostics import Severity, emit_simple
from src.builders.blender.plan_types import Anchor, Primitive
from src.builders.blender.spec.types import ArmsInputs, BuildContext


def _canon_arms_type(value: str) -> str:
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower()
    if normalized in {"none", "left", "right", "both"}:
        return normalized
    return "none"


def _slot_side(slot_name: str, min_x: float, max_x: float) -> str:
    if slot_name.endswith("left") or slot_name == "main_left":
        return "left"
    if slot_name.endswith("right") or slot_name == "main_right":
        return "right"
    center_x = (float(min_x) + float(max_x)) / 2.0
    return "left" if center_x < 0.0 else "right"


def _build_corner_chaise_arm(plan, inputs: ArmsInputs, ctx: BuildContext) -> None:
    arms_width_mm = max(0.0, float(inputs.arms_width_mm))
    if arms_width_mm <= 0.0:
        return

    chaise_request = None
    for request in inputs.requests:
        if request.slot_name == "chaise_free_end":
            chaise_request = request
            break
    if chaise_request is None:
        return
    if not chaise_request.allowed:
        emit_simple(
            ctx.diag,
            run_id=ctx.run_id,
            stage="build",
            component="arms",
            code="SLOT_SKIPPED",
            severity=Severity.INFO,
            path="arms.requests.chaise_free_end",
            source="computed",
            reason="slot is blocked",
            payload={"slot": "chaise_free_end", "segment": "chaise"},
        )
        return

    seat_height_mm = float(inputs.seat_height_mm)
    frame_thickness_mm = float(inputs.frame_thickness_mm)
    arm_height_mm = max(frame_thickness_mm * 2.0, seat_height_mm * 0.65)
    arm_center_z = (seat_height_mm - frame_thickness_mm) + (arm_height_mm / 2.0)
    slot_side = _slot_side(chaise_request.slot_name, chaise_request.min_x, chaise_request.max_x)
    slot_depth_mm = max(1.0, float(chaise_request.max_y) - float(chaise_request.min_y))
    if slot_side == "left":
        arm_center_x = float(chaise_request.min_x) - (arms_width_mm / 2.0)
    else:
        arm_center_x = float(chaise_request.max_x) + (arms_width_mm / 2.0)
    arm_center_y = (float(chaise_request.min_y) + float(chaise_request.max_y)) / 2.0

    name_prefix = "arm_chaise_free_end"
    plan.primitives.append(
        Primitive(
            name=f"{name_prefix}_frame",
            shape="board",
            dimensions_mm=(arms_width_mm, slot_depth_mm, arm_height_mm),
            location_mm=(arm_center_x, arm_center_y, arm_center_z),
        )
    )
    plan.anchors.append(
        Anchor(
            name=f"{name_prefix}_zone",
            location_mm=(arm_center_x, arm_center_y, seat_height_mm),
        )
    )


def build_arms(plan, inputs: ArmsInputs, ctx: BuildContext) -> None:
    seat_width_mm = float(inputs.seat_width_mm)
    seat_depth_mm = float(inputs.seat_depth_mm)
    seat_height_mm = float(inputs.seat_height_mm)
    seat_count = max(1, int(inputs.seat_count))
    seat_total_width_mm = seat_width_mm * seat_count
    frame_thickness_mm = float(inputs.frame_thickness_mm)
    back_height_mm = float(inputs.back_height_mm)
    arms_type = _canon_arms_type(inputs.arms_type)
    arms_width_mm = max(0.0, float(inputs.arms_width_mm))
    profile = str(inputs.profile or "box")
    arms = inputs.arms_config if isinstance(inputs.arms_config, dict) else {}
    back_support_for_arms = (
        inputs.back_support_config
        if isinstance(inputs.back_support_config, dict)
        else {}
    )
    primitives_out: list = []

    if inputs.layout_kind == "corner" and not inputs.requests:
        emit_simple(
            ctx.diag,
            run_id=ctx.run_id,
            stage="build",
            component="arms",
            code="CORNER_MVP_ARMS_MAIN_ONLY",
            severity=Severity.WARN,
            path="layout.kind",
            source="computed",
            reason="corner requests missing; fallback to main-only arms",
            resolved_value="main_only",
        )

    if profile not in {"box", "frame_box_open"}:
        emit_simple(
            ctx.diag,
            run_id=ctx.run_id,
            stage="build",
            component="arms",
            code="PROFILE_FALLBACK_TO_BOX",
            severity=Severity.WARN,
            path="arms.profile",
            source="fallback",
            input_value=profile,
            resolved_value="box",
            reason="unsupported profile",
            meta={"allowed": ["box", "frame_box_open"]},
        )
        profile = "box"

    strategy_dispatch = {
        "box": ("arm_box", build_arm_box_strategy),
        "frame_box_open": ("arm_frame_box_open", build_arm_frame_box_open_strategy),
    }
    handler_name, handler = strategy_dispatch[profile]

    emit_simple(
        ctx.diag,
        run_id=ctx.run_id,
        stage="build",
        component="arms",
        code="STRATEGY_SELECTED",
        severity=Severity.INFO,
        path="arms.profile",
        source="computed",
        payload={
            "strategy": profile,
            "key": {"profile": profile, "arms_type": arms_type},
            "handler": handler_name,
        },
        resolved_value={"profile": profile, "arms_type": arms_type},
        reason="dispatch arms build strategy",
    )

    build_left = arms_type in {"both", "left"}
    build_right = arms_type in {"both", "right"}
    if inputs.layout_kind == "corner" and inputs.requests:
        request_by_name = {request.slot_name: request for request in inputs.requests}
        left_request = request_by_name.get("main_left")
        right_request = request_by_name.get("main_right")
        if left_request is not None:
            build_left = bool(build_left and left_request.allowed)
            if not left_request.allowed:
                emit_simple(
                    ctx.diag,
                    run_id=ctx.run_id,
                    stage="build",
                    component="arms",
                    code="SLOT_SKIPPED",
                    severity=Severity.INFO,
                    path="arms.requests.main_left",
                    source="computed",
                    reason="slot is blocked",
                    payload={"slot": "main_left", "segment": "main"},
                )
        if right_request is not None:
            build_right = bool(build_right and right_request.allowed)
            if not right_request.allowed:
                emit_simple(
                    ctx.diag,
                    run_id=ctx.run_id,
                    stage="build",
                    component="arms",
                    code="SLOT_SKIPPED",
                    severity=Severity.INFO,
                    path="arms.requests.main_right",
                    source="computed",
                    reason="slot is blocked",
                    payload={"slot": "main_right", "segment": "main"},
                )

    if build_left:
        if handler_name == "arm_box":
            base_frame_top_z = seat_height_mm - frame_thickness_mm
            handler(
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
        else:
            handler(
                plan=plan,
                side="left",
                arms_width_mm=arms_width_mm,
                seat_total_width_mm=seat_total_width_mm,
                seat_depth_mm=seat_depth_mm,
                seat_height_mm=seat_height_mm,
                frame_thickness_mm=frame_thickness_mm,
                back_height_mm=back_height_mm,
                arms=arms,
                back_support_for_arms=back_support_for_arms,
                primitives_out=primitives_out,
                ctx=ctx,
            )

    if build_right:
        if handler_name == "arm_box":
            base_frame_top_z = seat_height_mm - frame_thickness_mm
            handler(
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
        else:
            handler(
                plan=plan,
                side="right",
                arms_width_mm=arms_width_mm,
                seat_total_width_mm=seat_total_width_mm,
                seat_depth_mm=seat_depth_mm,
                seat_height_mm=seat_height_mm,
                frame_thickness_mm=frame_thickness_mm,
                back_height_mm=back_height_mm,
                arms=arms,
                back_support_for_arms=back_support_for_arms,
                primitives_out=primitives_out,
                ctx=ctx,
            )
    if inputs.layout_kind == "corner" and inputs.requests:
        emit_simple(
            ctx.diag,
            run_id=ctx.run_id,
            stage="build",
            component="arms",
            code="STRATEGY_SELECTED",
            severity=Severity.INFO,
            path="arms.strategy",
            source="computed",
            payload={
                "strategy": "corner_main_plus_chaise",
                "handler": "straight_profile_plus_chaise_end",
                "requests": len(inputs.requests),
            },
            reason="corner extension builds chaise free-end arm",
        )
        _build_corner_chaise_arm(plan=plan, inputs=inputs, ctx=ctx)
