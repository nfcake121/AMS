from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, Optional, Tuple
from typing_extensions import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# =========================
# Enums / core types
# =========================

class SofaStyle(str, Enum):
    scandi = "scandi"
    loft = "loft"
    modern = "modern"
    minimal = "minimal"
    classic = "classic"


class SofaLayout(str, Enum):
    straight = "straight"
    corner = "corner"
    u_shape = "u_shape"
    modular = "modular"


class Orientation(str, Enum):
    left = "left"
    right = "right"


class ArmrestType(str, Enum):
    none = "none"
    left = "left"
    right = "right"
    both = "both"


class LegFamily(str, Enum):
    tapered_cone = "tapered_cone"
    tapered_prism = "tapered_prism"
    cylindrical = "cylindrical"
    block = "block"
    hairpin = "hairpin"
    sled = "sled"
    frame = "frame"


class SeatType(str, Enum):
    single = "single"
    cushions = "cushions"


# =========================
# Preferences (level-2)
# =========================

class RawPreferences(BaseModel):
    # thin / medium / thick — можно расширять позже
    leg_thickness_bias: Optional[Literal["thin", "medium", "thick"]] = None
    # box / rounded_bottom / rolled — пока совпадает с ArmsSpec.profile
    arm_profile: Optional[Literal["box", "rounded_bottom", "rolled"]] = None
    # soft / medium / firm — пока влияет только на seat_type
    seat_softness: Optional[Literal["soft", "medium", "firm"]] = None


# =========================
# Aliases / Canonicalization
# =========================

def _canon(s: str) -> str:
    s = s.strip().lower()
    s = s.replace("ё", "е")
    s = s.replace("-", " ")
    s = s.replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    return s


TYPE_ALIASES = {
    "диван": "sofa",
    "софа": "sofa",
    "sofa": "sofa",
}

STYLE_ALIASES = {
    "сканди": "scandi",
    "скандинавский": "scandi",
    "scandi": "scandi",

    "лофт": "loft",
    "loft": "loft",

    "современный": "modern",
    "модерн": "modern",
    "modern": "modern",

    "минимализм": "minimal",
    "минимальный": "minimal",
    "minimal": "minimal",

    "классический": "classic",
    "классика": "classic",
    "classic": "classic",
}

LAYOUT_ALIASES = {
    "прямой": "straight",
    "прямая": "straight",
    "straight": "straight",

    "угловой": "corner",
    "угловая": "corner",
    "corner": "corner",

    "п образный": "u_shape",
    "побразный": "u_shape",
    "u образный": "u_shape",
    "u shape": "u_shape",
    "u_shape": "u_shape",

    "секционный": "modular",
    "модульный": "modular",
    "modular": "modular",
}

LEG_ALIASES = {
    "конусные": "tapered_cone",
    "конус": "tapered_cone",
    "tapered cone": "tapered_cone",
    "tapered_cone": "tapered_cone",

    "пирамида": "tapered_prism",
    "призма": "tapered_prism",
    "скошенная пирамида": "tapered_prism",
    "tapered prism": "tapered_prism",
    "tapered_prism": "tapered_prism",

    "цилиндрические": "cylindrical",
    "цилиндр": "cylindrical",
    "cylindrical": "cylindrical",

    "блочные": "block",
    "кубики": "block",
    "block": "block",

    "hairpin": "hairpin",
    "шпильки": "hairpin",

    "sled": "sled",
    "полозья": "sled",

    "frame": "frame",
    "рамные": "frame",
}


# =========================
# Request model (сырой ввод)
# =========================

class SofaRequest(BaseModel):
    """
    Сырые параметры, извлечённые из текста (NER + нормализация).
    Могут быть неполными — Resolver заполнит дефолты.
    """

    type: Literal["sofa"] = "sofa"

    style: SofaStyle
    layout: SofaLayout
    orientation: Optional[Orientation] = None  # may be None; resolver fills for corner/u_shape

    seat_height_mm: Optional[int] = Field(default=None, ge=250, le=650)
    seat_depth_mm: Optional[int] = Field(default=None, ge=350, le=900)

    seat_width_range_mm: Optional[Tuple[int, int]] = None  # (min,max) mm
    seat_count: Optional[int] = Field(default=None, ge=1, le=8)

    has_chaise: Optional[bool] = None
    armrests: Optional[ArmrestType] = None
    leg_family: Optional[LegFamily] = None
    transformable: Optional[bool] = None

    preferences: Optional[RawPreferences] = None

    # --- Alias validators (before enum parsing) ---

    @field_validator("type", mode="before")
    @classmethod
    def _v_type(cls, v):
        if v is None:
            return v
        return TYPE_ALIASES.get(_canon(str(v)), v)

    @field_validator("style", mode="before")
    @classmethod
    def _v_style(cls, v):
        if v is None:
            return v
        return STYLE_ALIASES.get(_canon(str(v)), v)

    @field_validator("layout", mode="before")
    @classmethod
    def _v_layout(cls, v):
        if v is None:
            return v
        return LAYOUT_ALIASES.get(_canon(str(v)), v)

    @field_validator("leg_family", mode="before")
    @classmethod
    def _v_leg_family(cls, v):
        if v is None:
            return v
        return LEG_ALIASES.get(_canon(str(v)), v)

    # --- Structural validators ---

    @field_validator("seat_width_range_mm")
    @classmethod
    def validate_seat_width_range(cls, v: Optional[Tuple[int, int]]):
        if v is None:
            return None
        a, b = v
        if a <= 0 or b <= 0:
            raise ValueError("seat_width_range_mm values must be > 0")
        if a > b:
            raise ValueError("seat_width_range_mm min must be <= max")
        if a < 350 or b > 1200:
            raise ValueError("seat_width_range_mm out of bounds (350..1200 mm)")
        return v

    @model_validator(mode="after")
    def validate_layout_orientation(self):
        # В Request допускаем отсутствие orientation.
        # Resolver заполнит дефолт, если layout corner/u_shape.
        return self


# =========================
# Resolved specs (Builder input)
# =========================

class LegsSpec(BaseModel):
    family: LegFamily
    height_mm: int = Field(ge=30, le=260)
    params: Dict[str, Any] = Field(default_factory=dict)


class ArmsSpec(BaseModel):
    type: ArmrestType
    width_mm: int = Field(ge=0, le=400)
    profile: Literal["box", "rounded_bottom", "rolled"] = "box"


class FrameSpec(BaseModel):
    thickness_mm: int = Field(ge=20, le=80)
    back_thickness_mm: int = Field(ge=50, le=180)
    back_height_above_seat_mm: int = Field(ge=250, le=700)


class SofaResolved(BaseModel):
    """
    Полная спецификация. Builder обязан уметь собирать любой SofaResolved.
    """

    style: SofaStyle
    layout: SofaLayout
    orientation: Optional[Orientation] = None  # resolved for corner/u_shape

    seat_count: int = Field(ge=1, le=8)

    seat_height_mm: int = Field(ge=250, le=650)
    seat_depth_mm: int = Field(ge=350, le=900)
    seat_width_mm: int = Field(ge=350, le=1200)

    has_chaise: bool
    transformable: bool
    seat_type: SeatType

    legs: LegsSpec
    arms: ArmsSpec
    frame: FrameSpec

    @model_validator(mode="after")
    def sanity(self):
        total_seat_width = self.seat_count * self.seat_width_mm
        if self.arms.type == ArmrestType.both and total_seat_width < 900:
            raise ValueError("Too small sofa for two armrests with given seat_count/seat_width_mm")
        return self


# =========================
# Resolver defaults
# =========================

STYLE_DEFAULTS: Dict[SofaStyle, Dict[str, Any]] = {
    SofaStyle.scandi: dict(
        seat_count=3,
        seat_height_mm=440,
        seat_depth_mm=600,
        seat_width_mm=600,
        has_chaise=False,
        transformable=False,
        seat_type=SeatType.cushions,
        legs=dict(family=LegFamily.tapered_cone, height_mm=160, params={"r_top": 22, "r_bottom": 12}),
        arms=dict(type=ArmrestType.both, width_mm=120, profile="box"),
        frame=dict(thickness_mm=35, back_thickness_mm=90, back_height_above_seat_mm=420),
    ),
    SofaStyle.loft: dict(
        seat_count=3,
        seat_height_mm=430,
        seat_depth_mm=620,
        seat_width_mm=620,
        has_chaise=False,
        transformable=False,
        seat_type=SeatType.single,
        legs=dict(family=LegFamily.frame, height_mm=120, params={}),
        arms=dict(type=ArmrestType.both, width_mm=140, profile="box"),
        frame=dict(thickness_mm=40, back_thickness_mm=110, back_height_above_seat_mm=420),
    ),
    SofaStyle.modern: dict(
        seat_count=3,
        seat_height_mm=450,
        seat_depth_mm=620,
        seat_width_mm=620,
        has_chaise=False,
        transformable=False,
        seat_type=SeatType.single,
        legs=dict(family=LegFamily.block, height_mm=80, params={}),
        arms=dict(type=ArmrestType.both, width_mm=130, profile="rounded_bottom"),
        frame=dict(thickness_mm=40, back_thickness_mm=100, back_height_above_seat_mm=400),
    ),
    SofaStyle.minimal: dict(
        seat_count=3,
        seat_height_mm=430,
        seat_depth_mm=600,
        seat_width_mm=620,
        has_chaise=False,
        transformable=False,
        seat_type=SeatType.single,
        legs=dict(family=LegFamily.block, height_mm=40, params={}),
        arms=dict(type=ArmrestType.both, width_mm=110, profile="box"),
        frame=dict(thickness_mm=35, back_thickness_mm=90, back_height_above_seat_mm=380),
    ),
    SofaStyle.classic: dict(
        seat_count=3,
        seat_height_mm=460,
        seat_depth_mm=590,
        seat_width_mm=600,
        has_chaise=False,
        transformable=False,
        seat_type=SeatType.cushions,
        legs=dict(family=LegFamily.tapered_prism, height_mm=120, params={"top": [45, 45], "bottom": [30, 30]}),
        arms=dict(type=ArmrestType.both, width_mm=170, profile="rolled"),
        frame=dict(thickness_mm=45, back_thickness_mm=120, back_height_above_seat_mm=480),
    ),
}


# =========================
# Resolver (детерминированный)
# =========================

def resolve_sofa(req: SofaRequest) -> SofaResolved:
    """
    Детерминированно заполняет пропуски и приводит к полной спецификации для Builder.
    """

    defaults = STYLE_DEFAULTS[req.style]

    # 1) Orientation: required for corner/u_shape, but can be missing in Request.
    orientation = req.orientation
    if req.layout in {SofaLayout.corner, SofaLayout.u_shape} and orientation is None:
        orientation = Orientation.left  # system default

    # 2) Seat width: if user gave range — take midpoint; else style default.
    seat_width_mm = defaults["seat_width_mm"]
    if req.seat_width_range_mm is not None:
        a, b = req.seat_width_range_mm
        seat_width_mm = int(round((a + b) / 2))

    # 3) User overrides > defaults
    seat_count = req.seat_count or defaults["seat_count"]
    seat_height_mm = req.seat_height_mm or defaults["seat_height_mm"]
    seat_depth_mm = req.seat_depth_mm or defaults["seat_depth_mm"]

    has_chaise = req.has_chaise if req.has_chaise is not None else defaults["has_chaise"]
    transformable = req.transformable if req.transformable is not None else defaults["transformable"]

    # 4) legs/arms/frame dicts
    legs_dict = dict(defaults["legs"])
    if req.leg_family is not None:
        legs_dict["family"] = req.leg_family

    arms_dict = dict(defaults["arms"])
    if req.armrests is not None:
        arms_dict["type"] = req.armrests
        if req.armrests == ArmrestType.none:
            arms_dict["width_mm"] = 0

    frame_dict = dict(defaults["frame"])

    # 5) Preferences bias (safe, optional)
    if req.preferences is not None:
        prefs = req.preferences

        # leg thickness bias: only applies to families that use radii
        if prefs.leg_thickness_bias in {"thin", "thick"}:
            fam = legs_dict.get("family")
            params = dict(legs_dict.get("params", {}))

            # only for tapered_cone/cylindrical where r_top/r_bottom make sense
            if fam in {LegFamily.tapered_cone, LegFamily.cylindrical}:
                r_top = int(params.get("r_top", 22))
                r_bottom = int(params.get("r_bottom", 12))

                if prefs.leg_thickness_bias == "thin":
                    r_top = max(10, int(round(r_top * 0.8)))
                    r_bottom = max(6, int(round(r_bottom * 0.8)))
                else:  # thick
                    r_top = min(45, int(round(r_top * 1.2)))
                    r_bottom = min(40, int(round(r_bottom * 1.2)))

                params["r_top"] = r_top
                params["r_bottom"] = r_bottom
                legs_dict["params"] = params

        # arm profile preference
        if prefs.arm_profile is not None:
            arms_dict["profile"] = prefs.arm_profile

        # seat softness -> choose cushion seat type for soft/medium
        if prefs.seat_softness in {"soft", "medium"}:
            seat_type = SeatType.cushions
        else:
            seat_type = defaults["seat_type"]
    else:
        seat_type = defaults["seat_type"]

    return SofaResolved(
        style=req.style,
        layout=req.layout,
        orientation=orientation,

        seat_count=seat_count,
        seat_height_mm=seat_height_mm,
        seat_depth_mm=seat_depth_mm,
        seat_width_mm=seat_width_mm,

        has_chaise=has_chaise,
        transformable=transformable,
        seat_type=seat_type,

        legs=LegsSpec(**legs_dict),
        arms=ArmsSpec(**arms_dict),
        frame=FrameSpec(**frame_dict),
    )
