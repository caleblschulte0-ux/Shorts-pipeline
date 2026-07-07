# THIRD CHANNEL ("third") — brain playbook: THE EXPERIMENT CHANNEL

**Working title:** *Overload* — a mass-appeal, entertainment-first channel:
**"We run wild experiments. You watch them succeed — or break."**

The channel slug is `third`; every package sets `"channel": "third"` and the
uploader routes it to the `YOUTUBE_TOKEN_JSON_THIRD` secret. See §12 for
wiring and isolation.

This file is the channel. The brain reads it first and treats it as law.
Operator feedback gets written back INTO this file as permanent doctrine.

---

## 0. The money-printer doctrine (operator law, 2026-07-07)

The funnel is **mass audience → millions of views → brand → affiliate /
digital products / courses / sponsors** — NOT "niche tool → hope the right
person watches → hope they buy." Shorts is entertainment first; even
educational channels are entertaining. B2B utility content (workflow
tutorials, "stop doing X manually") is BANNED here — that material belongs
in a separate LinkedIn/X/SEO funnel, never on this channel.

The prior "Proof Mode" identity failed the mass test ("I don't clean
spreadsheets" → swipe). Its production machinery survives — the capture
harness, proof ledger, and truthfulness rules now serve SPECTACLE, not
tutorials. Same capability, opposite psychology:

- ~~"Stop cleaning spreadsheets by hand"~~ → **"I built the messiest
  spreadsheet ever. One command gets one shot to fix it."**
- ~~"This tool dedupes CSVs"~~ → **"Can it fix 10,000 broken rows before
  you can blink?"**

A tutorial promises usefulness. A challenge promises an OUTCOME — and the
viewer stays to see if it survives.

## 1. Identity (one swipe)

**Every video is an experiment with visible stakes: we build something
extreme, push it until it succeeds or breaks, and you watch the outcome
live.** Challenges, stress tests, simulations, impossible comparisons,
satisfying transformations. The viewer never needs a job, a tool, or
context to care — only eyes.

Distinct from the other channels by verb: channel 1 *tells* quirky news,
channel 2 *explains* data facts, channel 3 **RUNS experiments**.

## 2. The iron gate — the mass-appeal test (a package may not enter unless…)

> **The premise is understandable in ONE SECOND by someone with no job, no
> tools, and no English.** Concretely, every package must pass ALL of:
> - **The mom test / 16-year-old test / Brazil test** — would a teenager, a
>   parent, and a non-English speaker all get it and want the outcome?
> - **Works muted** — the visual alone carries the stakes and the outcome.
> - **One number of stakes** — the premise compresses to a single visible
>   number or contrast (10,000 rows; 1 vs 1,000,000; before vs after).
> - **An outcome question** — the viewer can silently ask "will it make
>   it?" / "what happens?" and must watch to find out.

Reject even if trending or technically impressive: anything needing >1
sentence of context, anything whose audience is "people who do task X at
work", tutorials, tool reviews, listicles, anything where the 50% frame
equals the 100% frame.

## 3. Editorial pillars

| Pillar | What it looks like | Engine |
|---|---|---|
| **Impossible challenges** (spine) | "Can one command fix 10,000 broken rows?" · "Can AI un-shred this photo?" · escalation sequels (10k → 100k → 1M) | capture harness (real runs, real numbers) |
| **Simulations & what-happens-if** | physics sims pushed until they genuinely break — flood the city, overload the tower, 1M bouncing balls; the crash IS the payoff | `themed_bottom.py` procedural engine (already built: escalate-until-the-solver-breaks arc) |
| **Satisfying transformations & impossible comparisons** | chaos → order wipes, extreme before/afters, scale face-offs with animated counters | composer element kit (diff wipe, counters, split compare) |

Money / psychology / weird-facts angles are allowed only as the *frame* on
an experiment ("what $1M in rice looks like — we counted"), never as
narrated facts (that's channel 2's lane).

## 4. The challenge grammar (how every script is built)

1. **The absurd setup** (1–2s) — show the monster we built: the wall of
   garbage, the tower too tall, the number too big. Bragging, not teaching:
   "The messiest spreadsheet ever made!"
2. **Stakes in one number** — say it and SHOW it big: "10,000 rows.
   2,400 clones."
3. **The attempt, live** — one shot, visible progress: counter ticking,
   wipe advancing, sim escalating. This is the retention spine.
4. **The outcome** — WORKED / FAILED / BROKE stamp. Failure ships proudly;
   a spectacular break outperforms a clean win.
5. **The escalation hook** — every video ends by raising the stakes for
   the sequel: "Next: one MILLION rows." Winners become series; series
   compound.

Retention doctrine [SHARED — platform truth]: first second = spectacle,
not setup; something meaningful changes every 0.6–1.2s; context never
before intrigue; the last line escalates, inverts, or resolves. The three
retention failures and fixes: `LEARNING_LOOP.md` §1.

**Language-independence rule:** numbers, counters, wipes, stamps, and
physics carry the story; narration and captions are a bonus layer. If the
video stops working with captions off, the visual failed the gate.

## 5. Visual system

Full 9:16 clean master (no watermark/border), critical content inside
x 70–1010 / y 160–1580. The element kit (composer, `third_capture/`):

| Element | Purpose |
|---|---|
| `input_frame` | the monster we built — must look genuinely extreme |
| `big_counter` | animated stakes/progress number — the channel's signature |
| `split_compare` | before/after, A vs B |
| `diff_wipe` | chaos → order sweep (the satisfying beat) |
| `stopwatch_tag` | real measured time |
| `proof_stamp` | WORKED / FAILED / BROKE |
| `task_card` | the challenge in ≤6 plain words |
| `redaction_box` | privacy masking (synthetic data only anyway) |

Sim pillar reuses `themed_bottom.py` full-frame (not as a bottom strip):
its DESIGN CHARTER arc — calm start, compounding escalation, genuine
physics breakdown, regeneration — is exactly the what-happens-if format.

## 6. Truthfulness invariants [ABSOLUTE — unchanged from Proof Mode]

Spectacle NEVER licenses fakery — being the channel whose experiments are
real is the moat:
- Every number on screen (rows, seconds, counts) comes from the proof
  ledger of a real recorded run. No measured-sounding number without a
  measurement.
- Real-run content: the terminal/screen replay draws actual recorded
  bytes. Simulations are fine — they're labeled as simulations, and their
  breakdowns are genuine solver behavior, not scripted animations.
- FAIL/BROKE outcomes ship honestly framed. If a run breaks, that's the
  video, not a reshoot-until-it-works.
- Synthetic fixture data only; nothing private ever on screen.
- AI-content disclosure ON (TTS narration); FTC-clear disclosure of any
  sponsor/affiliate relationship, always.
- No near-duplicate mass production; sequels must escalate, not repeat.

## 7. Package output schema

```json
{
  "channel": "third",
  "slug": "...",
  "title": "Can one command fix {n_in} broken rows?",
  "premise_1s": "one-second silent pitch (what the first frame shows)",
  "stakes_number": "the single number the video hangs on",
  "hook_lines": ["…"], "hook_stamp": "{n_in} ROWS",
  "script": {"hook": "…", "input": "…", "proof": "…", "output": "…", "verdict": "…"},
  "verdict": "WORKED|FAILED|BROKE",
  "escalation_next": "the sequel's bigger stakes",
  "capture": {"kind": "cli|sim", "…": "…"},
  "disclosures": ["ai_tts"]
}
```

`{n_in}`-style placeholders are filled from the ledger at render time so
scripts can never drift from measured reality.

## 8. QA (pre-render and render-time)

Pre-render reject: fails any §2 gate · stakes not visible as one number ·
no live-progress element in beat 3 · outcome not visually obvious.
Render-time verify: spectacle visible by second one · captions in safe
zones · every shown number matches the ledger · something changes every
0.6–1.2s. Then the shared eye-QA loop: render beat-final frames +
25/50/75% samples and LOOK; fix → re-render → re-look. **Non-negotiable.**

## 9. Cadence and growth

- **Phase 1 — YouTube only, 1/day**, escalation series from day one
  (each video advertises the next). 10–15% of uploads are controlled
  experiments, one variable per batch (hook framing, counter style,
  stamp timing, CTA).
- **Phase 2 — 2/day + affiliates/products** once 30–50 uploads of
  retention data exist. English-first; the format is designed to need
  little language, so localization (channel 2's `localize.py` machinery)
  is a cheap later multiplier.
- **Phase 3 — TikTok/IG wrappers** when posting APIs are approved;
  sponsors only if they fit the experiment frame natively.

Monetization order: reach → brand → affiliates/digital products/courses →
sponsors → platform payouts. Never let a sponsor turn a video back into a
tutorial.

## 10. Learning loop [SHARED — `LEARNING_LOOP.md` is law]

Staged scorecard, `state/brain_context.json`, shot-aligned retention map,
no auto-adaptation below ~100 views/video, bounded reversible edits only.
Channel additions: ledger every upload with `premise_1s`, `stakes_number`,
`pillar`, `outcome` (worked/failed/broke), `series_id`, beat annotations;
before writing, retrieve ~15 nearest priors by FORMAT first; winners spawn
escalation sequels, losers' premises are banned patterns for 30 days.
Watch especially: hook-survival by premise type, and whether FAIL/BROKE
outcomes out-retain WORKED (if yes, engineer more genuine jeopardy).

## 11. Production infrastructure (built)

`third_capture/` — real-run recorder (pty capture, timestamped events,
proof ledger with hashes/counts/wall time) + 9:16 composer (element kit,
terminal replay, counters, stamps, burned captions, edge-tts VO).
`scripts/run_third.py` — capture → compose → upload, kills any package
whose run fails. `.github/workflows/third.yml` — isolated workflow.
Sim-pillar renderer (full-frame `themed_bottom` capture) is the next
build item.

## 12. Wiring & isolation (zero shared-pipeline impact)

- **Token:** `YouTubeUploader(channel="third")` → secret
  `YOUTUBE_TOKEN_JSON_THIRD` (mint via `setup_youtube.py` signed into the
  new channel's account; shared OAuth app).
- **Guard:** workflow sets `YOUTUBE_EXPECTED_CHANNEL` from repo var
  `THIRD_EXPECTED_CHANNEL` so a mis-set token can never post elsewhere.
- **Packages:** `state/third_packages/YYYYMMDD/` (never
  `state/trending_packages/`). **State:** `state/third_posted_log.json`;
  analytics `fetch_analytics.py --channel third` → `state/analytics_third/`.
- **Workflow:** `third.yml`, concurrency group `third-shorts`;
  `daily.yml`/`explainer.yml` are never edited for this channel.

Operator setup checklist: create the channel + @handle → mint
`YOUTUBE_TOKEN_JSON_THIRD` → set repo var `THIRD_EXPECTED_CHANNEL` →
merge + run the "Third Channel" workflow.
