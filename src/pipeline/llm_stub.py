"""Optional LLM stub for patch-suggestion generation.

The stub is intentionally non-invasive: it never mutates IR or build plans.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.builders.blender.diagnostics import Event, build_diagnostics_summary


def _env_truthy(name: str) -> bool:
    value = os.environ.get(name, "")
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def llm_stub_enabled() -> bool:
    return _env_truthy("AMS_LLM_ENABLED")


@dataclass(frozen=True)
class PatchOp:
    op: str
    path: str
    value: Any
    reason: str
    source_event_code: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "path": self.path,
            "value": self.value,
            "reason": self.reason,
            "source_event_code": self.source_event_code,
            "confidence": float(self.confidence),
        }


def generate_patch_suggestions(
    *,
    ir: dict,
    events: Iterable[Event],
    metrics: dict[str, Any] | None = None,
    validators: dict[str, Any] | None = None,
) -> list[PatchOp]:
    del ir, metrics, validators
    suggestions: list[PatchOp] = []
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        if not event.path:
            continue
        code = str(event.code or "")
        if code.endswith("CLAMP"):
            reason = "resolver clamp observed"
            confidence = 0.6
        elif code.endswith("FALLBACK"):
            reason = "resolver fallback observed"
            confidence = 0.55
        elif "ALIAS" in code:
            reason = "resolver alias normalization observed"
            confidence = 0.5
        else:
            continue
        key = (event.path, repr(event.resolved_value), code)
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(
            PatchOp(
                op="replace",
                path=event.path,
                value=event.resolved_value,
                reason=reason,
                source_event_code=code,
                confidence=confidence,
            )
        )
    return suggestions


def _write_suggestions(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def maybe_generate_suggestions_from_env(
    *,
    ir: dict,
    events: Iterable[Event],
    metrics: dict[str, Any] | None = None,
    validators: dict[str, Any] | None = None,
) -> list[PatchOp]:
    if not llm_stub_enabled():
        return []

    events_list = list(events)
    suggestions = generate_patch_suggestions(
        ir=ir,
        events=events_list,
        metrics=metrics,
        validators=validators,
    )
    out_path = str(os.environ.get("AMS_LLM_PATCHES_JSON", "")).strip()
    if out_path:
        payload = {
            "enabled": True,
            "suggestions": [item.to_dict() for item in suggestions],
            "diagnostics_summary": build_diagnostics_summary(events_list),
        }
        _write_suggestions(Path(out_path), payload)
    return suggestions
