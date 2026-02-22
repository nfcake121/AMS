"""Arms component for Blender builder plan generation."""

from __future__ import annotations

from src.builders.blender.components.arms_strategies import (
    build_arm_box_strategy,
    build_arm_frame_box_open_strategy,
)
from src.builders.blender.diagnostics import Severity, emit_simple
from src.builders.blender.plan_types import Anchor, BuildPlan, Primitive
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


def _is_side_enabled(arms_type: str, side: str) -> bool:
    if side == "left":
        return arms_type in {"both", "left"}
    if side == "right":
        return arms_type in {"both", "right"}
    return False


def _emit_slot_skipped(ctx: BuildContext, slot_name: str, segment: str, reason: str) -> None:
    emit_simple(
        ctx.diag,
        run_id=ctx.run_id,
        stage="build",
        component="arms",
        code="BUILD_SLOT_SKIPPED",
        severity=Severity.INFO,
        path=f"arms.requests.{slot_name}",
        source="computed",
        reason=reason,
        payload={"slot": slot_name, "segment": segment},
    )


def _rename_main_slot_name(name: str, slot_name: str) -> str:
    if slot_name == "main_left":
        if name.startswith("arm_left_"):
            return "arm_main_left_" + name[len("arm_left_") :]
        if name == "arm_frame_left":
            return "arm_main_left_frame"
        if name == "arm_left_zone":
            return "arm_main_left_zone"
        return f"arm_main_left_{name}"
    if slot_name == "main_right":
        if name.startswith("arm_right_"):
            return "arm_main_right_" + name[len("arm_right_") :]
        if name == "arm_frame_right":
            return "arm_main_right_frame"
        if name == "arm_right_zone":
            return "arm_main_right_zone"
        return f"arm_main_right_{name}"
    return name


def _append_renamed_plan(plan, temp_plan: BuildPlan, slot_name: str) -> None:
    for primitive in temp_plan.primitives:
        plan.primitives.append(
            Primitive(
                name=_rename_main_slot_name(primitive.name, slot_name),
                shape=primitive.shape,
                dimensions_mm=primitive.dimensions_mm,
                location_mm=primitive.location_mm,
                rotation_deg=primitive.rotation_deg,
                params=dict(primitive.params),
            )
        )
    for anchor in temp_plan.anchors:
        plan.anchors.append(
            Anchor(
                name=_rename_main_slot_name(anchor.name, slot_name),
                location_mm=anchor.location_mm,
            )
        )


def _build_main_slot_arm(
    *,
    plan,
    inputs: ArmsInputs,
    ctx: BuildContext,
    slot_name: str,
    side: str,
    handler_name: str,
    handler,
    seat_total_width_mm: float,
    seat_depth_mm: float,
    seat_height_mm: float,
    frame_thickness_mm: float,
    back_height_mm: float,
    arms_width_mm: float,
    arms: dict,
    back_support_for_arms: dict,
) -> None:
    temp_plan = BuildPlan(metadata={})
    primitives_out: list = []
    if handler_name == "arm_box":
        base_frame_top_z = seat_height_mm - frame_thickness_mm
        handler(
            plan=temp_plan,
            side=side,
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
            plan=temp_plan,
            side=side,
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
    _append_renamed_plan(plan=plan, temp_plan=temp_plan, slot_name=slot_name)


def _build_corner_chaise_arm_box(plan, inputs: ArmsInputs, request) -> None:
    arms_width_mm = max(0.0, float(inputs.arms_width_mm))
    if arms_width_mm <= 0.0:
        return

    seat_height_mm = float(inputs.seat_height_mm)
    frame_thickness_mm = float(inputs.frame_thickness_mm)
    arm_height_mm = max(frame_thickness_mm * 2.0, seat_height_mm * 0.65)
    arm_center_z = (seat_height_mm - frame_thickness_mm) + (arm_height_mm / 2.0)
    slot_side = _slot_side(request.slot_name, request.min_x, request.max_x)
    slot_depth_mm = max(1.0, float(request.max_y) - float(request.min_y))
    if slot_side == "left":
        arm_center_x = float(request.min_x) - (arms_width_mm / 2.0)
    else:
        arm_center_x = float(request.max_x) + (arms_width_mm / 2.0)
    arm_center_y = (float(request.min_y) + float(request.max_y)) / 2.0

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


def _build_corner_chaise_arm_frame(plan, inputs: ArmsInputs, request) -> None:
    arms_width_mm = max(1.0, float(inputs.arms_width_mm))
    seat_height_mm = float(inputs.seat_height_mm)
    frame_thickness_mm = max(1.0, float(inputs.frame_thickness_mm))
    slot_depth_mm = max(1.0, float(request.max_y) - float(request.min_y))
    slot_center_y = (float(request.min_y) + float(request.max_y)) / 2.0

    slot_side = _slot_side(request.slot_name, request.min_x, request.max_x)
    side_sign = -1.0 if slot_side == "left" else 1.0
    if slot_side == "left":
        arm_center_x = float(request.min_x) - (arms_width_mm / 2.0)
    else:
        arm_center_x = float(request.max_x) + (arms_width_mm / 2.0)

    arm_bottom_z = seat_height_mm - frame_thickness_mm
    arm_height_mm = max(frame_thickness_mm * 2.0, seat_height_mm * 0.65)
    arm_center_z = arm_bottom_z + (arm_height_mm / 2.0)

    arms_cfg = inputs.arms_config if isinstance(inputs.arms_config, dict) else {}
    board_thickness_mm = float(arms_cfg.get("frame_thickness_mm", frame_thickness_mm))
    board_thickness_mm = max(10.0, min(max(10.0, arms_width_mm - 2.0), board_thickness_mm))
    top_bottom_thickness_mm = max(10.0, min(board_thickness_mm, arm_height_mm / 3.0))
    top_center_z = arm_bottom_z + arm_height_mm - (top_bottom_thickness_mm / 2.0)
    bottom_center_z = arm_bottom_z + (top_bottom_thickness_mm / 2.0)
    front_center_y = float(request.max_y) - (board_thickness_mm / 2.0)

    primitives = [
        Primitive(
            name="arm_chaise_free_end_outer",
            shape="board",
            dimensions_mm=(arms_width_mm, slot_depth_mm, arm_height_mm),
            location_mm=(arm_center_x, slot_center_y, arm_center_z),
        ),
        Primitive(
            name="arm_chaise_free_end_front",
            shape="beam",
            dimensions_mm=(arms_width_mm, board_thickness_mm, arm_height_mm),
            location_mm=(arm_center_x, front_center_y, arm_center_z),
        ),
        Primitive(
            name="arm_chaise_free_end_top_rail",
            shape="beam",
            dimensions_mm=(arms_width_mm, slot_depth_mm, top_bottom_thickness_mm),
            location_mm=(arm_center_x, slot_center_y, top_center_z),
        ),
        Primitive(
            name="arm_chaise_free_end_bottom_rail",
            shape="beam",
            dimensions_mm=(arms_width_mm, slot_depth_mm, top_bottom_thickness_mm),
            location_mm=(arm_center_x, slot_center_y, bottom_center_z),
        ),
    ]
    for primitive in primitives:
        plan.primitives.append(primitive)
        plan.anchors.append(Anchor(name=primitive.name, location_mm=primitive.location_mm))
    plan.anchors.append(
        Anchor(name="arm_chaise_free_end_zone", location_mm=(arm_center_x, slot_center_y, seat_height_mm))
    )
    plan.anchors.append(
        Anchor(
            name="arm_chaise_free_end_frame",
            location_mm=(arm_center_x + (side_sign * (arms_width_mm / 4.0)), slot_center_y, arm_center_z),
        )
    )


def _build_corner_chaise_arm(
    *,
    plan,
    inputs: ArmsInputs,
    ctx: BuildContext,
    arms_type: str,
    profile: str,
) -> None:
    chaise_request = None
    for request in inputs.requests:
        if request.slot_name == "chaise_free_end":
            chaise_request = request
            break
    if chaise_request is None:
        return
    if not chaise_request.allowed:
        _emit_slot_skipped(ctx, slot_name=chaise_request.slot_name, segment=chaise_request.segment, reason="slot blocked")
        return
    slot_side = _slot_side(chaise_request.slot_name, chaise_request.min_x, chaise_request.max_x)
    if not _is_side_enabled(arms_type, slot_side):
        _emit_slot_skipped(
            ctx,
            slot_name=chaise_request.slot_name,
            segment=chaise_request.segment,
            reason=f"arms_type {arms_type} disables {slot_side} side",
        )
        return
    if profile == "frame_box_open":
        _build_corner_chaise_arm_frame(plan=plan, inputs=inputs, request=chaise_request)
    else:
        _build_corner_chaise_arm_box(plan=plan, inputs=inputs, request=chaise_request)


def _build_arms_corner(
    *,
    plan,
    inputs: ArmsInputs,
    ctx: BuildContext,
    handler_name: str,
    handler,
    arms_type: str,
    profile: str,
    seat_total_width_mm: float,
    seat_depth_mm: float,
    seat_height_mm: float,
    frame_thickness_mm: float,
    back_height_mm: float,
    arms_width_mm: float,
    arms: dict,
    back_support_for_arms: dict,
) -> None:
    requests_by_name = {request.slot_name: request for request in inputs.requests}
    slots_used: list[str] = []
    for slot_name, side in (("main_left", "left"), ("main_right", "right")):
        request = requests_by_name.get(slot_name)
        if request is None:
            continue
        if not request.allowed:
            _emit_slot_skipped(ctx, slot_name=slot_name, segment=request.segment, reason="slot blocked")
            continue
        if not _is_side_enabled(arms_type, side):
            _emit_slot_skipped(ctx, slot_name=slot_name, segment=request.segment, reason=f"arms_type {arms_type} disables {side}")
            continue
        _build_main_slot_arm(
            plan=plan,
            inputs=inputs,
            ctx=ctx,
            slot_name=slot_name,
            side=side,
            handler_name=handler_name,
            handler=handler,
            seat_total_width_mm=seat_total_width_mm,
            seat_depth_mm=seat_depth_mm,
            seat_height_mm=seat_height_mm,
            frame_thickness_mm=frame_thickness_mm,
            back_height_mm=back_height_mm,
            arms_width_mm=arms_width_mm,
            arms=arms,
            back_support_for_arms=back_support_for_arms,
        )
        slots_used.append(slot_name)

    join_request = requests_by_name.get("join_blocked")
    if join_request is not None and not join_request.allowed:
        _emit_slot_skipped(ctx, slot_name="join_blocked", segment=join_request.segment, reason="join slot is blocked")

    _build_corner_chaise_arm(
        plan=plan,
        inputs=inputs,
        ctx=ctx,
        arms_type=arms_type,
        profile=profile,
    )
    if any(request.slot_name == "chaise_free_end" and request.allowed for request in inputs.requests):
        slots_used.append("chaise_free_end")
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
            "strategy": "corner_outer_only_frame",
            "handler": "build_arms_corner",
            "profile": profile,
            "slots_used": slots_used,
        },
        reason="dispatch corner arms strategy",
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

    if inputs.layout_kind == "corner" and inputs.requests:
        corner_profile = profile
        if corner_profile != "frame_box_open":
            emit_simple(
                ctx.diag,
                run_id=ctx.run_id,
                stage="build",
                component="arms",
                code="CORNER_PROFILE_OVERRIDE",
                severity=Severity.INFO,
                path="arms.profile",
                source="fallback",
                input_value=profile,
                resolved_value="frame_box_open",
                reason="corner outer-only strategy uses frame profile",
            )
            corner_profile = "frame_box_open"
        handler_name, handler = strategy_dispatch[corner_profile]
        _build_arms_corner(
            plan=plan,
            inputs=inputs,
            ctx=ctx,
            handler_name=handler_name,
            handler=handler,
            arms_type=arms_type,
            profile=corner_profile,
            seat_total_width_mm=seat_total_width_mm,
            seat_depth_mm=seat_depth_mm,
            seat_height_mm=seat_height_mm,
            frame_thickness_mm=frame_thickness_mm,
            back_height_mm=back_height_mm,
            arms_width_mm=arms_width_mm,
            arms=arms,
            back_support_for_arms=back_support_for_arms,
        )
        return

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
