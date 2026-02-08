# tools/inspect_blend.py
# Usage:
#   blender --background out/logs/sofa.blend --python C:\Users\Gigabyte\AMS\tools\inspect_blend.py

print("INSPECT_BLEND_START")

import bpy  # type: ignore


def axis_ranges_world(mesh, matrix_world):
    if not mesh or not getattr(mesh, "vertices", None):
        return None
    if len(mesh.vertices) == 0:
        return None

    xs = []
    ys = []
    zs = []
    for v in mesh.vertices:
        w = matrix_world @ v.co
        xs.append(w.x)
        ys.append(w.y)
        zs.append(w.z)

    return (
        (min(xs), max(xs)),
        (min(ys), max(ys)),
        (min(zs), max(zs)),
    )


def axis_spans(ranges):
    return (
        ranges[0][1] - ranges[0][0],
        ranges[1][1] - ranges[1][0],
        ranges[2][1] - ranges[2][0],
    )


def fmt_axis(ranges):
    return (
        f"x=({ranges[0][0]:.6f},{ranges[0][1]:.6f}) "
        f"y=({ranges[1][0]:.6f},{ranges[1][1]:.6f}) "
        f"z=({ranges[2][0]:.6f},{ranges[2][1]:.6f})"
    )


def mesh_counts(mesh):
    if not mesh:
        return (0, 0)
    verts = len(mesh.vertices) if getattr(mesh, "vertices", None) is not None else 0
    polys = len(mesh.polygons) if getattr(mesh, "polygons", None) is not None else 0
    return (verts, polys)


def fmt_modifiers(obj):
    if len(obj.modifiers) == 0:
        return "[]"

    rows = []
    for mod in obj.modifiers:
        show_viewport = bool(getattr(mod, "show_viewport", False))
        show_render = bool(getattr(mod, "show_render", False))
        show_in_editmode = bool(getattr(mod, "show_in_editmode", False))
        show_on_cage = bool(getattr(mod, "show_on_cage", False))
        rows.append(
            f"{mod.name}:{mod.type} "
            f"viewport={int(show_viewport)} render={int(show_render)} "
            f"edit={int(show_in_editmode)} cage={int(show_on_cage)}"
        )
    return "[" + ", ".join(rows) + "]"


def print_bend_modifiers(obj):
    for mod in obj.modifiers:
        if mod.type == "SIMPLE_DEFORM" and getattr(mod, "deform_method", "") == "BEND":
            origin = mod.origin.name if getattr(mod, "origin", None) else "None"
            print(f"BEND axis={mod.deform_axis} angle={float(mod.angle):.6f} origin={origin}")


def main():
    print("FILE:", bpy.data.filepath)
    print("BLENDER_VERSION:", bpy.app.version_string)
    print("Objects:", len(bpy.data.objects))

    depsgraph = bpy.context.evaluated_depsgraph_get()

    slats = [
        o
        for o in bpy.data.objects
        if o.type == "MESH" and ("slat" in o.name.lower() or o.name == "DEBUG_SLAT")
    ]
    slats = sorted(slats, key=lambda x: x.name)

    print("Slat-like:", len(slats))
    print("--- SLATS DUMP (first 60) ---")

    for obj in slats[:60]:
        eval_obj = obj.evaluated_get(depsgraph)
        eval_mesh = None
        base_verts, base_polys = mesh_counts(obj.data)
        try:
            eval_mesh = eval_obj.to_mesh()
            base_ranges = axis_ranges_world(obj.data, obj.matrix_world)
            eval_ranges = axis_ranges_world(eval_mesh, eval_obj.matrix_world)
        finally:
            if eval_mesh is not None:
                eval_obj.to_mesh_clear()

        print(f"\n- {obj.name}")
        print(f"BASE_MESH verts={base_verts} polys={base_polys}")
        print(f"MODIFIERS {fmt_modifiers(obj)}")
        print_bend_modifiers(obj)

        if base_ranges is None or eval_ranges is None:
            print("AXIS_RANGES_BASE x=(nan,nan) y=(nan,nan) z=(nan,nan)")
            print("AXIS_RANGES_EVAL x=(nan,nan) y=(nan,nan) z=(nan,nan)")
            print("RANGE_DELTAS dx=nan dy=nan dz=nan")
            print("BEND_EFFECT=NO")
            continue

        base_spans = axis_spans(base_ranges)
        eval_spans = axis_spans(eval_ranges)
        dx = abs(eval_spans[0] - base_spans[0])
        dy = abs(eval_spans[1] - base_spans[1])
        dz = abs(eval_spans[2] - base_spans[2])
        bend_effect = "OK" if max(dx, dy, dz) > 1e-5 else "NO"

        print(f"AXIS_RANGES_BASE {fmt_axis(base_ranges)}")
        print(f"AXIS_RANGES_EVAL {fmt_axis(eval_ranges)}")
        print(f"RANGE_DELTAS dx={dx:.6f} dy={dy:.6f} dz={dz:.6f}")
        print(f"BEND_EFFECT={bend_effect}")

    print("\nINSPECT_BLEND_DONE")


if __name__ == "__main__":
    main()
