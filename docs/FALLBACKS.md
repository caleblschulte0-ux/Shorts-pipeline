# Fallbacks — what happens when a dependency goes dark

Written 2026-07-30. This traces every stage of the daily chain, names what
it degrades to, and marks the places where the answer used to be "nothing
ships."

**The case these fallbacks are built for is the ordinary one:** the Claude
weekly usage limit is hit, so the authoring Routine does not run for a day
or three, several times a month. Not a lapsed subscription, not a
catastrophe — a recurring, expected gap that must cost zero videos. Every
gate below triggers on **"today's slate is short"**, never on "the
subscription is gone", because the pipeline cannot tell those apart and
should not try.

That frequency is what makes the design choices below non-negotiable:
because a fallback brain is a normal Tuesday rather than an incident, it has
to be visible in the daily report (§7) and it must never re-serve work that
already went out (§1).

The headline: **media, render, and upload have no Claude dependency at all.**
Everything at risk is upstream — authoring and judging.

---

## 1. Authoring — who writes the day's six packages

Three paths can produce `state/trending_packages/<date>/`, tried in this
order by the time the render runs:

| # | Path | Runs on | When it fires |
|---|---|---|---|
| 1 | The Routine (~09:19 UTC) | Claude subscription | normally; the real brain |
| 2 | **Reserve bank** (§5) | nothing — plain Python, offline | 09:45 UTC, if the day is short |
| 3 | **ChatGPT takeover** (§6) | ChatGPT scheduled task | 6:00 AM Central, if the day is *still* short |
| 4 | `daily.yml` "Brain" step | `CLAUDE_CODE_OAUTH_TOKEN` | at render time, if the dir is still empty |
| 5 | Groq via `shared/script_generator._call_llm` | `GROQ_API_KEY` | last resort; 6K TPM free tier, struggles with six scripts |

Paths 2 and 3 are new. Before they existed, a missed Routine meant paths 1
and 4 both produced nothing and the day fell straight to Groq — or to
`run_trending_daily.most_recent_package_dir()`, which re-serves yesterday's
slate. Both looked green in the Actions tab.

`_call_llm` itself has never preferred Claude. Its order is
**Groq → Gemini → Anthropic**, picked by whichever key is present
(`shared/script_generator.py:276`). An expired Claude subscription does not
touch it; a missing `ANTHROPIC_API_KEY` does not either, as long as
`GROQ_API_KEY` or `GEMINI_API_KEY` is set.

### The duplicate-upload trap (fixed)

The stale-slate fallback was actively dangerous once gaps became routine.
`most_recent_package_dir()` serves the previous day's directory when today's
is empty, and the **only** upload guard was a 6-hour rolling window — built
to stop a same-day double-fire, nothing more. On **day two of a gap** that
fallback would serve day one's slate 24 hours later, sail straight past the
6-hour window, and re-upload every video. A three-day gap compounded it.

`load_prewritten_packages()` now drops any package whose title is already in
`state/posted_log.json`, whichever directory it came from. If that empties a
stale directory it returns nothing and the run falls through to Groq —
**a weaker NEW script beats a duplicate upload**, and a duplicate is the one
failure the posted logs exist to prevent. Using a stale directory at all now
logs a loud warning naming what else came up short.

### How much cover the bank really provides

Be honest about the arithmetic: the Routine banks roughly one evergreen
package a day while it is healthy, and a full slate costs six. So the
reserve is **about a one-day buffer**, not a week's. Banking harder would be
self-defeating — writing extra packages spends the very Claude budget that
is running out.

That is the point of the ordering: the bank absorbs a one-day miss cleanly,
and **the ChatGPT takeover is what actually carries a multi-day gap.**

## 2. The exchange (Phase A → ChatGPT → Phase B)

No Claude dependency anywhere in the chain. Phase A judges media with
`funnel/media_judge.py` (heuristics plus an optional Gemini call), ChatGPT
answers on its own subscription, Phase B verifies and self-fills.

The failure mode here is not "Claude died", it's "there was nothing to
prepare": **a Phase A that finds no packages exits 0**, so a dead authoring
night is invisible in the Actions tab. Confirm the exchange ran by checking
for `exchange/bundles/<date>/bundle.json`, never by looking for a green
checkmark. The reserve fill now runs *before* Phase A precisely so this
stage has something to work on.

If ChatGPT no-shows, Policy A holds: Phase B self-fills the gaps with real
media and the 12:45 UTC backstop cron renders the day anyway.

## 3. Media, render, upload

No Claude anywhere.

- The funnel degrades provider by provider — a missing `PEXELS_API_KEY`
  narrows the search, it doesn't stop it.
- Engines follow the `maybe_*()` contract: return a result or `None`, never
  raise. `parallax` unavailable falls back to `still_motion.kenburns`.
- Renderers are ffmpeg/Pillow/matplotlib. TTS is Kokoro (local ONNX) with
  edge-tts as the network fallback.
- Upload is the YouTube API on its own OAuth token.

## 4. The showrunner — the one place that fails CLOSED

`scripts/showrunner_review.py` grades finished renders with a vision judge:

```
headless Claude CLI  x3 retries   (CLAUDE_CODE_OAUTH_TOKEN)
   └─ all fail →  _gemini_judge   (GEMINI_API_KEY)
        └─ fail →  RuntimeError("no vision judge available")
```

And `scripts/post_stories.py:265` refuses to skip it:
`SHOWRUNNER=off is not allowed on a publish run`. That is deliberate — it
stops a bad video shipping unwatched — but it means **no Claude *and* no
Gemini = the explainer channel publishes nothing.** `GEMINI_API_KEY` is the
load-bearing secret here, not `CLAUDE_CODE_OAUTH_TOKEN`.

If you ever need to ship with both judges down, that is a deliberate
operator decision, not a config toggle: it means publishing ungraded video.

## 5. The reserve bank — cover for a dead brain

`shared/package_buffer.py` + `scripts/package_reserve.py`. A small bank of
**evergreen** packages, banked while the brain is healthy and drawn
automatically on a day that comes up empty.

```
Routine authors 6 for today  +  1 extra evergreen -> state/package_buffer/inbox/
                                                        │
   exchange_phase_a.yml / daily.yml:  deposit ──────────┘
                                      fill  ── day short? draw into
                                                state/trending_packages/<date>/
```

Two invariants make it safe to run unattended:

- **Evergreen only.** Deposit refuses date-anchored language — weekday
  names, "yesterday", "breaking", "just announced", "3 hours ago",
  "March 14". A banked package may sit for weeks; a stale news script is
  worse than no video.
- **Drawn exactly once.** Withdrawal deletes the bank file and appends to
  `state/package_buffer/used.json`, and deposit refuses any slug already
  authored for a day. A reserve package can never collide with posted-log
  dedupe.

`fill` is a **no-op when the day is already at target**, so it never
displaces work the brain actually produced. It runs unconditionally in both
`exchange_phase_a.yml` and `daily.yml`.

```bash
python scripts/package_reserve.py status          # what's in the bank
python scripts/package_reserve.py fill --date 20260801 --dry-run
```

The bank starts **empty** and fills forward — it deliberately cannot be
seeded from past slates, because every one of those already aired. Expect
roughly a week of Routine runs before it holds a full slate of cover; the
`status` output prints `LOW` per format until it does, and step 5b of
`CLAUDE_ROUTINE_INSTRUCTIONS.md` tells the Routine to write one extra
evergreen package whenever it sees that.

## 6. The ChatGPT authoring takeover — the brain of last resort

`shared/authoring_brief.py` + `scripts/ingest_authored.py`. When Phase A
finds the day still short *after* the reserve fill, it puts an
`authoring_request` in the same `bundle.json` ChatGPT already reads at 6:00
AM Central and flips the bundle's `mode` to `"author"`. ChatGPT writes the
missing packages into its `response.json`; Phase B validates and promotes
them; the renderer cannot tell the difference.

```
09:45 UTC  Phase A   0 packages, bank empty
                     -> bundle.json  mode:"author", authoring_request{write:6, mix:2/2/2}
11:00 UTC  ChatGPT   reads the brief, writes response.json.authored[], DONE
           Phase B   INGEST: validate -> promote -> quarantine failures
                     cover media for the new packages (entity + self-fill)
                     -> daily.yml renders + uploads on the normal slots
```

Why the timing works: Phase A's backstop cron is 09:45 UTC = 4:45 AM
Central, so the brief is always on disk before ChatGPT's 6:00 AM task looks.

**Nothing ChatGPT writes is trusted.** Promotion runs the same structural
gate the reserve bank and the renderers use
(`package_buffer.structural_problems`), so the brief, the bank, and the
ingest cannot drift apart — we ask for exactly what we accept. A package
that fails is written to `exchange/bundles/<date>/authored_report.json` with
its reasons and does not ship; the rest of the slate is unaffected. Slugs
are path-sanitised before they become filenames.

The one rule the takeover inherits and does not relax: **the slate is
2 + 2 + 2**. The brief asks for the mix, and the ingest warns loudly if what
comes back is six of one format — the exact regression of 2026-07-30.

### Does it survive with nothing on the Claude side running?

The weekly limit takes out the morning Routine AND the in-CI brain at once —
they are the same subscription — and by day two the reserve bank is drained
too. Every link that still has to fire, and what it actually runs on:

| Link | Fires because | Needs Claude? |
|---|---|---|
| Phase A | `schedule: 45 9 * * *` — a GitHub cron | no |
| reserve fill inside Phase A | plain Python | no |
| the bundle / brief | `shared/authoring_brief.py`, pure data | no |
| ChatGPT authors | ChatGPT's own scheduled task, a **separate subscription** | no |
| ChatGPT's push fires Phase B | a user token, not `GITHUB_TOKEN`, so it CAN trigger workflows | no |
| Phase B (if no DONE) | `schedule: 45 12 * * *` backstop | no |
| ingest + validate | `package_buffer.structural_problems` | no |
| media for the new packages | entity resolver + funnel (Groq/Gemini/keyless lanes) | no |
| `daily.yml` renders | `workflow_run` on Phase B completing | no |
| `daily.yml`'s Brain step | — | yes, but it is `continue-on-error` and `exit 0`s on a missing token or a failed npm install, and skips entirely when the day already has packages |
| render + TTS + upload | ffmpeg / Kokoro / YouTube OAuth | no |
| **trending's publish gate** | there is none — **the showrunner veto is explainer-only** | no |

So the trending channel ships end to end on a fully dead Claude
subscription. Two things had to be fixed for that to be true rather than
merely intended:

1. **Phase B refused a day with no bundle.** It exited 2 on
   `read_bundle() is None` — but "Phase A never ran" is exactly the dead-day
   case, and ChatGPT may have authored the slate anyway. It now checks for
   authored packages first and proceeds in **ingest-only rescue mode**, with
   the same validation. Only no-bundle *and* nothing-authored is still a
   refusal.
2. **ChatGPT was purely reactive.** Its instruction was "read
   `bundle.json`" — no bundle meant it did nothing. It now decides from the
   repo instead: fewer than 6 files in
   `state/trending_packages/<today>/` is a takeover day, and it writes the
   slate and creates the response file itself (`exchange/README.md`).

(A far-edge case, noted only so it is not a surprise: GitHub disables
scheduled workflows in a repo with **no commit activity for 60 days**. The
pipeline commits state daily from several channels, so a normal weekly-limit
gap never approaches it.)

### Why only trending needs it

Checked channel by channel, 2026-07-30. **Trending was the only channel
with a hard same-day hole** — the others already self-heal, they just get
worse:

| Channel | Authoring on a Claude-out day | Still posts? |
|---|---|---|
| **Trending** | Routine dead, `daily.yml` brain dead → **was** Groq or a stale slate | only because of the reserve + takeover |
| **Explainer** | `story_forge._claude_words()` returns None → `_call_llm` (Groq→Gemini) → deterministic words | yes, if `GEMINI_API_KEY` is set for the showrunner |
| **Curiosity** | same `data_learning` stack | yes |
| **Third** | `author._call_claude()` → Groq → `fallback_title()` (safe raw clip title) | yes |

So the takeover covers trending because trending is where the floor was
"nothing" or "a duplicate". Everywhere else the floor is "a worse video".

That floor is genuinely worse, and the code says so in its own comments:
the third channel's Groq fallback once produced the title *"Silky Calls Him
Gay"* (`third_capture/author.py:133`), and story_forge's deterministic path
once shipped *"Congo, Dem. Rep. Beats Everyone On Male primary school age
children out-of-school"* (`scripts/story_forge.py:378`). Both have guards
now. Extending the ChatGPT takeover to those channels is therefore a
QUALITY project, not an availability one — and it is not a small one:
their workflows author inline (third authors titles for clips it captures
during the same run), so there is no bundle for ChatGPT to answer ahead of
time. Covering them means splitting each into a Phase A / Phase B exchange
the way trending is split. Not done; recorded here as the next honest step.

**Explainer's one-line fix is not the takeover — it is `GEMINI_API_KEY`.**
Its authoring already degrades on its own; only the showrunner (§4) can
stop it publishing.

## 7. Telling a fallback day from a normal one

A fallback brain is a recurring Tuesday, not an incident, so it cannot live
only in an Actions log. Every rendered package carries who wrote it —
`_authored_by: chatgpt-takeover` or `_reserve` — and `format_report()` turns
that into a banner at the TOP of `daily_report.md`:

> **ChatGPT wrote 6 of today's 6 packages** — the Claude Routine did not run
> (weekly limit?).

Top matters: the ntfy push sends only the first ~20 lines to your phone, so
a banner below the per-post list would never reach you. The same file is
posted to the tracking issue. A reserve draw adds its own line with the
top-up command, since the bank needs refilling once Claude is back.

A normal day prints no banner at all.

## 8. Summary — what actually breaks

| Secret / subscription gone | Consequence |
|---|---|
| Claude subscription / `CLAUDE_CODE_OAUTH_TOKEN` | Routine and in-CI brain both dark. Trending draws from the reserve, then ChatGPT authors the day (§6); only if BOTH miss does Groq write. Explainer publishing needs `GEMINI_API_KEY` for the showrunner. |
| `GEMINI_API_KEY` | Showrunner has no fallback judge → explainer publishes nothing if Claude is also down. Media judging gets dumber. |
| `GROQ_API_KEY` | Last-resort writer gone; ranking degrades. Harmless while packages are authored. |
| ChatGPT task | Policy A: Phase B self-fills, backstop cron renders. A weaker shot beats no video. |
| Stock provider keys | Narrower search, more gaps, more self-fill work. |
| YouTube token | Renders still produced; upload fails loudly. |
