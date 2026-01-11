# AMS

This repository sketches a workflow for turning natural language sofa requests into 3D assets:

1. NER extracts entities from user text.
2. Entities are normalized into a request payload.
3. The request is resolved into an intermediate representation (IR JSON).
4. Blender runner scripts consume the IR JSON to build geometry.
5. The Blender pipeline exports GLB assets.

The new builder subsystem lives in `src/builders/` with Blender and CAD stubs, while pipeline helpers live in `src/pipeline/`.

## How to run the builder

Run the builder and export a GLB using the Python runner (requires Blender installed):

```bash
python -m src.builders.blender.export_blender data/examples/sofa_ir.json out/glb/sofa.glb
```

To point at a custom Blender executable:

```bash
BLENDER_EXE=/path/to/blender python -m src.builders.blender.export_blender data/examples/sofa_ir.json out/glb/sofa.glb
```
