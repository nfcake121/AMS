"""Run builder_v01 inside Blender.

Usage (called by export_blender.py):
blender --background --python tools/blender/run_builder_v01.py -- path/to/sofa_ir.json

This version FIXES slat bending by doing vertex-level bending (bmesh),
instead of relying on SimpleDeform (which can appear "flat" in some pipeline cases).

Env vars:
- IR_PATH: override IR path
- BLEND_PATH: if set, saves .blend to that path
- DEBUG_SLAT=1: adds an extra DEBUG_SLAT
- APPLY_DEBUG_SLAT=1: bakes modifiers for DEBUG_SLAT
- APPLY_ALL_SLATS=1: bakes modifiers for ALL slats (optional)
- DEBUG_JSON=1: writes debug JSON metrics/validation log
"""

import json
import math
import os
import sys
from typing import Optional, Tuple

# --- ensure repo root in sys.path so "src.*" imports work ---
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.builders.blender import builder_v01 as builder_module  # noqa: E402
from src.builders.blender.builder_v01 import build_plan_from_ir  # noqa: E402


# -------------------------
# small helpers
# -------------------------

def _read_ir_path() -> str:
    """Resolve IR path from env or argv (after '--')."""
    if os.environ.get("IR_PATH"):
        return os.environ["IR_PATH"]

    if "--" in sys.argv:
        i = sys.argv.index("--")
        if len(sys.argv) > i + 1:
            return sys.argv[i + 1]

    # fallback: last arg
    if len(sys.argv) > 1:
        return sys.argv[-1]

    return ""


def _clear_scene() -> None:
    """Start from an empty scene."""
    import bpy  # type: ignore
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _ensure_mm_units() -> None:
    """Configure the scene for millimeter units.

    Blender units: meters. So 1 mm = 0.001 m.
    """
    import bpy  # type: ignore
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def _mm_to_m(v):
    return tuple(float(x) / 1000.0 for x in v)


def _apply_rotation_deg(obj, rotation_deg) -> None:
    if not rotation_deg:
        return
    try:
        rx, ry, rz = rotation_deg
    except (TypeError, ValueError):
        return
    if rx == 0 and ry == 0 and rz == 0:
        return
    obj.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))


def _bake_object_modifiers(obj) -> None:
    """Bake evaluated mesh into obj.data and clear modifiers."""
    import bpy  # type: ignore

    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    try:
        depsgraph.update()
    except Exception:
        pass

    eval_obj = obj.evaluated_get(depsgraph)
    new_mesh = bpy.data.meshes.new_from_object(
        eval_obj,
        depsgraph=depsgraph,
        preserve_all_data_layers=True,
    )
    obj.data = new_mesh
    obj.modifiers.clear()


# -------------------------
# primitives
# -------------------------

def _create_cube(name, dimensions_mm, location_mm):
    import bpy  # type: ignore
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=_mm_to_m(location_mm))
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = _mm_to_m(dimensions_mm)
    bpy.context.view_layer.update()
    return obj


def _create_cylinder(name, radius_mm, height_mm, location_mm):
    import bpy  # type: ignore
    bpy.ops.mesh.primitive_cylinder_add(
        radius=float(radius_mm) / 1000.0,
        depth=float(height_mm) / 1000.0,
        location=_mm_to_m(location_mm),
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_cone(name, r_top_mm, r_bottom_mm, height_mm, location_mm):
    import bpy  # type: ignore
    bpy.ops.mesh.primitive_cone_add(
        radius1=float(r_bottom_mm) / 1000.0,
        radius2=float(r_top_mm) / 1000.0,
        depth=float(height_mm) / 1000.0,
        location=_mm_to_m(location_mm),
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_anchor(name, location_mm):
    import bpy  # type: ignore
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.location = _mm_to_m(location_mm)
    bpy.context.scene.collection.objects.link(empty)
    return empty


# -------------------------
# slats: mesh + vertex bend
# -------------------------

def _create_slat_mesh(
    name: str,
    width_mm: float,
    length_mm: float,
    location_mm,
    rotation_deg,
    segments_len: int,
    segments_w: int,
    orientation: str,
):
    """Creates a grid plane:
    - horizontal: plane in XY (length along +Y), normal ~ +Z
    - vertical:   plane in XZ (length along +Z), normal ~ +Y (or -Y)
    """
    import bpy  # type: ignore
    import bmesh  # type: ignore

    segments_len = max(1, int(segments_len))
    segments_w = max(1, int(segments_w))

    width_m = float(width_mm) / 1000.0
    length_m = float(length_mm) / 1000.0

    bm = bmesh.new()

    # Start with unit grid in XY centered at origin
    bmesh.ops.create_grid(bm, x_segments=segments_w, y_segments=segments_len, size=1.0)

    # Normalize to target width/length in local space
    if bm.verts:
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        ext_x = max_x - min_x
        ext_y = max_y - min_y
        sx = (width_m / ext_x) if ext_x != 0.0 else 1.0
        sy = (length_m / ext_y) if ext_y != 0.0 else 1.0

        for v in bm.verts:
            v.co.x = (v.co.x - cx) * sx
            v.co.y = (v.co.y - cy) * sy
            v.co.z = 0.0

    # If vertical: rotate XY plane into XZ (so length becomes Z)
    if orientation == "vertical":
        from mathutils import Matrix  # type: ignore
        rot_m = Matrix.Rotation(math.radians(90.0), 4, "X")  # Y -> Z
        for v in bm.verts:
            v.co = rot_m @ v.co

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    for poly in mesh.polygons:
        poly.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    obj.location = _mm_to_m(location_mm)
    _apply_rotation_deg(obj, rotation_deg)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()
    return obj


def _bend_vertices_arc(
    obj,
    orientation: str,
    length_mm: float,
    arc_height_mm: float,
    arc_sign: float,
) -> Tuple[float, float]:
    """Bend vertices into a circular arc (sagitta).
    Returns (radius_m, angle_rad).
    - horizontal: length along local Y, sag applied to local Z
    - vertical:   length along local Z, sag applied to local Y  (back curvature)
    """
    import bmesh  # type: ignore

    if arc_height_mm <= 0.0 or length_mm <= 0.0:
        return (0.0, 0.0)

    L = float(length_mm) / 1000.0
    h = float(arc_height_mm) / 1000.0
    sign = -1.0 if arc_sign < 0 else 1.0

    # radius from sagitta
    # R = L^2/(8h) + h/2
    R = (L * L) / (8.0 * h) + (h / 2.0)
    if not math.isfinite(R) or R <= 0:
        return (0.0, 0.0)

    angle = L / R
    angle = max(-math.pi, min(math.pi, angle))

    half = L / 2.0

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    for v in bm.verts:
        if orientation == "vertical":
            t = v.co.z  # along length
        else:
            t = v.co.y

        t = max(-half, min(half, t))

        # sag = R - sqrt(R^2 - t^2)
        under = max(0.0, (R * R - t * t))
        sag = R - math.sqrt(under)

        if orientation == "vertical":
            v.co.y += sag * sign
        else:
            v.co.z += sag * sign

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

    return (R, angle)


def _axis_ranges_world(mesh, matrix_world):
    if not mesh or len(mesh.vertices) == 0:
        return None
    xs, ys, zs = [], [], []
    for v in mesh.vertices:
        w = matrix_world @ v.co
        xs.append(w.x)
        ys.append(w.y)
        zs.append(w.z)
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


# -------------------------
# plan primitive creator
# -------------------------

def _create_primitive(p, legs_params=None):
    """Create geometry for a Primitive from builder_v01 plan."""
    import bpy  # type: ignore

    shape = getattr(p, "shape", "cube")
    dims = getattr(p, "dimensions_mm", (100, 100, 100))
    loc = getattr(p, "location_mm", (0, 0, 0))
    rot = getattr(p, "rotation_deg", (0.0, 0.0, 0.0))

    if shape in {"cube", "beam", "board"}:
        obj = _create_cube(p.name, dims, loc)
        _apply_rotation_deg(obj, rot)
        return obj

    if shape == "slat":
        # defaults
        arc_height_mm = 0.0
        arc_sign = -1.0
        orientation = "horizontal"
        subdiv_cuts = 64
        edge_radius_mm = 1.0
        solidify_offset = 1.0

        params = getattr(p, "params", None)
        if isinstance(params, dict):
            try:
                arc_height_mm = float(params.get("arc_height_mm", 0.0))
            except (TypeError, ValueError):
                arc_height_mm = 0.0
            try:
                arc_sign = float(params.get("arc_sign", -1.0))
            except (TypeError, ValueError):
                arc_sign = -1.0
            try:
                orientation = str(params.get("orientation", "horizontal")).strip().lower()
            except (TypeError, ValueError):
                orientation = "horizontal"
            try:
                subdiv_cuts = int(params.get("subdiv_cuts", 64))
            except (TypeError, ValueError):
                subdiv_cuts = 64
            try:
                edge_radius_mm = float(params.get("edge_radius_mm", 1.0))
            except (TypeError, ValueError):
                edge_radius_mm = 1.0
            try:
                solidify_offset = float(params.get("solidify_offset", 1.0))
            except (TypeError, ValueError):
                solidify_offset = 1.0

        if orientation in {"seat"}:
            orientation = "horizontal"
        if orientation not in {"horizontal", "vertical"}:
            orientation = "horizontal"

        arc_sign = -1.0 if arc_sign < 0 else 1.0
        solidify_offset = max(-1.0, min(1.0, solidify_offset))

        # dims mapping
        if orientation == "vertical":
            # width X, thickness Y, length Z  (like your older logic)
            width_mm = float(dims[0])
            thickness_mm = float(dims[1])
            length_mm = float(dims[2])
        else:
            # width X, length Y, thickness Z
            width_mm = float(dims[0])
            length_mm = float(dims[1])
            thickness_mm = float(dims[2])

        # mesh density: must be high along length for nice arc
        subdiv_cuts = max(8, min(200, int(subdiv_cuts)))
        segments_len = max(40, min(240, subdiv_cuts * 2))
        segments_w = 4

        obj = _create_slat_mesh(
            name=p.name,
            width_mm=width_mm,
            length_mm=length_mm,
            location_mm=loc,
            rotation_deg=rot,
            segments_len=segments_len,
            segments_w=segments_w,
            orientation=orientation,
        )

        # do vertex bending (the fix)
        radius_m, angle_rad = (0.0, 0.0)
        if arc_height_mm > 0.0 and length_mm > 0.0:
            radius_m, angle_rad = _bend_vertices_arc(
                obj=obj,
                orientation=orientation,
                length_mm=length_mm,
                arc_height_mm=arc_height_mm,
                arc_sign=arc_sign,
            )

        # solidify thickness (works from normals of the plane)
        if thickness_mm > 0.0:
            solid = obj.modifiers.new(name="Solidify", type="SOLIDIFY")
            solid.thickness = float(thickness_mm) / 1000.0
            solid.offset = solidify_offset
            solid.use_even_offset = True

        # bevel edges
        if edge_radius_mm > 0.0:
            bevel = obj.modifiers.new(name="Bevel", type="BEVEL")
            bevel.width = float(edge_radius_mm) / 1000.0
            bevel.segments = 2
            bevel.limit_method = "ANGLE"
            bevel.angle_limit = math.radians(40.0)
            if hasattr(bevel, "harden_normals"):
                bevel.harden_normals = True

        # normals
        wn = obj.modifiers.new(name="WeightedNormal", type="WEIGHTED_NORMAL")
        wn.keep_sharp = True
        wn.weight = 50
        if hasattr(obj.data, "use_auto_smooth"):
            obj.data.use_auto_smooth = True
        if hasattr(obj.data, "auto_smooth_angle"):
            obj.data.auto_smooth_angle = math.radians(40.0)

        # optional baking
        if os.environ.get("APPLY_ALL_SLATS") == "1":
            _bake_object_modifiers(obj)

        # debug ranges (base/eval)
        if obj.name in {"DEBUG_SLAT", "slat_1"} or os.environ.get("DEBUG_SLAT") == "1":
            bpy.context.view_layer.update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            eval_mesh = eval_obj.to_mesh()

            base_ranges = _axis_ranges_world(obj.data, obj.matrix_world)
            eval_ranges = _axis_ranges_world(eval_mesh, eval_obj.matrix_world)

            print(
                f"[slat] name={obj.name} orientation={orientation} arc_height_mm={arc_height_mm} "
                f"radius_m={radius_m:.6f} angle_rad={angle_rad:.6f} "
                f"verts={len(obj.data.vertices)} mods={[m.type for m in obj.modifiers]}"
            )
            if base_ranges and eval_ranges:
                base_spans = (
                    base_ranges[0][1] - base_ranges[0][0],
                    base_ranges[1][1] - base_ranges[1][0],
                    base_ranges[2][1] - base_ranges[2][0],
                )
                eval_spans = (
                    eval_ranges[0][1] - eval_ranges[0][0],
                    eval_ranges[1][1] - eval_ranges[1][0],
                    eval_ranges[2][1] - eval_ranges[2][0],
                )
                dx = abs(eval_spans[0] - base_spans[0])
                dy = abs(eval_spans[1] - base_spans[1])
                dz = abs(eval_spans[2] - base_spans[2])
                print(
                    f"SLAT_RANGES_BASE x=({base_ranges[0][0]:.6f},{base_ranges[0][1]:.6f}) "
                    f"y=({base_ranges[1][0]:.6f},{base_ranges[1][1]:.6f}) "
                    f"z=({base_ranges[2][0]:.6f},{base_ranges[2][1]:.6f})"
                )
                print(
                    f"SLAT_RANGES_EVAL x=({eval_ranges[0][0]:.6f},{eval_ranges[0][1]:.6f}) "
                    f"y=({eval_ranges[1][0]:.6f},{eval_ranges[1][1]:.6f}) "
                    f"z=({eval_ranges[2][0]:.6f},{eval_ranges[2][1]:.6f})"
                )
                print(f"SLAT_RANGE_DELTAS dx={dx:.6f} dy={dy:.6f} dz={dz:.6f}")

            eval_obj.to_mesh_clear()

        return obj

    if shape == "cylindrical":
        obj = _create_cylinder(p.name, radius_mm=float(dims[0]) / 2.0, height_mm=float(dims[2]), location_mm=loc)
        _apply_rotation_deg(obj, rot)
        return obj

    if shape == "tapered_cone":
        r_top = None
        r_bottom = None
        if isinstance(legs_params, dict):
            try:
                if legs_params.get("r_top") is not None:
                    r_top = float(legs_params["r_top"])
                if legs_params.get("r_bottom") is not None:
                    r_bottom = float(legs_params["r_bottom"])
            except (TypeError, ValueError):
                r_top = None
                r_bottom = None
        if r_top is None or r_bottom is None:
            r_top = max(6.0, float(dims[0]) * 0.35)
            r_bottom = max(r_top + 2.0, float(dims[0]) * 0.6)
        obj = _create_cone(p.name, r_top_mm=r_top, r_bottom_mm=r_bottom, height_mm=float(dims[2]), location_mm=loc)
        _apply_rotation_deg(obj, rot)
        return obj

    # fallback -> cube
    obj = _create_cube(p.name, dims, loc)
    _apply_rotation_deg(obj, rot)
    return obj


# -------------------------
# main
# -------------------------

def main():
    import bpy  # type: ignore

    ir_path = _read_ir_path()
    if not ir_path:
        raise SystemExit("IR path is required. Pass it after '--' or set IR_PATH env var.")

    print(f"RUN_BUILDER_V01:{__file__}")
    print(f"REPO_ROOT:{REPO_ROOT}")
    print(f"BUILDER_MODULE:{builder_module.__file__}")

    _clear_scene()
    _ensure_mm_units()

    blend_path = os.environ.get("BLEND_PATH", "")
    print(f"IR_PATH:{ir_path}")
    print(f"BLEND_PATH:{blend_path}")

    with open(ir_path, "r", encoding="utf-8") as f:
        ir = json.load(f)

    plan = build_plan_from_ir(ir)
    legs = ir.get("legs", {}) if isinstance(ir.get("legs"), dict) else {}
    legs_params = legs.get("params", {}) if isinstance(legs.get("params"), dict) else None

    # build primitives
    for prim in plan.primitives:
        _create_primitive(prim, legs_params=legs_params)

    # optional debug slat
    if os.environ.get("DEBUG_SLAT") == "1":
        try:
            debug_slat = _create_primitive(
                builder_module.Primitive(
                    name="DEBUG_SLAT",
                    shape="slat",
                    dimensions_mm=(60.0, 600.0, 12.0),  # width, length, thickness (horizontal)
                    location_mm=(0.0, 900.0, 300.0),
                    rotation_deg=(0.0, 0.0, 0.0),
                    params={
                        "arc_height_mm": 35.0,
                        "arc_sign": -1.0,
                        "orientation": "horizontal",
                        "subdiv_cuts": 64,
                        "edge_radius_mm": 1.0,
                        "solidify_offset": 1.0,
                    },
                ),
                legs_params=legs_params,
            )
            print(f"DEBUG_SLAT_CREATED:{debug_slat.name} verts={len(debug_slat.data.vertices)}")
            if os.environ.get("APPLY_DEBUG_SLAT") == "1":
                _bake_object_modifiers(debug_slat)
                print("DEBUG_SLAT_BAKED:1")
        except Exception as exc:
            print(f"DEBUG_SLAT_CREATED:error={exc}")

    # anchors as empties
    for a in plan.anchors:
        _create_anchor(a.name, a.location_mm)

    object_names = sorted(obj.name for obj in bpy.data.objects)
    print(f"OBJECTS_TOTAL:{len(object_names)} FIRST:{object_names[:10]}")
    slat_count = sum(1 for name in object_names if name.startswith("slat_"))
    beam_count = sum(1 for name in object_names if name.startswith("beam_"))
    rail_count = sum(1 for name in object_names if name.startswith("rail_"))
    print(f"OBJECT_PREFIX_COUNTS slat_={slat_count} beam_={beam_count} rail_={rail_count}")

    if os.environ.get("DEBUG_JSON") == "1":
        try:
            from tools.blender.debug.io import ir_sha256, make_run_id, save_run_log  # noqa: E402
            from tools.blender.debug.metrics import collect_scene_metrics  # noqa: E402
            from tools.blender.debug.validators import validate  # noqa: E402

            debug_run_id = make_run_id()
            metrics = collect_scene_metrics()
            validation = validate(metrics, ir)
            debug_payload = {
                "run_id": debug_run_id,
                "source": "run_builder_v01",
                "ir_path": os.path.abspath(ir_path),
                "ir_sha256": ir_sha256(ir),
                "build": {
                    "primitives": len(plan.primitives),
                    "anchors": len(plan.anchors),
                },
                "metrics": metrics,
                "validation": validation,
            }
            debug_log_path = save_run_log(
                debug_payload,
                out_dir=os.path.join(REPO_ROOT, "out", "logs", "runs"),
                run_id=debug_run_id,
            )
            print(f"DEBUG_JSON_LOG:{debug_log_path}")
        except Exception as exc:
            print(f"DEBUG_JSON_ERROR:{exc}")

    # optionally save .blend
    if blend_path:
        os.makedirs(os.path.dirname(blend_path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    return {"status": "built", "primitives": len(plan.primitives), "anchors": len(plan.anchors)}


if __name__ == "__main__":
    main()
