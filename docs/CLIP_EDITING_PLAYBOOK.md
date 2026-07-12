# Clip Editing & Quality Playbook (third channel)

Operator-authored doctrine for the Twitch/Kick/Rumble clip channel. This is
the canonical reference for how the auto-editor (`third_capture/auto_edit.py`
+ `third_capture/clip_edit.py`) should behave. Fix the SYSTEM, not individual
videos. **Crop stability first, effects second** — better emojis and SFX will
not save a clip when the camera is pointing between both speakers.

Permanent doctrine:
- Subject visibility is more important than motion.
- Stable framing beats incorrect tracking.
- An effect is only good when it lands on the correct moment and improves it.
- When uncertain, preserve the original moment instead of inventing a bad edit.
- Good editing makes the moment feel stronger, not the editor more visible.

---

## Implementation status (keep this current)

Done:
- **No panning** — the crop is one static framing per clip; the camera never
  slides (killed the motion-sickness + midpoint-trap pan).
- **Never crop out the money shot** — face-crop only when faces are present in
  ≥50% of samples AND the dominant face is large (≥32% frame height, a real
  close-up). Otherwise show the WHOLE frame (blur-fill) so gameplay/action
  payoffs (bridge jump, drown, kill) are never sliced out. (§6 Law 8/9, §8)
- **Camera effects dialed back** — gentle punch (~1.06–1.12), subtle/zero
  shake; time effects (slow-mo, replay, dead-air) carry pacing. (§13, §19)
- **Audio preserved through the money moment** — slow-mo + replay are no longer
  muted; audio is time-stretched so sound never cuts off under the overlays.
  (§9 audio-cut rules, §13)
- **Overlay layer** — reaction emoji burst, word slam, anime speed-lines, all
  land on the money moment; degrade safely in the render ladder. (§11, §14)
- **Ironclad render ladder** — full → text-only → captions → plain → raw; a
  clip always ships. (§18 fallback ladder)
- **QA gate + vision review** (`third_capture/clip_qa.py`, wired into
  `run_third.py` before upload) — mechanical checks (black/frozen frames,
  ≥2.5s silence gaps, abrupt silent endings, A/V drift, duration bounds,
  face-crop-lost-the-face) + a labeled 12-frame contact sheet reviewed by the
  headless Claude CLI against the §17 checklist. A fail rejects the clip
  before upload (slug stays unposted; a different clip competes next run);
  QA-internal errors fail OPEN so the gate can't lose good clips. (§16, §17)
- **Defense in depth against bad INPUTS** — every production failure was an
  unusual input breaking an assumption, found too late. Three layers now
  catch them earlier and cheaper:
  - **Pre-flight** (`clip_qa.preflight`, in `run_third` right after
    download) validates the source in ~2s (streams present, ≥6s, ≥640px)
    before whisper/author/render spend 100s+; a bad source is blocklisted
    like a QA rejection.
  - **QA-rejected blocklist** — a clip that fails QA (or pre-flight) writes
    a `rejected-<slug>` entry to the posted log, so `posted_keys` can never
    re-pick it — this run or any future run. (Fix for: one 2s clip ate four
    slots back-to-back.)
  - **Sparse-speech cut guard** — when the transcript-derived cut is <8s or
    <4 words, keep the whole clip (front 45s); a near-silent clip's moment
    is visual and words can't locate it.
  - **CI smoke suite** (`scripts/smoke_third.py`, `.github/workflows/
    third-smoke.yml`) runs the REAL `edit()` + pre-flight + QA on synthetic
    tricky-input fixtures (apostrophe hook, 1-word clip, no-speech clip,
    corrupt/tiny sources) on every push to the third pipeline — regressions
    go red in CI (seconds, no network/secrets) instead of on the channel.
- **Shot-plan layer** (`third_capture/shot_plan.py`) — analysis on the SOURCE
  cut (§3: subject tracks with presence/size/talk-activity/position-jitter,
  scored — never just the largest face), layout classification (closeup /
  two_shot / split / facecam_gameplay / wide), an explicit reasoned Shot plan
  with a subject-containment (midpoint-trap) guard, executed on the program
  with static ffmpeg crops. Designed layouts: stacked facecam-panel +
  FULL-WIDTH gameplay (the action can't be cropped out) and stacked
  split-screen for far-apart two-shots (both people always visible — no
  midpoint, no ping-pong cuts). The plan + reasons land in the ledger
  (`shot_plan`). Wide/uncertain → blur-fill whole frame. (§3-§8)

- **Director-chosen cut boundaries (§4-5, §9)** — the author brain reads the
  TIME-STAMPED transcript and picks `edit.cut {start,end}`: begin at the
  setup (never mid-story), end after the full payoff AND its reaction. That
  window drives the render, replacing the blind first-word/last-word trim
  when the brain is confident. It also returns `edit.complete` — false when
  a clip starts mid-action with no context or its payoff is cut off; such
  clips are skipped + blocklisted (a confusing clip is worse than a lost
  slot). Both are validated against the real clip length; bad/absent values
  fall back to the heuristic tight-cut. (Directly targets: "cuts off before
  the payoff" / "starts in the middle so the viewer is lost".)
- **Clip boundaries (§9, heuristic fallback)** — never open on dead air; 2.2s
  reaction tail after the last word (the reaction IS the payoff); the 45s cap snaps back to the
  last word that fully fits (+1.0s) instead of slicing mid-word; captions
  only for words entirely inside the cut; 0.25s audio fade-out so no clip
  ends on an abrupt chop.
- **Spatial safe-zones (§15)** — the shot plan exports face bands in output
  coordinates; the emoji burst and word slam pick a vertical position that
  avoids faces and the caption zone from a candidate list (no hardcoded y).
- **Dimensional emoji set (§11)** — Microsoft Fluent UI Emoji 3D (MIT):
  one cohesive glossy/dimensional iOS-style set; the flat Noto generator
  remains as an offline fallback only.

- **SFX mixing rules (§12)** — all SFX mix into one bed that is sidechain-
  DUCKED by the dialogue: a boom can never bury what the streamer says.
- **Learning loop (§20)** — every run appends a compact record (layouts,
  render levels, QA verdicts, self-heals, errors) to
  `state/third_qa_stats.json` (last 30 runs, committed by CI) so recurring
  failure categories become visible across batches and turn into rules.
- **Self-healing QA (§18, beyond the playbook)** — a clip that fails QA is
  automatically re-rendered ONCE as the plain simple look and re-inspected
  before the slot is given up: "a clean basic clip is better than an
  ambitious broken clip", enforced by the pipeline itself.
- **Edit Director (beyond the playbook)** — the author brain (Claude, Groq
  fallback) that already reads every transcript now also DIRECTS the edit:
  picks the word slam VERBATIM from what was actually said (validated
  against the transcript — an invented word is discarded), chooses the
  reaction emoji from the asset whitelist, and can veto the replay when the
  moment is pure talk. Content-aware judgement layered over the signal
  heuristics, which remain the fallback when no author is available.

Not yet built (priority order per §21):
1. **Active-speaker shot sequences** — multi-shot plans that cut between
   speakers with hysteresis + minimum shot duration. DELIBERATELY DEFERRED:
   the operator's "let the camera be" doctrine outweighs it, and the
   split/stacked layouts already keep both speakers visible. (§5-§7)
2. **Setup/escalation/payoff narrative detection** — deeper §9: classify the
   beats and trim escalation-aware, beyond the word-safe bounds now in place.
3. **Per-frame occupancy maps** — full §15: hands/UI/gameplay-focus occupancy
   per frame (current safe zones are face bands + caption band).

---

## The playbook

### 1. Current system failures
Pans and causes motion sickness; stops between two speakers; tracks the wrong
person; crops the main speaker out; switches framing too late; cuts before
setup/payoff; adds effects at the wrong moment; places graphics over faces or
gameplay; cheap/inconsistent emoji; assumes motion beats a stable crop; renders
without checking final spatial/timing decisions. These reveal missing engine
laws, confidence handling, and QA gates.

### 2. Required pipeline
1 source analysis → 2 moment/narrative analysis → 3 speaker/subject tracking →
4 shot-plan generation → 5 crop/camera generation → 6 caption generation →
7 enhancement planning → 8 final composition → 9 automated spatial+temporal QA →
10 low-res review render → 11 final render. Do not crop/edit directly from raw
detections without a shot plan.

### 3. Source analysis
Record resolution, fps, duration, audio channels, faces + bounding boxes over
time, speaker changes + confidence, gameplay/screen regions, webcam regions,
static overlays, existing subtitles, chat boxes, alerts, logos, key objects,
source cuts, silences, laughter, yelling, audio peaks, likely setup/payoff/
reaction. Classify layout: solo full-screen; gameplay+facecam; two-person
conversation; podcast/interview; multi-person call; reacting to another video;
split-screen debate; gameplay without facecam; screen/browser; mixed/uncertain.
Different crop logic per class.

### 4. Main subject
The largest face is NOT automatically the subject. Score by: who is speaking,
who is discussed, who delivers setup/payoff, whose reaction matters, who is
visually active, who the premise centers on, how long they stay relevant,
detection→speaker confidence. Label per segment: PRIMARY / SECONDARY /
REACTION / IMPORTANT_SCREEN_CONTENT / BACKGROUND. The speaker, the person to
watch, and the person whose reaction is the joke may all differ — hold/cut to
the reaction subject when the silent reaction is the payoff.

### 5. Shot plan before camera motion
Create an explicit shot timeline before rendering (start, end, target subject,
framing mode, crop coords, reason, tracking confidence, transition, whether
captions/overlays occupy screen). The renderer executes the plan; it does not
improvise camera movement frame by frame.

### 6. Camera & crop laws
1. **Never frame empty space between subjects.** Frame one, show a deliberate
   wide, use split-screen, or cut — never settle on the midpoint. QA:
   MIDPOINT_TRAP.
2. **Stable shots are default.** Tracking dead zone; the crop stays still while
   the subject is in a safe central region; reposition only near the edge.
3. **Camera motion requires narrative motivation** (subject change, reaction
   becomes important, action elsewhere, layout change, deliberate punch-in).
   Not: a face moved slightly / motion available / want variety / tracker
   updated.
4. **Cuts more than pans** for separated speakers; short pans only when close +
   quick + establishing; never pan back and forth.
5. **Hysteresis.** Don't switch subject on a momentary higher score — require a
   meaningful, sustained advantage or a major event.
6. **Minimum shot duration.** No switching on tiny conversational changes; hold
   reactions; avoid cuts under ~1s; longer holds in setup, faster near payoff.
7. **Protect faces/heads.** Preserve full face, headroom, chin, shoulder
   context; never crop through eyes/mouth/chin/forehead/important hands.
8. **Limit digital zoom.** Don't enlarge a low-res facecam to blur; use a
   designed layout / enlarged facecam with background / wider source.
9. **Fall back safely** on low confidence: previous stable crop, wider crop,
   split-screen, or original composition letterboxed. Never make aggressive
   camera moves from weak detections.

### 7. Two/multi-speaker
Mode A intentional two-shot (both faces large, both reactions matter, close
enough). Mode B speaker cuts (alternating dialogue, expressions matter, too far
apart). Mode C reaction priority (hold the reaction that is the payoff). Mode D
designed split-screen (both must stay visible, too far apart, cutting hides
simultaneous reactions). 3+ people: identify the active pair/dominant subject,
don't chase every minor change, widen when chaotic, cut to individuals only
when meaningful.

### 8. Gameplay & facecam
Decide which carries the moment. Face-driven (reaction/argument/rage/laughter):
enlarge the face, keep enough gameplay context. Gameplay-driven (kill/fail/jump-
scare/glitch/reveal/play): gameplay primary, facecam as a secondary reaction
panel. Mixed: stable stacked / PiP. Never rapidly pan between regions — compose
both.

### 9. Boundaries & cutting
Identify setup / escalation / payoff / reaction / natural exit. **Start** early
enough to understand who/what/the expectation; trim dead time, keep context.
**End** not on the punchline — preserve the laugh, stunned silence, reaction,
realization, brief aftermath. **Audio:** never cut mid-word, mid-critical-
breath, right before laughter, or between statement and its response; use short
handles + natural silence; no abrupt cuts to hit an arbitrary duration.

### 10. Captions
Mandatory unless format says otherwise. Accurate word timing; high contrast;
consistent font; mobile-readable; sensible phrase grouping; active-word
highlight; speaker differentiation; profanity per channel rules. Must NOT cover
faces/mouths/gameplay UI/source captions/reaction graphics/platform UI. Dynamic
safe zones from the current crop. Emphasis via scale/weight/color/brief bounce/
underline/subtle glow — do not aggressively animate every word.

### 11. Emoji
Cohesive, polished, iOS-style: dimensional, glossy, expressive, readable,
consistent lighting, transparent, high-res. Don't mix flat/3D/native/sticker/
low-res. One approved set channel-wide; if Apple assets are unavailable/
unsuitable, use a legally usable set with the same qualities. Must not cover
faces/captions/gameplay/UI or sit offscreen. Enter exactly when the emotion/
joke lands; fast in, brief hold, clean exit. 0–3 meaningful emoji per clip; an
emoji must add interpretation/exaggeration/punctuation/clarity — if removing it
doesn't weaken the moment, don't add it.

### 12. Sound effects
Punctuate important edits (impact/pop/whoosh/scratch/rewind/bass/sparkle/error/
riser/comedic-silence/crowd). Not constant. Each SFX aligns tightly to a
specific visual/narrative event. Mixing: dialogue always understandable; no
clipping; normalize; duck under speech; avoid harsh repeated highs.

### 13. Zooms, pauses, replays, slow-mo
Punch zoom for reaction/punchline/realization/mistake/object — short, no
stacking. Pause/freeze with a purpose (notice something, comedic timing,
annotate, interrupt before payoff). Replay when hard to notice or worth seeing
again — usually shorter, highlight the area, add label/zoom/reframing, don't
just duplicate. Slow-mo for physical reactions/fails/precise plays/reveals/
comedy — not ordinary dialogue; preserve audio intelligently or replace with
designed sound when slowed speech is ugly.

### 14. Effect planning
Author effects on a timeline before rendering (timestamp, trigger, target,
duration, position, safe-zone check, audio relationship, reason). Do not place
effects from transcript-only timestamps; verify against rendered frames + audio
waveform.

### 15. Spatial composition
Before any overlay compute occupied regions (faces/hands/gameplay focus/
captions/source UI/facecam/objects/existing text/branding) into a per-frame
safe-placement map. Overlays use safe regions, not hardcoded coords. No safe
region → drop the optional overlay, reposition captions, redesign, or delay.

### 16. Automatic QA gates
Fail/flag on: primary subject missing during a relevant segment; crop center
between subjects (MIDPOINT_TRAP); face cut badly; excessive switching; back-and-
forth pan; uncomfortable acceleration; aggressive motion on low confidence;
blank space; action outside the crop. Motion-sickness: measure pan velocity/
acceleration/reversals/switch frequency/continuous-motion duration. Subject-
visibility per segment. Caption QA (offscreen/covers face/timing/readable/line
breaks/source conflict). Effect QA (timing window/full visibility/no covering/
audio align/no stuck effect/not too dense). Cut QA (cut-off words/missing setup/
abrupt end/payoff without reaction/repeated/black/frozen frames/audio breaks).

### 17. Human-like visual review
Generate low-res preview, contact sheet, frames around every crop change +
effect, crop-center movement graph, subject-visibility timeline, effect list.
Vision pass answers: right person visible? crop intentional? ever between
people? nauseating? effects covering content? setup/payoff preserved?
professional? anything broken? Low confidence → do not auto-publish.

### 18. Fallback ladder
1 stable crop on confirmed primary subject → 2 stable wide showing all
relevant subjects → 3 designed split-screen → 4 original composition in a
branded vertical canvas → 5 minimal captions-only → 6 reject. A clean basic
clip beats an ambitious broken one.

### 19. Restraint
Don't force every enhancement into every clip. A clip can be excellent with
stable framing + clean cuts + strong captions + one well-timed zoom + one SFX.
Judge by clarity/timing/impact/visibility/polish/restraint, not effect count.

### 20. Learning loop
After each batch identify the weakest failure category and turn every recurring
failure into a new QA rule / layout template / crop heuristic / confidence
threshold / fallback / effect preset / test fixture. Don't fix isolated clips
without improving the shared system.

### 21. Implementation priority
Phase 1 stabilize cropping (subject timeline, active-speaker, shot-plan layer,
dead-zone, hysteresis, midpoint-trap detection, stable fallbacks, pan velocity/
reversal limits) — before any more effects. Phase 2 clip boundaries. Phase 3
spatial awareness. Phase 4 effects presets (each with timing + spatial QA).
Phase 5 final quality gate (preview, contact sheet, movement graph, visibility
report, effect timeline, vision review, operator approval until proven).

### Final standard
The viewer should think "that was a really well-edited clip" — not "why is the
camera moving / where did the main person go / why is that emoji on his face /
why did it cut before the reaction." Succeed when the system reliably knows who
matters, what matters, when the moment lands, where to look, when to enhance,
and when to leave the clip alone.
