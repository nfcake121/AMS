"""Scene metrics collection for Blender debug runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


GROUP_KEYS = ("slat_", "back_slat_", "arm_", "frame_", "leg_")


def _bbox_from_points(points: Iterable[tuple[float, float, float]]) -> dict[str, list[float]] | None:
    coords = list(points)
    if not coords:
        return None
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    zs = [p[2] for p in coords]
    return {
        "min": [float(min(xs)), float(min(ys)), float(min(zs))],
        "max": [float(max(xs)), float(max(ys)), float(max(zs))],
    }


def _bbox_union(bboxes: Iterable[dict[str, list[float]] | None]) -> dict[str, list[float]] | None:
    valid = [b for b in bboxes if b]
    if not valid:
        return None
    return {
        "min": [
            float(min(b["min"][0] for b in valid)),
            float(min(b["min"][1] for b in valid)),
            float(min(b["min"][2] for b in valid)),
        ],
        "max": [
            float(max(b["max"][0] for b in valid)),
            float(max(b["max"][1] for b in valid)),
            float(max(b["max"][2] for b in valid)),
        ],
    }


def _bbox_spans(bbox: dict[str, list[float]] | None) -> dict[str, float]:
    if not bbox:
        return {"x": 0.0, "y": 0.0, "z": 0.0}
    return {
        "x": float(max(0.0, bbox["max"][0] - bbox["min"][0])),
        "y": float(max(0.0, bbox["max"][1] - bbox["min"][1])),
        "z": float(max(0.0, bbox["max"][2] - bbox["min"][2])),
    }


def _bbox_center(bbox: dict[str, list[float]] | None) -> tuple[float, float, float] | None:
    if not bbox:
        return None
    min_corner = bbox.get("min")
    max_corner = bbox.get("max")
    if not isinstance(min_corner, list) or not isinstance(max_corner, list):
        return None
    if len(min_corner) < 3 or len(max_corner) < 3:
        return None
    try:
        min_x = float(min_corner[0])
        min_y = float(min_corner[1])
        min_z = float(min_corner[2])
        max_x = float(max_corner[0])
        max_y = float(max_corner[1])
        max_z = float(max_corner[2])
    except (TypeError, ValueError):
        return None
    return (
        float((min_x + max_x) * 0.5),
        float((min_y + max_y) * 0.5),
        float((min_z + max_z) * 0.5),
    )


def _bbox_overlap_depths(
    a: dict[str, list[float]] | None,
    b: dict[str, list[float]] | None,
) -> tuple[float, float, float]:
    if not a or not b:
        return 0.0, 0.0, 0.0
    a_min = a.get("min")
    a_max = a.get("max")
    b_min = b.get("min")
    b_max = b.get("max")
    if not isinstance(a_min, list) or not isinstance(a_max, list):
        return 0.0, 0.0, 0.0
    if not isinstance(b_min, list) or not isinstance(b_max, list):
        return 0.0, 0.0, 0.0
    if len(a_min) < 3 or len(a_max) < 3 or len(b_min) < 3 or len(b_max) < 3:
        return 0.0, 0.0, 0.0
    dx = min(float(a_max[0]), float(b_max[0])) - max(float(a_min[0]), float(b_min[0]))
    dy = min(float(a_max[1]), float(b_max[1])) - max(float(a_min[1]), float(b_min[1]))
    dz = min(float(a_max[2]), float(b_max[2])) - max(float(a_min[2]), float(b_min[2]))
    return float(dx), float(dy), float(dz)


def _bbox_mtv(
    left_bbox: dict[str, list[float]] | None,
    right_bbox: dict[str, list[float]] | None,
) -> dict[str, Any] | None:
    dx, dy, dz = _bbox_overlap_depths(left_bbox, right_bbox)
    if dx <= 0.0 or dy <= 0.0 or dz <= 0.0:
        return None

    overlaps = {"x": float(dx), "y": float(dy), "z": float(dz)}
    axis, depth_m = min(
        ((key, value) for key, value in overlaps.items() if value > 0.0),
        key=lambda item: float(item[1]),
    )
    axis_index = {"x": 0, "y": 1, "z": 2}[axis]

    left_center = _bbox_center(left_bbox)
    right_center = _bbox_center(right_bbox)
    if left_center is None or right_center is None:
        sign = 1
    else:
        sign = -1 if float(left_center[axis_index]) < float(right_center[axis_index]) else 1

    delta_m = [0.0, 0.0, 0.0]
    delta_m[axis_index] = float(sign) * float(depth_m)

    return {
        "axis": str(axis),
        "depth_m": float(depth_m),
        "sign": int(sign),
        "delta_m": [float(delta_m[0]), float(delta_m[1]), float(delta_m[2])],
    }


def _bbox_overlap(a: dict[str, list[float]] | None, b: dict[str, list[float]] | None) -> tuple[float, dict[str, list[float]] | None]:
    if not a or not b:
        return 0.0, None
    min_corner = [
        max(float(a["min"][0]), float(b["min"][0])),
        max(float(a["min"][1]), float(b["min"][1])),
        max(float(a["min"][2]), float(b["min"][2])),
    ]
    max_corner = [
        min(float(a["max"][0]), float(b["max"][0])),
        min(float(a["max"][1]), float(b["max"][1])),
        min(float(a["max"][2]), float(b["max"][2])),
    ]
    dx = max_corner[0] - min_corner[0]
    dy = max_corner[1] - min_corner[1]
    dz = max_corner[2] - min_corner[2]
    if dx <= 0.0 or dy <= 0.0 or dz <= 0.0:
        return 0.0, None
    return float(dx * dy * dz), {"min": min_corner, "max": max_corner}


def _group_match(name: str, group_key: str) -> bool:
    lower_name = name.lower()
    if group_key == "slat_":
        return lower_name.startswith("slat_")
    if group_key == "back_slat_":
        return lower_name.startswith("back_slat_")
    if group_key == "arm_":
        return (
            lower_name.startswith("arm_")
            or lower_name.startswith("left_arm")
            or lower_name.startswith("right_arm")
            or "_arm_" in lower_name
        )
    if group_key == "frame_":
        return (
            lower_name.startswith("frame_")
            or lower_name.startswith("beam_")
            or lower_name.startswith("rail_")
            or lower_name.startswith("back_rail_")
            or lower_name in {"seat_support", "back_frame", "back_panel"}
        )
    if group_key == "leg_":
        return lower_name.startswith("leg_")
    return False


def _object_base_bbox_world(obj: Any) -> dict[str, list[float]] | None:
    from mathutils import Vector  # type: ignore

    if obj.type == "MESH" and getattr(obj, "data", None) and len(obj.data.vertices) > 0:
        points = []
        for vertex in obj.data.vertices:
            world = obj.matrix_world @ vertex.co
            points.append((float(world.x), float(world.y), float(world.z)))
        return _bbox_from_points(points)

    if hasattr(obj, "bound_box") and obj.bound_box:
        points = []
        for corner in obj.bound_box:
            world = obj.matrix_world @ Vector(corner)
            points.append((float(world.x), float(world.y), float(world.z)))
        return _bbox_from_points(points)

    location = getattr(obj, "location", None)
    if location is None:
        return None
    return {
        "min": [float(location.x), float(location.y), float(location.z)],
        "max": [float(location.x), float(location.y), float(location.z)],
    }


def _mesh_bbox_world(mesh: Any, matrix_world: Any) -> dict[str, list[float]] | None:
    if not mesh or len(mesh.vertices) == 0:
        return None
    points = []
    for vertex in mesh.vertices:
        world = matrix_world @ vertex.co
        points.append((float(world.x), float(world.y), float(world.z)))
    return _bbox_from_points(points)


def _modifier_info(modifier: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": str(getattr(modifier, "name", "")),
        "type": str(getattr(modifier, "type", "")),
    }
    if payload["type"] == "SIMPLE_DEFORM":
        payload["deform_method"] = str(getattr(modifier, "deform_method", ""))
        payload["axis"] = str(getattr(modifier, "deform_axis", ""))
        try:
            payload["angle"] = float(getattr(modifier, "angle", 0.0))
        except (TypeError, ValueError):
            payload["angle"] = 0.0
        origin_obj = getattr(modifier, "origin", None)
        payload["origin"] = origin_obj.name if origin_obj is not None else None
    return payload


def _collect_object_metrics(obj: Any, depsgraph: Any) -> dict[str, Any]:
    base_bbox = _object_base_bbox_world(obj)
    eval_bbox = base_bbox
    vertices = 0
    polygons = 0

    if obj.type == "MESH":
        eval_obj = obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()
        try:
            vertices = int(len(eval_mesh.vertices))
            polygons = int(len(eval_mesh.polygons))
            eval_bbox = _mesh_bbox_world(eval_mesh, eval_obj.matrix_world) or base_bbox
        finally:
            eval_obj.to_mesh_clear()

    base_spans = _bbox_spans(base_bbox)
    eval_spans = _bbox_spans(eval_bbox)
    bbox_delta = {
        "x": float(eval_spans["x"] - base_spans["x"]),
        "y": float(eval_spans["y"] - base_spans["y"]),
        "z": float(eval_spans["z"] - base_spans["z"]),
    }

    return {
        "name": str(obj.name),
        "type": str(obj.type),
        "verts": vertices,
        "polys": polygons,
        "modifiers": [_modifier_info(mod) for mod in obj.modifiers],
        "bbox_world": eval_bbox,
        "bbox_world_base": base_bbox,
        "bbox_spans": eval_spans,
        "bbox_spans_base": base_spans,
        "bbox_delta": bbox_delta,
    }


def _collect_groups(objects: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for key in GROUP_KEYS:
        members = [obj for obj in objects if _group_match(str(obj.get("name", "")), key)]
        groups[key] = {
            "count": len(members),
            "objects": [str(obj.get("name", "")) for obj in members],
            "bbox_world": _bbox_union(obj.get("bbox_world") for obj in members),
        }
    return groups


def _collect_overlap_pairs(
    left_names: Iterable[str],
    right_names: Iterable[str],
    object_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    total = 0.0
    pair_index = 0
    for left_name in left_names:
        left_bbox = object_index.get(left_name, {}).get("bbox_world")
        if not left_bbox:
            continue
        for right_name in right_names:
            right_bbox = object_index.get(right_name, {}).get("bbox_world")
            if not right_bbox:
                continue
            volume, bbox = _bbox_overlap(left_bbox, right_bbox)
            if volume <= 0.0:
                continue
            total += volume
            mtv_bbox = _bbox_mtv(left_bbox, right_bbox)
            pairs.append(
                {
                    "pair_index": int(pair_index),
                    "pair_key": f"{left_name}|{right_name}",
                    "left": left_name,
                    "right": right_name,
                    "volume": float(volume),
                    "bbox_world": bbox,
                    "mtv_bbox": mtv_bbox,
                }
            )
            pair_index += 1
    return {"total_volume": float(total), "pairs": pairs}


def collect_scene_metrics() -> dict[str, Any]:
    """Collect object-level and group-level Blender scene metrics."""
    import bpy  # type: ignore

    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    try:
        depsgraph.update()
    except Exception:
        pass

    scene_objects = sorted(bpy.data.objects, key=lambda item: item.name.lower())
    objects = [_collect_object_metrics(obj, depsgraph) for obj in scene_objects]
    groups = _collect_groups(objects)
    object_index = {str(obj.get("name", "")): obj for obj in objects}

    overlaps = {
        "slats_vs_arms": _collect_overlap_pairs(
            groups["slat_"]["objects"],
            groups["arm_"]["objects"],
            object_index,
        ),
        "slats_vs_frame": _collect_overlap_pairs(
            groups["slat_"]["objects"],
            groups["frame_"]["objects"],
            object_index,
        ),
        "back_slats_vs_frame": _collect_overlap_pairs(
            groups["back_slat_"]["objects"],
            groups["frame_"]["objects"],
            object_index,
        ),
    }

    return {
        "version": "debug-metrics-v2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "units": {"length": "m", "volume": "m3"},
        "object_count": len(objects),
        "objects": objects,
        "groups": groups,
        "overlaps": overlaps,
    }
