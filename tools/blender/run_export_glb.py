"""Export GLB from Blender scene."""

import os
import sys

import bpy


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


def main():
    """Entry point for Blender execution."""
    glb_path = _read_glb_path()
    os.makedirs(os.path.dirname(glb_path), exist_ok=True)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format="GLB",
        use_selection=False,
    )

    return {
        "status": "exported",
        "path": glb_path,
    }


if __name__ == "__main__":
    main()
