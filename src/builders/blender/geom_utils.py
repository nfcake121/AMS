"""Shared numeric and geometry helpers for Blender builder modules."""

from __future__ import annotations

import math
from typing import Dict, Iterable, Protocol, Tuple


class PrimitiveLike(Protocol):
    dimensions_mm: Tuple[float, float, float]
    location_mm: Tuple[float, float, float]
    rotation_deg: Tuple[float, float, float]


def ir_value(ir: dict, key: str, default: float) -> float:
    value = ir.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, float(value)))


def primitive_bbox_world(primitive: PrimitiveLike) -> Dict[str, Tuple[float, float, float]]:
    dx, dy, dz = primitive.dimensions_mm
    cx, cy, cz = primitive.location_mm
    half_x = float(dx) / 2.0
    half_y = float(dy) / 2.0
    half_z = float(dz) / 2.0
    try:
        rx_deg, ry_deg, rz_deg = primitive.rotation_deg
    except (TypeError, ValueError):
        rx_deg, ry_deg, rz_deg = (0.0, 0.0, 0.0)
    if rx_deg == 0.0 and ry_deg == 0.0 and rz_deg == 0.0:
        world_half_x = half_x
        world_half_y = half_y
        world_half_z = half_z
    else:
        rx = math.radians(float(rx_deg))
        ry = math.radians(float(ry_deg))
        rz = math.radians(float(rz_deg))
        cxr, sxr = math.cos(rx), math.sin(rx)
        cyr, syr = math.cos(ry), math.sin(ry)
        czr, szr = math.cos(rz), math.sin(rz)

        # Blender default Euler order is XYZ.
        r00 = cyr * czr
        r01 = -cyr * szr
        r02 = syr
        r10 = sxr * syr * czr + cxr * szr
        r11 = -sxr * syr * szr + cxr * czr
        r12 = -sxr * cyr
        r20 = -cxr * syr * czr + sxr * szr
        r21 = cxr * syr * szr + sxr * czr
        r22 = cxr * cyr

        world_half_x = abs(r00) * half_x + abs(r01) * half_y + abs(r02) * half_z
        world_half_y = abs(r10) * half_x + abs(r11) * half_y + abs(r12) * half_z
        world_half_z = abs(r20) * half_x + abs(r21) * half_y + abs(r22) * half_z
    return {
        "min": (cx - world_half_x, cy - world_half_y, cz - world_half_z),
        "max": (cx + world_half_x, cy + world_half_y, cz + world_half_z),
    }


def primitives_union_bbox(primitives: Iterable[PrimitiveLike]) -> Dict[str, Tuple[float, float, float]]:
    min_x = float("inf")
    min_y = float("inf")
    min_z = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")
    max_z = float("-inf")
    has_any = False
    for primitive in primitives:
        has_any = True
        bbox = primitive_bbox_world(primitive)
        bmin = bbox["min"]
        bmax = bbox["max"]
        min_x = min(min_x, bmin[0])
        min_y = min(min_y, bmin[1])
        min_z = min(min_z, bmin[2])
        max_x = max(max_x, bmax[0])
        max_y = max(max_y, bmax[1])
        max_z = max(max_z, bmax[2])
    if not has_any:
        return {
            "min": (0.0, 0.0, 0.0),
            "max": (0.0, 0.0, 0.0),
        }
    return {
        "min": (min_x, min_y, min_z),
        "max": (max_x, max_y, max_z),
    }
