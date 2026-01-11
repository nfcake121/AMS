"""Runner that triggers Blender build from an IR JSON path."""

# TODO: load IR JSON and dispatch to Blender runner scripts.

def run_blender_build(ir_json_path):
    """Run Blender build for the given IR JSON path."""
    # NOTE: bpy import must stay inside this function for non-Blender contexts.
    # TODO: implement Blender dispatch logic.
    try:
        import bpy  # noqa: F401
    except ModuleNotFoundError:
        # TODO: handle execution outside Blender environment.
        bpy = None

    return {
        "ir_json_path": ir_json_path,
        "blender_available": bpy is not None,
    }
