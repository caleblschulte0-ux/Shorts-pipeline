# Storage Pipeline Audit

*Audited 2026-07-09 against commit `ae5fc2f`. Covers: what files the pipeline creates, where they live, what's committed vs ephemeral, cost/reliability/inefficiency risks, and the target architecture with executable tickets.*

---

## 1. Executive summary

The pipeline's core storage design — **small JSON state committed to git, big media kept ephemeral** — is fundamentally sound and cheaper than any paid alternative. You do not need external storage, Git LFS, or a database. What you need is to *actually enforce* the design you already have, because right now it's violated in three expensive ways:

1. **80MB of MP4s are tracked in git** (10 `preview/*.mp4` + `samples/economy_story.mp4`) despite `preview/` being gitignored — the ignore rule landed after the files were committed, and git never ignores already-tracked paths. Result: an **87MB pack in a repo that is 3 days old with 61 commits**. Extrapolated, this breaks GitHub's soft limits within months. *(Untracked in this branch; history purge is Ticket 7.)*

2. **State durability depends on the weakest `git push` in the fleet.** All four channels persist posted-logs/analytics by committing to `main`, concurrently — `daily` finishing triggers `explainer` and `third` *simultaneously*, and until this branch, `scout` fired on *every* push to main. `daily` and `explainer` have hardened 5-attempt push loops (explainer even union-merges the posted log). But **`third.yml`, `longform.yml`, and `scout.yml` have naive or zero retry**. A lost posted-log entry = the same video uploaded twice — this already happened (the "batch-3 incident" referenced in `third.yml`).

3. **`state/translation_cache.json` (1.6MB) is rewritten wholesale by three different channels** and has already deposited ~15MB of blobs into history across 11 versions. It's the single worst churn file and the highest-contention shared write.

Everything else is smaller-bore: caches that don't persist across CI runs (so stock footage and AI images are re-fetched/re-generated daily), non-atomic JSON writes, unbounded growth of committed analytics/packages, a latent credential-in-tree bug (fixed in this branch), and an unreviewed-LLM-to-main auto-merge path.

**Verdict:** no architectural rewrite needed. Enforce the existing model with ~10 targeted tickets, purge history once, and this scales to many channels for $0.

---

## 2. Current architecture map

### Channels × state × workflows

| Channel | Orchestrator | Config source | Posted log | Analytics | Workflow | Push robustness |
|---|---|---|---|---|---|---|
| trending/daily | `scripts/run_trending_daily.py` | `state/trending_packages/YYYYMMDD/*.json` | `state/posted_log.json` | `state/analytics/` | `daily.yml` | ✅ 5-attempt loop + cherry-pick fallback |
| explainer | `scripts/post_stories.py` | `data_learning/niche.config.json` | `state/explainer_posted_log.json` | `state/analytics_explainer/` | `explainer.yml` | ✅ 5-attempt loop + **union-merge of posted log** (gold standard) |
| curiosity | `scripts/post_curiosity.py` | `data_learning/curiosity.config.json` | `state/curiosity_posted_log.json` | `state/analytics_curiosity/` | `curiosity.yml` (cron disarmed) | ⚠️ retry loop, `-X ours` |
| third (Proof Mode) | `scripts/run_third.py` | `state/third_packages/YYYYMMDD/*.json` | `state/third_posted_log.json` | — | `third.yml` | ❌ single naive retry |
| longform | `scripts/build_longform.py` | (explainer config) | `state/longform_log.json` | — | `longform.yml` (Sunday cron) | ❌ single naive retry |
| scout (shared funnel) | `scripts/scout_sources.py` | — | — | `state/scouted_sources.json` | `scout.yml` | ❌ zero retry |

Shared writes: `state/translation_cache.json` (explainer + curiosity + third), `state/brain_context.json`, `state/video_ledger.json`, `data_learning/viz_mechanics.json`.

### Where every file class lives today

| File class | Location | Committed? | Cleaned up? |
|---|---|---|---|
| Posted logs / upload IDs | `state/*_posted_log.json` | ✅ yes (correct) | never (correct — append-only) |
| Analytics snapshots | `state/analytics*/YYYYMMDD.json` + `latest.json` | ✅ yes | ❌ never pruned/rolled up |
| Brain memory | `state/brain_context.json`, `state/video_ledger.json` | ✅ yes | bounded by convention only (≤200 lines) |
| Daily packages | `state/trending_packages/YYYYMMDD/`, `state/third_packages/` | ✅ yes (226+ files) | ❌ never |
| Translation cache | `state/translation_cache.json` | ✅ yes | ❌ grows + full rewrites |
| Final renders | `output/*.mp4` | ❌ gitignored | ephemeral runner (fine) |
| Preview renders | `preview/` + `preview-renders` orphan branch + artifacts | ⚠️ 10 old MP4s were tracked | orphan branch force-replaced (good pattern) |
| QA frames | `output/qa_frames/` | ❌ | ephemeral (fine) |
| TTS/audio/SFX | per-render `mkdtemp` workdirs | ❌ | `/tmp` never `rmtree`'d (harmless in CI, leaks locally) |
| Downloaded stock video | `/tmp/topic_videos/` (hardcoded) | ❌ | **wiped every CI run → re-downloaded daily** |
| Subject/hook/scene images | `state/hook_images/` etc. | ❌ gitignored | re-downloaded every CI run |
| AI-generated images | caller-specified `dest` | ❌ | **not content-addressed → regenerated every run** |
| Entity/news caches | `state/entity_media_cache.json`, `state/news_image_cache.json` | ❌ gitignored | reset every CI run |
| Models (Kokoro ~350MB, rembg ~170MB, music ~110MB) | runner dirs | ❌ | ✅ actions/cache (but no `restore-keys`) |
| OAuth tokens | env → `/tmp` files | ❌ (gitignored patterns) | latent bug wrote one into the repo tree (fixed this branch) |

### Trigger topology (the race map)

```
morning Claude Routine ──dispatch──▶ scout.yml ──push state──▶ main
                        ──dispatch──▶ daily.yml ──push state──▶ main
                                          │ (workflow_run: completed)
                              ┌───────────┴───────────┐
                              ▼                       ▼
                        explainer.yml            third.yml     ← run SIMULTANEOUSLY,
                        push state ──▶ main      push state ──▶ main   both write
                                                          translation_cache.json
Sunday cron ──▶ longform.yml ──push state──▶ main
```

Concurrency groups only serialize runs of the *same* workflow. Nothing serializes cross-workflow pushes to `main`.

---

## 3. Biggest risks, ranked by severity

| # | Risk | Severity | Evidence |
|---|---|---|---|
| 1 | **Duplicate upload after a lost posted-log commit.** `third.yml`/`longform.yml` have one naive push retry; a race with a concurrent channel push fails the persist step → uploaded video's log entry stranded → re-upload next run. Already happened once ("batch-3 incident", `third.yml:122`). | 🔴 High — audience-visible, YouTube-strike-adjacent | `third.yml:134-135`, `longform.yml:109-110` vs. explainer's union-merge (`explainer.yml:484-500`) |
| 2 | **Unreviewed LLM → main → runs with secrets.** `auto-merge.yml` squash-merges *any* non-draft `claude/*` PR with no checks; the CI brain runs headless Claude with Bash allowed and all API tokens in env. A hallucinated or prompt-injected change ships and executes with credentials. | 🔴 High — supply-chain | `auto-merge.yml:19`; brain steps in `daily.yml:236-239`, `explainer.yml:290-293` |
| 3 | **Multi-writer contention on `main`** (see trigger map). Every race consumes push-retry budget; the shared `translation_cache.json` is written by the three weakest-to-strongest pushers with `-X ours`, so silent cache-entry loss is routine. | 🟠 Medium-high | workflow fan-out + `state/translation_cache.json` in 3 persist lists |
| 4 | **Non-atomic state writes.** Nearly every JSON write is in-place `write_text()`; a crash mid-write truncates a posted log. Only `media_funnel._save_json` does temp+rename. Git push loops are the only safety net. | 🟠 Medium | `run_trending_daily.py:79`, `post_stories.py:56`, `run_third.py:64`, `fetch_analytics.py` |
| 5 | **Credential file written into the repo working tree** by `fetch_analytics._resolve_secret` (`ROOT/.{name}.runtime.json`), not covered by the `token*.json` ignore pattern. One widened `git add` away from committing an OAuth refresh token. | 🟠 Medium (latent — function was dead code) | **Fixed in this branch**: function deleted, `*.runtime.json` gitignored |
| 6 | **Repo size trajectory.** 87MB pack at 3 days old. Committed MP4s + translation-cache churn + daily analytics/package files compound. GitHub soft-warns at 1GB; pushes/clones/CI checkouts slow long before that. | 🟠 Medium (time bomb, not a today-problem) | `git count-objects -vH`: size-pack 86.65 MiB |
| 7 | **Silent quality rot.** Broad `except Exception` around every media provider means a dead API key degrades to stock/placeholder with only a printed line. Partially mitigated by the relevance gate and the zero-post safeguard. | 🟡 Medium-low | `entity_media.py:326`, `hook_media.py:94`, and dozens more |
| 8 | **Negative-result cache poisoning**: `entity_media_cache.json` caches "no media found" forever within a run; a transient network blip poisons that entity until the file resets. | 🟡 Low (self-heals each CI run) | `entity_media.py:305-307` |

## 4. Biggest inefficiencies, ranked by ROI

| # | Inefficiency | Cost today | Fix ROI |
|---|---|---|---|
| 1 | 80MB tracked MP4s + ~15MB translation-cache blobs in history | Every clone/CI checkout pays it, forever, compounding | ⭐⭐⭐ Untrack (done this branch) + one-time history purge |
| 2 | Stock video cache hardcoded to `/tmp/topic_videos/` | Full re-download of stock footage **every run** — bandwidth, wall-clock, provider quota | ⭐⭐⭐ One-line path change + actions/cache |
| 3 | AI-generated images not content-addressed | Same prompts re-billed to Gemini/Pollinations across runs | ⭐⭐⭐ Hash(prompt+params) key + actions/cache |
| 4 | `scout.yml` fired on every push to main | ~4-8 pointless runs/day, each one also *pushing to main* and worsening risk #3 | ⭐⭐⭐ Path filter (done this branch) |
| 5 | `translation_cache.json` committed with full rewrites | ~1.4MB of pack per touch, ×3 channels | ⭐⭐ Split per channel or move to actions/cache |
| 6 | Entity/hook/news caches gitignored → cold every run | Re-resolution API calls daily | ⭐⭐ actions/cache the `state/*_cache.json` files |
| 7 | No `restore-keys` on any actions/cache | Any key miss = full 350MB Kokoro re-download | ⭐⭐ Add `restore-keys` fallbacks |
| 8 | Stale workflows & dead code (`claude-smoke`, `test_funnel`, `gemini-diag` — deleted this branch; `make_trending.py`, `make_motiongraphic.py`, `tiktok_demo.py`, `run_daily.py`→`make_short.py` chain) | Maintenance confusion more than compute | ⭐ Delete |
| 9 | Committed analytics/packages grow unbounded (`state/analytics*/` dailies, `trending_packages/YYYYMMDD/`) | ~50-100KB/day/channel — small now, thousands of files in a year | ⭐ Rollup policy (keep the data, compact the files) |

---

## 5. Exact files / folders / workflows to inspect (index)

- **Persist/push logic:** `daily.yml:375-423`, `explainer.yml:428-509` (the union-merge to copy), `curiosity.yml:259-286`, `third.yml:121-136`, `longform.yml:99-111`, `scout.yml:49-61`
- **State writers:** `scripts/run_trending_daily.py:79`, `scripts/post_stories.py:54-56`, `scripts/post_curiosity.py:53-55`, `scripts/run_third.py:41-64`, `scripts/fetch_analytics.py:440-462`, `localize.py:81-89`
- **Dedupe/posting guards:** `run_trending_daily.py:652-679` (6h window), `run_third.py:41-50,177` (clip-key), `uploaders.py:241-257` (wrong-channel guard)
- **Caches:** `media_funnel.py:80-172` (the *only* TTL'd + atomic cache — the reference implementation), `entity_media.py:274-330`, `data_learning/hook_media.py:65-95`, `topic_video.py:68`
- **Secrets:** `uploaders.py:102-127` (correct /tmp pattern), `.gitignore:37-46`
- **Auto-merge exposure:** `.github/workflows/auto-merge.yml:19`

## 6. Recommended folder structure

Mostly *keep what you have* — the layout is fine; the policies are what's missing. Target:

```
state/                         # COMMITTED — small JSON only, hard rule: no file >256KB, no binaries
  <channel>/                   # (long-term) per-channel dirs instead of prefixed filenames:
    posted_log.json            #   posted log = sacred, append-only, union-merged
    analytics/latest.json      #   + rolling dailies (90d) + monthly rollups
    packages/YYYYMMDD/*.json   #   authored packages
  shared/
    brain_context.json, video_ledger.json, scouted_sources.json
cache/                         # GITIGNORED — persisted via actions/cache only
  translation/<channel>.json   # split per channel, sorted-key stable serialization
  entities.json, news_images.json
  stock_video/<sha1>.mp4       # moved from /tmp/topic_videos
  gen_images/<sha1-of-prompt+params>.png
output/                        # GITIGNORED — render workspace, dies with the runner
preview/                       # GITIGNORED — publish via `preview-renders` orphan branch + artifacts (existing pattern, keep it)
```

The `state/<channel>/` reorg is long-term (Ticket 11) — renaming live state files mid-flight is risk for cosmetic gain. Do it last or never; the prefixed names work.

## 7. Commit vs cache vs artifact vs delete — the policy

| Class | Policy | Why |
|---|---|---|
| Posted logs, upload IDs | **Commit** (union-merge on conflict, never prune) | Loss = duplicate posts. Git history is your backup. |
| Brain memory (`brain_context`, `video_ledger`, `viz_mechanics`) | **Commit** (keep size-bounded) | The learning loop's source of truth; Claude reads it from the repo. |
| Analytics snapshots | **Commit**, rollup: dailies for 90d → monthly aggregates forever | Never lose the learning data, but don't hold 3,650 files in 10 years. |
| Daily packages (`trending_packages/`, `third_packages/`) | **Commit**, archive dirs >90d into one `archive/YYYYMM.json` per month | Same. |
| Translation cache | **actions/cache** (per-channel files) with a committed snapshot only if regeneration cost proves painful | Regenerable at modest LLM cost; not worth 1.4MB pack churn per touch. |
| Media caches (entity, news, hook URLs) | **actions/cache**, keyed on script hash, `restore-keys` fallback | Regenerable; caching just saves quota + latency. |
| Downloaded stock footage, AI-gen images | **actions/cache**, content-addressed (`sha1(url)` / `sha1(prompt+params)`) | The actual money-saver. |
| Final renders | **Delete** (die with the runner). YouTube *is* the archive. Optionally upload-artifact 5-day retention for debugging | Never in git. |
| Preview renders, contact sheets, QA frames | **Artifacts** (14d) + `preview-renders` orphan branch (existing pattern — good) | Reviewable without pack bloat. |
| Models (Kokoro, rembg, music) | **actions/cache** (already done) + add `restore-keys` | — |
| Credentials | **env → /tmp only**, never the tree | — |
| Logs (`scout_errors.log`) | Commit is acceptable while small; cap size, truncate oldest | — |

Nothing here needs paid storage. actions/cache gives 10GB/repo free (LRU-evicted, 7-day idle expiry — always code the "cache miss = re-download" path, which you already have).

## 8. Migration plan

### Phase 0 — Quick wins (✅ applied on this branch)
1. Untracked `preview/*.mp4` + `samples/economy_story.mp4` (`git rm --cached`; files stay on disk); gitignored `samples/*.mp4`.
2. Deleted latent credential-in-tree code path in `fetch_analytics.py` (dead function `_resolve_secret`); added `*.runtime.json` to `.gitignore`.
3. Deleted stale workflows: `claude-smoke.yml`, `test_funnel.yml`, `gemini-diag.yml`.
4. Narrowed `scout.yml` push trigger to `scripts/scout_sources.py` + new `.github/triggers/scout` file.

### Phase 1 — Reliability (do these before adding any more channels)
Tickets 1, 2, 3 below: shared hardened commit script everywhere, atomic writes, translation-cache split. These close the duplicate-post hole.

### Phase 2 — Cost/efficiency
Tickets 4, 5, 6, 8: persistent media caches, content-addressed AI gens, `restore-keys`, analytics rollup.

### Phase 3 — One-time cleanup (operator-coordinated)
Ticket 7 (history purge — the only destructive step) and Ticket 9 (dead code sweep).

### Phase 4 — Long-term ideal
Tickets 10-12: auto-merge gating, per-channel `state/` layout, per-video manifest.

---

## 9. Implementation tickets (one Claude Code session each)

**Ticket 1 — Shared hardened state-commit script.** Create `scripts/ci_commit_state.sh`: 5-attempt loop; `git pull --rebase --autostash`; on rebase failure, back up the named state files, hard-reset to `origin/main`, restore, **union-merge every `*_posted_log.json`** (generalize the inline Python from `explainer.yml:484-500` into `scripts/merge_posted_log.py`), re-commit. Replace the persist steps in `third.yml`, `longform.yml`, `scout.yml`, `curiosity.yml`, `daily.yml`, `explainer.yml` with calls to it. *Acceptance: kill -9 a fake concurrent push race in a test and verify no posted-log entry is lost.*

**Ticket 2 — Atomic JSON writes.** Add `atomic_write_json(path, obj)` (temp file in same dir + `os.replace`, sorted keys, trailing newline) to a small `fsutil.py`; adopt in the 5 posted-log writers, `fetch_analytics.py`, `localize.py`, and scout. Model it on `media_funnel._save_json` (`media_funnel.py:138-142`).

**Ticket 3 — Translation cache: split + evict from git.** Split `state/translation_cache.json` per channel (`localize.py` keyed by channel env), move to `cache/translation/<channel>.json`, gitignore, persist via actions/cache keyed `translation-<channel>-v1` with `restore-keys`. `git rm --cached` the old file. Keep a `--snapshot` escape hatch that commits a copy if regeneration cost ever hurts.

**Ticket 4 — Stock-video cache out of /tmp.** `topic_video.py:68`: `/tmp/topic_videos` → `ROOT/cache/stock_video` (env-overridable), gitignore `cache/`, add actions/cache with key `stock-video-v1` + `restore-keys` to `daily.yml`/`preview.yml`. Add a size cap (delete oldest beyond ~2GB) so the cache doesn't grow past eviction usefulness.

**Ticket 5 — Content-address AI image generation.** In `gemini_images.py`, before generating: `key = sha1(model + prompt + str(params))`; check `cache/gen_images/<key>.png`; write there on success and copy to the caller's `dest`. actions/cache the dir. Also gives cross-channel reuse for free; add a per-channel salt if visual repetition across channels becomes a concern.

**Ticket 6 — Analytics + package rollup.** Monthly job (or step in `daily.yml`): fold `state/analytics*/YYYYMMDD.json` older than 90 days into `state/analytics*/rollup/YYYYMM.json` (preserving per-video final metrics + retention curves), delete the dailies; same for `trending_packages/`/`third_packages/` dirs >90d → `archive/YYYYMM.json`. **Never touch posted logs.**

**Ticket 7 — History purge (operator-run, destructive).** Once Phase 0 has merged: pause routines/workflows (`PAUSED` file), `git filter-repo --path preview --path samples/economy_story.mp4 --invert-paths` (also strip historical `translation_cache.json` blobs), force-push `main`, re-clone everywhere, unpause. Shrinks the pack from ~87MB to <10MB. Cheap now (3-day-old repo, no forks); expensive forever later. Do it soon or accept the 87MB floor permanently.

**Ticket 8 — `restore-keys` everywhere.** Add `restore-keys` fallbacks to the Kokoro, gameplay, rembg, broll, and music caches in all five render workflows so a key change degrades to a stale-cache hit instead of a full re-download.

**Ticket 9 — Dead code sweep.** Delete `make_trending.py`, `make_motiongraphic.py`, `tiktok_demo.py`, `tiktok_demo_oneclick.ps1`, and the unused `scripts/run_daily.py` → `make_short.py`/`make_explainer.py` chain (verify no workflow/doc references first). Also `scripts/diag_gemini.py` (its workflow is gone).

**Ticket 10 — Gate auto-merge.** `auto-merge.yml` currently merges any non-draft `claude/*` PR sight-unseen. Minimum: require a passing sanity check (workflows parse, `py_compile` all touched Python, no file >1MB, no new binary, no diff touching `.github/workflows/` or `uploaders.py` without a human label). Ideal: allowlist the paths the brain is *supposed* to write (`state/*_packages/**`, `data_learning/*.md`).

**Ticket 11 — (Optional, long-term) per-channel `state/<channel>/` layout** per §6. Only worth it when adding channel #5+; requires touching every orchestrator + workflow persist list in one PR.

**Ticket 12 — (Optional) per-video manifest.** One `state/<channel>/videos/<slug>.json` per posted video: package ref, render decisions, QA verdict, upload ID, experiment tags, analytics pointer. Gives Claude's brain a searchable per-video memory instead of grepping five logs. Fold into Ticket 11's layout.

**Also fix while nearby (small):** entity-cache negative entries should carry a TTL (`entity_media.py:305-307`); `media_funnel._quota_check` should decrement on failed calls (`media_funnel.py:175-202`).

---

## 10. What I deliberately did NOT recommend

- **Git LFS** — solves nothing here; you shouldn't be committing media at all, and LFS adds quota billing + CI friction.
- **S3/R2/GCS** — unjustified. YouTube stores your finals, git stores your state, actions/cache stores your regenerables. Revisit only if you someday need render intermediates shared across jobs >10GB.
- **A database** — the JSON-in-git model gives you versioning, audit trail, and Claude-readability for free. The fix is atomicity + merge discipline, not Postgres.
- **Serializing all channels behind one global lock** — would fix races but serialize 60-120 min renders. The union-merge commit script (Ticket 1) fixes correctness without the wall-clock cost.
