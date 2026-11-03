# Data — Blender character look development

Caleb's supplied `reference.jpeg` is the visual target. These are unapproved look-development iterations, not an exact reconstruction or a production rig.

```sh
blender -b -t 6 --python tools/data_character/build.py -- /tmp/data-character
```

Current script writes front and three-quarter PNGs and a compressed editable `data_reference.blend`. Blender 4.0.2 CPU Cycles, 160 samples; no paid APIs or pipeline imports. No production-render or publishing changes.

## Current revision: friendlier face

The thin beveled cubes used for the eye whites made them unnaturally square. Replaced them with convex rounded squircle surfaces, rounder pupils with a gentle converging gaze and two catchlights, and tapered capped brows. Materials are more matte; the frontal lights are broader and the rear rim is weaker to reduce harsh highlights and dark facial shadows. Head sits closer to a new collar. Shoes have rounded toes and a flat sole; hands are smaller and the coat uses a softer ivory material. Changes build on the prior deeper teal, closer frames and wider coat.

All character objects are under `DATA_ROOT`. No armature, skin weighting, facial shape keys or lip sync yet. Do not replace the production 2D host or assume Caleb has approved this model. Review the actual front and three-quarter renders against his supplied reference first.

Original committed 3D mascot work from Claude was not found during the initial repository inspection; this separate path avoids overwriting work in another workspace.
