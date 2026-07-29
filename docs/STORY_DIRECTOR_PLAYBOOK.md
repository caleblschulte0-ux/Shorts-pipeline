# STORY DIRECTOR PLAYBOOK

Building a True Multi-Clip Internet Story System

**Status**: This document defines the required architecture for upgrading
the Twitch/Kick story system from a clip-compilation generator into a
genuine automated story editor. This is an implementation specification.
Do not treat it as optional creative guidance.

## 1. Product Goal

The final video should feel like a well-edited story someone naturally
encounters on TikTok, YouTube Shorts, Instagram Reels, or X. It must not
feel like: several completed Shorts stitched together, a slideshow, a
presentation, a news package, a documentary with excessive exposition, or
an AI-generated compilation.

A stranger should understand: 1. Who is involved. 2. What happened.
3. Why it matters. 4. How the situation changed. 5. What the payoff was.

The system must construct one continuous narrative from raw source
material.

## 2. Non-Negotiable Rule: No Title Cards

**Full-screen title cards are prohibited.** The video must never stop
showing the source footage merely to display text on a blank screen,
colored background, branded screen, or standalone chapter card.

Do not: fade to black and display text, generate a separate card.mp4,
interrupt a stream clip with a blank chapter screen, pause the story for
labels such as "IT GETS WORSE," insert standalone chapter cards between
beats, or display introductory text before the footage begins.

**Context must appear over active footage.** Allowed examples: "EARLIER
THAT DAY", "THEN HIS FRIEND RESPONDED", "TWO DAYS LATER", "BUT THAT
WASN'T THE END", "HE HADN'T SEEN THE CLIP YET".

Overlay requirements: maximum normal duration 0.7-1.5 seconds; never
cover the primary face or action; semi-transparent background only when
needed; prefer upper-third placement; two to six words; do not obscure
dialogue captions; do not pause, freeze, or replace the footage; no
overlay when the transition is already obvious.

**Opening rule**: the first frame must contain actual moving footage. A
hook may appear over the opening footage, but the footage must begin
immediately underneath it. No logo animation, no title screen, no
introductory card, no fade-in from black, no delayed footage.

## 3. Current Architectural Problem

The old system found clips, asked an AI to order them, edited each clip
separately with the single-clip editor, inserted chapter cards, and
concatenated. That produces an edited compilation, not a unified story —
each clip behaves as its own miniature production (own money moment,
pacing, replay, zooms, effects, beginning and ending).

The upgraded system reverses the relationship: **the story director
controls the whole timeline; individual clips are raw material inside
that timeline.**

## 4. Required System Architecture

1. Source discovery  2. Source expansion  3. Multimodal scene analysis
4. Story eligibility determination  5. Story architecture  6. Story-level
edit planning  7. Rough-cut rendering  8. Narrative review  9. Automatic
revision  10. Final QA and publication.

No stage should silently substitute for another.

## 5. Source Discovery

Search for STORY EVIDENCE, not merely high-performing clips: the original
incident, the immediate reaction, another person's response, later
developments, apologies, explanations, consequences, resolutions,
alternate perspectives. A story cluster is based on an event or changing
relationship — not merely repeated appearances by the same streamer.

**Event identity**: each developing story has an event record that
survives between runs (`state/third_events.json`):

```json
{"event_id": "stable-cudi-argument-202607",
 "people": ["stableronaldo", "cudi"], "event_type": "argument",
 "first_seen": "2026-07-20", "last_updated": "2026-07-23",
 "known_claims": [], "candidate_sources": [], "published_versions": []}
```

## 6. VOD and Context Expansion

A Twitch clip frequently begins after the setup or ends before the
reaction. Use VOD offsets to retrieve ~30-90s before and after promising
sources; transcribe the expanded range; search it for names,
explanations, setup, consequences, reactions.

Expansion triggers: the clip begins mid-sentence; the subject is not
identified; the central action already occurred; the payoff is missing;
the reaction appears cut off; a referenced person hasn't been shown; the
story model marks the clip incomplete.

**When necessary context cannot be recovered, reject the story rather
than inventing an explanation.**

## 7. Multimodal Scene Analysis

Transcripts alone are insufficient. Every candidate source receives a
structured scene analysis from: the complete timestamped transcript,
sampled video frames, face/subject detection, motion and audio activity,
and metadata. Output: people, location, summary, dialogue_beats
(start/end/speaker/purpose), visual_beats, emotional_state,
missing_context, candidate_windows.

**Do not summarize a clip using only its first 40 words.** The complete
relevant transcript must remain available to the story director.

## 8. Story Eligibility Gate

A set of clips is not automatically a story. A valid story contains a
**meaningful change**: allies become opponents; an accusation receives a
response; a challenge is attempted and resolved; someone is embarrassed
and reacts; a misunderstanding is clarified; an event produces
consequences; an argument escalates or ends; a prediction is proven
right or wrong. A collection of funny moments involving the same person
is not a story.

Required elements before editing: Premise, Central question, Setup,
Escalation, Payoff, Ending emotion. Reject when the premise or payoff
cannot be stated clearly.

## 9. Story Structure Selection

Approved structures: **A. Chronological** (setup→escalation→payoff),
**B. Cold Open** (reaction→beginning→payoff; only when the setup is
slower than the reaction), **C. Mystery and Reveal**, **D. Two
Perspectives** (A's action→B's response→consequence), **E. Escalation**,
**F. Before and After**. The model must explicitly choose one structure
and explain why. Do not cold-open merely because a high-motion moment
exists.

## 10. Story-Level Edit Decision List

The director generates a complete story EDL controlling the entire final
timeline: premise, central_question, structure, target_duration, an
opening segment with hook_overlay, beats with source_id/start/end/role/
purpose/transition/context_overlay/effects, and an ending
(reaction_hold). **Every included segment must have a stated narrative
purpose.** If a segment does not add information, emotion, escalation,
or payoff, remove it.

## 11. Dedicated Story Renderer

Create a story-specific renderer. Do not build stories by repeatedly
calling the normal autonomous clip editor and concatenating. Use
low-level functions (extract/reframe/caption/context-overlay/emphasis/
audio/assemble). The story director decides how they are used.

**Required code change**: remove the standalone chapter-card system —
delete `_card()`, `CARD_DUR`, `card_<index>.mp4`, card insertion, and
the `card` field. Replace with `context_overlay` burned onto the
beginning of the corresponding MOVING segment. Do not retain a disabled
card pathway.

## 12. Narrative Cutting Rules

Preserve setup and payoff — protect the exact lines and visuals required
to understand the event; never cut only by speech density, motion
energy, view count, or strongest reaction. Remove repetition (repeated
explanations, greetings, unrelated chat interaction, duplicated
reactions, second versions of the same joke). Start late, end early —
but not too early: leave after the line lands, the facial reaction
completes, the consequence is visible, the emotional beat settles; never
cut the final half-second of a laugh, stunned silence, embarrassment, or
realization. At most ONE replay per story, only when the action was hard
to see, comparison helps, or replaying adds understanding.

## 13. Transition Rules

Preferred: hard cut; J-cut; L-cut; match cut when natural; very short
crossfade only when time has clearly passed. Avoid: title cards, long
fades, excessive transitions, spinning effects, template wipes, fake
camera flashes at every cut.

## 14. Audio Direction

One consistent audio mix: normalize dialogue between sources; suppress
severe volume differences; remove abrupt starts/endings; duck music
under dialogue; support J/L cuts; preserve reaction sounds; consistent
loudness. Music optional, never overpowering or dishonestly dramatic.
Narration only when essential context cannot be shown; brief, verified,
no motive claims, never replacing footage that could show it better.

## 15. Visual Direction

Maintain visual continuity across streams: consistent face sizing when
practical; no radical crop jumps without reason; preserve important
action; split-screen when two perspectives matter; overlays never cover
the subject. Layout decisions per story beat according to narrative
purpose.

## 16. Effect Budget

Global maximums per story: major replay 0-1; slow-motion 0-1; strong
impact 0-2; large emphasis word 0-2; context overlays only when
necessary; emoji overlays normally 0; chapter/title cards 0 —
prohibited. The climax receives more emphasis than the setup.

## 17. Context Overlay Rules

Overlays prevent confusion, never decorate: use for a time jump, speaker
change, location change, new person, or why a response matters. Good:
"EARLIER THAT NIGHT", "HIS FRIEND SAW THE CLIP", "THEN SHE RESPONDED".
Bad: "THE STORY BEGINS", "IT GETS CRAZY", "THE CLIMAX", "PART TWO",
"WHAT HAPPENS NEXT". Always on moving footage.

## 18. Rough-Cut Narrative Review

Provide the critic with the premise, EDL, final timestamped transcript,
timestamped contact sheet, source identities, and duration. It judges:
can a stranger explain it; is the central question clear; is anyone
shown before introduction; is information missing/repeated; does every
beat advance; is chronology clear; does the opening create curiosity and
the ending answer it; is anything misleading; is emphasis correct; does
it feel like ONE story. It returns timestamped revisions with a
publish/story_score verdict.

## 19. Automatic Revision Loop

Permit ONE controlled revision (adjust boundaries, remove repetition,
extend a reaction, add/remove an overlay, change a transition, rebalance
audio, remove an effect). After it: narrative review again, mechanical
QA, publish only if both pass. If still confusing, abandon and use a
normal clip.

## 20. Story-Specific QA

Reject when: the opening refers to footage that no longer appears; the
payoff beat is missing; a time jump misleads; unrelated events are
combined; a fact repeats excessively; an overlay contradicts footage; a
person is not introduced; no meaningful change; the ending feels cut
off; the result resembles disconnected clips. Stricter on coherence
than cosmetics.

## 21. Fallback Rules

Abandon to a normal clip when: no recoverable setup; no payoff; the
event cannot be verified; sources cannot download; the story requires
invented narration; the timeline confuses; fewer than two meaningful
beats survive; narrative QA still fails after one revision. **Do not
force the story slot to produce a story. A good standalone clip is
better than a fake narrative.**

## 22. Measurement

Track per story: story_structure, n_beats, duration, used_narration,
used_vod_expansion, context_overlay_count, replay_count, revision_count,
narrative_score. When analytics allow, measure opening retention, drop
at source switches and overlays, completion through payoff, replays,
comments, shares, search traffic, and performance by structure. Do not
increase story volume until ~20-25 mature story posts provide evidence.

## 23. Implementation Sequence

**Phase One (Coherence)**: scene reports; VOD expansion; event records;
structure selection; exact in/out points; rich story EDL; dedicated
renderer; removal of title/chapter cards; narrative QA; one revision
pass. **Phase Two (Editing Quality)**: J/L cuts; effect budgeting;
dialogue normalization; overlays over live footage; visual continuity;
optional verified narration. **Phase Three (Learning)**: optimize
structures, durations, beat counts, openings, switch frequency, overlay
frequency, narration, endings — only after coherence is reliable.

## 24. Required Acceptance Tests

**Title-card prohibition**: no standalone card video generated; no blank
or colored text screen; every frame contains source footage; context
text only over moving footage. **Narrative control**: the director
selects exact in/out points; each segment has a documented purpose; the
renderer follows the story EDL; beats do not independently add replays
or slow motion. **Context recovery**: mid-event clips trigger VOD
expansion; expanded context is incorporable; missing context causes
rejection, not invention. **Story QA**: a confusing timeline fails; a
repeated explanation is detected; a missing payoff fails; a misleading
time overlay fails; a coherent setup-to-payoff story passes.
**Revision**: a critic-requested adjustment changes the second render;
only one revision allowed; continued failure falls back to a normal
clip.

## 25. Final Creative Standard

The viewer should think: "That was a good clip explaining what
happened." Not: "This is four Twitch clips stitched together." / "Why
did it stop for a title card?" / "I have no idea who these people are."
/ "The AI made this look more dramatic than it was."

**The strongest system behavior is restraint.** Use only the context,
effects, cuts, and narration necessary to make the real event clear and
compelling. The story is the product. The editing exists to make the
story understandable.
