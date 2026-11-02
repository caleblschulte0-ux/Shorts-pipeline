# Data — Blender reference prototype

Requested by Caleb on 2026-11-02, using his supplied teal professor reference. Standalone look-development asset; does not replace the production 2D host.

## Run

```sh
blender -b -t 4 --python tools/data_character/build.py -- /tmp/data-character
```

Writes front, three-quarter, side and back PNGs, plus `data_reference.blend`. Verified with Blender 4.0.2 / CPU Cycles, 64 samples. No paid APIs, pipeline imports, posting, or workflow changes. Denoising is disabled because Ubuntu Blender has no OpenImageDenoiser.

## Implemented

Rounded teal head, two oval ears, thick open rounded-square glasses. Separate eye pads, pupils, highlights, brows, nose and curved smile. Slightly lanky silhouette; continuous tapered coat shell, folded lapels, red tie and blue pen pocket. Rounded mitten hands. All character objects parented to `DATA_ROOT`. Four studio views with consistent lighting.

## Claude handoff

Repository main and remote branch tips were inspected. The only committed Blender module found was `data_learning/blender_hero.py` (chart monoliths); Claude's in-progress 3D mascot was not located. This separate path avoids overwriting that work.

Open `preview/data_reference.blend` or run the command above. Compare the actual renders to `reference.jpeg`. Keep the large head and glasses, modest body width, and slightly lanky torso/legs. The geometry helpers are independent of studio setup and can be reused in another model builder.

This is **look development, not an animation-ready rig**: no armature, skin weighting, facial shape keys, lip sync or production-render integration yet. Parts are named and independently adjustable; repeated limb names receive Blender numeric suffixes. Establish the neutral appearance before rigging. For expressions, move brows and pupils and replace the smile curve.

The source reference is an AI illustration, not exact orthographic CAD: use silhouette and visual proportions as the guide rather than assuming every view is geometrically consistent.
