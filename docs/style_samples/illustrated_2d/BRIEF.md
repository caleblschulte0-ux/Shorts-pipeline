# Brief: A/B test an illustrated 2D style on the explainer (Data mascot) channel

**From:** the operator, 2026-09-23. He watched three 33-second style samples
made for another channel. He liked one of them, the illustrated 2D one, and
said: *"that 2D animation, I want to start A/B testing that on the mascot
channel. Because like that looked great, and if we could throw the mascot on
there and input our data and make sure that we can constantly make something
that looks that good in a wide variety of situations and a wide variety of
data, that would be fucking awesome."*

## The reference

The sample's source is in this folder: `sample_a.py` and `common.py`, with
`timing.json` holding the beat times. It uses pycairo and was drawn by hand
for one script about ocean depth. The operator has the rendered MP4 and can
attach it to this chat. To render it yourself:

    pip install pycairo
    mkdir -p ~/.fonts && cp assets/fonts/*.ttf ~/.fonts/ && fc-cache -f
    python docs/style_samples/illustrated_2d/sample_a.py /tmp/a.mp4

It runs in about 32 seconds on a session box. With no narration file it
produces a silent render.

What makes it look good, and so what the system has to reproduce every time:

- **Every frame is a full-bleed illustrated world, not a chart on a ground.**
  Each scene is built from layered gradients, two-tone shaded shapes (a lit
  face and a shadow face), rim light, soft radial glows and a foreground
  layer. Sunset sky over Everest, a split of space and the deep sea, a
  descent that darkens with depth.
- **The number is a physical act made of the subject.** Everest drops into
  the Mariana Trench with a splash, and a bracket measures the 2,000 m of
  water left above its summit. Twelve astronauts pop onto the Moon's rim one
  at a time while the count ticks up. A depth readout rises as the sub
  sinks. This is the same "tier 1 = made of the subject" rule the channel
  already grades (`depictions`, `VIZ_BRAIN.md`), drawn in a richer style.
- **Nothing is ever still.** Clouds drift, fish swim, particles stream past,
  light rays sway, bubbles rise and glows pulse on top of every scene. The
  temporal gate never sees a freeze, and every scene has depth.
- **Entrances are timed to the narration**, with ease-out and a small
  overshoot "pop". The big numbers are in Anton, the labels in Inter, and
  quick dips to black mark the cuts between beats.
- **Colour means something**: water darkens with depth, the subject is warm
  and the setting is cool.

## The job

Build an **illustrated renderer arm** for the explainer and A/B test it
against the current look. It should work from the channel's own sourced
datasets and include Data, across the full range of stories the channel
makes, not only ones that happen to suit an ocean.

1. **The seam already exists; use it.** `relationships.py` picks the claim
   and `studio_render._MACHINES` maps the claim to a machine. The
   illustrated arm should be a second draw layer for those machines (plus
   illustrated scene kits: environments, props and ambient motion), chosen
   per video. Do not fork the pipeline and do not add a second classifier.
   Where a claim has no illustrated drawing yet, fall back to the current
   renderer for that scene and record that it did.
2. **Generality is the real work.** The sample was drawn by hand for one
   story. The system needs a library of parameterised scene kits (settings
   such as sky, space, ocean, city, farm, body, factory and landscape, plus
   subject props) that the brain or the relationship chooses from and the
   data drives. Prove it the way `MotionMustBeVISIBLE` and
   `seed_exemplars.py` prove the machines: render every kit on every data
   shape through the real path before it can be used.
3. **Data belongs in the scene, not as a sticker.** The rig in
   `scripts/build_mascot_svg.py` is the character's single source of truth,
   and `mascot_director` already renders any pose as SVG through cairosvg,
   so it can be composited straight into a cairo frame. He should act inside
   the world: riding the sub, standing on the summit, counting the
   astronauts. Remember `decorative_mascot` was the channel's top showrunner
   complaint. If his flat look clashes with the shaded world, show the
   operator a side-by-side and ask. Changing the rig needs his explicit
   request.
4. **The A/B split lives in `config/channel_registry.json`**, the only place
   channel policy lives, for example as a style weight on `data_story`. Each
   posted video records its style arm in its posted-log entry and in
   `state/showrunner_verdicts.jsonl`. The retro brief compares the arms by
   percentile against same-age videos and reports its sample size honestly.
   A dozen videos per arm is noise, and the brief should say so.
5. **The format.** The explainer ships Shorts, not 16:9. Recompose for
   1080×1920: the worlds stack vertically well (sky above, depth below), and
   the text needs title clearance.
6. **The look rules.** `shared/look.py` is the one place colour is decided,
   and `test_the_channel_has_a_look.py` holds it. The illustrated arm needs
   its own tokens in `look.py`, not hex values named in a composer. Keep one
   accent on the subject and text in ink. Illustrated scenery is a new
   *palette*, and the operator's 2026-09-10 ruling asks for sharp, clean and
   professional, so write the new tokens down in `docs/CHANNEL_LOOK.md`.

## What does not change

- **The showrunner gates both arms, unchanged.** It is fail-closed and its
  BLOCK is sovereign. The illustrated arm earns its place by passing it, and
  no format directive may soften a criterion for it. The honesty rules hold
  too: every number drawn comes from the sourced dataset. The sample
  animated real figures (8,849 m, 10,935 m, 12, "a few dozen"). Decoration
  may move, but it may not add a quantity the data does not have.
- **Motion is measured with the gate's own detector, not asserted.**
- **Keep render time in check.** pycairo at 30 fps took about one second per
  second of video here. Check the explainer's CI budget with four videos a
  day.
- **Branch discipline.** Work on a `claude/*` branch and rebase before any PR
  (auto-merge squashes).
- **No media in git.** Previews go to artifacts or `preview-renders`.

## Done means

- Both arms are live in production, with the split set in the registry.
- A preview render from three very different datasets (for example a
  ranking, a trend and a share) looks as good as the sample, includes Data,
  and passes the showrunner. Show the operator those three before the split
  goes live.
- The retro brief reports the two arms side by side.

---

_The reference renderer (`sample_a.py`, `common.py`, `timing.json`) lives on
branch `claude/youtube-longform-videos-lp018g` under this same path. The
general version built from this brief is `data_learning/illustrated.py`._
