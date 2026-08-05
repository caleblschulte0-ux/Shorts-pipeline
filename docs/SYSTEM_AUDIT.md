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

## Addendum, same day: Phase B was consuming the WRONG DAY'S BUNDLE

Found while checking whether the 2026-08-01 ChatGPT run behaved. Both workers
did their jobs perfectly — 17 verified checkpoints, `response.json` and `DONE`
as separate commits in the right order, 16/16 media pointers passing strict
validation with zero rejects. **And none of it was applied.**

Phase B fired on the `DONE` push at 12:04 UTC, ran for nine minutes, and
exited green — against **`D="20260730"`**.

The date came from:

```bash
git log -1 --name-only --pretty=format: | grep -oE '...DONE' | head -1
```

on a `fetch-depth: 1` checkout. A shallow clone's single commit is **grafted**
— it has no parent — so git reports *every file in the tree* as added. The
grep matched all three bundles' `DONE` markers and `head -1` took the
**oldest**. Reproduced locally: a depth-1 clone lists `20260730`, `20260731`,
`20260801` and picks `20260730`.

It looked correct on 2026-07-30 only because the oldest bundle and the current
date were the same day. **The error grows by one day for every day the repo
keeps another DONE marker**, and it is completely silent — the run succeeds,
writes a report for the wrong date, and reports "ready to render".

Cost so far: today's 16 generated, uploaded, SHA-verified ChatGPT images were
never pinned. The five videos that posted on 2026-08-01 shipped without them.

**Fixed:** `fetch-depth: 2` (so a parent exists to diff against) plus
`git diff-tree --no-commit-id --name-only -r HEAD`, `sort -r` instead of
`head -1` on an unsorted list, and a hard check that the resolved date
actually has a `DONE` — a wrong-but-plausible date is exactly what made this
invisible. Two tests pin it.

Not back-applied: today's videos already posted, and re-running Phase B now
would only pin local cache paths that do not exist in CI. The fix takes effect
on the next `DONE`.

---

## Second pass, same day: the alarm, and the bug that would have eaten tomorrow

### The identity drift — this one would have broken tomorrow, silently

Chasing the wrong-bundle bug turned up a worse one right behind it.

Bundle identity was the **sha256 of `bundle.json`'s raw bytes**. Phase A fires
on every auto-merge and re-judges media each time — it rewrote that file **six
times on 2026-08-01**, the last one at 12:25 UTC, *five hours after* the 06:00
media worker finished at 07:04.

Every rewrite silently invalidated every checkpoint written before it. And
because a DONE run now **requires** checkpoints (fixed earlier today), the
next clean day would have refused all seventeen verified images and
stock-filled the whole slate. The strictness I added this morning would have
turned a cosmetic rewrite into a total media loss.

**Fixed two ways:**

1. Identity now hashes **the ask**, not the file — `ask_fingerprint()` over
   request ids, prompt hashes, agreed filenames and the registry snapshot. A
   re-judge that changes nothing a worker acts on leaves it untouched; a
   changed prompt or a new request moves it, which is exactly when a
   checkpoint should die.
2. It is published as a sidecar, `exchange/bundles/<date>/BUNDLE_ID`, that
   workers **copy** instead of computing. A worker that only copies a string
   cannot hash the wrong thing.

Plus: **Phase A now refuses to rewrite a bundle whose ask changed while
checkpoints exist.** Moving the goalposts under a running worker needs
`--rebuild-contract` and says so loudly.

Step 3.5 of `scripts/exchange_dry_run.py` reproduces the exact scenario — a
Phase A rewrite mid-flight — and asserts the checkpoint survives it.

### The alarm — so nothing is silent again

`scripts/daily_alarm.py` + `.github/workflows/alarm.yml`, 01:15 UTC daily.

Every failure this pipeline has had reported on the **steps** it ran, never on
the **outcome** it produced, and a step can succeed at the wrong thing. The
alarm checks outcomes against `config/channel_registry.json`: did each channel
ship its target, did the exchange actually land, was ChatGPT's media pinned,
did a retired format ship, is the reserve bank covered.

It comments on the tracking issue **only when something is wrong** — a daily
"all good" is how people stop reading — and fails the run so it is red in the
Actions tab.

Verified against both real incidents: it flags 2026-07-27 (`no_posts_*` ×4)
and 2026-08-01 (`done_but_no_report`, critical). 14 tests pin it, including
the false-alarm cases — it defers publishing checks mid-day, because an alarm
that cries wolf is one people learn to ignore.

### The scripts/ suite — 34 live tests nothing ran

Triaged rather than deleted, because triage found them alive: **34 of the 37
pass**. Two need a render environment (skipped by name in CI, honestly, not
quietly). One — `test_run_ledger.py` — had been failing since `overall_10`
became a required verdict field, and nobody knew because nothing ran it. The
fixture was stale, not the gate; fixed. All 35 now run in the auto-merge gate.

---

## Third pass, same day: everything in the old "NOT fixed" list

The operator's ruling on the list below was short: *"I don't give a shit —
push to solve it for me and get it all fucking fixed."* So A–H were worked
top to bottom. Seven of the eight are closed. The one that is not is not a
judgement call — it is mechanically blocked in this environment, and the
exact command is below.

### D (was: the 6/day channel has no showrunner) — FIXED

The taste gate now runs on trending. The decision logic — fail CLOSED on a
publish run, `SHOWRUNNER=off` refused on a publish run, a brain BLOCK is
sovereign — moved out of `scripts/post_stories.py`, where it protected one
channel, into **`shared/showrunner_gate.py`**, which both channels call.
Copying the block into trending would have been the wrong fix and is
forbidden ("never copy shared logic into a channel").

`decide()` is a pure function, so the fail-closed policy is testable without
rendering anything. 25 tests in `tests/test_showrunner_gate.py`, including a
sweep asserting that **no combination of inputs ships a BLOCK**, and an AST
check that `decide()` never reassigns `blocked` — the shape a bypass would
take.

**The dangerous part, caught before it shipped:** a fail-closed gate with no
judge holds *everything*. `daily.yml`'s render step did not carry
`CLAUDE_CODE_OAUTH_TOKEN` (explainer's did), so the first run under the new
gate would have rendered six shorts over ~40 minutes and published **none**
of them, with every step green. The token is now on the step, and the
preflight refuses the run outright when neither it nor `GEMINI_API_KEY`
exists — a check ADDED, never a way to skip the gate.

### C (was: five capabilities built and unwired) — FIXED

Not by writing five new callers, but by finding that four of them were
duplicates of code the channels had already grown privately.

**`shared/captions.py`** — the repo had **five** independent ASS caption
builders. It is now the single grouper for three of them
(`make_reddit_story`, `make_explainer_stacked`, `third_capture/clip_edit`),
each delegating with parameters that reproduce its old behaviour *exactly*.
That equivalence is the test: 1,500 generated word-streams compared against
the original implementations, copied verbatim into
`tests/test_captions.py` as oracles. The rule sets stay deliberately
different — explainer breaks on `:` and `;`, reddit does not — and a test
asserts they did not get "made consistent". `clip_edit`'s latent quirk
(a blank word broke a line, because `"" in ".?!,"` is `True` in Python) is
reproduced behind a flag named `blank_breaks`, so it can be fixed
deliberately rather than silently.

**`funnel/feeds.py`** — `scripts/discover_topic.py` had its own narrower RSS
parser and now delegates. Free side effect: Atom feeds used to yield zero
topics silently; they work now.

**`funnel/article_extract.py`** — a topic discovered from RSS arrived as a
headline and a link, and `topic.snippets` (the context argument
`script_generator.generate` already takes) was left empty, so the writer
invented the middle of the story. `_research()` now fills it with the real
article text before the script is written. Best-effort by contract: a
paywall, a timeout, no network, the module missing entirely — all leave the
run exactly as it was. Research must never cost the day; 20 tests hold that.

**`engines/svg_motion.py`** — demoted to `experimental` with a decision
date. It was built for animated cards and `text_card`, the card format it
would have served, was retired the next day. It has no consumer, and
`status: active` was the lie.

Which surfaced the **second-order bug**: the engine registry was wrong in
BOTH directions at once. `still_motion` said `consumers: []` while two
renderers called `maybe_kenburns` (so a session would have rebuilt it);
`svg_motion` claimed production status with no caller. Metadata drifts the
moment nothing checks it. `tests/test_engine_registry_honesty.py` now
checks the registry against the code: an engine that is `active` and not
`gated` must have a real consumer, every consumer it names must actually
import it, and `experimental` requires a decision date so "not yet" cannot
quietly become "forever".

### G (was: `shared/uploaders.py` untested) — FIXED

35 tests, no network. The last thing that runs before a video becomes
public, and it held the guard that stops the pipeline posting to the wrong
channel. Covered: secret hygiene (credentials arrive by phone paste and
arrive dirty), the wrong-channel guard — including an assertion that it runs
**before** `videos().insert()`, since a guard that fires after the video is
already public is decoration — every real API limit (title 100, description
5000, tags 30), the synthetic-media disclosure, and the rule that once
`insert()` returns, **nothing** may lose the video: a thumbnail 403, a
captions 403 and a translator failure are each proven not to.

### H (was: 25 legacy root shims) — FIXED

Only four real legacy imports were left; they now use the canonical package
paths, and all 18 shims are deleted. `tests/test_repo_layout.py` keeps the
root clean: an allow-list of what may live there, an AST scan for imports of
the retired names, and a check that each deleted shim's real module exists
in a package.

### E and F — already fixed earlier the same day

E (silent outage, no alert) is `scripts/daily_alarm.py` + `alarm.yml`.
F (37 tests in `scripts/` run by nothing) is triaged and wired into CI.

### Smaller things — FIXED

`data_learning/niche.config.json` (719 KB) was rewritten in full on every
explainer run whether anything changed or not. Two runs that both changed
nothing still produced two conflicting 719 KB diffs — which is why
`explainer.yml` carries an `--autostash -X ours` retry loop around its push.
All four writers now go through `shared.fsutil.write_json_if_changed`.

The file is **not** re-sharded, deliberately. Splitting 192 stories across
files touches five readers plus five inline-python blocks in workflows, on
the config of the one channel that demonstrably works (§B: a 1,063-view
video). That is a change to make on its own, with a preview render, not as
the tail of a long session the night before a run.

**`scripts/test_expressions.py` was failing, and the renderer was innocent.**
`render_test_clip` did `if out.exists(): return out`, so a render interrupted
mid-write (a timeout, a Ctrl-C) poisoned the cache *permanently* — every
later run reused the truncated file and failed the size check.
`housing_expr.mp4` sat at 69 KB against a ~300 KB expectation and the suite
reported a broken scene that renders perfectly. The cache is now validated
(size **and** duration) rather than trusted; the run went 5-passed-1-failed
to **6/6**, and it immediately caught a second corrupt artifact
(`transportation_baseline.mp4`, 1.90 s of an expected 2.50 s).

---

## STILL NOT FIXED — one item, and it is not a judgement call

### A. 1.21 GB of git history in 53 stale remote branches

**Blocker: branch deletion is refused by this environment, twice over.**

`main` itself is clean — the weight is entirely in the stale branches
(rendered mp4s: `output/curiosity_money-goes.mp4` at 89/85/34/25 MB across
revisions, `preview/*.mp4` at 21–23 MB each). Deleting the branches IS the
whole fix; no history rewrite of `main` is needed.

I could not do it. Two independent blocks:

1. the session's git proxy hangs up on a delete push (`fatal: the remote end
   hung up`), and
2. `git push --delete` is refused by this environment's command classifier
   before it even reaches the network.

I did not try to route around either, and the GitHub MCP surface available
here has no delete-branch tool.

Run from a normal clone. Note that `--merged` reports only ONE branch as
merged, because `auto-merge.yml` **squash**-merges, which breaks ancestry —
so judge by the PR, not by git:

```bash
# every branch whose PR was merged (squash-merge safe)
gh pr list --state merged --limit 300 --json headRefName \
  --jq '.[].headRefName' | sort -u > /tmp/merged.txt
git branch -r | sed 's|origin/||' | grep -E '^(claude|agent)/' \
  | grep -Fxf /tmp/merged.txt | xargs -n1 git push origin --delete
```

Branch tips are recoverable from GitHub for a period after deletion, and
every one of these branches has its content on `main` already.

---

## Verification (third pass)

| | |
|---|---|
| unit suite | 477 → 499 → 522 → **654 tests**, all passing |
| split-worker dry run | 9/9 |
| channel-contract acceptance | 7/7 |
| `scripts/` suite | 35 files; `test_expressions.py` now 6/6 |
| compile + import smoke | all 8 entrypoints import after the shim removal |

New this pass: `tests/test_showrunner_gate.py` (25),
`tests/test_uploaders.py` (35), `tests/test_captions.py` (25),
`tests/test_research_intake.py` (20), `tests/test_fsutil_writes.py` (12),
`tests/test_repo_layout.py` (5), `tests/test_engine_registry_honesty.py` (10).

---

## Fourth pass, 2026-08-05: the ChatGPT emergency edits, line-audited

Context: the Claude subscription lapsed ~2026-08-01. With the operator's
explicit authorization, ChatGPT edited production code on 08-02/08-03 to
finish the whole-pipeline takeover — a sanctioned one-off exception to the
"only Claude edits" ruling, now closed (see CLAUDE.md). It notated its work
well (`docs/CHATGPT_CHANGES_2026-08-02.md`,
`docs/CHATGPT_CHANNEL_SEPARATION_2026-08-03.md`), which made this audit
tractable. Every code file it touched was diffed and judged.

### RATIFIED — kept, they are real fixes

- **`pin_verified_media` (`scripts/exchange_phase_b.py`)** — Phase B used to
  commit `/home/runner/...` paths from its disposable VM into packages; the
  separate render runner could not read them and silently lost every ChatGPT
  image. Now the durable Drive URL + file_id + sha256 ride the package. The
  single best fix of the takeover work. Also kept: the idempotent takeover
  repair (a rerun reattaches response media to already-promoted packages).
- **Takeover identity (`shared/media_checkpoint.py`)** — a no-bundle
  takeover has no `BUNDLE_ID` to copy, and a late Phase A cron would mint a
  new identity and invalidate every takeover checkpoint (the wrong-bundle
  failure shape again). `takeover.json` now pins identity for a claimed
  date. Fails toward refusal, never acceptance.
- **The manifest-only renderer** — `--require-manifest` in
  `run_trending_daily.py`; daily.yml no longer authors (in-CI brain removed)
  or back-fills (reserve fill removed — it still runs in Phase A, the right
  place). The render job is deterministic; re-authoring at render time hid
  broken handoffs.
- **Channel separation** — Data is Explainer's mascot; trending renders
  without it (registry rev 3, `mascot_pose` gone from contracts,
  `tests/test_channel_mascot_separation.py`).
- **Format-aware showrunner directive** — the judge is told what a
  reddit_story/graph_race is supposed to demonstrate instead of blocking a
  narrative for lacking a chart. Gate stays sovereign; my 25 gate tests are
  untouched, ChatGPT only added.
- **The illustrated Reddit layout, layout-aware vision QA, the
  production-outcome file, `production_supervisor` in the registry.**

### REPAIRED — the damage

1. **The failure counter punished the gate.** The run going RED on any
   shortfall (right — visibility) also fed the auto-pause counter, so two
   days where the showrunner correctly held one video would pause the whole
   channel — mechanized "more output via a lower bar" pressure, against the
   old explicit ruling that a quarantine must not bump the counter. Fixed:
   RED on shortfall stays; the counter bumps only on a ZERO-upload day, read
   from the production outcome file. `tests/test_production_outcome.py` pins
   both halves.
2. **The two judges contradicted each other about the mascot.** The 08-02
   vision-QA text told the judge a mascot in a trending frame was
   "intentional"; the 08-03 separation made it a brand violation the
   showrunner must flag. ChatGPT fixed the showrunner side and missed its
   own vision-QA text. Fixed; tested.
3. **`registry_acceptance.py` was broken on main since 08-02** — step 6
   hardcoded `registry_revision == 1`; ChatGPT bumped the registry to rev
   2, then 3, and never saw the failure because **its pushes went straight
   to main, bypassing the auto-merge gate that runs this script**. Fixed to
   compare against the revision captured at freeze time. This is also the
   audit's sharpest lesson: the gate can only guard what goes through it.
4. **Doctrine drift** — CLAUDE.md still claimed the reserve fill runs in
   daily.yml; corrected. The who-may-edit ruling now records the exception
   as closed and re-asserts the line.
5. **The alarm now reads the production outcome** — `repair_required`
   sitting at end of day is a critical (`production_repair_<cid>`), which is
   ChatGPT's own "DONE is not production completion" contract, wired into
   the thing that shouts.

Suite: 666 (as found) → **680 tests**, dry run 9/9, acceptance 7/7 (was
6/7 on main).
