"""Blender-only visualization helpers for debug overlap offenders."""

from __future__ import annotations

import os
from typing import Any


TARGET_GROUPS = ("frame_", "slat_", "back_slat_", "arm_", "leg_")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _valid_bbox(bbox: Any) -> bool:
    if not isinstance(bbox, dict):
        return False
    min_corner = bbox.get("min")
    max_corner = bbox.get("max")
    if not isinstance(min_corner, list) or not isinstance(max_corner, list):
        return False
    return len(min_corner) >= 3 and len(max_corner) >= 3


def _bbox_union(a: dict[str, list[float]] | None, b: dict[str, list[float]] | None) -> dict[str, list[float]] | None:
    if not a:
        return b
    if not b:
        return a
    return {
        "min": [
            min(_safe_float(a["min"][0]), _safe_float(b["min"][0])),
            min(_safe_float(a["min"][1]), _safe_float(b["min"][1])),
            min(_safe_float(a["min"][2]), _safe_float(b["min"][2])),
        ],
        "max": [
            max(_safe_float(a["max"][0]), _safe_float(b["max"][0])),
            max(_safe_float(a["max"][1]), _safe_float(b["max"][1])),
            max(_safe_float(a["max"][2]), _safe_float(b["max"][2])),
        ],
    }


def _scene_bbox_from_metrics(metrics: dict[str, Any] | None) -> dict[str, list[float]] | None:
    if not isinstance(metrics, dict):
        return None

    groups = metrics.get("groups", {})
    bbox: dict[str, list[float]] | None = None
    if isinstance(groups, dict):
        for group_key in TARGET_GROUPS:
            payload = groups.get(group_key, {})
            if not isinstance(payload, dict):
                continue
            group_bbox = payload.get("bbox_world")
            if _valid_bbox(group_bbox):
                bbox = _bbox_union(bbox, group_bbox)

    if bbox:
        return bbox

    objects = metrics.get("objects", [])
    if not isinstance(objects, list):
        return None
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        if str(obj.get("type", "")).upper() != "MESH":
            continue
        obj_bbox = obj.get("bbox_world")
        if _valid_bbox(obj_bbox):
            bbox = _bbox_union(bbox, obj_bbox)
    return bbox


def _material(name: str, rgba: tuple[float, float, float, float]) -> Any:
    import bpy  # type: ignore

    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)

    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
        node_tree = getattr(mat, "node_tree", None)
        if node_tree and node_tree.nodes:
            principled = node_tree.nodes.get("Principled BSDF")
            if principled is not None:
                principled.inputs[0].default_value = rgba
                principled.inputs[7].default_value = 0.35

    if hasattr(mat, "diffuse_color"):
        mat.diffuse_color = rgba
    return mat


def _details(problem: dict[str, Any]) -> dict[str, Any]:
    details = problem.get("details", {})
    if isinstance(details, dict):
        return details
    return {}


def _add_name(target: set[str], value: Any) -> None:
    name = str(value).strip()
    if name:
        target.add(name)


def _names_from_pairs_top(details: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    pairs_top = details.get("pairs_top", [])
    if not isinstance(pairs_top, list):
        return names
    for pair in pairs_top:
        if not isinstance(pair, dict):
            continue
        _add_name(names, pair.get("left", ""))
        _add_name(names, pair.get("right", ""))
    return names


def _names_from_top5(details: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    top5 = details.get("top5", [])
    if not isinstance(top5, list):
        return names
    for item in top5:
        if not isinstance(item, dict):
            continue
        _add_name(names, item.get("name", ""))
    return names


def _names_from_missing_details(details: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    missing_by_object = details.get("missing_by_object", [])
    if isinstance(missing_by_object, list):
        for item in missing_by_object:
            if not isinstance(item, dict):
                continue
            _add_name(names, item.get("name", ""))
    elif isinstance(missing_by_object, dict):
        for key in missing_by_object.keys():
            _add_name(names, key)
    return names


def _names_from_no_effect_details(details: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    _add_name(names, details.get("name", ""))

    by_object = details.get("by_object")
    if isinstance(by_object, list):
        for item in by_object:
            if not isinstance(item, dict):
                continue
            _add_name(names, item.get("name", ""))
    elif isinstance(by_object, dict):
        for key in by_object.keys():
            _add_name(names, key)

    offenders = details.get("offenders")
    if isinstance(offenders, list):
        for item in offenders:
            if isinstance(item, dict):
                _add_name(names, item.get("name", ""))
            else:
                _add_name(names, item)

    top = details.get("top")
    if isinstance(top, list):
        for item in top:
            if isinstance(item, dict):
                _add_name(names, item.get("name", ""))
            else:
                _add_name(names, item)

    top5 = details.get("top5")
    if isinstance(top5, list):
        for item in top5:
            if isinstance(item, dict):
                _add_name(names, item.get("name", ""))
            else:
                _add_name(names, item)
    return names


def _collect_offenders_by_priority(validation: dict[str, Any]) -> tuple[set[str], set[str], set[str], set[str]]:
    red: set[str] = set()
    blue: set[str] = set()
    orange: set[str] = set()
    offender_codes: set[str] = set()

    problems = validation.get("problems", [])
    if not isinstance(problems, list):
        return red, blue, orange, offender_codes

    for problem in problems:
        if not isinstance(problem, dict):
            continue
        code = str(problem.get("code", "")).strip().upper()
        details = _details(problem)

        names: set[str] = set()
        if code.startswith("OVERLAP_"):
            names = _names_from_pairs_top(details)
            red.update(names)
        elif code in {"SLATS_NOT_BENT", "BACK_SLATS_NOT_BENT"}:
            names = _names_from_top5(details)
            blue.update(names)
        elif code in {"MOD_EXPECTATION_MISSING", "MOD_EXPECTATION_NO_EFFECT"}:
            if code == "MOD_EXPECTATION_MISSING":
                names = _names_from_missing_details(details)
            else:
                names = _names_from_no_effect_details(details)
            orange.update(names)

        if names:
            offender_codes.add(code)

    return red, blue, orange, offender_codes


def _look_at_rotation(camera_obj: Any, target_xyz: tuple[float, float, float]) -> None:
    from mathutils import Vector  # type: ignore

    target_vec = Vector((target_xyz[0], target_xyz[1], target_xyz[2]))
    direction = target_vec - camera_obj.location
    if direction.length <= 1e-9:
        return
    camera_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _ensure_camera_and_light(
    scene_bbox: dict[str, list[float]] | None,
    lens_mm: float = 50.0,
) -> tuple[Any, Any]:
    import bpy  # type: ignore

    center_x = 0.0
    center_y = 0.0
    center_z = 0.0
    extent_x = 2.0
    extent_y = 2.0
    extent_z = 1.5
    if scene_bbox:
        min_corner = scene_bbox["min"]
        max_corner = scene_bbox["max"]
        center_x = 0.5 * (_safe_float(min_corner[0]) + _safe_float(max_corner[0]))
        center_y = 0.5 * (_safe_float(min_corner[1]) + _safe_float(max_corner[1]))
        center_z = 0.5 * (_safe_float(min_corner[2]) + _safe_float(max_corner[2]))
        extent_x = max(0.1, _safe_float(max_corner[0]) - _safe_float(min_corner[0]))
        extent_y = max(0.1, _safe_float(max_corner[1]) - _safe_float(min_corner[1]))
        extent_z = max(0.1, _safe_float(max_corner[2]) - _safe_float(min_corner[2]))

    extent = max(extent_x, extent_y, extent_z)
    cam_distance = max(2.5, extent * 2.4)

    camera_obj = bpy.data.objects.get("DEBUG_CAMERA")
    if camera_obj is None:
        camera_data = bpy.data.cameras.new(name="DEBUG_CAMERA")
        camera_obj = bpy.data.objects.new("DEBUG_CAMERA", camera_data)
        bpy.context.scene.collection.objects.link(camera_obj)
    if getattr(camera_obj, "data", None) is not None:
        camera_obj.data.lens = float(lens_mm)
        camera_obj.data.clip_end = max(200.0, cam_distance * 20.0)

    camera_obj.location.x = center_x + cam_distance
    camera_obj.location.y = center_y - cam_distance
    camera_obj.location.z = center_z + cam_distance * 0.75
    _look_at_rotation(camera_obj, (center_x, center_y, center_z))
    bpy.context.scene.camera = camera_obj

    light_obj = bpy.data.objects.get("DEBUG_LIGHT")
    if light_obj is None:
        light_data = bpy.data.lights.new(name="DEBUG_LIGHT", type="SUN")
        light_obj = bpy.data.objects.new(name="DEBUG_LIGHT", object_data=light_data)
        bpy.context.scene.collection.objects.link(light_obj)
    if getattr(light_obj, "data", None) is not None:
        light_obj.data.energy = 3.0

    light_obj.location.x = center_x + cam_distance * 0.4
    light_obj.location.y = center_y - cam_distance * 0.2
    light_obj.location.z = center_z + cam_distance * 1.2
    _look_at_rotation(light_obj, (center_x, center_y, center_z))
    return camera_obj, light_obj


def apply_debug_visualization(
    validation: dict[str, Any],
    metrics: dict[str, Any] | None = None,
    snapshot_blend_path: str | None = None,
    snapshot_png_path: str | None = None,
    camera_lens_mm: float = 50.0,
) -> dict[str, Any]:
    """Highlight offenders and optionally save .blend and PNG snapshots."""
    try:
        import bpy  # type: ignore
    except Exception:
        return {
            "offender_count": 0,
            "painted_red": 0,
            "painted_gray": 0,
            "snapshot_blend_path": "",
            "snapshot_png_path": "",
            "error": "bpy unavailable",
        }

    red_offenders, blue_offenders, orange_offenders, offender_codes = _collect_offenders_by_priority(validation)
    all_offenders = set(red_offenders) | set(blue_offenders) | set(orange_offenders)

    offender_mat = _material("MAT_DEBUG_OFFENDER", (0.92, 0.16, 0.16, 1.0))
    bent_mat = _material("MAT_DEBUG_BENT", (0.18, 0.42, 0.95, 1.0))
    orange_mat = _material("MAT_DEBUG_ORANGE", (0.95, 0.52, 0.14, 1.0))
    other_mat = _material("MAT_DEBUG_OTHER", (0.58, 0.58, 0.58, 1.0))

    painted_red = 0
    painted_blue = 0
    painted_orange = 0
    painted_gray = 0
    for obj in bpy.data.objects:
        if str(getattr(obj, "type", "")) != "MESH":
            continue
        mesh = getattr(obj, "data", None)
        if mesh is None or not hasattr(mesh, "materials"):
            continue

        if obj.name in red_offenders:
            target_material = offender_mat
            painted_red += 1
        elif obj.name in blue_offenders:
            target_material = bent_mat
            painted_blue += 1
        elif obj.name in orange_offenders:
            target_material = orange_mat
            painted_orange += 1
        else:
            target_material = other_mat
            painted_gray += 1

        if len(mesh.materials) == 0:
            mesh.materials.append(target_material)
        else:
            mesh.materials[0] = target_material

    scene_bbox = _scene_bbox_from_metrics(metrics)
    _ensure_camera_and_light(scene_bbox, lens_mm=camera_lens_mm)

    saved_blend_path = ""
    if snapshot_blend_path:
        blend_path = os.path.abspath(str(snapshot_blend_path).strip())
        if blend_path:
            parent_dir = os.path.dirname(blend_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=blend_path)
            saved_blend_path = blend_path

    saved_png_path = ""
    if snapshot_png_path:
        png_path = os.path.abspath(str(snapshot_png_path).strip())
        if png_path:
            parent_dir = os.path.dirname(png_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            scene = bpy.context.scene
            scene.render.image_settings.file_format = "PNG"
            scene.render.filepath = png_path
            bpy.ops.render.render(write_still=True)
            saved_png_path = png_path

    codes_csv = ",".join(sorted(offender_codes))
    print(f"DEBUG_OFFENDERS_COUNT:{len(all_offenders)}")
    print(f"DEBUG_OFFENDER_CODES:{codes_csv}")

    return {
        "offender_count": len(all_offenders),
        "overlap_offender_count": len(red_offenders),
        "bent_offender_count": len(blue_offenders),
        "mod_offender_count": len(orange_offenders),
        "offender_codes": sorted(offender_codes),
        "painted_red": painted_red,
        "painted_blue": painted_blue,
        "painted_orange": painted_orange,
        "painted_gray": painted_gray,
        "snapshot_blend_path": saved_blend_path,
        "snapshot_png_path": saved_png_path,
    }
