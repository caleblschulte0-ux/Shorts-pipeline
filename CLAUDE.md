# Shorts-pipeline — notes for Claude sessions

Multi-channel automated YouTube pipeline (trending/daily, explainer,
curiosity, third "Proof Mode"). Channels are defined by orchestrator +
config + posted-log + token env, not by folders — see
`docs/STORAGE_AUDIT.md` §2 for the full map.

## The showrunner is the permanent, autonomous quality authority — DO NOT WEAKEN IT

The explainer channel fails CLOSED (see `docs/EDITORIAL_RESET.md`). The
headless-Claude SHOWRUNNER (`scripts/showrunner_review.py`) is the standing
editor-with-a-veto and it is **load-bearing** — treat it like the posted
logs, never as something to trim:

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

**Trending is THREE formats, 2 each, 6/day**: `reddit_story` (gameplay +
post card + TTS), `text_card` (typographic card over b-roll), `graph_race`
(animated chart). It is NOT the old single stacked/gameplay format — that is
a fallback shape only. Full spec + required fields per format:
`CLAUDE_ROUTINE_INSTRUCTIONS.md` (top section). It regressed to 6-of-one on
2026-07-30 because the spec lived only in the Routine's prompt; if you ever
see a slate of six identical formats, that is the bug.

## Repo layout: the funnel (reorg 2026-07-30 — docs/PIPELINE_LAYOUT.md)

Top-of-funnel media in **`funnel/`** (media_funnel, topic/entity image
finders, stock search, gemini_images AI-gen, usage ledger, og_scrape,
gameplay_scanner). Cross-channel utilities in **`shared/`** (fsutil,
uploaders, localize, script_generator, themed_bottom). Render capabilities
in **`engines/`**. Channels are thin consumers: daily renderers at root
(`make_*.py`), explainer/curiosity in `data_learning/`, third in
`third_capture/`, orchestrators in `scripts/`.

- Import canonically: `from funnel import media_funnel`,
  `from shared import uploaders`. The old root names (`media_funnel.py`,
  `fsutil.py`, …) still exist as sys.modules shims — legacy imports keep
  working and share the same module object — but write NEW code against
  the packages.
- New shared capability → `funnel/` (media), `engines/` (render engine),
  `shared/` (everything else). Never copy shared logic into a channel.
- Capability sprint 2026-07-30 added: `shared/video_qa.py` (finished-render
  QA — run it before uploads), `shared/captions.py` (karaoke ASS captions),
  `funnel/feeds.py` + `funnel/article_extract.py` (research intake), and
  the `svg_motion` engine (animated vector cards). All opt-in, all tested
  via `python -m unittest tests.test_capabilities`.

## The story forge keeps the queue full of REAL data

`scripts/story_forge.py` discovers indicators from the live World Bank WDI
catalogue, fetches world trends / country rankings, and writes datasets with
honest provenance (publisher, url, access_date, officiality=official). The
brain writes only the WORDS and the SCENE; every number comes from the
source. Run by `story_forge.yml` (twice daily) and by every posting run.
Never refill the queue with LLM-invented numbers — the editorial gate
refuses them, so a queue full of them still ships nothing.

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

| Agent | May write | May NEVER write |
|---|---|---|
| **Claude** | everything, on a `claude/*` branch through a PR | — |
| **ChatGPT** | the day's CONTENT (`exchange/bundles/<date>/response.json`, authored packages, media pointers) and retro SUGGESTIONS (`retro/<date>/proposals/*.json`) | any code, workflow, gate, doc, or contract |
| **CI** | run output — `state/`, `data_learning/data/`, reports | anything that changes behaviour |

Content authoring during a takeover is the quarterback role and is fine —
it keeps the channel posting, and everything it writes is validated and
quarantined on failure before it can render. Changing *how the pipeline
works* is Claude's alone, every time, through a reviewed branch.

`scripts/authorship_gate.py` enforces it from the other side, because a
rule that lives only in a README is a rule enforced by the agent it
constrains:

- **Smuggling** — a `.py`/`.yml` inside `retro/*/proposals/` or
  `exchange/bundles/`. Agent areas hold DATA and SUGGESTIONS only.
- **Contract edits** — an agent editing `retro/README.md` or
  `exchange/README.md`, i.e. its own instructions.
- **Direct pushes** — pipeline code changed on main outside a PR, which
  skips the sanity gate, the placement gate, and this one.

It runs on every PR (`auto-merge.yml`) and on every push to main
(`governance.yml`). CI's own state commits touch data only and pass clean.

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
