# Pipeline layout — the funnel architecture (reorg 2026-07-30)

The repo is organized as one funnel feeding every channel. Top of funnel
finds/generates media; the shared layer holds everything all channels use;
each channel is a thin consumer at the bottom. **Every channel has access to
everything above the channel line.**

```
        ┌─────────────────────────────────────┐
        │      funnel/   TOP OF FUNNEL MEDIA  │   find + generate media
        └───────────────────┬─────────────────┘
        ┌───────────────────┴─────────────────┐
        │  shared/ + engines/  SHARED LAYER   │   everything channels share
        └───────────────────┬─────────────────┘
   ┌─────────┬──────────────┼──────────────┬─────────────┐
   daily     explainer      curiosity      third         longform/scout
```

## funnel/ — top of funnel media

| Module | Job |
|---|---|
| `funnel/media_funnel.py` | 22-provider parallel media funnel (source_class + license) |
| `funnel/topic_media.py` | Wikipedia/Openverse subject-image finder |
| `funnel/entity_media.py` | entity → media resolution + funnel cache |
| `funnel/media_usage.py` | cross-video usage ledger (repetition penalty) |
| `funnel/gemini_images.py` | AI image generation (Pollinations primary, free) + vision QA + thumbnails |
| `funnel/og_scrape.py` | og:image hero scraping for evidence URLs |
| `funnel/stock_search.py` | stock video meta-search (`pexels_search`, `pixabay_search`, `mixkit_search`) |
| `funnel/topic_video.py` | topic → stock video finder |
| `funnel/gameplay_scanner.py` | gameplay library motion-scanner (bottom-half supply) |
| `funnel/higgsfield.py` | still-image animation via external API (dormant) |
| `funnel/feeds.py` | RSS/Atom research intake, TTL-cached (stdlib, never raises) |
| `funnel/article_extract.py` | clean article text from a URL (trafilatura lane + dependency-free heuristic) |

## shared/ — everything else shared between all channels

| Module | Job |
|---|---|
| `shared/fsutil.py` | atomic JSON writes (all state IO goes through this) |
| `shared/uploaders.py` | multi-channel YouTube upload + token routing + TikTok/Reels |
| `shared/localize.py` | translation / localized metadata |
| `shared/script_generator.py` | LLM call helpers (Claude/Groq) + script authoring |
| `shared/themed_bottom.py` | themed bottom-half game renderer |
| `shared/video_qa.py` | finished-render QA: black/freeze/silence/loudness (`python -m shared.video_qa out.mp4`); `passes()` fails closed |
| `shared/captions.py` | word-timed karaoke ASS captions from whisper words + ffmpeg burn |

## engines/ — registered render capabilities

Unchanged, already shared: registry + CLI (`python -m engines list|info|doctor|install|demo`).
See `docs/ENGINE_REGISTRY.md`. Contract: `maybe_*()` returns result or `None`, never raises.

## Channels (bottom of funnel — thin consumers)

| Channel | Orchestrator | Renderer stack |
|---|---|---|
| daily/trending | `scripts/run_trending_daily.py` | `make_explainer_stacked.py`, `make_graph_race.py`, `make_reddit_story.py`, `make_text_card.py`, `reddit_card.py` (root) |
| explainer | `scripts/post_stories.py` | `data_learning/` |
| curiosity | `scripts/post_curiosity.py` | `data_learning/longform_render.py` |
| third (Proof Mode) | `scripts/run_third.py` | `third_capture/` |
| longform | `scripts/build_longform.py` | `data_learning/` |

Operator tools stay at root: `setup_youtube.py`, `seed_gameplay.py`.
CI plumbing stays in `scripts/`: `ci_commit_state.sh`, `merge_posted_log.py`, etc.

## Rules

1. **Channels import canonically**: `from funnel import media_funnel`,
   `from shared import uploaders`, `from engines import ...`. Never add new
   code that imports the old root names.
2. **Legacy shims exist and are safe**: every pre-reorg root module
   (`media_funnel.py`, `fsutil.py`, …) is a shim that aliases the canonical
   module via `sys.modules` — old imports still work and share the same
   module object (caches, quota state, singletons identical). Older docs and
   branches that reference old paths therefore remain valid.
3. **New shared capability?** Media acquisition/generation → `funnel/`.
   Registered render engine with the `maybe_*` contract → `engines/`.
   Everything else cross-channel → `shared/`. Channel-specific → that
   channel's stack. Never copy shared logic into a channel.
4. **Nothing shared may live inside a channel dir.** If a second channel
   needs it, it moves up the funnel.
5. Path constants inside `funnel/`/`shared/` modules anchor to the **repo
   root** (`Path(__file__).resolve().parent.parent`) — caches stay in
   `cache/`, state in `state/`, exactly as before the reorg.
