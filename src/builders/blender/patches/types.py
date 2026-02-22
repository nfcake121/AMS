"""Types for patch operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


PatchOpName = Literal["set", "inc"]


@dataclass(frozen=True)
class PatchOp:
    op: PatchOpName
    path: str
    value: Any = None
    delta: float | int | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "path": self.path,
            "value": self.value,
            "delta": self.delta,
            "meta": dict(self.meta),
        }


@dataclass(frozen=True)
class PatchResult:
    applied: list[PatchOp] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    changed: bool = False
