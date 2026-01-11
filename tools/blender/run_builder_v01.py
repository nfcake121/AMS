"""Run builder_v01 inside Blender."""

import json
import os
import sys

import bpy

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.builders.blender.builder_v01 import build_plan_from_ir


def _read_ir_path() -> str:
    """Resolve IR path from env or argv."""
    if os.environ.get("IR_PATH"):
        return os.environ["IR_PATH"]
    if "--" in sys.argv:
        index = sys.argv.index("--")
        if len(sys.argv) > index + 1:
            return sys.argv[index + 1]
    if len(sys.argv) > 1:
        return sys.argv[-1]
    return ""


def _ensure_scene_units():
    """Configure the scene for millimeter units."""
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001


def _clear_scene():
    """Start from an empty scene."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _create_cube(name, dimensions_mm, location_mm):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location_mm)
    obj = bpy.context.active_object
    obj.name = name
    obj.dimensions = dimensions_mm
    return obj


def _create_cylinder(name, radius_mm, height_mm, location_mm):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius_mm, depth=height_mm, location=location_mm)
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_cone(name, radius_top_mm, radius_bottom_mm, height_mm, location_mm):
    bpy.ops.mesh.primitive_cone_add(
        radius1=radius_bottom_mm,
        radius2=radius_top_mm,
        depth=height_mm,
        location=location_mm,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _create_hairpin_leg(base_name, location_mm, height_mm, thickness_mm):
    offset_x = thickness_mm
    offset_y = thickness_mm * 0.5
    left_loc = (location_mm[0] - offset_x, location_mm[1], location_mm[2])
    right_loc = (location_mm[0] + offset_x, location_mm[1], location_mm[2])
    _create_cylinder(f"{base_name}_left", thickness_mm * 0.25, height_mm, left_loc)
    _create_cylinder(f"{base_name}_right", thickness_mm * 0.25, height_mm, right_loc)
    connector_loc = (location_mm[0], location_mm[1] - offset_y, location_mm[2] - height_mm / 2.0)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=thickness_mm * 0.2,
        depth=offset_x * 2.0,
        location=connector_loc,
        rotation=(1.5708, 0.0, 0.0),
    )
    connector = bpy.context.active_object
    connector.name = f"{base_name}_connector"


def _create_leg(primitive, thickness_mm):
    shape = primitive.shape
    dims = primitive.dimensions_mm
    if shape == "cylindrical":
        _create_cylinder(primitive.name, thickness_mm / 2.0, dims[2], primitive.location_mm)
    elif shape == "tapered_cone":
        _create_cone(primitive.name, thickness_mm * 0.2, thickness_mm * 0.6, dims[2], primitive.location_mm)
    elif shape == "tapered_prism":
        _create_cube(primitive.name, dims, primitive.location_mm)
    elif shape == "hairpin":
        _create_hairpin_leg(primitive.name, primitive.location_mm, dims[2], thickness_mm)
    elif shape in {"sled", "frame"}:
        _create_cube(primitive.name, (dims[0] * 2.0, thickness_mm, dims[2]), primitive.location_mm)
    else:
        _create_cube(primitive.name, dims, primitive.location_mm)


def _create_anchor(anchor):
    empty = bpy.data.objects.new(anchor.name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.location = anchor.location_mm
    bpy.context.scene.collection.objects.link(empty)


def main():
    """Entry point for Blender execution."""
    ir_path = _read_ir_path()
    if not ir_path:
        raise ValueError("IR path is required.")

    _clear_scene()
    _ensure_scene_units()

    with open(ir_path, "r", encoding="utf-8") as handle:
        ir = json.load(handle)

    plan = build_plan_from_ir(ir)

    for primitive in plan.primitives:
        if primitive.shape in {"cylindrical", "tapered_cone", "tapered_prism", "hairpin", "sled", "frame"}:
            _create_leg(primitive, thickness_mm=primitive.dimensions_mm[0])
        elif primitive.shape == "cube":
            _create_cube(primitive.name, primitive.dimensions_mm, primitive.location_mm)
        else:
            _create_cube(primitive.name, primitive.dimensions_mm, primitive.location_mm)

    for anchor in plan.anchors:
        _create_anchor(anchor)

    blend_path = os.environ.get("BLEND_PATH")
    if blend_path:
        os.makedirs(os.path.dirname(blend_path), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)

    return {
        "status": "built",
        "primitives": len(plan.primitives),
        "anchors": len(plan.anchors),
    }


if __name__ == "__main__":
    main()
