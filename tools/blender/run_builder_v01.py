"""Run builder_v01 inside Blender.

Usage (called by export_blender.py):
blender --background --python tools/blender/run_builder_v01.py -- path/to/sofa_ir.json
"""

import json
import math
import os
import sys

# --- ensure repo root in sys.path so "src.*" imports work ---
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.builders.blender import builder_v01 as builder_module  # noqa: E402
from src.builders.blender.builder_v01 import build_plan_from_ir  # noqa: E402


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
    import bpy  # type: ignore  # Blender-only

    bpy.ops.wm.read_factory_settings(use_empty=True)


def _ensure_mm_units() -> None:
    """Configure the scene for millimeter units.

    Blender units: meters. So 1 mm = 0.001 m.
    """
    import bpy  # type: ignore  # Blender-only

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def _mm_to_m(v):
    """Convert tuple(mm) -> tuple(m)."""
    return tuple(x / 1000.0 for x in v)


def _create_cube(name, dimensions_mm, location_mm):
    import bpy  # type: ignore  # Blender-only

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=_mm_to_m(location_mm))
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = _mm_to_m(dimensions_mm)
    bpy.context.view_layer.update()
    return obj


def _create_cylinder(name, radius_mm, height_mm, location_mm):
    import bpy  # type: ignore  # Blender-only

    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius_mm / 1000.0,
        depth=height_mm / 1000.0,
        location=_mm_to_m(location_mm),
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_cone(name, r_top_mm, r_bottom_mm, height_mm, location_mm):
    import bpy  # type: ignore  # Blender-only

    bpy.ops.mesh.primitive_cone_add(
        radius1=r_bottom_mm / 1000.0,
        radius2=r_top_mm / 1000.0,
        depth=height_mm / 1000.0,
        location=_mm_to_m(location_mm),
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_anchor(name, location_mm):
    import bpy  # type: ignore  # Blender-only

    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.location = _mm_to_m(location_mm)
    bpy.context.scene.collection.objects.link(empty)
    return empty


def _apply_rotation_deg(obj, rotation_deg):
    import math

    if not rotation_deg:
        return
    try:
        rx, ry, rz = rotation_deg
    except (TypeError, ValueError):
        return
    if rx == 0 and ry == 0 and rz == 0:
        return
    obj.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))


def _create_slat_object(
    name,
    width_mm,
    length_mm,
    thickness_mm,
    location_mm,
    rotation_deg,
    segments_len,
    segments_w=2,
):
    import bpy  # type: ignore  # Blender-only
    import bmesh  # type: ignore  # Blender-only

    try:
        segments_len = int(segments_len)
    except (TypeError, ValueError):
        segments_len = 12
    try:
        segments_w = int(segments_w)
    except (TypeError, ValueError):
        segments_w = 2
    segments_len = max(1, segments_len)
    segments_w = max(1, segments_w)

    width_m = float(width_mm) / 1000.0
    length_m = float(length_mm) / 1000.0
    _ = thickness_mm  # thickness is handled by Solidify modifier later

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=segments_w, y_segments=segments_len, size=1.0)

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


def _create_primitive(p, legs_params=None):
    """Create geometry for a Primitive from builder_v01 plan."""
    shape = getattr(p, "shape", "cube")
    dims = getattr(p, "dimensions_mm", (100, 100, 100))
    loc = getattr(p, "location_mm", (0, 0, 0))
    rot = getattr(p, "rotation_deg", (0.0, 0.0, 0.0))

    # v0.1: cube/beam/board share the same box geometry.
    if shape in {"cube", "beam", "board"}:
        obj = _create_cube(p.name, dims, loc)
        _apply_rotation_deg(obj, rot)
        return obj

    if shape == "slat":
        import bpy  # type: ignore  # Blender-only

        arc_height_mm = 0.0
        arc_sign = -1.0
        orientation = "horizontal"
        subdiv_level = None
        subdiv_cuts = 48
        edge_radius_mm = 1.0
        solidify_mm = 0.0
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
                subdiv_level = int(params.get("subdiv_level"))
            except (TypeError, ValueError):
                subdiv_level = None
            try:
                subdiv_cuts = int(params.get("subdiv_cuts", 48))
            except (TypeError, ValueError):
                subdiv_cuts = 48
            try:
                edge_radius_mm = float(params.get("edge_radius_mm", 1.0))
            except (TypeError, ValueError):
                edge_radius_mm = 1.0
            try:
                solidify_offset = float(params.get("solidify_offset", 1.0))
            except (TypeError, ValueError):
                solidify_offset = 1.0

        if orientation == "seat":
            orientation = "horizontal"

        arc_sign = -1.0 if arc_sign < 0 else 1.0

        if orientation == "vertical":
            # width -> X, length -> Z, thickness -> Y
            width_mm = float(dims[0])
            length_mm = float(dims[2])
            thickness_mm = float(dims[1])
            deform_axis = "Z"
        else:
            # width -> X, length -> Y, thickness -> Z
            orientation = "horizontal"
            width_mm = float(dims[0])
            length_mm = float(dims[1])
            thickness_mm = float(dims[2])
            deform_axis = "Y"

        try:
            subdiv_cuts_int = int(subdiv_cuts)
        except (TypeError, ValueError):
            subdiv_cuts_int = 48
        segments_len = max(12, min(200, subdiv_cuts_int * 2))

        obj = _create_slat_object(
            p.name,
            width_mm,
            length_mm,
            thickness_mm,
            loc,
            rot,
            segments_len,
            segments_w=2,
        )

        if orientation == "vertical":
            # Rotate plane into XZ so thickness (Solidify) is along Y and bend axis can be Z.
            import bmesh  # type: ignore  # Blender-only
            from mathutils import Matrix  # type: ignore  # Blender-only

            bm = bmesh.new()
            bm.from_mesh(obj.data)
            rot_m = Matrix.Rotation(math.radians(90.0), 4, "X")
            for v in bm.verts:
                v.co = rot_m @ v.co
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()

        bpy.context.view_layer.update()

        cuts_used = segments_len
        verts_before = len(obj.data.vertices)
        polys_before = len(obj.data.polygons)
        verts_after_subdiv = verts_before
        polys_after_subdiv = polys_before
        solidify_mm = thickness_mm

        solidify_offset = max(-1.0, min(1.0, solidify_offset))

        if solidify_mm > 0.0:
            solid = obj.modifiers.new(name="Solidify", type="SOLIDIFY")
            solid.thickness = solidify_mm / 1000.0
            solid.offset = solidify_offset
            solid.use_even_offset = True

        angle_rad = None
        radius_mm = None
        if arc_height_mm > 0.0 and length_mm > 0.0:
            arc_height_mm = min(max(0.0, arc_height_mm), length_mm / 2.0)
            # Sagitta formula -> bend angle in radians (clamped for stability).
            radius_mm = (length_mm * length_mm) / (8.0 * arc_height_mm) + (arc_height_mm / 2.0)
            if radius_mm > 0.0 and math.isfinite(radius_mm):
                angle_rad = length_mm / radius_mm
                angle_rad = max(-math.pi, min(math.pi, angle_rad))
            else:
                angle_rad = None

            helpers = bpy.data.collections.get("_helpers")
            if helpers is None:
                helpers = bpy.data.collections.new("_helpers")
                bpy.context.scene.collection.children.link(helpers)
                helpers.hide_viewport = True
                helpers.hide_render = True
            origin_name = f"{p.name}_bend_origin"
            origin = bpy.data.objects.get(origin_name)
            if origin is None:
                origin = bpy.data.objects.new(origin_name, None)
                origin.empty_display_type = "PLAIN_AXES"
                helpers.objects.link(origin)
            from mathutils import Vector  # type: ignore  # Blender-only

            half_len_m = (length_mm / 1000.0) / 2.0
            if deform_axis == "Y":
                origin.location = obj.matrix_world @ Vector((0.0, -half_len_m, 0.0))
            else:
                origin.location = obj.matrix_world @ Vector((0.0, 0.0, -half_len_m))
            # Keep origin axes aligned with the slat so deform_axis behaves predictably.
            origin.rotation_euler = obj.rotation_euler
            origin.hide_viewport = True
            origin.hide_render = True
            if obj.name == "DEBUG_SLAT":
                origin_loc = origin.location
                obj_loc = obj.location
                print(
                    "DEBUG_SLAT_ORIGIN "
                    f"name={obj.name} axis={deform_axis} length_mm={length_mm} "
                    f"origin=({origin_loc.x:.4f}, {origin_loc.y:.4f}, {origin_loc.z:.4f}) "
                    f"obj=({obj_loc.x:.4f}, {obj_loc.y:.4f}, {obj_loc.z:.4f})"
                )

            arc_sign = -1.0 if arc_sign < 0 else 1.0
            if angle_rad is not None:
                mod = obj.modifiers.new(name="Bend", type="SIMPLE_DEFORM")
                mod.deform_method = "BEND"
                mod.deform_axis = deform_axis
                mod.angle = angle_rad * arc_sign
                mod.origin = origin
                mod.show_viewport = True
                mod.show_render = True
                if hasattr(mod, "show_in_editmode"):
                    mod.show_in_editmode = True
                if hasattr(mod, "show_on_cage"):
                    mod.show_on_cage = True
                mod_types = [m.type for m in obj.modifiers]
                print(
                    "DEBUG_SLAT "
                    f"{obj.name} axis={deform_axis} angle={mod.angle} origin={origin.name} mods={mod_types}"
                )
                bpy.context.view_layer.update()

        if edge_radius_mm > 0.0:
            bevel = obj.modifiers.new(name="Bevel", type="BEVEL")
            bevel.width = edge_radius_mm / 1000.0
            bevel.segments = 2
            bevel.limit_method = "ANGLE"
            bevel.angle_limit = math.radians(40.0)
            if hasattr(bevel, "harden_normals"):
                bevel.harden_normals = True

        wn = obj.modifiers.new(name="WeightedNormal", type="WEIGHTED_NORMAL")
        wn.keep_sharp = True
        wn.weight = 50
        if hasattr(obj.data, "use_auto_smooth"):
            obj.data.use_auto_smooth = True
        if hasattr(obj.data, "auto_smooth_angle"):
            obj.data.auto_smooth_angle = math.radians(40.0)

        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            eval_mesh = eval_obj.to_mesh()
            print(
                f"DEBUG_SLAT_EVAL {obj.name} verts={len(eval_mesh.vertices)} "
                f"polys={len(eval_mesh.polygons)}"
            )
            eval_obj.to_mesh_clear()
        except Exception as exc:
            print(f"DEBUG_SLAT_EVAL {obj.name} error={exc}")

        angle_rad_value = angle_rad if angle_rad is not None else 0.0
        bend_angle = angle_rad_value * (-1.0 if arc_sign < 0 else 1.0)
        print(
            f"[slat] name={p.name} bend_angle={bend_angle} axis={deform_axis} "
            f"arc_height_mm={arc_height_mm} pos_y={obj.location.y:.3f} pos_z={obj.location.z:.3f}"
        )
        if verts_before <= 0:
            verts_before = len(obj.data.vertices)
        if polys_before <= 0:
            polys_before = len(obj.data.polygons)
        if verts_after_subdiv <= 0:
            verts_after_subdiv = len(obj.data.vertices)
        if polys_after_subdiv <= 0:
            polys_after_subdiv = len(obj.data.polygons)
        radius_value = radius_mm if radius_mm is not None else 0.0
        print(
            f"DEBUG_SLAT_SUBDIV {obj.name} cuts={cuts_used} axis={deform_axis} "
            f"angle={bend_angle} verts={verts_after_subdiv}"
        )
        mod_list = [f"{m.name}:{m.type}" for m in obj.modifiers]
        print(f"SLAT_VERTS:{p.name} verts={len(obj.data.vertices)}")
        print(f"SLAT_MODS:{mod_list}")
        print(
            f"[slat] name={p.name} dims={dims} orientation={orientation} "
            f"arc_height_mm={arc_height_mm} arc_sign={arc_sign} radius_mm={radius_value} "
            f"angle_rad={angle_rad_value} "
            f"verts_before={verts_before} polys_before={polys_before} "
            f"verts_after={verts_after_subdiv} polys_after={polys_after_subdiv}"
        )
        bend_angle = (angle_rad * arc_sign) if angle_rad is not None else 0.0
        world_loc = obj.matrix_world.to_translation()
        print(
            f"[slat_debug] name={p.name} bend_angle_rad={bend_angle} "
            f"world_loc=({world_loc.x:.3f}, {world_loc.y:.3f}, {world_loc.z:.3f}) "
            f"orientation={orientation}"
        )
        print(
            f"[slat] {p.name} dims={dims} orientation={orientation} subdiv_level={subdiv_level} "
            f"arc_height_mm={arc_height_mm} angle_rad={angle_rad} solidify_mm={solidify_mm} "
            f"bevel_width_m={edge_radius_mm / 1000.0 if edge_radius_mm > 0.0 else 0.0}"
        )
        return obj

    if shape == "cylindrical":
        # dims: (thickness, thickness, height)
        obj = _create_cylinder(p.name, radius_mm=dims[0] / 2.0, height_mm=dims[2], location_mm=loc)
        _apply_rotation_deg(obj, rot)
        return obj

    if shape == "tapered_cone":
        # prefer legs.params radii when available
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
            # simple default taper if params not encoded in primitive
            r_top = max(6.0, dims[0] * 0.35)
            r_bottom = max(r_top + 2.0, dims[0] * 0.6)
        obj = _create_cone(p.name, r_top_mm=r_top, r_bottom_mm=r_bottom, height_mm=dims[2], location_mm=loc)
        _apply_rotation_deg(obj, rot)
        return obj

    # fallback -> cube
    obj = _create_cube(p.name, dims, loc)
    _apply_rotation_deg(obj, rot)
    return obj


def main():
    import bpy  # type: ignore  # Blender-only

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

    if os.environ.get("DEBUG_SLAT") == "1":
        try:
            debug_slat = _create_primitive(
                builder_module.Primitive(
                    name="DEBUG_SLAT",
                    shape="slat",
                    dimensions_mm=(60.0, 600.0, 12.0),
                    location_mm=(0.0, 900.0, 300.0),
                    rotation_deg=(0.0, 0.0, 0.0),
                    params={
                        "arc_height_mm": 35.0,
                        "arc_sign": -1.0,
                        "orientation": "horizontal",
                        "subdiv_cuts": 48,
                        "edge_radius_mm": 1.0,
                        "solidify_mm": 0.0,
                    },
                ),
                legs_params=legs_params,
            )
            print(f"DEBUG_SLAT_CREATED:{debug_slat.name}")
            print(f"DEBUG_SLAT_BBOX:{debug_slat.bound_box}")
            print(f"DEBUG_SLAT_VERTS:{len(debug_slat.data.vertices)}")
            if os.environ.get("APPLY_DEBUG_SLAT") == "1":
                depsgraph = bpy.context.evaluated_depsgraph_get()
                eval_obj = debug_slat.evaluated_get(depsgraph)
                new_mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=depsgraph)
                debug_slat.data = new_mesh
                debug_slat.modifiers.clear()
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

    # optionally save .blend
    if blend_path:
        os.makedirs(os.path.dirname(blend_path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    return {"status": "built", "primitives": len(plan.primitives), "anchors": len(plan.anchors)}


if __name__ == "__main__":
    main()
