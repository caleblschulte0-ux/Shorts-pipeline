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
