"""Resolved spec and build context types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.builders.blender.diagnostics import DiagnosticsSink, Event, NoopDiagnosticsSink


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
class LegsSpec:
    family: str | None
    height_mm: float | int | None
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass(frozen=True)
class ResolvedSpec:
    style: str
    preset_id: str
    arms: ArmsSpec
    back: BackSpec
    legs: LegsSpec
    seat: object | None = None


@dataclass
class ResolveDiagnostics:
    warnings: list[Event] = field(default_factory=list)

    def emit(self, event: Event) -> None:
        self.warnings.append(event)


@dataclass(frozen=True)
class BuildContext:
    run_id: str
    debug: bool
    diag: DiagnosticsSink = field(default_factory=NoopDiagnosticsSink, repr=False, compare=False)


@dataclass(frozen=True)
class Layout:
    seat_count: int
    seat_width_mm: float
    seat_depth_mm: float
    seat_height_mm: float
    seat_total_width_mm: float
    total_width_mm: float
    frame_thickness_mm: float
    seat_min_x: float
    seat_max_x: float
    seat_min_y: float
    seat_max_y: float
    seat_top_z: float
    floor_z: float
    seat_support_center_z: float
    seat_support_top_z: float
    base_frame_top_z: float
    base_frame_center_z: float
    back_base_y: float
    back_plane_y: float


@dataclass(frozen=True)
class SeatFrameInputs:
    seat_count: int
    total_width_mm: float
    seat_depth_mm: float
    frame_thickness_mm: float
    base_frame_center_z: float
    slats_enabled: bool
    seat_total_width_mm: float
    seat_support_center_z: float


@dataclass(frozen=True)
class SeatSlatsInputs:
    slats_enabled: bool
    seat_depth_mm: float
    seat_total_width_mm: float
    slat_count: int
    slat_width_mm: float
    slat_thickness_mm: float
    slat_arc_height_mm: float
    slat_arc_sign: float
    slat_margin_x_mm: float
    slat_margin_y_mm: float
    slat_clearance_mm: float
    slat_mount_mode: str
    slat_mount_offset_mm: float
    slat_rail_inset_mm: float
    slat_rail_height_mm: float
    slat_rail_width_mm: float
    slat_rail_inset_y_mm: float
    base_frame_top_z: float
    seat_support_top_z: float


@dataclass(frozen=True)
class BackInputs:
    back: BackSpec
    seat_total_width_mm: float
    total_width_mm: float
    seat_depth_mm: float
    frame_thickness_mm: float
    seat_support_top_z: float
    base_frame_top_z: float
    base_frame_center_z: float
    back_plane_y: float


@dataclass(frozen=True)
class ArmsInputs:
    arms_type: str
    arms_width_mm: float
    profile: str
    seat_width_mm: float
    seat_depth_mm: float
    seat_height_mm: float
    seat_count: int
    frame_thickness_mm: float
    back_height_mm: float
    arms_config: dict[str, Any]
    back_support_config: dict[str, Any]


@dataclass(frozen=True)
class LegsInputs:
    family: str | None
    height_mm: float | int | None
    total_width_mm: float
    frame_thickness_mm: float
    seat_depth_mm: float
    base_frame_top_z: float
