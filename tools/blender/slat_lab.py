"""Isolated slat deformation lab for Blender 4.4.

Run:
  blender --background --factory-startup --python tools/blender/slat_lab.py -- [options]

Options (after "--"):
  --out_blend <path>   Save .blend (optional)
  --apply              Bake modifiers for variant C
  --arc_mm <float>     Sagitta height in mm (default 35)
  --length_mm <float>  Slat length in mm (default 600)
  --width_mm <float>   Slat width in mm (default 60)
  --thick_mm <float>   Slat thickness in mm (default 12)
  --segments <int>     Grid segments along length (default 80)
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass


def _mm_to_m(x_mm: float) -> float:
    return float(x_mm) / 1000.0


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


@dataclass
class Opts:
    out_blend: str = ""
    apply: bool = False
    arc_mm: float = 35.0
    length_mm: float = 600.0
    width_mm: float = 60.0
    thick_mm: float = 12.0
    segments: int = 80


def _parse_opts(argv: list[str]) -> Opts:
    opts = Opts()

    if "--" in argv:
        args = argv[argv.index("--") + 1 :]
    else:
        args = []

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--apply":
            opts.apply = True
            i += 1
            continue
        if a == "--out_blend" and i + 1 < len(args):
            opts.out_blend = str(args[i + 1])
            i += 2
            continue
        if a == "--arc_mm" and i + 1 < len(args):
            try:
                opts.arc_mm = float(args[i + 1])
            except (TypeError, ValueError):
                pass
            i += 2
            continue
        if a == "--length_mm" and i + 1 < len(args):
            try:
                opts.length_mm = float(args[i + 1])
            except (TypeError, ValueError):
                pass
            i += 2
            continue
        if a == "--width_mm" and i + 1 < len(args):
            try:
                opts.width_mm = float(args[i + 1])
            except (TypeError, ValueError):
                pass
            i += 2
            continue
        if a == "--thick_mm" and i + 1 < len(args):
            try:
                opts.thick_mm = float(args[i + 1])
            except (TypeError, ValueError):
                pass
            i += 2
            continue
        if a == "--segments" and i + 1 < len(args):
            try:
                opts.segments = int(args[i + 1])
            except (TypeError, ValueError):
                pass
            i += 2
            continue

        i += 1

    opts.segments = int(_clamp(opts.segments, 1, 500))
    return opts


def _bend_angle_from_sagitta(length_mm: float, arc_mm: float) -> tuple[float, float]:
    """Return (angle_rad, radius_mm)."""
    if length_mm <= 0.0 or arc_mm <= 0.0:
        return 0.0, 0.0
    arc_mm = min(max(0.0, arc_mm), length_mm / 2.0)
    radius_mm = (length_mm * length_mm) / (8.0 * arc_mm) + (arc_mm / 2.0)
    if radius_mm <= 0.0 or not math.isfinite(radius_mm):
        return 0.0, radius_mm
    angle_rad = length_mm / radius_mm
    angle_rad = max(-math.pi, min(math.pi, angle_rad))
    return angle_rad, radius_mm


def _ensure_child_collection(scene_coll, name: str, hide: bool) -> "bpy.types.Collection":
    import bpy  # type: ignore

    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    if coll.name not in scene_coll.children:
        scene_coll.children.link(coll)
    coll.hide_viewport = bool(hide)
    coll.hide_render = bool(hide)
    return coll


def _move_obj_to_collection(obj, dst_coll) -> None:
    # Ensure object is only linked to dst_coll.
    for c in list(obj.users_collection):
        if c != dst_coll:
            c.objects.unlink(obj)
    if obj not in dst_coll.objects:
        dst_coll.objects.link(obj)


def _create_origin_empty(name: str, location, rotation_euler, helpers_coll):
    import bpy  # type: ignore

    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.location = location
    if rotation_euler is not None:
        empty.rotation_euler = rotation_euler
    empty.hide_viewport = True
    empty.hide_render = True
    helpers_coll.objects.link(empty)
    return empty


def _mesh_bbox_world(mesh, matrix_world):
    from mathutils import Vector  # type: ignore

    if not mesh.vertices:
        zero = Vector((0.0, 0.0, 0.0))
        return zero, zero
    min_v = None
    max_v = None
    for v in mesh.vertices:
        co = matrix_world @ v.co
        if min_v is None:
            min_v = co.copy()
            max_v = co.copy()
        else:
            min_v.x = min(min_v.x, co.x)
            min_v.y = min(min_v.y, co.y)
            min_v.z = min(min_v.z, co.z)
            max_v.x = max(max_v.x, co.x)
            max_v.y = max(max_v.y, co.y)
            max_v.z = max(max_v.z, co.z)
    return min_v, max_v


def _print_obj_stats(obj, label: str) -> None:
    mesh = obj.data
    mods = [f"{m.name}:{m.type}" for m in obj.modifiers]
    bb_min, bb_max = _mesh_bbox_world(mesh, obj.matrix_world)
    print(
        f"OBJ {label} name={obj.name} verts={len(mesh.vertices)} polys={len(mesh.polygons)} "
        f"bbox_min=({bb_min.x:.6f},{bb_min.y:.6f},{bb_min.z:.6f}) "
        f"bbox_max=({bb_max.x:.6f},{bb_max.y:.6f},{bb_max.z:.6f}) mods={mods}"
    )


def _print_obj_eval_stats(obj, label: str) -> tuple[float, float]:
    import bpy  # type: ignore

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    try:
        bb_min, bb_max = _mesh_bbox_world(eval_mesh, eval_obj.matrix_world)
        mods = [f"{m.name}:{m.type}" for m in obj.modifiers]
        print(
            f"OBJ_EVAL {label} name={obj.name} verts={len(eval_mesh.vertices)} polys={len(eval_mesh.polygons)} "
            f"bbox_min=({bb_min.x:.6f},{bb_min.y:.6f},{bb_min.z:.6f}) "
            f"bbox_max=({bb_max.x:.6f},{bb_max.y:.6f},{bb_max.z:.6f}) mods={mods}"
        )
        return bb_min.z, bb_max.z
    finally:
        eval_obj.to_mesh_clear()


def _create_grid_slat_object(name: str, width_m: float, length_m: float, segments_len: int, segments_w: int):
    import bpy  # type: ignore
    import bmesh  # type: ignore

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
    return obj


def _add_bend_modifier(obj, origin, axis: str, angle_rad: float) -> None:
    mod = obj.modifiers.new(name="Bend", type="SIMPLE_DEFORM")
    mod.deform_method = "BEND"
    mod.deform_axis = axis
    mod.angle = angle_rad
    mod.origin = origin
    if hasattr(mod, "show_viewport"):
        mod.show_viewport = True
    if hasattr(mod, "show_render"):
        mod.show_render = True
    if hasattr(mod, "show_in_editmode"):
        mod.show_in_editmode = True
    if hasattr(mod, "show_on_cage"):
        mod.show_on_cage = True


def main() -> None:
    import bpy  # type: ignore
    from mathutils import Vector  # type: ignore

    opts = _parse_opts(sys.argv)

    print(f"BLENDER_VERSION:{bpy.app.version_string}")
    print(f"FILEPATH:{bpy.data.filepath}")
    print(
        "OPTS "
        f"out_blend={opts.out_blend!r} apply={opts.apply} arc_mm={opts.arc_mm} "
        f"length_mm={opts.length_mm} width_mm={opts.width_mm} thick_mm={opts.thick_mm} segments={opts.segments}"
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    lab_coll = _ensure_child_collection(scene.collection, "_lab", hide=False)
    helpers_coll = _ensure_child_collection(scene.collection, "_helpers", hide=True)

    width_m = _mm_to_m(opts.width_mm)
    length_m = _mm_to_m(opts.length_mm)
    thick_m = _mm_to_m(opts.thick_mm)

    # Use negative angle to bend "upwards" in +Z for axis=Y in typical orientation.
    angle_rad, radius_mm = _bend_angle_from_sagitta(opts.length_mm, opts.arc_mm)
    bend_angle = -angle_rad
    print(f"BEND_CALC arc_mm={opts.arc_mm} length_mm={opts.length_mm} radius_mm={radius_mm} angle_rad={bend_angle}")

    # Layout: three objects spaced in X.
    base_z = 0.30
    loc_a = Vector((-0.45, 0.0, base_z))
    loc_b = Vector((0.00, 0.0, base_z))
    loc_c = Vector((0.45, 0.0, base_z))

    # A) SLAT_CUBE
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc_a)
    obj_a = bpy.context.active_object
    obj_a.name = "SLAT_CUBE"
    obj_a.dimensions = (width_m, length_m, thick_m)
    _move_obj_to_collection(obj_a, lab_coll)
    origin_a = _create_origin_empty("SLAT_CUBE_ORIGIN", obj_a.location.copy(), obj_a.rotation_euler, helpers_coll)
    _add_bend_modifier(obj_a, origin_a, axis="Y", angle_rad=bend_angle)

    # B) SLAT_GRID
    obj_b = _create_grid_slat_object("SLAT_GRID", width_m=width_m, length_m=length_m, segments_len=opts.segments, segments_w=2)
    obj_b.location = loc_b
    lab_coll.objects.link(obj_b)
    mod_solid_b = obj_b.modifiers.new(name="Solidify", type="SOLIDIFY")
    mod_solid_b.thickness = thick_m
    mod_solid_b.offset = 0.0
    mod_solid_b.use_even_offset = True
    origin_b = _create_origin_empty(
        "SLAT_GRID_ORIGIN",
        obj_b.matrix_world @ Vector((0.0, -length_m / 2.0, 0.0)),
        obj_b.rotation_euler,
        helpers_coll,
    )
    _add_bend_modifier(obj_b, origin_b, axis="Y", angle_rad=bend_angle)

    # C) SLAT_GRID_APPLIED
    obj_c = obj_b.copy()
    obj_c.data = obj_b.data.copy()
    obj_c.name = "SLAT_GRID_APPLIED"
    obj_c.location = loc_c
    lab_coll.objects.link(obj_c)
    # Replace bend origin to avoid sharing the same empty.
    for m in obj_c.modifiers:
        if m.type == "SIMPLE_DEFORM":
            origin_c = _create_origin_empty(
                "SLAT_GRID_APPLIED_ORIGIN",
                obj_c.matrix_world @ Vector((0.0, -length_m / 2.0, 0.0)),
                obj_c.rotation_euler,
                helpers_coll,
            )
            m.origin = origin_c

    bpy.context.view_layer.update()

    # Logs: base mesh stats.
    _print_obj_stats(obj_a, label="BASE")
    _print_obj_stats(obj_b, label="BASE")
    _print_obj_stats(obj_c, label="BASE")

    # Logs: evaluated stats (show modifier effect).
    _print_obj_eval_stats(obj_a, label="EVAL")
    b_base_minz, b_base_maxz = _mesh_bbox_world(obj_b.data, obj_b.matrix_world)
    b_eval_minz, b_eval_maxz = _print_obj_eval_stats(obj_b, label="EVAL")
    print(f"Z_RANGE SLAT_GRID base=({b_base_minz.z:.6f},{b_base_maxz.z:.6f}) eval=({b_eval_minz:.6f},{b_eval_maxz:.6f})")

    c_base_minz, c_base_maxz = _mesh_bbox_world(obj_c.data, obj_c.matrix_world)
    c_eval_minz, c_eval_maxz = _print_obj_eval_stats(obj_c, label="EVAL")
    print(
        f"Z_RANGE SLAT_GRID_APPLIED base=({c_base_minz.z:.6f},{c_base_maxz.z:.6f}) "
        f"eval=({c_eval_minz:.6f},{c_eval_maxz:.6f})"
    )

    if opts.apply:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj_c.evaluated_get(depsgraph)
        new_mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=depsgraph)
        old_mesh = obj_c.data
        obj_c.data = new_mesh
        obj_c.modifiers.clear()
        if old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
        bpy.context.view_layer.update()
        _print_obj_stats(obj_c, label="APPLIED")

    if opts.out_blend:
        out_blend = os.path.abspath(opts.out_blend)
        out_dir = os.path.dirname(out_blend)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=out_blend)
        print(f"SAVED_BLEND:{out_blend}")


if __name__ == "__main__":
    main()
