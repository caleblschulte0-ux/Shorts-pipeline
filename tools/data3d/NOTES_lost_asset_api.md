# Data, the 3D asset

`data_asset.blend` holds the rigged character (ChatGPT's model with elbows, knees, eyelids, an iris and a mouth with shape keys, every material, no street). `data_asset.py` is the only way scripts use him; nothing outside it touches a bone.

```python
from data_asset import load
data = load(bpy.context.scene)                  # appends the asset; builds it in place if the .blend is missing
data.place(x, y, rot_deg=0)                     # world position (metres) and facing (rest facing is -Y)
data.look_at(target, t)                         # head aims at a world point at time t; later acts keep that gaze
data.expression(name, t0, t1=None, blend=0.22)  # happy surprised worried laughing thinking sad excited skeptical neutral
data.say([(t, openness), ...], key='open')      # mouth 0..1 over time (keys: open oh grin frown surprised mm)
data.walk_to((x, y), t0, t1)                    # turns to face the way, walks with knees, feet planted, settles
data.run_to((x, y), t0, t1)
data.turn_to(rot_deg, t0, t1)                   # in place, with a foot shuffle
data.act('wave'|'thumbs_up'|'point'|'jump'|'sit'|'stand'|'lean_in'|'nod'|'shrug', t0, **kw)  # returns when it ends
data.hold(pL, pR, t0, t1=None); data.release(t) # both hands on two world points (2-bone IK; out of reach is clamped and printed)
data.blink(t); data.gaze(t, dx, dz); data.breathe(t0, t1)
n_frames = data.finish()                        # call once at the end: easing, ear/tie overlap, frame range
```

Times are seconds at 24 fps. `data.height` is his height in metres (0.95). Scale is 0.2 m per rig unit.

- The face is geometry, not decals: eyeballs are spheres (radius `EYE_R`) sunk `EYE_SINK` into the head so only a shallow dome shows inside each lens, with a pupil cap that rotates for gaze; lids are skin caps (eye radius + 1 mm) that rotate about the eye centre with a dark margin, hidden at rest (`LID_U_DEG`/`LID_L_DEG`); brows are thin dark-teal tubes just above the frame top; the mouth is one outline curve (lip tube) plus a cutter that booleans the cavity into the head (teeth and tongue inside), with cheek and jaw shape keys on the head (the flat `mm` mouth also thins the lip tube: `bevel_depth` is keyed between `LIP_R` and `MM_LIP_R`); brows pivot about the head centre so they stay on the surface. `data_cx3.py` builds it on top of `data_cx2.py`.
- Expressions are blends of mouth keys, lids, brows, pupils and a head accent (`EXPRESSIONS` in `data_asset.py`); add one by adding a dict entry.
- `say()` takes any (time, openness) list, so it can be driven from a TTS amplitude envelope later.
- Build or rebuild the library: `vbpy/bin/python -I data_asset.py` (reads `data_cx3.py` + `rig2.py`).
- Close-ups of the face at 128 spp: `vbpy/bin/python -I closeup_sheet.py 128 600 data_face_closeups.jpg`.
- Smoke test every expression, mouth key and act into `data_asset_sheet.jpg`: `vbpy/bin/python -I smoke_sheet.py 64 300`.
- Street demo: `./anim3.sh OUTDIR SPP PCT` renders `anim3.py` through `scene.py`; `./post.sh OUTDIR out.mp4` encodes.

## Rendering rule (caaleb, 2026-11-04)

Never start or restart a full render without a fast test pass first: `./testpass.sh t_anim3` renders every 10th frame
of the demo at 6 spp / 25% in minutes and tiles them to `t_anim3.jpg`. View it at FULL resolution and check that face
parts follow the head, the glasses never intersect, the feet stay planted, the mouth syncs to the say timeline and the
expressions ease in and out. Only then `./anim3.sh c_full 20 45`, then the 8-frame sheet (`python3 sheet.py c_full
clip2_sheet.jpg 8`), the flicker check in a static region (`python3 -I flicker.py c_full L T R B`, target < 0.6/255 mean)
and `./post.sh c_full data_cx_clip2.mp4`. A running full render is not killed for a small defect: finish it, report it.

## Skinned rig + motion capture (2026-11-04)

`data_asset_skin.blend` (the default: `SKIN=0` falls back to the rigid `data_asset.blend`) carries `rig3.py`'s
DEFORMING rig: coat, sleeves, legs and neck wear an Armature modifier with chain weights so hips, spine, shoulders,
elbows and knees bend through the surface; head, face, ears, hands and shoes stay rigid on their bones. Bones:
root spine chest neck head, clav/arm/fore/hand and leg/shin/foot .L/.R (`.L` is x<0 = Data's RIGHT).

Motion comes from CMU mocap (Bruce Hahne's BVH port, `$S/mocap/<subject>_<clip>.bvh`, 120 fps, frame 1 = T pose)
retargeted by `mocap.py` on world-space segment direction + twist, so no rest pose has to match:

```python
data.mocap('18_08', t0, t1, start_s=2.0, speed=1.0, head=False, travel=False, loop=True, hold=None, facing=None)
    # keys every mapped bone from the clip between t0 and t1; yaw-corrected so the clip faces Data's rest (-Y);
    # root follows the hips height, feet are clamped to the ground, hands are kept out of the head
data.mocap_walk_to((x, y), t0, t1, name='02_01', start_s=0.35)
    # a real walk cycle: turns to the heading, slows playback when the distance is short so feet keep up, lands on target
```

Clips on disk: walks 02_01 16_21 82_12, idle 40_10, conversation 18_08 19_08 18_09, laugh 13_14 14_17, shrug 111_25,
very happy 79_69, scared 79_73, directing traffic 13_27. `vbpy/bin/python -I skin_check.py 16 300` tiles twelve posed
cells to `skin_check.jpg`. Lids are now full-dome caps built tilted back (`LID_CAP_DEG`, `LID_TILT`); a blink rotates
them 128 degrees and returns to whatever the expression had (`_lid_value`). The two-shot demo is `anim4.py`
(`./testpass4.sh t4` first, then `./anim4.sh c4 20 45`, `python3 sheet.py c4 clip3_sheet.jpg 8`, `./post.sh c4 data_cx_clip3.mp4`).
- `data.rest_bones(t0, t1)` eases every mocap-driven bone from the pose it holds at t0 back to rest by t1; call it after a
  clip whose last frame must not be held (the laugh's spread arms once stayed to the end of the shot). `lean_in` takes
  `push=` (hips toward the lens, rig units; 0.12 keeps the head inside a medium shot). The eye has a skin SOCKET collar
  (`Eye socket`, everything beyond 66 degrees off the front) so no eye white shows beside a lid from any angle, and the upper lid
  shell rides outside the lower one. **scene.py skips a frame whose file already exists** — delete the range before a
  partial re-render, or it silently renders nothing and reports DONE.

## Rest face, body layers, planted walk (2026-11-05, clip 4)

- **His neutral face is FLAT.** The mouth's basis geometry is the relaxed line (`MOUTH_KEYS['rest']` in
  `data_cx3.py`); `smile` is an explicit shape key like `open`/`oh`/`grin`. Every expression eases back to the flat
  line, so nothing "tries to go back to a weird smile". `expression('smile', t0, t1)` is the deliberate smile;
  `'happy'` is smile 0.85 + grin 0.25.
- **Closed eyes are a dome, not a cap.** `_lid()` keys a 2.5% (upper) / 3.5% (lower) scale-down with the close, so the
  closed lid flattens against the eye and the upper stays outside the lower; the crease is the dark margin tube.
- `data.mocap(name, t0, t1, ..., blend_in=0.45, blend_out=0.35, max_bow=18)`: the clip slerps IN from whatever pose
  the bones hold at t0 and OUT to rest over those seconds (eased), the spine/chest bow is clamped to `max_bow`
  degrees so a laugh never puts the crown out of frame, and the root location is blended the same way.
- `data.gesture_beats(times, side='R', amp=1.0)`: an ADDITIVE layer on top of any mocap - one chest-height beat
  per time (wind-up 0.16 s, release 0.32 s) on arm/forearm/hand. `data.breathe(t0, t1)` is a second additive layer
  (chest rise, spine and clavicle sway) under everything. Both are keyed after the clip, never instead of it.
- Hands never pass through the big head: `_hands_clear()` folds the arm by the window-minimum of what each frame
  needs, blurred over +/-4 frames, so a frame that needs folding never sits next to one that does not (the old
  per-frame loop made 30-47 deg/frame pops; now max 14-19 on accents only).
- `data.mocap_walk_from((x, y), direction, t0, t1, name='02_01')`: places him where the clip's OWN stride lands him
  on (x, y), so the walk runs at travel scale 1.0 and the feet stay planted (measured: <= 3 mm/frame through every
  stance while the body moves 11.5 mm/frame). Use it instead of `mocap_walk_to` when the end point matters.
- Measure, do not assert: `PROBE5=1` in `anim5.py` prints foot slide per flat-foot frame, 2nd-difference jitter per
  bone, the hand-head ellipsoid metric and the crown's NDC in shot B. Copy that block into any new beat script.
- Workflow for a clip: `./testpass5.sh NAME` (every 10th frame, 6 spp, 25%) -> read NAME.jpg at full size ->
  take `$S/render.lock` -> `./anim5.sh OUT 20 45` -> `sheet.py` + `flicker.py` -> `./post.sh OUT clip.mp4`.
  Full chain with active-talking arms: CMU 19_08 (149 deg/s arm activity, picked by `analyze_clips.py`).
- `data.head_bob(t0, t1, lag=3)`: a walking head - pitch from the hips' own bounce, lagged 3 frames, a touch of roll.
- `data.expression(name, t0, t1, cross='other')`: come straight from a held expression (one with no t1) so two reactions
  in a row never show a blank face between them (clip 4 had four such frames between surprise and laugh).
- `scan_talk.py CLIP...`: per 4 s window of a talk clip, hand height above the hips, longest hold, speed, hips travel,
  yaw range and spine lean - pick a talking window by numbers, not by name (14_17 leans 60-90 deg, 13_27 spins).
