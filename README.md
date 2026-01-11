# AMS

This repository sketches a workflow for turning natural language sofa requests into 3D assets:

1. NER extracts entities from user text.
2. Entities are normalized into a request payload.
3. The request is resolved into an intermediate representation (IR JSON).
4. Blender runner scripts consume the IR JSON to build geometry.
5. The Blender pipeline exports GLB assets.

The new builder subsystem lives in `src/builders/` with Blender and CAD stubs, while pipeline helpers live in `src/pipeline/`.
