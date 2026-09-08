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

### Keys EXPIRE, and an expired key looks exactly like a broken one

On **2026-09-07** every trending backfill attempt died in under two seconds on
`HTTPError: HTTP Error 401: Unauthorized`, so three slots the showrunner had
correctly emptied could not be re-authored and the day shipped 3 of 6. The key was
about ninety days old and rotating it fixed it immediately. The exact cause is
NOT confirmed — Groq does not document a key lifetime anywhere public, and the
expiry setting lives in the authenticated console. Treat "the key aged out" as
the working theory it is, not as a documented policy.

Two things follow, and both are now true:

* **Groq's console offers a key that never expires — take that option.**
  (Observed by the operator on 2026-09-07 and not present when the previous
  key was made; not in any changelog I could find.) A credential with a timer
  on it is a scheduled outage nobody has written down.
* **No unattended path may name one provider.** `_call_llm` walks
  Groq → Gemini → Anthropic until one ANSWERS, but only when the caller does
  not name a backend — an explicit `backend=` is exact by design. The
  trending backfill named `"groq"`, so the chain it was standing on could not
  catch it. That is the second time the same shape has cost a day: on
  2026-08-11 all four backfill attempts died on `HTTP Error 429` with
  `GEMINI_API_KEY` configured and idle. The chain was fixed that day; the
  caller was not, until now.
  `tests/test_no_single_provider_dependency.py` fails the build if any
  unattended path pins a backend again.

**When a provider call starts failing instantly and identically, check the key's
expiry before you debug the code.** A 401 in 0.3 seconds is a credential, not a
bug — nothing else fails that fast or that consistently.

Rotate at <https://console.groq.com/keys>, then update the `GROQ_API_KEY`
repository secret. Ten workflows read that exact name (`daily`, `explainer`,
`story_forge`, `curiosity`, both `exchange` phases, `retitle`, and the two
previews), so renaming it silently disables all of them.

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

### What actually carries a dead brain

Nothing on the Claude side. **The ChatGPT takeover (§6) is the whole
answer** — it authors the missing slate from the live registry, with or
without a bundle from Phase A. Retry (§5) is a different mechanism for a
different failure: it refills a slot the GATES emptied, on a day that was
authored fine.

## 2. The exchange (Phase A → ChatGPT → Phase B)

No Claude dependency anywhere in the chain. Phase A judges media with
`funnel/media_judge.py` (heuristics plus an optional Gemini call), ChatGPT
answers on its own subscription, Phase B verifies and self-fills.

The failure mode here is not "Claude died", it's "there was nothing to
prepare": **a Phase A that finds no packages exits 0**, so a dead authoring
night is invisible in the Actions tab. Confirm the exchange ran by checking
for `exchange/bundles/<date>/bundle.json`, never by looking for a green
checkmark.

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

## 5. Retry — cover for a slot the gates emptied

`run_trending_daily._backfill`. A slot a gate refused is not a lost slot: the
run authors a REPLACEMENT — discovery, ranking, a new script, a new render —
and puts it through the identical path.

```
6 slots attempted
  1 shipped, 5 held by the showrunner
        │
        └─ _backfill: discover fresh topics (excluding every posted title)
                      -> run_one() -> render -> technical QA -> vision QA
                      -> SHOWRUNNER (same gate, same bar)
                      -> shipped, or held again and the next topic tries
```

Three properties keep it honest:

- **It is not a bypass.** The replacement goes through `run_one`, the exact
  function every other video goes through. `_backfill` contains no reference
  to the showrunner at all, and `tests/test_backfill.py` fails if one grows.
  A replacement the gate also refuses stays refused.
- **It cannot duplicate an upload.** Candidate topics are filtered against
  `posted_titles()` before anything renders.
- **It is bounded.** `MAX_BACKFILL` (default 4) attempts, so a
  systematically bad day costs renders, not the job timeout. When discovery
  has nothing fresh the day stays short and the report says so — it never
  fabricates a video to hit the number.

A short day after retries is a REAL alarm (`trending_short_after_retries`)
and a retro signal (`slots.backfilled` / `slots.short` in the brief). High
backfill with zero shortfall means the safety net is working and the
AUTHORING is weak — which is the useful thing to know, and was invisible
while the retro only counted uploads.

### There is no reserve bank

There used to be: `shared/package_buffer.py` + `scripts/package_reserve.py`,
a shelf of pre-authored evergreen packages drawn when a day came up short.
The operator retired it on 2026-08-05 — *"there shouldn't be a reserve bank.
If something doesn't run properly, it goes through and tries again."*

The reasoning holds up. A shelf covers only as many failures as somebody
remembered to stock it for; ours held two packages against a low-water mark
of twelve, so it would have covered one bad slot and then been empty for a
week — while reading, in every status output, like a safety net that was
there. Re-authoring has no such ceiling.

Its structural validator survived and moved to `shared/package_schema.py`.
That was never about banking: it is the answer to "is this package well
formed", which every producer still needs.

## 6. The ChatGPT whole-pipeline takeover — the brain of last resort

`shared/authoring_brief.py` + `scripts/ingest_authored.py`. When Phase A
finds the day short, it puts an
`authoring_request` in the same `bundle.json` ChatGPT already reads at 6:00
AM Central and flips the bundle's `mode` to `"author"`. ChatGPT writes the
missing packages into its `response.json`; Phase B validates and promotes
them; the renderer cannot tell the difference.

```
09:45 UTC  Phase A   0 packages
                     -> bundle.json  mode:"author", authoring_request{write, mix} <- registry
11:00 UTC  ChatGPT   reads the brief, writes response.json.authored[], DONE
           Phase B   INGEST: validate -> promote -> quarantine failures
                     cover media for the new packages (entity + self-fill)
                     -> daily.yml renders + uploads on the normal slots
```

Phase A normally lands the brief before ChatGPT's 6:00 AM task. GitHub cron
may drift, however, and Phase A itself is allowed to fail. Therefore a
missing bundle is an explicit takeover signal: the worker reads the live
registry, inventories every enabled channel, and starts the same work without
waiting for a Claude-authored package or a Python-generated bundle.

**Nothing ChatGPT writes is trusted.** Promotion runs the same structural
gate every other producer is held to
(`shared/package_schema.py:structural_problems`), so the brief and the
ingest cannot drift apart — we ask for exactly what we accept. A package
that fails is written to `exchange/bundles/<date>/authored_report.json` with
its reasons and does not ship; the rest of the slate is unaffected. Slugs
are path-sanitised before they become filenames.

The one rule the takeover inherits and does not relax: **the slate is
whatever `config/channel_registry.json` currently says**. The brief
asks for that mix, and the ingest warns loudly if what
comes back is six of one format — the exact regression of 2026-07-30.

### Does it survive with nothing on the Claude side running?

The weekly limit takes out the morning Routine AND the in-CI brain at once —
they are the same subscription. Every link that still has to fire, and what
it actually runs on:

| Link | Fires because | Needs Claude? |
|---|---|---|
| Phase A | `schedule: 45 9 * * *` — a GitHub cron | no |
| the bundle / brief | `shared/authoring_brief.py`, pure data | no |
| ChatGPT authors | ChatGPT's own scheduled task, a **separate subscription** | no |
| ChatGPT's push fires Phase B | a user token, not `GITHUB_TOKEN`, so it CAN trigger workflows | no |
| Phase B (if no DONE) | DST-aware 08:30 Central backstop gate | no |
| ingest + validate | `package_schema.structural_problems` | no |
| media for the new packages | entity resolver + funnel (Groq/Gemini/keyless lanes) | no |
| `daily.yml` renders | `workflow_run` on Phase B completing | no |
| `daily.yml`'s Brain step | — | yes, but it is `continue-on-error` and `exit 0`s on a missing token or a failed npm install, and skips entirely when the day already has packages |
| render + TTS + upload | ffmpeg / Kokoro / YouTube OAuth | no |
| publish gates | the shared showrunner/technical/vision gates | no (Gemini is the judge fallback) |

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

### Whole-pipeline ownership (registry revision 2)

The old design stopped at Trending because the other channels had local
fallbacks. That confused "a workflow returned something" with "the production
day is covered." The current registry assigns `production_supervisor` to
**every enabled channel**:

| Channel | ChatGPT takeover responsibility |
|---|---|
| **Trending** | Author the exact registry shortfall, supply/reverify media, and supervise render/QA/upload. |
| **Explainer** | Preserve sourced dataset values, replace deterministic words where requested, and supervise its specialized renderer/upload. |
| **Curiosity** | Stock the queue when required and supervise the registered long-form worker. |
| **Third** | Do not fabricate a clip recipe; invoke/monitor the capture workflow and verify required uploads. |

`response.json` and `DONE` close the exchange handoff only. The supervisor's
job continues through actual workflow outcomes. A day is not reported as
successful because packages were promoted or a renderer was triggered; the
required videos must clear QA and have verified upload results, or the day
must carry an explicit terminal failure.

## 7. Telling a fallback day from a normal one

A fallback brain is a recurring Tuesday, not an incident, so it cannot live
only in an Actions log. Every rendered package carries who wrote it —
`_authored_by: chatgpt-takeover` — and `format_report()` turns that into a
banner at the TOP of `daily_report.md`:

> **ChatGPT wrote 6 of today's 6 packages** — the Claude Routine did not run
> (weekly limit?).

Top matters: the ntfy push sends only the first ~20 lines to your phone, so
a banner below the per-post list would never reach you. The same file is
posted to the tracking issue. A day that had to re-author a refused slot
adds its own line saying how many, because a high count means the authoring
needs work — never that the gate does.

A normal day prints no banner at all.

## 7b. The credential heartbeat — which key is dead, and only when it is

Operator, 2026-09-08: *"I can't be refreshing the Gemini key all the time."*

They should not have to, and the reason it felt that way is that **every
preflight in this repo checks whether a credential is SET**. A revoked key is
a non-empty string, so it passes all of them and dies at the moment it is
needed — which is exactly how 2026-09-07 went: `GROQ_API_KEY` present, the
workflow green, the preflight satisfied, three trending slots gone.

`scripts/credential_check.py` makes the cheapest possible LIVE call to each
credential and reports what came back. `credentials.yml` runs it at 13:10 UTC
— after authoring, before the first post, so there is still time to act.

**The distinction it exists to make is DEAD vs LIMITED.** A 401 means the key
is gone and somebody has to mint a new one. A 429 means the key is fine and
the window is spent; refreshing it changes nothing. Reporting both as "the
key is broken" is precisely what teaches an operator to rotate keys on a
schedule to stay ahead of a problem they do not have.

| verdict | what it means | what to do |
|---|---|---|
| `ok` | the service answered | nothing |
| `dead` | 401/403, or a 400 that names the key | replace this one |
| `limited` | 429 — accepted, then throttled | nothing; the key is fine |
| `unset` | not configured | nothing, if unused |
| `unreachable` | 5xx, DNS, timeout, no CLI | says nothing about the key |

Four rules hold it honest, all tested:

- **It alerts on a CHANGE to dead, never on the standing state.** A daily
  alarm for a key you already know about is how somebody learns to ignore the
  channel that will one day say something new — the same reasoning `daily.yml`
  uses for its `phase_b_incomplete` skip.
- **It reports and never ACTS.** No secret is edited, no channel disabled, no
  workflow behaviour changed. A checker that can switch things off is a new
  way for the day to go dark quietly.
- **A probe that explodes is `unreachable`, not `dead`.** A DNS hiccup
  reported as a dead key costs a credential rotation nobody needed.
- **YouTube tokens are DISCOVERED from the environment, not listed**, so a new
  channel cannot be the one nobody is watching. A dead upload token does not
  degrade a day, it ends it: the video renders, passes every gate, and has
  nowhere to go.

The subscription token has no cheap HTTP probe, so it is exercised the way the
showrunner exercises it — by running the CLI. Without the CLI installed the
row reads `unreachable`, never `dead`.

## 8. Summary — what actually breaks

| Secret / subscription gone | Consequence |
|---|---|
| Claude subscription / `CLAUDE_CODE_OAUTH_TOKEN` | Routine and in-CI brain both dark. ChatGPT authors the day (§6); only if that misses too does Groq write. Explainer publishing needs `GEMINI_API_KEY` for the showrunner. |
| `GEMINI_API_KEY` | Showrunner has no fallback judge → explainer publishes nothing if Claude is also down. Media judging gets dumber. |
| `GROQ_API_KEY` | Last-resort writer gone; ranking degrades. Harmless *while packages are authored* — but NOT for the trending backfill, which is the last unattended chance to fill a slot a gate emptied. That path used to name Groq explicitly and lost three slots to an expired key on 2026-09-07; it is unpinned now, so the chain falls through to Gemini and then Anthropic. Prefer a key with no expiry — see above. |
| ChatGPT task | Policy A: Phase B self-fills, backstop cron renders. A weaker shot beats no video. |
| Stock provider keys | Narrower search, more gaps, more self-fill work. |
| YouTube token | Renders still produced; upload fails loudly. |
