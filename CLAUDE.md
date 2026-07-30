# Shorts-pipeline — notes for Claude sessions

Multi-channel automated YouTube pipeline (trending/daily, explainer,
curiosity, third "Proof Mode"). Channels are defined by orchestrator +
config + posted-log + token env, not by folders — see
`docs/STORAGE_AUDIT.md` §2 for the full map.

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

## Storage rules (from the audit — docs/STORAGE_AUDIT.md)

- Never commit media (mp4/png renders) or files >256KB to git; `state/` is
  for small JSON only. Renders die with the runner; previews go to the
  `preview-renders` orphan branch or artifacts.
- Posted logs (`state/*_posted_log.json`) are sacred append-only dedupe
  state — losing an entry means a duplicate upload.
- Do NOT open PRs from `claude/*` branches casually: `auto-merge.yml`
  squash-merges any non-draft `claude/*` PR with no review.
