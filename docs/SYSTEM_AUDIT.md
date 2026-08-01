# System audit — 2026-08-01

Whole-repo review: what is wrong, what was fixed in the same change, and what
is deliberately left with the reason and the exact action needed.

Governed by **rule zero** (`CLAUDE.md`): a finding you could fix and didn't is
worse than no finding. Everything below is either FIXED or has a named blocker
and a command.

---

## The one that matters most

**76 videos. 354 total views. Median 2. One like. Zero comments.**

That is the trending channel's entire life to 2026-07-31. It is not a
slow-growth problem — the oldest videos (30 days) sit at 0–12 views and the
newest at 0–16. Nothing compounds.

The traffic breakdown says why:

| Source | Views |
|---|---|
| `YT_SEARCH` | 494 |
| `YT_CHANNEL` | 61 |
| **`SHORTS` (the feed)** | **56** |
| `EXT_URL` | 15 |
| `HASHTAGS` | 1 |

**A Shorts channel getting 56 feed views across 76 videos is not being
distributed.** 78% of views come from search — and the top search terms are
`ticket banana`, `land of natura wisconsin dells`, `mr baller`, `van wert
tornado 2002`. Those are people looking for something else who landed on us.
That is not an audience.

Three of the fixes below were actively suppressing distribution. None of them
were visible from a green pipeline, which is the point: **every workflow has
been passing this entire time.**

---

## FIXED in this change

### 1. Every hashtag on every video was being ignored — for the channel's entire life
`scripts/run_trending_daily.py`

YouTube discards **all** hashtags on a video that carries more than 15. Not
"ranks them lower" — discards the set. `_hashtag_list` defaulted to
`max_total=25`, and with 15 topical tags from the package plus a 10-tag
baseline, every upload shipped **21–22**. So the channel disabled its own
hashtags on all 76 videos, and `HASHTAGS: 1` in analytics read like "hashtags
don't work" rather than "we switched them off".

**Fixed:** hard cap `YT_HASHTAG_LIMIT = 15`, enforced even against a caller
passing a bigger `max_total`; baseline trimmed from 10 tags to 4 so topical
ones survive the cap. Pinned by `tests/test_upload_metadata.py`.

### 2. Four of every six videos uploaded with a description that was ONLY hashtags
`scripts/run_trending_daily.py`

`_description` started with `pkg["script"]`. `text_card` and `graph_race`
packages have no `script` field. So their description was literally
`"\n\n#tag #tag #tag …"` — a bare wall of 21 hashtags, no prose, no context,
no keywords. Verified against the real 2026-07-31 slate: 4 of 6.

The two `reddit_story` descriptions were the opposite failure — the full
narration verbatim, the same words the TTS is already speaking.

**Fixed:** every format now opens with the title, then the best prose the
package actually has (`script`, `text`, or a generated plain-language summary
of a chart: series names, year span, y-axis label), then the source line, then
≤15 hashtags. A `graph_race` that had `"\n\n#openai #anthropic…"` now reads
*"OpenAI vs Anthropic: Valuation By Year / OpenAI vs Anthropic, 2023 to 2026,
Valuation ($ billions). / Sources: …"*.

### 3. `shared/video_qa.py` was imported by nothing while CLAUDE.md said to run it
`scripts/run_trending_daily.py`

213 lines of finished-render QA — black frames, frozen frames, silence,
missing audio, loudness — built in a capability sprint and **never called by
any production code**. `CLAUDE.md` told every session "run it before uploads".
No caller ever did. A black or silent render went straight to YouTube.

Worse, the QA that *did* exist (Gemini vision) returns early for `text_card`
and `graph_race` — under the current graph-led ruling that is **4 of 6 videos
with no check at all**, and it needs an API key.

**Fixed:** `_technical_qa()` runs on every render, every format, before the
vision early-return. No API key needed. Fails **open** on analysis trouble (no
ffmpeg, timeout, unreadable file) so the QA tool can never become the outage
it exists to prevent — it only blocks on a defect it measured. Proven against
real ffmpeg-generated files: a healthy render passes, a black/silent one is
blocked with `black 99% of runtime; silent 100% of runtime; loudness -70.0
LUFS outside [-30.0, -8.0]`.

### 4. CI ran almost none of the test suite
`.github/workflows/auto-merge.yml`

477 tests in 16 files. The auto-merge gate ran **two of them** (both added an
hour earlier, in the registry work) plus a compile check — and `automerge`
needed only that job. **A PR breaking every other test merged itself.** The
punch-up guard, the package buffer, the split-worker checkpoints, levity, the
retro loop: never executed in CI, ever.

**Fixed:** a `tests` job runs the full suite, the split-worker dry run, and
the channel-contract acceptance run; `automerge` now needs `[sanity, tests]`.

### 5. `unittest discover` was BROKEN on main — and finding #4 would have shipped it
`tests/*.py`, `tests/test_retro.py`

Caught while verifying fix #4. `python -m unittest discover -s tests` **fails
on clean `main`**:

```
ImportError: 'test_exchange' module incorrectly imported from
'/home/user/Shorts-pipeline/scripts'. Expected '.../tests'.
```

`scripts/` holds **37 `test_*.py` files of its own** — an entire second test
suite nothing runs — and one of them, `scripts/test_exchange.py`, shadows
`tests/test_exchange.py`. Eleven test modules did
`sys.path.insert(0, ROOT/"scripts")`, putting the shadow ahead of the real
module, so discovery died the moment anything imported or byte-compiled the
`scripts` copy. It appeared to work only while `scripts/__pycache__` happened
to be absent.

Had I not caught it, gating CI on that exact command would have failed every
PR from the first merge.

**Fixed:** all eleven modules now `sys.path.append` for `scripts/`, never
insert at 0. Guarded by two new tests — one runs discovery in a subprocess and
asserts it exits clean, one greps for the banned insert.

**It also exposed a false-negative it had been hiding.**
`test_retro.py::test_no_workflow_applies_a_proposal_untriaged_or_unrecorded`
matched the bare word `proposals`, which also matches `curiosity-ci.yml`
running `scripts/test_learning_proposals.py` — an unrelated unit test. The
assertion had never actually run, because discovery crashed before reaching
it. Retightened to match the retro proposal path.

### 6. Three workflows ran with inherited write permissions
`.github/workflows/{curiosity-ci,third-smoke,verify_token}.yml`

No `permissions:` block, so they inherited the repo default. CI jobs that only
read and run tests were holding tokens that can push to `main`.

**Fixed:** `permissions: contents: read` on all three. All 24 workflows now
declare permissions explicitly.

### 7. `state/` grew ~800 KB/day forever, against its own storage rule
`scripts/fetch_analytics.py`

`docs/STORAGE_AUDIT.md` says `state/` is for small JSON only. Each channel
wrote a full analytics snapshot per day — 226–281 KB each — and kept every
one. 101 snapshots had accumulated: **11 MB of `state/`'s 14 MB**, growing
without bound.

**Fixed:** `prune_snapshots()` keeps the newest 30 dated files per channel
(`--keep-days`, `0` disables). `latest.json` is never touched, git history
keeps everything, and nothing reads past 30 days.

---

## NOT fixed — needs your decision or a destructive action

### A. 1.21 GB of git history, ~1.15 GB of it abandoned branches
**Blocker: destructive and outward-facing. Your call, not mine.**

`main` is clean — the only binaries on it are four small SFX `.wav`s. The
weight is **54 stale remote branches** carrying rendered mp4s:
`output/curiosity_money-goes.mp4` at 89 MB, 85 MB, 34 MB, 25 MB across
revisions; `preview/*.mp4` at 21–23 MB each.

Five of those branches are already merged into `main` and safe to drop:

```bash
git branch -r --merged origin/main | grep -v HEAD | grep origin/claude/ \
  | sed 's|origin/||' | xargs -n1 git push origin --delete
```

Reclaiming the rest means rewriting history on branches that are not merged —
`git filter-repo --path-glob '*.mp4' --invert-paths` plus a force-push, which
breaks every existing clone. **Say the word and I'll do it; I won't do it
unasked.**

### B. The channel has never produced a single retention datapoint
**Blocker: needs views, not code.**

`usable_for_retention` requires ≥50 views. The channel's all-time maximum is
**45**. So `average_view_percentage` has never been populated for any trending
video, and the learning loop, the retro percentiles and the multi-day
experiments are all running on view counts with a median of 2 — noise being
laundered into conclusions.

`scripts/build_retro.py` is honest about thin bands, which is why this has not
produced a garbage ruling yet. But **no experiment on this channel can
conclude anything until distribution improves.** Fixes 1–3 above are the
plausible unblock; the honest read is that we should not trust any A/B result
here for weeks.

### C. Five capabilities still built and unwired
**Blocker: each needs a design decision about whether the channel wants it.**

`shared/video_qa.py` is fixed above. Still dark:

| Module | LOC | Built for |
|---|---|---|
| `shared/captions.py` | — | word-timed karaoke captions |
| `funnel/feeds.py` | — | RSS/Atom research intake |
| `funnel/article_extract.py` | 153 | clean article text |
| `engines/svg_motion.py` | — | animated vector cards |
| `engines/parallax` | — | depth parallax (honestly gated, E2) |

Only `parallax` documents why it is dormant. **Burn-down: adopt or delete.**
Karaoke captions are the one with a real retention argument on a Shorts
channel — I did not wire it because it changes what every video looks like,
and that is your call.

### D. The 6/day channel has no showrunner; the 1/day channel has one
**Blocker: an editorial decision about cost and veto power.**

The headless-Claude showrunner watches rendered frames and holds a sovereign
veto — on **explainer**, which ships 1/day. Trending ships 6/day with only
technical QA (now) and a key-gated vision check on one of three formats.
The most quality machinery points at the lowest-volume channel.

### E. Silent three-day outage, 26–28 July
**Blocker: needs a decision on where an alert should go.**

`posted_log.json`: 7 videos on the 23rd, 4 on the 24th, 5 on the 25th, then
**0, 0, 0**, then 5 on the 29th. Nothing alerted. The pipeline has no
"we shipped nothing today" signal at all — every workflow was green through
the gap. A cheap fix exists (a scheduled check that opens an issue when the
posted log gains nothing for 24h), but it needs to route somewhere you'll see.

### F. 37 test files live in `scripts/`, run by nothing
**Blocker: needs a call on whether they are still meaningful.**

A whole second suite — `test_judge_*.py`, `test_repair_*.py`,
`test_publish_security.py`, `test_story_*.py` — sitting in `scripts/`, outside
`tests/`, executed by no workflow and no discovery run. Some are stale
one-offs; some (`test_publish_security.py`) sound load-bearing. The shadowing
bug above is a symptom of them being there.

The safe move is to triage: move the live ones into `tests/`, delete the dead
ones. I did not do it blind because deleting a test that still means something
is worse than leaving it — **tell me to triage them and I will.**

### G. 15 modules have no test at all
Mostly provider adapters (`pexels_search`, `pixabay_search`, `og_scrape`,
`stock_search`, `vod_miner`) plus `shared/uploaders.py` — **the module that
actually talks to YouTube is untested.** Adapters are network-shaped and hard
to test honestly; `uploaders.py` is not, and is the highest-value gap.

### H. 25 legacy `.py` shims still at repo root
`entity_media.py`, `media_funnel.py`, `fsutil.py` … kept as `sys.modules`
aliases after the 2026-07-30 reorg so old imports keep working. Deliberate and
documented, but the migration has been "temporary" for a while and root is the
first thing a new reader sees.

---

## Smaller things

- `data_learning/niche.config.json` is **719 KB / 192 stories** in one file
  that gets rewritten on every explainer run — a merge-conflict magnet and the
  second-largest file in the repo.
- `assets/models/haarcascade_frontalface_default.xml` (930 KB) is the largest
  tracked file; a vendored OpenCV model, fine to keep but worth knowing.
- 413 `except Exception` blocks. Most implement a documented never-raise
  contract; the density still makes a genuine failure easy to lose.
- No action pinned to a SHA (`uses: actions/checkout@v4`, not a digest).
  Standard practice, low risk here, worth knowing.
- `scripts/format_scoreboard.py` now derives its buckets from the registry,
  but its module docstring still described a three-format channel until this
  change.

---

## Verification

477 → **499 tests** (19 new in `tests/test_upload_metadata.py`, 3 new guards
in `tests/test_no_second_source_of_truth.py`), the split-worker dry run 8/8,
and the channel-contract acceptance run 7/7 — all now executed by CI on every
`claude/*` PR, which was itself finding #4.

Note the arithmetic: the suite reported "477 passing" earlier in the day
purely because discovery was crashing before it finished. Fixing #5 is what
made the count real.
