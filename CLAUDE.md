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
(`_a_pose`: hand targets + lower body + props + expression + motion). The rig
(how he's drawn) never changes; WHAT he does is regenerated per beat via
`author_performance(...)` — brain-authored when `MASCOT_BRAIN=1`, else a
distinct preset rotated by scene index so no two beats reuse the same act
(two "sitting" beats can be totally different: spooning soup off a can vs.
gripping a bird mid-flight). Add new acts as `POSE_PRESETS` entries; never
regress him to one static reused pose.

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
