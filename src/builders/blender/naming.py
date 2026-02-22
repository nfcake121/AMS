"""Naming policy contract for plan primitives and anchors.

This module is intentionally lightweight: it centralizes prefixes and
string-building helpers without changing existing geometry code paths.
"""

from __future__ import annotations


PREFIXES: dict[str, str] = {
    "arm": "arm_",
    "arm_main_left": "arm_main_left_",
    "arm_main_right": "arm_main_right_",
    "arm_chaise_free_end": "arm_chaise_free_end_",
    "back": "back_",
    "back_main": "back_main_",
    "back_chaise": "back_chaise_",
    "back_corner": "back_corner_",
    "back_rail": "back_rail_",
    "back_slat": "back_slat_",
    "beam": "beam_",
    "beam_main": "beam_main_",
    "beam_chaise": "beam_chaise_",
    "beam_corner": "beam_corner_",
    "beam_cross_chaise": "beam_cross_chaise_",
    "leg": "leg_",
    "leg_chaise": "leg_chaise_",
    "leg_point": "leg_point_",
    "rail": "rail_",
    "rail_chaise": "rail_chaise_",
    "seat_support": "seat_support",
    "slat": "slat_",
    "slat_chaise": "slat_chaise_",
}


def arm_name(side: str, part: str) -> str:
    side_token = str(side).strip().lower()
    part_token = str(part).strip().lower()
    return f"{PREFIXES['arm']}{side_token}_{part_token}"


def back_name(part: str) -> str:
    return f"{PREFIXES['back']}{str(part).strip().lower()}"


def back_rail_name(part: str) -> str:
    return f"{PREFIXES['back_rail']}{str(part).strip().lower()}"


def back_slat_name(part: str) -> str:
    return f"{PREFIXES['back_slat']}{str(part).strip().lower()}"


def beam_name(part: str) -> str:
    return f"{PREFIXES['beam']}{str(part).strip().lower()}"


def leg_name(index: int) -> str:
    return f"{PREFIXES['leg']}{int(index)}"


def leg_point_name(index: int) -> str:
    return f"{PREFIXES['leg_point']}{int(index)}"


def rail_name(part: str) -> str:
    return f"{PREFIXES['rail']}{str(part).strip().lower()}"


def slat_name(index: int) -> str:
    return f"{PREFIXES['slat']}{int(index)}"
