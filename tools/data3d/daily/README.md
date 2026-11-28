# The daily 3D short: one a day, start to finish in one sitting

Operator, 2026-11-28, after the lava short spent 90 hours without a video: *"fix whatever is broken and make this into
a fully autonomous system that produces a new 3d video in a timely manner like at the very least 1 a day."*

What was broken was never the render (about two hours on twenty free runners). It was that every shot was three
hundred lines of hand-written Blender, found wrong one forty-minute judge round at a time, in a loop whose only exit
was a pass from a panel that tops out near 78 against a bar of 70. A daily short is made differently:

| | legacy story | daily story (`"pipeline": "daily"` in script.json) |
|---|---|---|
| the place | a set built by hand | a real photographed place (`s.place(env)`, Poly Haven, CC0) |
| the props | modelled by hand | scanned models placed by where they are on the screen |
| a shot | 200-400 lines | about 15 lines of `store/director.py` |
| a look at it | 5 minutes | 20 seconds (`QUICK=1`) |
| the checks | 22 strict gates, any one stops the build | all still measured and printed; none stops the build |
| the exit | a panel pass | the day's video renders (`data3d_ship.yml`); the operator's yes posts it |

Nothing here posts. `data3d_upload.yml` on main posts, on the operator's word, through the showrunner gate.

## The run, in order (about three hours, most of it the render)

1. **Topic.** A true, current, visually spectacular STORY (operator 2026-11-23): something happens to someone, with a
   turn. No history, no lists of facts. Not one already in `daily/used.json`. Find it and its sources on the web; every
   claim in the lines needs a source with the sentence that says it.
2. **Script.** `stories/<slug>/script.json`: `pipeline: daily`, `title`, `voice`, five `lines` (about 15-20 spoken
   words each, a hook that names the thing, each line because-of or but the one before, a question to end),
   `links`, `sources`, `sets` (one place name per line, all different), `draft_windows`. Copy `stories/spacejunk`.
3. **Places.** One photographed place per line, never one used before (`daily/used.json` lists them). Fetch new ones
   with `env <id>` lines in `.github/triggers/data3d_assets` (the session's proxy refuses Poly Haven; the workflow
   reaches it), then `git fetch origin data3d-assets && git archive FETCH_HEAD polyhaven | tar -x -C cache`.
   `python daily/scout.py <env>` prints the eight views a place offers: pick the turn whose floor is OPEN where he and
   the props will stand (a photograph's own furniture cannot stand in front of him).
4. **Shots.** `stories/<slug>/shots.py` with `store/director.py`. The grammar that passes (280 verdicts audited
   2026-11-27): the WORLD acts, Data reacts; one locked lens; three props at most; the event beside him, big.
   Look at each: `STORY=<slug> SHOT=n QUICK=1 KEYS=4 python -I store/shots.py /tmp/out 6 30` (four stills, 20 s).
   The showrunner held the first daily short (spacejunk, 44) mainly as `decorative_mascot`: Data stood beside the
   event. In every beat HE does the thing or it happens TO him (he catches it, carries it, dodges it), and every prop
   is the story's own, never set dressing. Fix what the stills show. Two looks a shot, three at most; a shot that still fails loses its hardest element.
5. **Render.** Push `.github/triggers/data3d_ship` with `story=<slug>` and a new `rev=`. It voices, renders every
   shot, assembles, and puts `data3d_short.mp4` on the `preview-renders` branch under `data3d/<slug>/`.
6. **Deliver.** Watch the finished video's contact sheet yourself. Bring the operator the finished video in the
   thread, nothing before it. Add the slug, its places and its gags to `daily/used.json`.

## Rules that stay (the operator's, all still in force)

Data is the approved model, never rebuilt. The world is real, never clay or glossy. Every beat is in its own place;
no set, prop gag or background is reused across videos. Props he is near match the place's look (no "Scooby-Doo
effect"): scanned models or plain real materials, never toy boxes. No hold on a still picture: give him something to
do every second or so (`s.act`). Always look at stills before a full render. Posting waits for the operator.
