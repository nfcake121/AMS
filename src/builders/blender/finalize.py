"""Finalize-stage helpers for Blender build plans."""

from __future__ import annotations

from src.builders.blender.diagnostics import Severity, emit_simple
from src.builders.blender.plan_types import Anchor, BuildPlan
from src.builders.blender.spec.types import BuildContext, Layout


def finalize_plan(plan: BuildPlan, *, layout: Layout, build_ctx: BuildContext, ir: dict) -> BuildPlan:
    plan.anchors.append(Anchor(name="seat_zone", location_mm=(0.0, 0.0, layout.seat_support_center_z)))
    emit_simple(
        build_ctx.diag,
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
    return plan
