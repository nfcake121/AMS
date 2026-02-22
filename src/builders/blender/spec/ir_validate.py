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
_REQUIRED_KEYS = {
    "version",
    "style",
    "layout",
    "seat_count",
    "seat_width_mm",
    "seat_depth_mm",
    "seat_height_mm",
}
_CORNER_LAYOUT_VALUES = {"corner", "l_shape"}
_CORNER_DEFAULTS: dict[str, Any] = {
    "chaise_side": "right",
    "chaise_extra_depth_mm": 300.0,
    "corner_gap_mm": 0.0,
    "join_mode": "shared_corner_post",
}


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


def _emit_missing_required(diagnostics: IRSchemaDiagnostics, path: str, default_value: Any) -> None:
    emit_simple(
        diagnostics,
        stage="ir_schema",
        component="resolver",
        code="IR_SCHEMA_MISSING_REQUIRED",
        severity=Severity.WARN,
        path=path,
        source="fallback",
        input_value=None,
        resolved_value=default_value,
        reason="missing required field",
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


def _emit_numeric_coerce(
    diagnostics: IRSchemaDiagnostics,
    path: str,
    old_value: Any,
    normalized_value: Any,
) -> None:
    emit_simple(
        diagnostics,
        stage="ir_schema",
        component="resolver",
        code="IR_SCHEMA_TYPE_COERCE",
        severity=Severity.INFO,
        path=path,
        source="ir",
        input_value=old_value,
        resolved_value=normalized_value,
        reason="safe numeric coercion",
        meta={"expected_type": "number"},
    )


def _is_corner_layout_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return value.strip().lower() in _CORNER_LAYOUT_VALUES


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
            if key in _REQUIRED_KEYS:
                _emit_missing_required(diagnostics=diagnostics, path=key, default_value=default_value)
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
        if isinstance(value, str):
            candidate = value.strip()
            try:
                numeric_value = float(candidate)
            except (TypeError, ValueError):
                had_fallback = True
                normalized[key] = default_value
                _emit_type_fallback(
                    diagnostics=diagnostics,
                    path=key,
                    old_value=value,
                    fallback_value=default_value,
                    expected_type="number",
                )
                continue
            if key == "seat_count":
                normalized_numeric: Any = int(round(numeric_value))
                if normalized_numeric <= 0:
                    had_fallback = True
                    normalized_numeric = int(default_value)
                    _emit_type_fallback(
                        diagnostics=diagnostics,
                        path=key,
                        old_value=value,
                        fallback_value=normalized_numeric,
                        expected_type="number",
                    )
                    continue
            else:
                normalized_numeric = float(numeric_value)
            normalized[key] = normalized_numeric
            _emit_numeric_coerce(
                diagnostics=diagnostics,
                path=key,
                old_value=value,
                normalized_value=normalized_numeric,
            )
            continue
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

    if _is_corner_layout_value(normalized.get("layout")):
        if "corner" not in normalized:
            normalized["corner"] = {}
            _emit_missing_default(diagnostics=diagnostics, path="corner", default_value={})
        corner_value = normalized.get("corner")
        if not isinstance(corner_value, dict):
            had_fallback = True
            normalized["corner"] = {}
            _emit_type_fallback(
                diagnostics=diagnostics,
                path="corner",
                old_value=corner_value,
                fallback_value={},
                expected_type="object",
            )
        corner = normalized.get("corner", {})
        if not isinstance(corner, dict):
            corner = {}
            normalized["corner"] = corner

        for key, default_value in _CORNER_DEFAULTS.items():
            path = f"corner.{key}"
            if key not in corner:
                corner[key] = deepcopy(default_value)
                _emit_missing_default(diagnostics=diagnostics, path=path, default_value=default_value)

        for key in {"chaise_side", "join_mode"}:
            path = f"corner.{key}"
            value = corner.get(key)
            if not isinstance(value, str):
                had_fallback = True
                corner[key] = str(_CORNER_DEFAULTS[key])
                _emit_type_fallback(
                    diagnostics=diagnostics,
                    path=path,
                    old_value=value,
                    fallback_value=corner[key],
                    expected_type="string",
                )

        for key in {"chaise_extra_depth_mm", "corner_gap_mm"}:
            path = f"corner.{key}"
            default_value = float(_CORNER_DEFAULTS[key])
            value = corner.get(key)
            if isinstance(value, str):
                candidate = value.strip()
                try:
                    numeric_value = float(candidate)
                except (TypeError, ValueError):
                    had_fallback = True
                    corner[key] = default_value
                    _emit_type_fallback(
                        diagnostics=diagnostics,
                        path=path,
                        old_value=value,
                        fallback_value=default_value,
                        expected_type="number",
                    )
                    continue
                corner[key] = float(numeric_value)
                _emit_numeric_coerce(
                    diagnostics=diagnostics,
                    path=path,
                    old_value=value,
                    normalized_value=corner[key],
                )
                continue
            if not isinstance(value, (int, float)):
                had_fallback = True
                corner[key] = default_value
                _emit_type_fallback(
                    diagnostics=diagnostics,
                    path=path,
                    old_value=value,
                    fallback_value=default_value,
                    expected_type="number",
                )

    diagnostics.normalized_ir = normalized
    return (not had_fallback), diagnostics
