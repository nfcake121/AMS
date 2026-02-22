"""IR schema stage integration for builder pipeline."""

from __future__ import annotations

from src.builders.blender.diagnostics import emit_simple
from src.builders.blender.spec.ir_validate import ir_schema_validate
from src.builders.blender.spec.types import BuildContext


def validate_and_normalize_ir(ir: dict, ctx: BuildContext) -> dict:
    """Validate IR schema and emit diagnostics into build sink."""
    _ok, diagnostics = ir_schema_validate(ir)
    for event in diagnostics.warnings:
        emit_simple(
            ctx.diag,
            ts=event.ts,
            run_id=ctx.run_id,
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
    return diagnostics.normalized_ir
