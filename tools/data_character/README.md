# Data — Blender character look development

Caleb's supplied `reference.jpeg` is the visual target. These are unapproved look-development iterations, not an exact reconstruction or a production rig.

```sh
blender -b -t 6 --python tools/data_character/build.py -- /tmp/data-character
```

Current script writes front and three-quarter PNGs and a compressed editable `data_reference.blend`. Blender 4.0.2 CPU Cycles, up to 384 adaptive samples; no paid APIs or pipeline imports. No production-render or publishing changes.

## Current revision: friendlier face

The thin beveled cubes used for the eye whites made them unnaturally square. Replaced them with convex rounded squircle surfaces, rounder pupils with a gentle converging gaze and two catchlights, and tapered capped brows. Materials are more matte; the frontal lights are broader and the rear rim is weaker to reduce harsh highlights and dark facial shadows. The separate collar ring has been removed. Shoes are single rounded meshes with flattened bottoms; hands are smaller and the coat uses a softer ivory material. Changes build on the prior deeper teal, closer frames and wider coat.

All character objects are under `DATA_ROOT`. No armature, skin weighting, facial shape keys or lip sync yet. Do not replace the production 2D host or assume Caleb has approved this model. Review the actual front and three-quarter renders against his supplied reference first.

Original committed 3D mascot work from Claude was not found during the initial repository inspection; this separate path avoids overwriting work in another workspace.

## Proportions and shading revision

Removed the added sole objects. Head is narrower and a little taller, glasses and eyes are slightly wider, nose smaller and smile broader. The teal material has more red and is brighter; coat intensity is reduced. A stronger key and weaker fill create directional shading on a lighter charcoal stage. Current review renders and comparison are in preview/. These changes are pending Caleb’s review.

The eye whites and coat have been reduced to avoid blown-out white surfaces; pupils use a separate, darker material. Brows are fuller and the teal surface is slightly less rough. A pixel comparison of masked front-view skin regions was used as a color sanity check alongside visual review, not as a claim of an exact reference match.

The coat/upper body is 10% longer above the hem, and the head assembly is raised 0.17 scene units to meet the shoulders, addressing the short-torso proportion visible in the reference comparison.
