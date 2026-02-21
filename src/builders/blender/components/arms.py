"""Arms component for Blender builder plan generation."""

from __future__ import annotations

from src.builders.blender.components.arms_strategies import (
    build_arm_box_strategy,
    build_arm_frame_box_open_strategy,
)
from src.builders.blender.diagnostics import Severity, emit_simple
from src.builders.blender.spec.types import ArmsInputs, BuildContext


def _canon_arms_type(value: str) -> str:
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower()
    if normalized in {"none", "left", "right", "both"}:
        return normalized
    return "none"


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
            "key": {"profile": profile, "arms_type": arms_type},
            "handler": handler_name,
        },
        resolved_value={"profile": profile, "arms_type": arms_type},
        reason="dispatch arms build strategy",
    )

    build_left = arms_type in {"both", "left"}
    build_right = arms_type in {"both", "right"}

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
