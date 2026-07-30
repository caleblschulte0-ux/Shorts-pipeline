# Fallbacks — what happens when a dependency goes dark

Written 2026-07-30 in answer to a direct question: *"what happens top to
bottom if my Claude subscription runs out?"* This traces every stage of the
daily chain, names what it degrades to, and marks the places where the
answer used to be "nothing ships."

The headline: **media, render, and upload have no Claude dependency at all.**
Everything at risk is upstream — authoring and judging.

---

## 1. Authoring — who writes the day's six packages

Three paths can produce `state/trending_packages/<date>/`, tried in this
order by the time the render runs:

| # | Path | Runs on | If it's gone |
|---|---|---|---|
| 1 | The Routine (~09:19 UTC) | Claude subscription | nothing authored; no PR; no auto-merge |
| 2 | `daily.yml` "Brain" step | `CLAUDE_CODE_OAUTH_TOKEN` | `continue-on-error`, logs a warning, leaves the dir empty |
| 3 | **Reserve bank** | nothing — plain Python, offline | draws banked evergreen packages |
| 4 | Groq via `shared/script_generator._call_llm` | `GROQ_API_KEY` | 6K TPM free tier; struggles writing six scripts back to back |

Path 3 is new (see §5). Before it existed, a dead subscription meant paths
1 and 2 both produced nothing and the day fell straight to Groq — or to
`run_trending_daily.most_recent_package_dir()`, which re-serves **yesterday's
already-posted slate**. Both are bad outcomes that looked green in the
Actions tab.

`_call_llm` itself has never preferred Claude. Its order is
**Groq → Gemini → Anthropic**, picked by whichever key is present
(`shared/script_generator.py:276`). An expired Claude subscription does not
touch it; a missing `ANTHROPIC_API_KEY` does not either, as long as
`GROQ_API_KEY` or `GEMINI_API_KEY` is set.

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

## 6. Summary — what actually breaks

| Secret / subscription gone | Consequence |
|---|---|
| Claude subscription / `CLAUDE_CODE_OAUTH_TOKEN` | Routine and in-CI brain both dark. Trending draws from the reserve; when the reserve empties, Groq writes. Explainer publishing needs `GEMINI_API_KEY` for the showrunner. |
| `GEMINI_API_KEY` | Showrunner has no fallback judge → explainer publishes nothing if Claude is also down. Media judging gets dumber. |
| `GROQ_API_KEY` | Last-resort writer gone; ranking degrades. Harmless while packages are authored. |
| ChatGPT task | Policy A: Phase B self-fills, backstop cron renders. A weaker shot beats no video. |
| Stock provider keys | Narrower search, more gaps, more self-fill work. |
| YouTube token | Renders still produced; upload fails loudly. |
