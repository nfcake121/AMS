"""IR schema validation and soft normalization before resolve."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from src.builders.blender.diagnostics import Event, Severity, emit_simple


_DEFAULT_IR: dict[str, Any] = {
    "version": "0.1",
    "style": "default",
    "layout": "straight",
    "seat_count": 3,
    "seat_width_mm": 600.0,
    "seat_depth_mm": 600.0,
    "seat_height_mm": 440.0,
    "frame": {},
    "legs": {},
    "arms": {},
    "slats": {},
    "back_support": {},
}

_STRING_KEYS_WITH_DEFAULTS = {
    "version": "0.1",
    "style": "default",
    "layout": "straight",
}

_NUMERIC_KEYS_WITH_DEFAULTS = {
    "seat_count": 3,
    "seat_width_mm": 600.0,
    "seat_depth_mm": 600.0,
    "seat_height_mm": 440.0,
}

_OBJECT_KEYS_WITH_DEFAULTS = {
    "frame": {},
    "legs": {},
    "arms": {},
    "slats": {},
    "back_support": {},
}

_OPTIONAL_STRING_KEYS = {"id", "preset_id"}


@dataclass
class IRSchemaDiagnostics:
    warnings: list[Event] = field(default_factory=list)
    normalized_ir: dict[str, Any] = field(default_factory=dict)

    def emit(self, event: Event) -> None:
        self.warnings.append(event)


def _emit_missing_default(diagnostics: IRSchemaDiagnostics, path: str, default_value: Any) -> None:
    emit_simple(
        diagnostics,
        stage="ir_schema",
        component="resolver",
        code="IR_SCHEMA_DEFAULT_APPLIED",
        severity=Severity.INFO,
        path=path,
        source="global",
        input_value=None,
        resolved_value=default_value,
        reason="missing->default",
    )


def _emit_type_fallback(
    diagnostics: IRSchemaDiagnostics,
    path: str,
    old_value: Any,
    fallback_value: Any,
    expected_type: str,
) -> None:
    emit_simple(
        diagnostics,
        stage="ir_schema",
        component="resolver",
        code="IR_SCHEMA_TYPE_COERCE",
        severity=Severity.WARN,
        path=path,
        source="fallback",
        input_value=old_value,
        resolved_value=fallback_value,
        reason=f"type fallback to {expected_type}",
        meta={"expected_type": expected_type},
    )


def ir_schema_validate(ir: Any) -> tuple[bool, IRSchemaDiagnostics]:
    """Validate and normalize IR structure before resolver.

    Returns:
      ok: False when any type fallback was required.
      diagnostics: Structured events + normalized IR payload.
    """
    diagnostics = IRSchemaDiagnostics()
    had_fallback = False

    if not isinstance(ir, dict):
        normalized = deepcopy(_DEFAULT_IR)
        _emit_type_fallback(
            diagnostics=diagnostics,
            path="$",
            old_value=type(ir).__name__,
            fallback_value="{}",
            expected_type="object",
        )
        emit_simple(
            diagnostics,
            stage="ir_schema",
            component="resolver",
            code="IR_SCHEMA_MISSING_REQUIRED",
            severity=Severity.WARN,
            path="$",
            source="fallback",
            input_value=type(ir).__name__,
            resolved_value="object",
            reason="root must be object",
        )
        diagnostics.normalized_ir = normalized
        return False, diagnostics

    normalized = deepcopy(ir)

    for key, default_value in _DEFAULT_IR.items():
        if key not in normalized:
            normalized[key] = deepcopy(default_value)
            _emit_missing_default(diagnostics, path=key, default_value=default_value)

    for key, default_value in _STRING_KEYS_WITH_DEFAULTS.items():
        value = normalized.get(key)
        if not isinstance(value, str):
            had_fallback = True
            normalized[key] = str(default_value)
            _emit_type_fallback(
                diagnostics=diagnostics,
                path=key,
                old_value=value,
                fallback_value=normalized[key],
                expected_type="string",
            )

    for key in _OPTIONAL_STRING_KEYS:
        if key not in normalized:
            continue
        value = normalized.get(key)
        if not isinstance(value, str):
            had_fallback = True
            normalized[key] = ""
            _emit_type_fallback(
                diagnostics=diagnostics,
                path=key,
                old_value=value,
                fallback_value=normalized[key],
                expected_type="string",
            )

    for key, default_value in _NUMERIC_KEYS_WITH_DEFAULTS.items():
        value = normalized.get(key)
        if not isinstance(value, (int, float)):
            had_fallback = True
            normalized[key] = default_value
            _emit_type_fallback(
                diagnostics=diagnostics,
                path=key,
                old_value=value,
                fallback_value=default_value,
                expected_type="number",
            )

    for key, default_value in _OBJECT_KEYS_WITH_DEFAULTS.items():
        value = normalized.get(key)
        if not isinstance(value, dict):
            had_fallback = True
            normalized[key] = deepcopy(default_value)
            _emit_type_fallback(
                diagnostics=diagnostics,
                path=key,
                old_value=value,
                fallback_value=default_value,
                expected_type="object",
            )

    diagnostics.normalized_ir = normalized
    return (not had_fallback), diagnostics
