# Shorts-pipeline — notes for Claude sessions

## Rule zero: if you can fix it, fix it — do not just name it

Operator ruling, 2026-08-01. An audit that lists a problem you were capable
of fixing, and then does not fix it, is worse than no audit: it converts a
bug into a bug PLUS a false sense that someone is handling it. The finding
gets read as progress.

So, in this repo:

- **Found it, can fix it, fix is in scope → fix it in the same change.**
  Not a ticket, not a "recommendation", not a follow-up.
- **Genuinely cannot fix it** — it needs a credential you do not have, an
  operator decision, a destructive action (history rewrite, deleting remote
  branches, anything outward-facing) — then say so **plainly, with the exact
  command or decision required**, and say WHY you stopped. "Needs your call"
  is a fix handed over; "worth considering" is litter.
- **Never build a capability and leave it unwired.** `shared/video_qa.py`
  sat imported-by-nothing for weeks while `CLAUDE.md` told every session to
  "run it before uploads". Five modules were in that state at the
  2026-08-01 audit. A capability nothing calls is not a capability, and a
  doc claiming otherwise is a lie the next session inherits.
  All five are now wired or honestly demoted, and the usual reason one was
  "missing" turned out to be that a channel had already grown its own copy
  privately — **look for the duplicate before you write the caller.** When
  you consolidate copies, the test is EQUIVALENCE against the originals
  (`tests/test_captions.py` is the pattern: the old implementations kept
  verbatim as oracles, compared over generated input). A cleanup that
  quietly re-cuts every video is not a cleanup.

The standing audit record — what was found, what was fixed, what is
deliberately left and why — is `docs/SYSTEM_AUDIT.md`.

Multi-channel automated YouTube pipeline (trending/daily, explainer,
curiosity, third "Proof Mode"). Channels are defined by orchestrator +
config + posted-log + token env, not by folders — see
`docs/STORAGE_AUDIT.md` §2 for the full map.

## The showrunner is the permanent, autonomous quality authority — DO NOT WEAKEN IT

The explainer channel fails CLOSED (see `docs/EDITORIAL_RESET.md`), and as
of 2026-08-01 **so does trending**. The headless-Claude SHOWRUNNER
(`scripts/showrunner_review.py`) is the standing editor-with-a-veto and it is
**load-bearing** — treat it like the posted logs, never as something to trim:

- **The policy lives in ONE place: `shared/showrunner_gate.py`.** Both
  publishing channels call it; `decide()` is pure, so the fail-closed rules
  are testable without rendering anything. Never re-implement it inline in a
  channel — that is how trending went six months shipping 6 unwatched videos
  a day while explainer was gated. The evidence that settled it is in
  `docs/SYSTEM_AUDIT.md` §B: explainer 1/day gated, best video 1,063 views;
  trending 6/day ungated, best video 45.
- **A fail-closed gate with no judge holds everything.** Any workflow that
  publishes MUST carry `CLAUDE_CODE_OAUTH_TOKEN` (or `GEMINI_API_KEY` as the
  fallback judge) on the render step, and say so in its preflight. Without
  that check the run renders a full slate and publishes none of it, green
  the whole way.

- It judges via the **Claude HEADLESS BRAIN** (the `claude` CLI on the
  `CLAUDE_CODE_OAUTH_TOKEN` subscription), NOT the paid Anthropic API. Keep
  it headless. It WATCHES the rendered video (samples frames, Reads them).
- Its BLOCK is **sovereign**: the brain judges what it SEES with full
  latitude, and code may only ever ADD blocks (a low-score / auto-fail floor),
  never flip a brain BLOCK to ship. Do not add any bypass.
- On a **publish** run it fails CLOSED (no verdict / infra error / timeout ⇒
  hold). `SHOWRUNNER=off` is refused on a publish run. Do not "fix" a failing
  gate by disabling it — fix the gate (or the video).
- Every verdict is appended to `state/showrunner_verdicts.jsonl` (its durable
  memory). The rubric it judges against is `docs/DIRECTOR.md`.

If a future task asks you to make the channel ship more / faster, the answer
is better videos, never a weaker gate.

## Data (the mascot) performs a bespoke pose PER SCENE

`data_learning/mascot_director.py` renders **any** pose from parameters
(`_a_pose`: hand targets + lower body + props + expression + motion). WHAT he
does is regenerated per beat via `author_performance(...)` — brain-authored
when `MASCOT_BRAIN=1`, else a distinct preset rotated by scene index so no two
beats reuse the same act (two "sitting" beats can be totally different:
spooning soup off a can vs. gripping a bird mid-flight). Add new acts as
`POSE_PRESETS` entries; never regress him to one static reused pose.

The RIG (how he is drawn) lives in `scripts/build_mascot_svg.py` and is the
single source of truth; `assets/mascot/host/*.svg|png` are generated from it
(`python scripts/build_mascot_svg.py --png`). Changing it changes the
character, so change it only on an explicit request — and regenerate the
assets in the same commit.

## `config/channel_registry.json` is the ONLY place channel policy lives

How many videos a channel ships, in which formats, which formats are retired,
what ChatGPT is responsible for, queue minimums, media requirements, where
output goes — **all of it is in one JSON file**, resolved through
`shared/channel_registry.py`:

```bash
python -m shared.channel_registry            # every channel, one line each
python -m shared.channel_registry --mix trending
python -m shared.channel_registry --validate
python -m shared.channel_registry --markdown # the table docs embed
```

Change that file and everything inherits: the Routine prompt, Phase A's
bundle, ChatGPT's authoring brief, media requests, Phase B validation,
promotion, the reserve bank, and the no-bundle takeover. **No scheduled-task
prose ever needs editing.** Never write a count or a mix anywhere else —
`tests/test_no_second_source_of_truth.py` runs in the auto-merge gate and
fails the PR if a second copy grows back. That test exists because the
2026-07-31 graph-led ruling landed in one of five places that stated the mix,
and the reserve bank went on banking a retired format with everything green.

- **A day's bundle FREEZES the registry** into `bundle.json.contract`
  (revision, sha256, `source_commit`, resolved plan per channel, doctrine
  hashes). That snapshot governs that date; a registry change starts with the
  next bundle. `--rebuild-contract` is the deliberate migration.
- **Precedence**: the date's snapshot → the registry → the doctrine files it
  names (read at `source_commit`) → docs, which are explanatory only.
- **A missing or invalid registry fails CLOSED.** Falling back to a
  historical mix is how a retired format gets authored on a day nobody is
  watching.
- Deep editorial doctrine stays in its own files (voice, topic banks,
  per-format writing rules). The registry says WHAT and HOW MANY; those say
  HOW. Verify the whole chain offline with
  `python scripts/registry_acceptance.py`.

Trending's formats are `reddit_story` (gameplay + post card + TTS) and
`graph_race` (animated chart); `text_card` is retired. **Those are the
current values, not a rule — read the registry.** It is NOT the old single
stacked/gameplay format, which is a fallback shape only. Per-format writing
specs: `CLAUDE_ROUTINE_INSTRUCTIONS.md` and
`shared/authoring_brief.py:FORMAT_SPECS`. It regressed to 6-of-one on
2026-07-30 because the spec lived only in the Routine's prompt; if you ever
see a slate of one format, that is the bug.

## Repo layout: the funnel (reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md)

Top-of-funnel media in **`funnel/`** (media_funnel, topic/entity image
finders, stock search, gemini_images AI-gen, usage ledger, og_scrape,
gameplay_scanner). Cross-channel utilities in **`shared/`** (fsutil,
uploaders, localize, script_generator, themed_bottom). Render capabilities
in **`engines/`**. Channels are thin consumers: daily renderers at root
(`make_*.py`), explainer/curiosity in `data_learning/`, third in
`third_capture/`, orchestrators in `scripts/`.

- Import canonically: `from funnel import media_funnel`,
  `from shared import uploaders`. **The 18 root shims are GONE** (deleted
  2026-08-01) — `import fsutil` is now an ImportError, not a deprecation.
  `tests/test_repo_layout.py` keeps the root clean and stops them growing
  back.
- New shared capability → `funnel/` (media), `engines/` (render engine),
  `shared/` (everything else). Never copy shared logic into a channel.
- The 2026-07-30 sprint's five capabilities are all WIRED as of 2026-08-01
  (they spent a day as the exact thing rule zero forbids):
  `shared/video_qa.py` runs on every trending render; `shared/captions.py`
  is the single caption grouper for `make_reddit_story`,
  `make_explainer_stacked` and `third_capture/clip_edit` (each delegating
  with parameters that reproduce its old output EXACTLY — see
  `tests/test_captions.py`, which holds that against the original
  implementations); `funnel/feeds.py` backs `scripts/discover_topic.py`;
  `funnel/article_extract.py` fills `topic.snippets` so the writer works
  from the real article instead of a headline. `engines/svg_motion.py` is
  `experimental` with a decision date — it has no consumer and says so.
- **The engine registry has to tell the truth.** `active` + not `gated`
  means something really imports it; `tests/test_engine_registry_honesty.py`
  checks the metadata against the code in both directions, because it was
  once wrong in both at the same time.

## The story forge keeps the queue full of REAL data

`scripts/story_forge.py` discovers indicators from the live World Bank WDI
catalogue, fetches world trends / country rankings, and writes datasets with
honest provenance (publisher, url, access_date, officiality=official). The
brain writes only the WORDS and the SCENE; every number comes from the
source. Run by `story_forge.yml` (twice daily) and by every posting run.
Never refill the queue with LLM-invented numbers — the editorial gate
refuses them, so a queue full of them still ships nothing.

## Score the PLAN before you spend a render — `shared/film_metrics.py`

Ruling, 2026-08-05, from a sprint that went backwards. Five full renders of one
story on 08-01/02, 2.5–4.5 hours each. Between them, one change apiece, chosen
by whatever the last blind judge complained about loudest. **Two of the five
made the film worse and nobody could know until the next video existed.** Net
movement over twelve hours of compute: 4.0 → 3.0.

So: **a render is only ever spent on a plan that is not already known to be
broken.** The plan is scoreable offline, in milliseconds, with no media, no
ffmpeg, no judge and no network.

```bash
python scripts/quality_sprint.py check SLUG   # score it, compare, REFUSE on a guard trip
python scripts/quality_sprint.py next         # what the EVIDENCE says to work on
python scripts/quality_sprint.py status       # the ledger + whether it is improving
```

- **`next` is the half that improves the CODE, not the film.** It splits the
  judges' complaints into ones that RECUR across renders (the machine makes
  them) and ones seen ONCE (that film had them). Choosing from the loudest line
  of the latest verdict is a sample size of one — that is exactly how a single
  UI_WIDGET note became a code change that deleted every human in the film and
  cost a full point. Its first real run said UI_WIDGET **once**, SAMENESS and
  BORING in **every** judged render.
- **`produce()` records every render itself** into
  `state/curiosity_quality_ledger.jsonl`. Never backfill it by hand — that is
  how two regressions went unnoticed for a day, and a row whose score was
  inferred rather than measured is worse than a missing row. Unjudged means
  `null`, never a guess.
- **Not measured is `None`, never `0`.** A false zero on an unmeasured axis
  manufactures a fake regression; this module did that to itself once.
- **`unanchored_media` is ADVISORY and has no lever.** Deriving queries from
  narration takes it 8/15 → 0/15 while producing `'means next person breathe'`.
  A measure that can be satisfied without improving the film must never be
  wired to an automatic transformation.
- A metric that goes up while the film gets worse is a bad metric. `compare()`
  reports regressions as loudly as wins, and any regression makes the whole
  change a REGRESSION.

The two shared modules the sprint has produced so far, both found by looking
for *constants where a decision belonged*:

- **`shared/cut_rhythm.py`** — `MAX_UNCHANGED` is a ceiling, but it was also
  the literal length of every lead shot, so a 39-shot film had FOUR distinct
  shot lengths. Varies where the cut lands beneath the ceiling. Never changes a
  beat's total duration: the narration is underneath it.
- **`shared/camera_grammar.py`** — `direction` and `pan` were supported by the
  renderer and never set by the planner, so every shot of every film pushed in.
  The move follows the beat's role (REVEAL/CLOSE pull out, HOOK/PAYOFF push
  in), and no two ADJACENT shots may share one.

## Engines: the shared capability layer — USE IT

`engines/` is the top-of-pipeline capability library any channel, script,
or Claude session can call. Before building a rendering/media capability
from scratch (animating a still, depth effects, future physics/maps/audio),
check whether an engine already exists or is ticketed:

```bash
python -m engines list            # every engine + availability (offline, fast)
python -m engines info <engine>   # metadata, license, pinned models, sample cmd
python -m engines doctor          # health-check all engines (no network)
python -m engines install <name>  # provision deps + checksum-verified models
python -m engines demo kenburns --image X --out Y
```

Full registry, triage verdicts, and the ticket backlog (E1–E14):
`docs/ENGINE_REGISTRY.md`. Contract: `maybe_*()` functions return a result
or `None`, never raise — safe to call best-effort from any renderer.

Rules:
- **`parallax` is active but GATED** (E2 verdict 2026-07-10: photos pass,
  flat art/text refused by the input suitability gate). First adoption in
  any channel still requires a preview render before flipping a default.
  `still_motion.kenburns` is always the fallback.
- New engines follow the checklist at the bottom of the registry doc
  (headless, CPU-viable, commercial-safe license, pinned models, `maybe_*`
  contract). One at a time, each earning its slot with a better video.
- Models/caches live in `cache/` (gitignored) — never commit binaries.

## ChatGPT exchange (docs/EXCHANGE_PIPELINE.md)

The daily run splits so ChatGPT contributes BEFORE any render: Phase A finds
media and judges every shot against its script line, writes one bundle of gap
requests + scripts, and stops. ChatGPT answers (images to Drive, punch-ups to
git) and writes a DONE marker, which fires Phase B: verified media pull,
self-fill for anything unfulfilled, guarded punch-up, then render.

- **Pollinations is retired as the AI-image path** — all AI images come from
  ChatGPT; gaps it misses get filled with real media by the self-fill pass.
- **Policy A**: a ChatGPT no-show never costs the day (self-fill + a 06:15
  backstop cron). A weaker shot beats no video.
- `shared/punchup_guard.py` is not advisory: a rewrite that changes any
  number/date/entity or the beat structure is rejected and the original ships.
- **ChatGPT is TWO workers now** (2026-07-31): a **06:00 Central MEDIA worker**
  (generate + upload + verify images, checkpoint each one, never writes
  `response.json` or `DONE`) and a **07:00 Central FINALIZER** (recover, fill
  gaps, punch up, author, then `response.json` and `DONE` as separate commits).
  They cannot see each other's context, so the repo is their shared memory:
  `exchange/bundles/<date>/media-progress/<safe_request_id>.json`, contract in
  `shared/media_checkpoint.py`. **`DONE` is the only thing that fires Phase B**
  — a checkpoint push must never start a render, or the day renders at 06:05
  with nothing authored and every check green. Filenames are deterministic
  (`<date>__<safe_request_id>.png`) and published in the bundle BEFORE either
  worker starts, which is what makes an orphaned upload recoverable. Verify the
  contract offline with `python scripts/exchange_dry_run.py`.
  Three rules that are not negotiable: **a DONE run REQUIRES checkpoints**
  (only the no-DONE emergency backstop may accept media without them); a
  pointer must match its checkpoint on **every** field (filename, file_id,
  folder_id, sha256, bytes, format, width, height, link-visible sharing), not
  just the hash; and **one Drive file may back exactly one request** — a
  file_id under two request_ids refuses BOTH, identical hashes included.
- **Phase B's backstop is 08:30 CENTRAL, from two UTC crons** (`30 13` and
  `30 14`), gated in-code by `zoneinfo` — never a single UTC cron. The old
  12:45 UTC one was 6:45 Central in WINTER, fifteen minutes before the 07:00
  finalizer starts, so for half the year it would have rendered an unfinished
  day with everything green. If the ChatGPT finalizer ever moves, move
  `FINALIZER_HOUR_CENTRAL` in `scripts/exchange_phase_b.py`, not the crons.
- **The chain is LIVE and automatic** (2026-07-30): Routine authors packages ->
  auto-merge -> **Phase A** -> ChatGPT -> DONE -> **Phase B** -> daily.yml
  renders. `daily.yml` NO LONGER fires on auto-merge or on a
  `state/trending_packages/**` push — those would render with pre-ChatGPT media
  and defeat the exchange. Phase A took that slot; daily.yml now fires only on
  Phase B completing (or a manual `.github/triggers/daily` touch).
- Never dispatch `daily.yml` as the step after authoring — it is the LAST step.
- Clock: Routine ~09:19 UTC -> Phase A (auto, 09:45 cron backstop) -> ChatGPT
  6:00 AM Central -> Phase B (auto on DONE, 12:45 UTC backstop) -> render.
  Posts land 8:00/9:30/11:00/12:30/2:00/3:30 Central. Phase B's backstop is
  DELIBERATELY late (12:45 UTC): ChatGPT's task is local-time and shifts an
  hour at DST while these crons do not, so an earlier backstop would render
  pre-ChatGPT media for half the year with everything green.
- A Phase A that finds no packages exits 0 — so this bug class is INVISIBLE in
  the Actions tab. To confirm the exchange ran, check for
  `exchange/bundles/<date>/bundle.json`, not a green checkmark.
- Third/explainer chain off "Daily Shorts", so they now run ~1.5h later too.

## Third channel: story arc system (docs/STORY_ARC_SYSTEM.md)

The third channel's `story_count` daily slots auto-detect narrative arcs
(clips clustered by shared people across days) and compile them into
multi-clip stories — quality-gated by a showrunner brain, falling back to
a normal clip when no genuine arc exists. Compilation dedupe rides
`story_key` (member-set hash), never member `source_url`s. Content
standard: docs/THIRD_INTERNET_PLAYBOOK.md.

## Media acquisition (docs/MEDIA_ACQUISITION.md)

Every visual carries a `source_class` + license (recorded in the audit
sidecar). Copyrighted media is NOT auto-rejected — it enters through the
transformative-evidence lane when the script directly engages with it,
the amount is proportionate, and the use is documented. Never bypass
DRM/paywalls/rate limits. The funnel pulls from 18 providers; new source
adapters are tickets M1–M9 in the doctrine doc.

## Fallbacks + the reserve bank (docs/FALLBACKS.md)

Every fallback path is traced top-to-bottom in `docs/FALLBACKS.md`. The two
things worth knowing without opening it:

- **Authoring is the only Claude-dependent stage.** Media, render, and
  upload have no Claude dependency; `_call_llm` has always preferred
  Groq → Gemini → Anthropic. The showrunner is the exception and it fails
  CLOSED — no Claude *and* no `GEMINI_API_KEY` means the explainer channel
  publishes nothing (`post_stories.py` refuses `SHOWRUNNER=off` on a
  publish run).
- **Two lines cover a dead brain, in order.** The **reserve bank** first,
  then the **ChatGPT authoring takeover** (`shared/authoring_brief.py` +
  `scripts/ingest_authored.py`): Phase A puts an `authoring_request` in the
  bundle, ChatGPT writes the day's packages, Phase B validates and promotes
  them. Nothing ChatGPT writes is trusted — promotion runs the same
  structural gate the bank and the renderers use, and a failure is
  quarantined into `authored_report.json`, never rendered. It runs the SAME
  DAY (Phase A 4:45am Central → ChatGPT 6:00am → render → the normal
  publish slots), so a Claude-out morning costs zero posts.
  The takeover covers TRENDING because that was the only channel whose
  floor was "nothing" or "a duplicate upload". Explainer, curiosity and
  third all self-heal to Groq/deterministic authoring — they keep posting,
  just worse. Extending the takeover to them is a quality project needing
  a Phase A/B split per channel; see `docs/FALLBACKS.md` §6.
- **The reserve bank** (`shared/package_buffer.py`) covers a dead brain:
  banked EVERGREEN packages drawn automatically when a day comes up short.
  `fill` is a no-op on a normal day, so it runs unconditionally in both
  `exchange_phase_a.yml` and `daily.yml`. Deposit refuses date-anchored
  language; a package is drawn exactly once (`state/package_buffer/used.json`)
  so it can never duplicate an upload. The Routine tops it up — step 5b of
  `CLAUDE_ROUTINE_INSTRUCTIONS.md`.

## WHO MAY EDIT THIS PIPELINE — Claude, and only Claude

Operator ruling. **Claude is the only agent that edits this repository.**
ChatGPT can run quarterback when the Claude subscription is out, but it
**never makes additions — only suggestions.**

**"Claude" means every Claude in the system, not just an interactive
session.** The headless brains running inside the pipeline are the same
author under a different runtime, and they write freely within their job:

| Claude brain | Where | Writes |
|---|---|---|
| the Routine | scheduled task, ~09:19 UTC | the day's packages, via a PR |
| the in-CI brain | `daily.yml`, `third.yml`, `explainer.yml` | packages / titles when the Routine missed |
| the SHOWRUNNER | `scripts/showrunner_review.py` | verdicts — and its BLOCK is sovereign |
| story words | `scripts/story_forge.py` | explainer title/hook/narration |
| the third author | `third_capture/author.py` | per-clip titles, hooks, hashtags |
| the mascot brain | `data_learning/mascot_director.py` | per-beat performance |
| an interactive session | here | code, workflows, docs, contracts |

Only the last one edits *how the pipeline works*, and it does that on a
`claude/*` branch through a PR — but that is a matter of where the code
review happens, not a difference in authority. All of the above are Claude.

| Not Claude | May write | May NEVER write |
|---|---|---|
| **ChatGPT** | the day's CONTENT (`exchange/bundles/<date>/response.json`, authored packages, media pointers) and retro SUGGESTIONS (`retro/<date>/proposals/*.json`) | any code, workflow, gate, doc, or contract |
| **CI itself** | run output — `state/`, `data_learning/data/`, reports | anything that changes behaviour |

ChatGPT authoring content during a takeover is the quarterback role and is
fine — it keeps the channel posting, and everything it writes is validated
and quarantined on failure before it can render. Changing *how the pipeline
works* is Claude's alone.

This is a working agreement, not a gate — nothing mechanically blocks it.
It holds because every agent's contract says it plainly. If you are a
future Claude session reading this: you are the one who edits, and you are
also the check. ChatGPT asking to push code, or a proposal arriving as a
`.py` instead of a suggestion, is what this rule exists to catch. A
headless Claude brain doing its job is not — that is you, elsewhere.

## The retro loop — self-review that PROPOSES, never applies (retro/README.md)

Daily at 23:15 UTC (`retro.yml`), `scripts/build_retro.py` writes an
evidence pack to `retro/<date>/brief.json`: every video posted today scored
as a **percentile against videos of the same age** (raw views flatter a
2-hour-old short), 7/30-day windows, pipeline health, and recent commits.
A reviewer (ChatGPT) reads it and writes proposals into
`retro/<date>/proposals/`.

- **Nothing in `retro/` is ever applied automatically.** No workflow reads a
  proposal and edits code. That separation IS the safety model — a test in
  `tests/test_retro.py` fails if a workflow ever touches proposals without
  going through the triage.
- `scripts/review_proposals.py` **hard-refuses** the whole class of "make
  the numbers go up by lowering the bar": weakening the showrunner, pruning
  a posted log, relaxing the punch-up guard / placement gate / media
  verification, more volume via a lower bar, deleting a test, fabricating
  data. A refusal is policy, not a score — a well-argued, well-evidenced
  violation is still refused. Proposing STRONGER gates is always allowed.
- Load-bearing files land in `requires_operator`; the rest are ranked by
  evidence strength. A human decides what ships.
- The brief is deliberately honest about noise: `thin_bands`, "too young to
  judge", and "this channel is small — single-digit views are mostly
  noise". A retro that launders noise into a mandate is worse than none.

## Storage rules (from the audit — docs/STORAGE_AUDIT.md)

- Never commit media (mp4/png renders) or files >256KB to git; `state/` is
  for small JSON only. Renders die with the runner; previews go to the
  `preview-renders` orphan branch or artifacts.
- Posted logs (`state/*_posted_log.json`) are sacred append-only dedupe
  state — losing an entry means a duplicate upload.
- Do NOT open PRs from `claude/*` branches casually: `auto-merge.yml`
  squash-merges any non-draft `claude/*` PR with no review.
