"""IR resolver -> normalized building spec."""

from __future__ import annotations

from src.builders.blender.spec.catalog import default_preset_id, get_preset
from src.builders.blender.spec.types import (
    ArmsSpec,
    BackFrameSpec,
    BackSlatsSpec,
    BackSpec,
    BackStrapsSpec,
    CenterPostSpec,
    ResolveDiagnostics,
    ResolvedSpec,
)


_PROFILE_ALIASES = {
    "scandi_frame": "frame_box_open",
    "frame_open": "frame_box_open",
    "scandi_open_frame": "frame_box_open",
    "frame_box_open": "frame_box_open",
}

_BACK_FRAME_LAYOUT_ALIASES = {
    "single": "single",
    "full": "single",
    "split_2": "split_2",
}

_BACK_SLAT_ORIENTATION_VALUES = {"vertical", "horizontal"}
_BACK_SLAT_LAYOUT_VALUES = {"full", "split_center"}
_BACK_SUPPORT_MODES = {"panel", "slats", "straps"}
_BACK_ATTACH_MODES = {"seat_rear_beam", "none"}


def _warn(
    diagnostics: ResolveDiagnostics,
    code: str,
    message: str,
    path: str,
    old,
    new,
    source: str = "resolver",
) -> None:
    diagnostics.warnings.append(
        {
            "code": code,
            "message": message,
            "path": path,
            "old": old,
            "new": new,
            "source": source,
        }
    )


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _as_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(default)


def _pick_value(explicit: dict, preset: dict, key: str, fallback):
    if isinstance(explicit, dict) and key in explicit:
        return explicit[key], "ir"
    if isinstance(preset, dict) and key in preset:
        return preset[key], "preset"
    return fallback, "global"


def _clamp_non_negative(
    diagnostics: ResolveDiagnostics,
    value: float,
    path: str,
) -> float:
    if value < 0.0:
        _warn(
            diagnostics,
            code="BACK_CLAMP",
            message=f"{path} clamped to 0.0",
            path=path,
            old=value,
            new=0.0,
        )
        return 0.0
    return value


def _clamp_range(
    diagnostics: ResolveDiagnostics,
    value: float,
    path: str,
    min_value: float,
    max_value: float,
) -> float:
    clamped = max(min_value, min(max_value, float(value)))
    if clamped != float(value):
        _warn(
            diagnostics,
            code="BACK_CLAMP",
            message=f"{path} clamped to [{min_value}, {max_value}]",
            path=path,
            old=value,
            new=clamped,
        )
    return clamped


def _canon_arms_type(value) -> str:
    if not isinstance(value, str):
        return "none"
    normalized = value.strip().lower()
    if normalized in {"none", "left", "right", "both"}:
        return normalized
    return "none"


def _canonical_profile(profile_raw, style_raw) -> tuple[str, bool]:
    if isinstance(profile_raw, str):
        profile_text = profile_raw.strip().lower()
    else:
        profile_text = ""

    if isinstance(style_raw, str):
        style_text = style_raw.strip().lower()
    else:
        style_text = ""

    style_is_open = style_text in _PROFILE_ALIASES
    profile_alias = _PROFILE_ALIASES.get(profile_text)
    if profile_alias is not None:
        return profile_alias, False
    if profile_text == "box":
        return ("frame_box_open", False) if style_is_open else ("box", False)
    if style_is_open:
        return "frame_box_open", False
    # Unknown profile fallback keeps behavior stable and is reported to diagnostics.
    return "box", bool(profile_text)


def _canonical_choice(
    diagnostics: ResolveDiagnostics,
    path: str,
    value_raw,
    allowed: set[str],
    fallback: str,
) -> str:
    if isinstance(value_raw, str):
        value = value_raw.strip().lower()
        if value in allowed:
            return value
        if value:
            _warn(
                diagnostics,
                code="BACK_FALLBACK",
                message=f"unsupported {path} fallback to {fallback}",
                path=path,
                old=value_raw,
                new=fallback,
            )
    return fallback


def resolve_back_spec(ir: dict, preset: dict, diagnostics: ResolveDiagnostics) -> BackSpec:
    has_back_support = "back_support" in ir
    back_support_raw = ir.get("back_support")
    if has_back_support and not isinstance(back_support_raw, dict):
        _warn(
            diagnostics,
            code="BACK_FALLBACK",
            message="back_support must be an object; fallback to defaults",
            path="back_support",
            old=type(back_support_raw).__name__,
            new="{}",
        )
    back_support = back_support_raw if isinstance(back_support_raw, dict) else {}

    preset_back = preset.get("back", {}) if isinstance(preset.get("back"), dict) else {}
    preset_back_frame = preset_back.get("frame", {}) if isinstance(preset_back.get("frame"), dict) else {}
    preset_back_slats = preset_back.get("slats", {}) if isinstance(preset_back.get("slats"), dict) else {}
    preset_back_straps = preset_back.get("straps", {}) if isinstance(preset_back.get("straps"), dict) else {}
    preset_center_post = (
        preset_back_frame.get("center_post", {})
        if isinstance(preset_back_frame.get("center_post"), dict)
        else {}
    )

    if not has_back_support:
        _warn(
            diagnostics,
            code="BACK_DEFAULT_USED",
            message="back_support not provided; defaults resolved for future component use",
            path="back_support",
            old=None,
            new=preset_back.get("mode", "panel"),
        )

    frame_root = ir.get("frame", {}) if isinstance(ir.get("frame"), dict) else {}
    frame_thickness_default = _as_float(frame_root.get("thickness_mm", 35.0), 35.0)
    frame_back_height_default = _as_float(frame_root.get("back_height_above_seat_mm", 420.0), 420.0)
    frame_back_thickness_default = _as_float(frame_root.get("back_thickness_mm", 90.0), 90.0)

    back_mode_raw, _ = _pick_value(back_support, preset_back, "mode", "panel")
    back_mode = _canonical_choice(
        diagnostics=diagnostics,
        path="back_support.mode",
        value_raw=back_mode_raw,
        allowed=_BACK_SUPPORT_MODES,
        fallback="panel",
    )

    height_raw, _ = _pick_value(back_support, preset_back, "height_above_seat_mm", frame_back_height_default)
    thickness_raw, _ = _pick_value(back_support, preset_back, "thickness_mm", frame_back_thickness_default)
    offset_y_raw, _ = _pick_value(back_support, preset_back, "offset_y_mm", 0.0)
    margin_x_raw, _ = _pick_value(back_support, preset_back, "margin_x_mm", 40.0)
    margin_z_raw, _ = _pick_value(back_support, preset_back, "margin_z_mm", 30.0)
    rail_inset_raw, _ = _pick_value(back_support, preset_back, "rail_inset_mm", 0.0)
    rail_width_raw, _ = _pick_value(back_support, preset_back, "rail_width_mm", frame_thickness_default)
    rail_depth_raw, _ = _pick_value(back_support, preset_back, "rail_depth_mm", frame_thickness_default)
    rail_height_raw, _ = _pick_value(back_support, preset_back, "rail_height_mm", _as_float(rail_width_raw, frame_thickness_default))
    bottom_rail_split_raw, _ = _pick_value(back_support, preset_back_frame, "bottom_rail_split", False)
    bottom_rail_gap_raw, _ = _pick_value(back_support, preset_back_frame, "bottom_rail_gap_mm", 60.0)
    split_center_raw, _ = _pick_value(back_support, preset_back_frame, "split_center", False)
    frame_layout_raw, frame_layout_source = _pick_value(back_support, preset_back_frame, "frame_layout", None)
    bottom_rail_attach_raw, _ = _pick_value(back_support, preset_back_frame, "bottom_rail_attach_mode", "seat_rear_beam")

    back_slats = back_support.get("slats", {}) if isinstance(back_support.get("slats"), dict) else {}
    center_post_ir = back_support.get("center_post", {}) if isinstance(back_support.get("center_post"), dict) else {}

    center_post_enabled_raw, _ = _pick_value(center_post_ir, preset_center_post, "enabled", False)
    center_post_enabled = _as_bool(center_post_enabled_raw, False)
    center_post_thickness_raw, _ = _pick_value(
        center_post_ir,
        preset_center_post,
        "thickness_mm",
        _as_float(rail_width_raw, frame_thickness_default),
    )
    center_post_inset_raw, _ = _pick_value(center_post_ir, preset_center_post, "inset_y_mm", 0.0)
    center_post_thickness_mm = _clamp_non_negative(
        diagnostics,
        _as_float(center_post_thickness_raw, _as_float(rail_width_raw, frame_thickness_default)),
        "back_support.center_post.thickness_mm",
    )
    center_post_inset_y_mm = _as_float(center_post_inset_raw, 0.0)

    if "center_post_width_mm" in back_support:
        center_post_width_mm = _as_float(back_support.get("center_post_width_mm"), _as_float(rail_width_raw, frame_thickness_default))
    elif center_post_enabled or ("thickness_mm" in center_post_ir):
        center_post_width_mm = center_post_thickness_mm
    elif "center_post_width_mm" in preset_back_frame and preset_back_frame.get("center_post_width_mm") is not None:
        center_post_width_mm = _as_float(preset_back_frame.get("center_post_width_mm"), _as_float(rail_width_raw, frame_thickness_default))
    elif center_post_enabled or ("thickness_mm" in preset_center_post):
        center_post_width_mm = center_post_thickness_mm
    else:
        center_post_width_mm = _as_float(rail_width_raw, frame_thickness_default)
    center_post_width_mm = _clamp_non_negative(
        diagnostics,
        center_post_width_mm,
        "back_support.center_post_width_mm",
    )

    back_rail_height_mm_for_default = _clamp_non_negative(
        diagnostics,
        _as_float(rail_height_raw, _as_float(rail_width_raw, frame_thickness_default)),
        "back_support.rail_height_mm",
    )
    default_bottom_rail_height_mm = max(10.0, round(back_rail_height_mm_for_default * 0.5))

    has_bottom_rail_height = "bottom_rail_height_mm" in back_support
    has_legacy_bottom_rail_thickness = "bottom_rail_thickness_mm" in back_support
    if has_bottom_rail_height:
        bottom_rail_height_mm = _as_float(back_support.get("bottom_rail_height_mm"), default_bottom_rail_height_mm)
    elif has_legacy_bottom_rail_thickness:
        legacy_value = _as_float(back_support.get("bottom_rail_thickness_mm"), default_bottom_rail_height_mm)
        if legacy_value < back_rail_height_mm_for_default:
            bottom_rail_height_mm = legacy_value
        else:
            bottom_rail_height_mm = default_bottom_rail_height_mm
    else:
        bottom_rail_height_raw, _ = _pick_value(back_support, preset_back_frame, "bottom_rail_height_mm", default_bottom_rail_height_mm)
        bottom_rail_height_mm = _as_float(bottom_rail_height_raw, default_bottom_rail_height_mm)

    slat_count_raw, _ = _pick_value(back_slats, preset_back_slats, "count", 10)
    slat_width_raw, _ = _pick_value(back_slats, preset_back_slats, "width_mm", 35.0)
    slat_thickness_raw, _ = _pick_value(back_slats, preset_back_slats, "thickness_mm", 10.0)
    slat_arc_height_raw, _ = _pick_value(back_slats, preset_back_slats, "arc_height_mm", 0.0)
    slat_arc_sign_raw, _ = _pick_value(back_slats, preset_back_slats, "arc_sign", -1.0)
    slat_orientation_raw, _ = _pick_value(back_slats, preset_back_slats, "orientation", "vertical")
    slat_layout_raw, _ = _pick_value(back_slats, preset_back_slats, "layout", "full")
    slat_gap_raw, slat_gap_source = _pick_value(back_slats, preset_back_slats, "gap_mm", 0.0)
    slat_center_gap_raw, _ = _pick_value(back_slats, preset_back_slats, "center_gap_mm", 0.0)

    strap_count_raw, _ = _pick_value(
        back_support.get("straps", {}) if isinstance(back_support.get("straps"), dict) else {},
        preset_back_straps,
        "count",
        6,
    )
    strap_width_raw, _ = _pick_value(
        back_support.get("straps", {}) if isinstance(back_support.get("straps"), dict) else {},
        preset_back_straps,
        "width_mm",
        30.0,
    )
    strap_thickness_raw, _ = _pick_value(
        back_support.get("straps", {}) if isinstance(back_support.get("straps"), dict) else {},
        preset_back_straps,
        "thickness_mm",
        6.0,
    )

    height_above_seat_mm = _clamp_non_negative(
        diagnostics,
        _as_float(height_raw, frame_back_height_default),
        "back_support.height_above_seat_mm",
    )
    thickness_mm = _clamp_non_negative(
        diagnostics,
        _as_float(thickness_raw, frame_back_thickness_default),
        "back_support.thickness_mm",
    )
    offset_y_mm = _clamp_range(
        diagnostics,
        _as_float(offset_y_raw, 0.0),
        "back_support.offset_y_mm",
        -100.0,
        200.0,
    )
    margin_x_mm = _clamp_non_negative(
        diagnostics,
        _as_float(margin_x_raw, 40.0),
        "back_support.margin_x_mm",
    )
    margin_z_mm = _clamp_non_negative(
        diagnostics,
        _as_float(margin_z_raw, 30.0),
        "back_support.margin_z_mm",
    )
    rail_inset_mm = _clamp_non_negative(
        diagnostics,
        _as_float(rail_inset_raw, 0.0),
        "back_support.rail_inset_mm",
    )
    rail_width_mm = _clamp_non_negative(
        diagnostics,
        _as_float(rail_width_raw, frame_thickness_default),
        "back_support.rail_width_mm",
    )
    rail_depth_mm = _clamp_non_negative(
        diagnostics,
        _as_float(rail_depth_raw, frame_thickness_default),
        "back_support.rail_depth_mm",
    )
    rail_height_mm = _clamp_non_negative(
        diagnostics,
        _as_float(rail_height_raw, rail_width_mm),
        "back_support.rail_height_mm",
    )
    bottom_rail_gap_mm = _clamp_non_negative(
        diagnostics,
        _as_float(bottom_rail_gap_raw, 60.0),
        "back_support.bottom_rail_gap_mm",
    )
    bottom_rail_height_mm = _clamp_non_negative(
        diagnostics,
        _as_float(bottom_rail_height_mm, default_bottom_rail_height_mm),
        "back_support.bottom_rail_height_mm",
    )
    bottom_rail_split = _as_bool(bottom_rail_split_raw, False)
    split_center = _as_bool(split_center_raw, False)

    if frame_layout_source == "global" and frame_layout_raw is None:
        frame_layout = "split_2" if bottom_rail_split else "single"
    else:
        layout_normalized = (
            str(frame_layout_raw).strip().lower()
            if isinstance(frame_layout_raw, str)
            else ("split_2" if bottom_rail_split else "single")
        )
        frame_layout = _BACK_FRAME_LAYOUT_ALIASES.get(layout_normalized, "single")
        if layout_normalized not in _BACK_FRAME_LAYOUT_ALIASES:
            _warn(
                diagnostics,
                code="BACK_FALLBACK",
                message="unsupported back_support.frame_layout fallback to single",
                path="back_support.frame_layout",
                old=frame_layout_raw,
                new="single",
            )

    bottom_rail_attach_mode = _canonical_choice(
        diagnostics=diagnostics,
        path="back_support.bottom_rail_attach_mode",
        value_raw=bottom_rail_attach_raw,
        allowed=_BACK_ATTACH_MODES,
        fallback="seat_rear_beam",
    )

    slat_orientation = _canonical_choice(
        diagnostics=diagnostics,
        path="back_support.slats.orientation",
        value_raw=slat_orientation_raw,
        allowed=_BACK_SLAT_ORIENTATION_VALUES,
        fallback="vertical",
    )
    slat_layout = _canonical_choice(
        diagnostics=diagnostics,
        path="back_support.slats.layout",
        value_raw=slat_layout_raw,
        allowed=_BACK_SLAT_LAYOUT_VALUES,
        fallback="full",
    )

    slat_count = max(
        0,
        _as_int(slat_count_raw, 10),
    )
    if slat_count != _as_int(slat_count_raw, 10):
        _warn(
            diagnostics,
            code="BACK_CLAMP",
            message="back_support.slats.count clamped to >= 0",
            path="back_support.slats.count",
            old=slat_count_raw,
            new=slat_count,
        )
    slat_width_mm = _clamp_non_negative(
        diagnostics,
        _as_float(slat_width_raw, 35.0),
        "back_support.slats.width_mm",
    )
    slat_thickness_mm = _clamp_non_negative(
        diagnostics,
        _as_float(slat_thickness_raw, 10.0),
        "back_support.slats.thickness_mm",
    )
    slat_arc_height_mm = _clamp_non_negative(
        diagnostics,
        _as_float(slat_arc_height_raw, 0.0),
        "back_support.slats.arc_height_mm",
    )
    slat_gap_mm = _clamp_non_negative(
        diagnostics,
        _as_float(slat_gap_raw, 0.0),
        "back_support.slats.gap_mm",
    )
    slat_center_gap_mm = _clamp_non_negative(
        diagnostics,
        _as_float(slat_center_gap_raw, 0.0),
        "back_support.slats.center_gap_mm",
    )
    slat_has_gap_mm = slat_gap_source in {"ir", "preset"}
    slat_arc_sign = _as_float(slat_arc_sign_raw, -1.0)

    strap_count = max(0, _as_int(strap_count_raw, 6))
    if strap_count != _as_int(strap_count_raw, 6):
        _warn(
            diagnostics,
            code="BACK_CLAMP",
            message="back_support.straps.count clamped to >= 0",
            path="back_support.straps.count",
            old=strap_count_raw,
            new=strap_count,
        )
    strap_width_mm = _clamp_non_negative(
        diagnostics,
        _as_float(strap_width_raw, 30.0),
        "back_support.straps.width_mm",
    )
    strap_thickness_mm = _clamp_non_negative(
        diagnostics,
        _as_float(strap_thickness_raw, 6.0),
        "back_support.straps.thickness_mm",
    )

    split_center_requested = split_center
    if slat_layout == "split_center":
        split_center_requested = True
    if center_post_enabled:
        split_center_requested = True
    if split_center_requested:
        frame_layout = "split_2"

    return BackSpec(
        has_back_support=has_back_support,
        mode=back_mode,
        frame=BackFrameSpec(
            height_above_seat_mm=height_above_seat_mm,
            thickness_mm=thickness_mm,
            offset_y_mm=offset_y_mm,
            margin_x_mm=margin_x_mm,
            margin_z_mm=margin_z_mm,
            rail_inset_mm=rail_inset_mm,
            rail_width_mm=rail_width_mm,
            rail_depth_mm=rail_depth_mm,
            rail_height_mm=rail_height_mm,
            bottom_rail_split=bottom_rail_split,
            bottom_rail_gap_mm=bottom_rail_gap_mm,
            split_center=split_center_requested,
            frame_layout=frame_layout,
            bottom_rail_attach_mode=bottom_rail_attach_mode,
            bottom_rail_height_mm=bottom_rail_height_mm,
            center_post=CenterPostSpec(
                enabled=center_post_enabled,
                thickness_mm=center_post_thickness_mm,
                inset_y_mm=center_post_inset_y_mm,
                width_mm=center_post_width_mm,
            ),
        ),
        slats=BackSlatsSpec(
            orientation=slat_orientation,
            layout=slat_layout,
            count=slat_count,
            width_mm=slat_width_mm,
            thickness_mm=slat_thickness_mm,
            arc_height_mm=slat_arc_height_mm,
            arc_sign=slat_arc_sign,
            gap_mm=slat_gap_mm,
            has_gap_mm=slat_has_gap_mm,
            center_gap_mm=slat_center_gap_mm,
        ),
        straps=BackStrapsSpec(
            count=strap_count,
            width_mm=strap_width_mm,
            thickness_mm=strap_thickness_mm,
        ),
    )


def resolve(ir: dict, preset_id: str | None = None) -> tuple[ResolvedSpec, ResolveDiagnostics]:
    diagnostics = ResolveDiagnostics()

    style_raw = ir.get("style", "default") if isinstance(ir, dict) else "default"
    style = str(style_raw).strip().lower() if isinstance(style_raw, str) else "default"
    if not style:
        style = "default"

    effective_preset_id = (
        str(preset_id).strip()
        if isinstance(preset_id, str) and preset_id.strip()
        else default_preset_id(style)
    )
    preset = get_preset(style, effective_preset_id)
    preset_arms = preset.get("arms", {}) if isinstance(preset.get("arms"), dict) else {}

    arms = ir.get("arms", {}) if isinstance(ir.get("arms"), dict) else {}

    arms_type_raw = arms.get("type") if "type" in arms else preset_arms.get("type")
    if arms_type_raw is None:
        arms_type_raw = "none"
    arms_type = _canon_arms_type(arms_type_raw)

    width_raw = arms.get("width_mm", preset_arms.get("width_mm", 120.0))
    width_mm = _as_float(width_raw, 120.0)
    if width_mm < 0.0:
        _warn(
            diagnostics,
            code="ARMS_WIDTH_CLAMP",
            message="arms.width_mm clamped to 0.0",
            path="arms.width_mm",
            old=width_mm,
            new=0.0,
        )
        width_mm = 0.0

    profile_raw = arms.get("profile", preset_arms.get("profile", "box"))
    style_for_profile_raw = arms.get("style", preset_arms.get("style", "box"))
    profile, profile_fallback = _canonical_profile(profile_raw, style_for_profile_raw)
    if profile_fallback:
        _warn(
            diagnostics,
            code="PROFILE_FALLBACK_TO_BOX",
            message="unsupported arms.profile fallback to box",
            path="arms.profile",
            old=profile_raw,
            new="box",
        )

    back_spec = resolve_back_spec(ir=ir, preset=preset, diagnostics=diagnostics)

    resolved = ResolvedSpec(
        style=style,
        preset_id=effective_preset_id,
        arms=ArmsSpec(
            type=arms_type,
            width_mm=width_mm,
            profile=profile,
        ),
        back=back_spec,
        seat=None,
        legs=None,
    )
    return resolved, diagnostics
