"""Diagnostics contracts and sink implementations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Protocol


class Severity(IntEnum):
    INFO = 0
    WARN = 1
    ERROR = 2
    FATAL = 3


SEVERITY_LABELS: dict[int, str] = {
    int(Severity.INFO): "info",
    int(Severity.WARN): "warn",
    int(Severity.ERROR): "error",
    int(Severity.FATAL): "fatal",
}
SEVERITY_MIN = int(Severity.INFO)
SEVERITY_MAX = int(Severity.FATAL)
VALID_SEVERITIES = frozenset(SEVERITY_LABELS.keys())

VALID_STAGES = frozenset({"resolve", "layout", "build", "debug"})
VALID_SOURCES = frozenset({"ir", "preset", "global", "fallback", "computed"})
VALID_COMPONENTS = frozenset(
    {"resolver", "layout", "seat_frame", "seat_slats", "back", "arms", "legs", "builder"}
)
DEFAULT_STAGE = "build"
DEFAULT_SOURCE = "computed"
DEFAULT_COMPONENT = "builder"


def utc_now_iso() -> str:
    """Return UTC timestamp in stable ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Event:
    """Unified diagnostics event schema."""

    ts: str
    run_id: str
    stage: str
    component: str
    code: str
    severity: int
    path: str
    source: str
    input_value: Any
    resolved_value: Any
    reason: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_event(
    *,
    run_id: str = "",
    stage: str,
    component: str,
    code: str,
    severity: int = 0,
    path: str = "",
    source: str = "",
    input_value: Any = None,
    resolved_value: Any = None,
    reason: str = "",
    meta: dict[str, Any] | None = None,
    ts: str = "",
) -> Event:
    if not ts:
        ts = utc_now_iso()
    stage_value_raw = stage
    stage_candidate = str(stage).strip().lower() if isinstance(stage, str) else ""
    stage_value = stage_candidate if stage_candidate in VALID_STAGES else DEFAULT_STAGE
    component_value_raw = component
    component_candidate = str(component).strip().lower() if isinstance(component, str) else ""
    component_value = component_candidate if component_candidate in VALID_COMPONENTS else DEFAULT_COMPONENT
    source_value_raw = source
    source_candidate = str(source).strip().lower() if isinstance(source, str) else ""
    source_value = source_candidate if source_candidate in VALID_SOURCES else DEFAULT_SOURCE
    try:
        severity_value = int(severity)
    except (TypeError, ValueError):
        severity_value = int(Severity.INFO)
    meta_value = dict(meta) if isinstance(meta, dict) else {}
    normalized_from: dict[str, Any] = {}
    if stage_value != stage_candidate:
        normalized_from["stage"] = stage_value_raw
    if component_value != component_candidate:
        normalized_from["component"] = component_value_raw
    if source_value != source_candidate:
        normalized_from["source"] = source_value_raw
    if normalized_from:
        existing_normalized = meta_value.get("normalized_from")
        if isinstance(existing_normalized, dict):
            merged_normalized = dict(normalized_from)
            merged_normalized.update(existing_normalized)
            meta_value["normalized_from"] = merged_normalized
        else:
            meta_value["normalized_from"] = normalized_from
        if not reason:
            reason = "normalized diagnostics vocabulary"
    return Event(
        ts=ts,
        run_id=run_id,
        stage=stage_value,
        component=component_value,
        code=code,
        severity=max(SEVERITY_MIN, min(SEVERITY_MAX, severity_value)),
        path=path,
        source=source_value,
        input_value=input_value,
        resolved_value=resolved_value,
        reason=reason,
        meta=meta_value,
    )


def emit_simple(
    sink: DiagnosticsSink,
    *,
    code: str,
    path: str = "",
    payload: Any = None,
    severity: int = Severity.INFO,
    component: str = DEFAULT_COMPONENT,
    stage: str = DEFAULT_STAGE,
    iter_index: int | None = None,
    source: str = DEFAULT_SOURCE,
    reason: str = "",
    run_id: str = "",
    input_value: Any = None,
    resolved_value: Any = None,
    meta: dict[str, Any] | None = None,
    ts: str = "",
    **extra_meta: Any,
) -> Event:
    merged_meta = dict(meta) if isinstance(meta, dict) else {}
    if extra_meta:
        merged_meta.update(extra_meta)
    if payload is not None and "payload" not in merged_meta:
        merged_meta["payload"] = payload
    if iter_index is not None:
        merged_meta["iter_index"] = int(iter_index)
    event = make_event(
        ts=ts,
        run_id=run_id,
        stage=stage,
        component=component,
        code=code,
        severity=severity,
        path=path,
        source=source,
        input_value=input_value,
        resolved_value=resolved_value,
        reason=reason,
        meta=merged_meta,
    )
    sink.emit(event)
    return event


class DiagnosticsSink(Protocol):
    """Sink interface for structured diagnostics events."""

    def emit(self, event: Event) -> None:
        """Publish one diagnostics event."""


def _normalize_event(event: Event) -> Event:
    if event.ts and event.run_id:
        return event
    return make_event(
        ts=event.ts or utc_now_iso(),
        run_id=event.run_id or "",
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


class NoopDiagnosticsSink:
    """Default diagnostics sink that drops all events."""

    def emit(self, event: Event) -> None:
        del event


class JsonlDiagnosticsSink:
    """Append diagnostics events to a JSONL file."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def emit(self, event: Event) -> None:
        normalized = _normalize_event(event)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(normalized.to_dict(), ensure_ascii=False, sort_keys=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")
