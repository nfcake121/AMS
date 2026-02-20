"""Resolved spec and build context types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArmsSpec:
    type: str
    width_mm: float
    profile: str


@dataclass(frozen=True)
class CenterPostSpec:
    enabled: bool
    thickness_mm: float
    inset_y_mm: float
    width_mm: float


@dataclass(frozen=True)
class BackFrameSpec:
    height_above_seat_mm: float
    thickness_mm: float
    offset_y_mm: float
    margin_x_mm: float
    margin_z_mm: float
    rail_inset_mm: float
    rail_width_mm: float
    rail_depth_mm: float
    rail_height_mm: float
    bottom_rail_split: bool
    bottom_rail_gap_mm: float
    split_center: bool
    frame_layout: str
    bottom_rail_attach_mode: str
    bottom_rail_height_mm: float
    center_post: CenterPostSpec


@dataclass(frozen=True)
class BackSlatsSpec:
    orientation: str
    layout: str
    count: int
    width_mm: float
    thickness_mm: float
    arc_height_mm: float
    arc_sign: float
    gap_mm: float
    has_gap_mm: bool
    center_gap_mm: float


@dataclass(frozen=True)
class BackStrapsSpec:
    count: int
    width_mm: float
    thickness_mm: float


@dataclass(frozen=True)
class BackSpec:
    has_back_support: bool
    mode: str
    frame: BackFrameSpec
    slats: BackSlatsSpec
    straps: BackStrapsSpec


@dataclass(frozen=True)
class ResolvedSpec:
    style: str
    preset_id: str
    arms: ArmsSpec
    back: BackSpec
    seat: object | None = None
    legs: object | None = None


@dataclass
class ResolveDiagnostics:
    warnings: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class BuildContext:
    run_id: str | None
    debug: bool
