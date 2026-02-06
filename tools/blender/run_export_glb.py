"""Export GLB from Blender scene."""

import os
import sys

import bpy  # type: ignore  # Blender-only


def _read_glb_path() -> str:
    """Resolve GLB path from env or argv."""
    if os.environ.get("GLB_PATH"):
        return os.environ["GLB_PATH"]
    if "--" in sys.argv:
        index = sys.argv.index("--")
        if len(sys.argv) > index + 1:
            return sys.argv[index + 1]
    if len(sys.argv) > 1:
        return sys.argv[-1]
    return "out/glb/sofa.glb"


def _export_apply_kwargs():
    props = bpy.ops.export_scene.gltf.get_rna_type().properties
    if "export_apply" in props:
        return {"export_apply": True}
    if "export_apply_modifiers" in props:
        return {"export_apply_modifiers": True}
    return {}


def _is_exportable_mesh(obj) -> bool:
    if obj.type != "MESH":
        return False
    if obj.name.endswith("_bend_origin"):
        return False
    for col in obj.users_collection:
        if col.name == "_helpers":
            return False
    if obj.hide_get() or obj.hide_viewport or obj.hide_render:
        return False
    if not obj.visible_get():
        return False
    return True


def main():
    """Entry point for Blender execution."""
    glb_path = _read_glb_path()
    glb_path = os.path.abspath(glb_path)
    os.makedirs(os.path.dirname(glb_path), exist_ok=True)

    print(f"RUN_EXPORT_GLB:{__file__}")
    print(f"BLEND_PATH:{bpy.data.filepath}")
    print(f"GLB_PATH:{glb_path}")

    if os.path.exists(glb_path):
        try:
            os.remove(glb_path)
        except OSError as exc:
            print(f"WARNING: failed to remove existing GLB {glb_path}: {exc}")

    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    helpers = bpy.data.collections.get("_helpers")
    if helpers is not None:
        helpers.hide_viewport = True
        helpers.hide_render = True

    export_objs = [obj for obj in bpy.data.objects if _is_exportable_mesh(obj)]
    tmp_coll = bpy.data.collections.get("_export_tmp")
    if tmp_coll is None:
        tmp_coll = bpy.data.collections.new("_export_tmp")
        bpy.context.scene.collection.children.link(tmp_coll)
    tmp_coll.hide_viewport = False
    tmp_coll.hide_render = False

    tmp_objects = []
    tmp_meshes = []
    for obj in export_objs:
        eval_obj = obj.evaluated_get(depsgraph)
        try:
            mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=depsgraph)
            used_new_from_object = True
        except Exception:
            used_new_from_object = False
            mesh_eval = eval_obj.to_mesh()
            mesh = mesh_eval.copy()
            eval_obj.to_mesh_clear()
        tmp = bpy.data.objects.new(obj.name, mesh)
        tmp.matrix_world = obj.matrix_world
        tmp_coll.objects.link(tmp)
        tmp_objects.append(tmp)
        tmp_meshes.append(mesh)

    print(f"EXPORT_MESH_OBJECTS:{len(tmp_objects)}")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in tmp_objects:
        obj.select_set(True)
    if tmp_objects:
        bpy.context.view_layer.objects.active = tmp_objects[0]

    export_kwargs = {
        "filepath": glb_path,
        "export_format": "GLB",
        "use_selection": True,
    }
    export_kwargs.update(_export_apply_kwargs())

    result = bpy.ops.export_scene.gltf(**export_kwargs)
    print(f"GLTF_EXPORT_RESULT:{result}")
    bpy.context.view_layer.update()

    size = os.path.getsize(glb_path) if os.path.exists(glb_path) else 0
    print(f"GLB_SIZE_BYTES:{size}")
    if size <= 0:
        raise SystemExit(2)

    for obj in tmp_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in tmp_meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    return {
        "status": "exported",
        "path": glb_path,
    }


if __name__ == "__main__":
    main()
