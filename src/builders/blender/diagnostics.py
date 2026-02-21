"""Diagnostics contracts and sink implementations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


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
    return Event(
        ts=ts,
        run_id=run_id,
        stage=stage,
        component=component,
        code=code,
        severity=max(0, min(2, int(severity))),
        path=path,
        source=source,
        input_value=input_value,
        resolved_value=resolved_value,
        reason=reason,
        meta=dict(meta) if isinstance(meta, dict) else {},
    )


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
