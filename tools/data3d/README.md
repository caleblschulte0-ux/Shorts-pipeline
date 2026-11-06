# tools/data3d — the 3D Data character and the 3D explainer sets (rebuild, 2026-11-06)

The first build of all this lived only in a session scratchpad and was wiped by a container restart on
2026-11-06 02:03Z. Everything here is committed on every change for that reason. Nothing in this folder is imported by
the posting pipeline; it is tooling for the 3D look trial (caaleb's rule: the pipeline keeps posting the 2D B-look
until 3D is approved).

- `base_build.py`: ChatGPT/Codex's approved Data model, verbatim from branch `codex/data-3d-reference`. Never redesign him.
- `character.py`: the rig on that model and the animation API (see NOTES_lost_asset_api.md for the API the lost
  version had; this one keeps the same names where it can).
- `store/`: the checkout set, staging, lighting and post.
- Environment: `python3.11 -m venv vbpy && vbpy/bin/pip install bpy==5.0.0 pillow numpy` (the bpy wheel is 380 MB).

Director rules (caaleb): pose for the ONE camera that sees it (Crash Bandicoot / early PlayStation): a side-on arm to a
cart handle is one straight line shoulder to handle end, measured every frame, never eyeballed. Still for approval
before any clip; a fast every-10th-frame test pass viewed at full size before any full render.
