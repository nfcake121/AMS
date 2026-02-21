"""Plan result dataclasses shared by builder and components."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Primitive:
    """Represents a basic geometry primitive."""

    name: str
    shape: str
    dimensions_mm: Tuple[float, float, float]
    location_mm: Tuple[float, float, float]
    rotation_deg: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    params: Dict[str, float] = field(default_factory=dict)


@dataclass
class Anchor:
    """Named anchor or empty location."""

    name: str
    location_mm: Tuple[float, float, float]


@dataclass
class BuildPlan:
    """Container for primitives and anchors to build a sofa frame."""

    primitives: List[Primitive] = field(default_factory=list)
    anchors: List[Anchor] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
