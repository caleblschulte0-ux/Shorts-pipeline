# THE PRO DOCTRINE — how the system improves from here (operator spec, 2026-07-15)

The 90-second cut proved the new foundation works: **real footage + designed 2D
+ narration + music, no cartoon/chart spine.** This document is the governing
contract for every render from now on. Do NOT restart the renderer again unless
the footage-plus-2D architecture fails across multiple different topics.

The permanent rule, above everything:

> **Use the simplest visual method that produces the strongest finished result.
> The system is successful when viewers cannot tell which parts were automated,
> because every visual choice feels deliberate.**

Priority order when choosing how to show a beat:
1. Strong real footage
2. Excellent editing and pacing
3. Designed explanatory 2D
4. Clean sound and narration
5. Rare, proven 3D
6. Technical novelty (last — the channel does not win by using the most tools)

---

## 1. Smart footage selection — inspect the EXACT window, not the source
A clip is never chosen because the search terms matched. Before a segment is
committed, the system inspects the **exact time range it plans to use** (not a
general sample of the source) and analyzes:
- does the subject actually appear, and stay visible for the whole window;
- is it live action (not simulation / animation / diagram / title card / ad);
- does the window contain unrelated graphics, embedded text/captions, or
  dominating logos/watermarks;
- is the camera movement usable (not a jarring cut/lurch mid-window);
- does it match the narration at that exact moment;
- is it visually compatible with the surrounding shots.

**Reject a segment containing any of:** educational diagrams where real footage
is expected · unrelated animations · title cards · black frames · credits ·
presenter intros · text-heavy frames · repeated shots · low-resolution imagery ·
accidental UI/player controls · sudden visual changes inside the window.

When a window fails, try the next clean window, then the next source, then fall
back to the beat's designed-2D/animation alternative — never ship a bad clip.
(This is what caught us: the ICON "Airglow" clip is a *produced* piece with a
nitrogen molecule diagram spliced in; a black-frame-only scan missed it.)

## 2. A real designed-2D language — editorial motion, not prettier charts
Do not replace old bar charts with slightly nicer bar charts. Build reusable
templates keyed to the **idea being explained**, not to a chart type:
relative scale · accumulation · movement · cause and effect · hierarchy ·
chronology · transformation · comparison · uncertainty · geographic change ·
physical mechanisms.

Every 2D beat must have: one obvious focal point · strong visual hierarchy ·
limited text · intentional typography · smooth motivated transitions ·
consistent spacing · a controlled color system · full use of the frame · a
direct connection to the narration. **Numbers should interact with the footage
or visual world whenever possible** rather than float as isolated dashboard
elements.

## 3. 3D is experimental and optional — not approved for automatic flagship use
A 3D sequence may enter a video only when ALL hold:
- footage cannot show the required event/perspective;
- 2D cannot explain it as effectively;
- the sequence has a clear narrative purpose;
- the final rendered pixels look professional;
- it does not resemble the old cartoon-globe style;
- it passes independent visual review;
- it fits the render budget;
- a strong 2D or footage fallback exists.

For every proposed 3D moment, compare **A: real footage · B: designed 2D ·
C: custom 3D**, and use C only when it clearly wins. Never add 3D for variety.
If 3D repeatedly fails, auto-use the approved 2D/footage fallback and continue.

## 4. Whole-video direction — plan a rhythm, don't pick shots independently
Every video has: a strong full-frame opening · a mix of real-world footage and
explanation · escalating visual scale/consequence · deliberate moments of visual
simplicity · no repeated visual grammar for too long · a clear payoff · an
ending stronger than the opening.

**Before rendering, generate a visual plan** that, for each shot, states: what
the viewer should look at · what visual system is used · why it is appropriate ·
what changes during the shot · how it connects to the previous shot · how it
advances the viewer's understanding. Reject long runs of disconnected footage,
repeated number cards, or graphics that merely restate the narration.

## 5. Independent validation from the rendered pixels
Internal logs and a successful render do NOT prove quality. Every finished video
is reviewed from pixels alone (the blind judge panel) for: does it look like a
real documentary channel · any section automated/cheap · templated graphics ·
footage relevant and clean · obvious subject · intentional transitions ·
narration and visuals agree · complete ending · any generated scene that should
have been footage.

On a serious visual failure, Claude autonomously: (1) identifies the failing
shot type, (2) replaces/redesigns it, (3) re-renders only the affected section,
(4) re-runs the full review, (5) **preserves the fix as a reusable system
improvement** (a rule here + code, not a one-off patch). Do NOT ask the owner to
diagnose the failure.

---

*Success metric: a viewer cannot tell which parts were automated, because every
visual choice feels deliberate.*

---

# THE EDITORIAL DIRECTION SYSTEM (operator spec, 2026-07-15, after the 89.9s render)

The 89.9s render proved the RENDERING FOUNDATION (real footage + designed 2D +
narration + music + assembly, consistent navy/white/gold identity, full-frame
footage). It did NOT prove the DIRECTING SYSTEM. The pipeline still thinks like
an asset assembler:

    narration sentence -> classify footage|graphic -> pick ONE visual ->
    hold it until the sentence ends -> next sentence

That is why the video is segmented: prolonged number cards, prolonged sentence
cards, one reused comparison, repeated Earth footage, rigid
footage->graphic->footage alternation, and an ending whose spoken payoff and
visual payoff land separately. **The renderer is the execution layer, not the
intelligence.** The next leap is a story-to-visual DIRECTION system.

**3D is frozen out of the production path** (experimental R&D lane only; it may
return only when it beats footage AND 2D and passes both the pixel and the
editorial judge). The unsolved problem is editorial intelligence, not photoreal.

## The law that must change
A beat may NOT be represented by one unchanged visual for its whole narration
window merely because that visual stays relevant. One narration beat may need
three or four visual developments. Counters ticking, slight zooms, ambient
drift and particle noise DO NOT count as development.

## THE BEAT CONTRACT (declared before any media search or render)
Every beat carries: narrative_job (hook/setup/proof/mechanism/comparison/
escalation/twist/payoff/bridge) · starting_belief · new_understanding ·
central_question · primary_subject · required_action · visual_function
(evidence/explanation/experience/comparison/atmosphere/transition) ·
preferred_mode (footage/footage+annotation/designed_2d/still+motion/exp_3d) ·
phases (setup→development→proof→payoff→bridge) · max_unchanged_duration ·
text_role · transition_requirement · ending_state · fallback · failure_risks.
The renderer NEVER receives just "show Earth's speed" — it receives a directed
assignment.

## THE SHOT CONTRACT (each shot inside a beat)
start/end · narration_span · narrative_function · source_type · source_candidate
· exact_segment · primary_subject · visible_action · begin_state · end_state ·
camera/motion direction · visual_energy · overlays · text_role · transition
in/out · reuse_status · expected_information_gain · exhaustion_trigger · fallback.

## PACING LAWS (permanent)
- No full-screen number card may carry a major beat by itself.
- No full narration sentence may sit on an empty background as a fallback.
- No unchanged graphic may remain solely because narration continues.
- No chart may stay the primary visual after its comparison is understood.
- No footage may be chosen only because it matches a topic keyword.
- No visual grammar may repeat consecutively without development.
- No repeated source footage without a declared callback purpose.
- No weaker visual after the final payoff.
- Intentional stillness is allowed only when it creates tension, comprehension,
  or emotional weight. Camera motion may never substitute for information.

## TEXT ROLE SYSTEM
Every text use is classified: title · hero_value · annotation · quote · caption
· emotional_thesis. A full narration sentence does NOT automatically become an
emotional-thesis card. Full narration paragraphs on blank backgrounds are
PROHIBITED as a fallback. A standalone number must begin transforming into
explanation within a few seconds. Supporting text attaches to a visible subject.
Text-only scenes require a declared editorial purpose — never a media-search
fallback.

## FOOTAGE = SHOT INTENTION, not keyword search
Search from the intended visual ACTION and narrative JOB, not transcript nouns.
For every candidate the selector knows: what the audience believes now, what
they should understand after, the subject that must appear, the action that must
occur, whether the shot is evidence/atmosphere/explanation/transition, the
needed motion direction, how it connects to neighbors, what must NOT appear,
whether text/diagram/still is allowed, whether exact real footage is required.
A visually impressive but narratively generic clip LOSES to a plainer clip that
communicates the idea precisely. (The rocket open looks pro but says "rockets
are fast," not "you are moving while apparently still.")

## EDITORIAL 2D — organized by explanatory FUNCTION, not chart type
relative_motion · scale · accumulation · cause_and_effect · mechanism ·
transformation · spatial_relationship · hierarchy · uncertainty · chronology ·
annotation. Bars/lines/gauges remain SUPPORTING tools; a chart may not carry a
major beat without transforming into another explanatory mode. Information
display != visual explanation != visual evidence != visual experience.

## FOOTAGE + GRAPHICS COMPOSITING (explicit layers)
base_footage · environmental_graphic · subject_highlight · data_annotation ·
typography · transition_element. Graphics should frequently ANNOTATE or
TRANSFORM footage, not replace it with a separate card. (footage_number was the
first step: number over footage.)

## CONTINUITY DIRECTOR
Plan each transition on motion/direction/subject-position/scale/color/
brightness/momentum/semantic-relationship/persistent-element. Choose among hard
cut · motion match · shape match · scale match · graphic carryover · tracked
annotation · footage↔diagram transform · sound bridge · intentional contrast.
Never pick a transition because it "looks cool"; preserve continuity or create
deliberate contrast. Break the rigid footage→card→footage alternation.

## REUSE / CALLBACK DETECTION
Perceptual-hash repeated source footage. Reuse must be labeled intentional
(opening callback / before-after / transformed context / recurring anchor /
refrain) with altered context, else auto-replace with a different shot.

## ENDING CONTRACT (planned BEFORE the middle shots)
The final spoken payoff and final visual payoff land TOGETHER. The ending
resolves the opening / reinterprets it / reveals the largest context / shows the
consequence / creates an intentional loop. After the primary payoff, the video
may NOT return to an earlier weaker visual state.

## VISUAL EXHAUSTION
A visual is exhausted when the subject is established, the only remaining change
is a number incrementing, the composition is unchanged, narration has moved to a
new relationship, and the next seconds only reinforce a known fact. On
exhaustion: transform · reveal a layer · change scale · cut to evidence · change
reference frame · annotate a new relationship · introduce a consequence · or
exit. Never solve it with arbitrary camera movement.

## JUDGE PANEL EXPANSION (repairable labels, not just scores)
Keep the blind PIXEL-QUALITY judge (render only). Add:
- EDITORIAL-ALIGNMENT judge (beat contract + narration + render, no code): does
  the visual do the actual narrative job, or is it only topically related?
- CONTINUITY judge (whole timeline): flow, repeated grammar, hard alternation,
  motion/color/scale continuity, accidental repetition, pacing.
- VISUAL-EXHAUSTION judge: where the eye goes, shots held past their information,
  text-as-fallback.
- PAYOFF judge: does the ending resolve the opening; do the strongest line and
  image land together; are the final seconds weaker than earlier material.
Labels: TOPICAL_BUT_NOT_EDITORIAL · VISUAL_EXHAUSTED · STATIC_NUMBER_CARD ·
TEXT_AS_FALLBACK · CHART_CARRYING_BEAT · FOOTAGE_GRAPHICS_DISCONNECTED ·
ACCIDENTAL_REUSE · PAYOFF_SPLIT_FROM_IMAGE · POST_CLIMAX_DOWNGRADE ·
SHOT_TOO_LONG · TEMPLATE_REPETITION.

## AUTOMATED REPAIR (labels -> strategies; switch modes, don't polish forever)
STATIC_NUMBER_CARD -> attach value to footage / split beat into phases / build
explanation / add consequence / shorten. TOPICAL_BUT_NOT_EDITORIAL -> regenerate
the media query from the narrative job. TEXT_AS_FALLBACK -> source evidence or
construct a designed visual. CHART_CARRYING_BEAT -> transform into mechanism/
scale/environment/consequence. PAYOFF_SPLIT_FROM_IMAGE -> rebuild the ending as
one unit. After repeated failure, switch visual mode rather than re-polishing.
Learn repair CLASSES; don't treat every failure as novel.

## MEDIA-AVAILABILITY TIERS (do NOT overfit to NASA)
A: exact real footage · B: exact still + restrained motion/crop/annotation ·
C: designed explanatory 2D (invisible/abstract/historical) · D: reconstructed
environment (stylized 2D/maps/archival/simulated data) · E: proven 3D. NEVER
fall back to generic stock just because exact footage is missing.

## AUDIO FINISHING
Classify pauses by function (comprehension/suspense/transition/emotional/breath/
accidental-TTS); remove repeated sentence-boundary TTS gaps; align intentional
pauses to visual/musical events; true-peak limit at <= -1 dBTP; validate the
ENCODED deliverable (current mix ~-14.2 LUFS but true-peak over 0 dBFS).

## AUTONOMY + EFFICIENCY
Owner receives concise reports only — never asked to review contact sheets, code,
or technical choices. Claude owns implementation/testing/diagnosis/repair/
rollback/promotion/quarantine. Tiered rendering (storyboard -> lowres timeline ->
judge -> re-render only failing segments -> full assembly -> audio/encode QA ->
publish or quarantine). Cache stable pieces (segments, narration, music,
graphics, judge results, hashes). New directing rules enter via canaries; auto-
revert + regression-case on worse output.

## VALIDATION BAR (before the general engine is production-ready)
Prove on THREE archetypes, each passing all judges: (1) space/scale, (2)
mechanism/engineering (diagram-heavy), (3) non-space investigative/biological/
historical (incomplete footage). If it only works when NASA already filmed the
subject beautifully, it is not a general documentary engine.

## THE ARCHITECTURE
research -> story model -> BEAT INTENT PLANNER -> visual director ->
footage/2D/exp-3D choice -> shot sequence planner -> footage selector ->
2D designer -> continuity+compositing director -> audio director -> renderer ->
independent judge panel -> automated repair -> publishing -> analytics learning.
The renderer is the execution layer. The intelligence is the planning + judging.
