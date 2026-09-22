# OpenRangeInteractive — the documentary pipeline

**What ships:** three times a week (`curiosity.yml`, Mon/Wed/Fri 15:00 UTC,
plus `clock.yml` re-firing a missed slot), one 8–10 minute 1920x1080
documentary on an evergreen curiosity topic, uploaded to the
OpenRangeInteractive channel **only if the fail-closed showrunner passes it**.

```bash
python scripts/ori_author.py                     # top the script queue up (needs a brain)
python -m data_learning.ori_documentary --slug how-deep-is-the-ocean --out o.mp4
python -m data_learning.ori_documentary --slug how-deep-is-the-ocean --out o.mp4 --seconds 75   # preview
python scripts/post_ori.py --dry-run             # render + judge, no upload
```

Stop everything for this channel: commit `state/curiosity_kill_switch`.

## Why (2026-09-22)

The channel posted one video (2026-07-08) and then nothing for eleven weeks.
The "pro" producer (`scripts/produce.py` + `pro_render`, and a further 1,500
commits on the unmerged `feature/curiosity-pro-integration`) took two-plus
hours a render and its own blind judges returned five of five cuts BORING,
so every run quarantined; it also required an owner approval file written on
the runner, which a cron can never have. The operator, the day this was
built: *"I want you to be producing videos reliably that work and look good
... People do them all the time on the internet ... they get hundreds and
thousands of views."*

The format those channels share is plain and proven, and this builds it in
~30 minutes of CI: calm narration over **real footage that changes every ~4
seconds**, the numbers on screen as they are said, chapter cards, a ducked
music bed, captions, and a thumbnail made from a real frame. 8+ minutes so
mid-roll ads apply.

## The pieces

| file | job |
|---|---|
| `data_learning/ori_episodes/<slug>.json` | one episode script — the queue. `validate()` in the renderer is the contract |
| `data_learning/ori.config.json` | topic bank, queue minimum, the technical floor (min seconds, max footage misses) |
| `scripts/ori_author.py` | writes the next script with the brain chain (Claude CLI first, never the mailbox), validated, one retry with the reasons |
| `data_learning/ori_documentary.py` | script -> mp4 + thumbnail + chapters + captions |
| `scripts/post_ori.py` | kill switch -> reconcile -> render -> floor -> **showrunner** -> leak scan -> claim -> upload -> receipt -> `state/curiosity_posted_log.json` |

## Rules the tests hold (`tests/test_ori_documentary.py`)

- Every on-screen stat is **said in its own beat** — a number the narrator
  never says is usually one the author made up.
- 1,150–1,900 narrated words, 5–10 chapters, 3+ sources with real URLs.
- No clip twice in one film; a shot with no footage becomes a dark drift
  (never black) and is counted — too many misses and the episode does not ship.
- The gate runs before the upload, knows it is a publish run, and a BLOCK
  never reaches the uploader. A claim is written before the upload and a
  receipt after, so a crash in between is reconciled, never guessed.

## What is deliberately left

- The registry entry for `curiosity` still describes the retired pro queue
  and stays `enabled: false`, so Phase A/B, the daily alarm and ChatGPT's
  stocking job do not start supervising this channel. The documentary path
  publishes from its own cron, gated, exactly like `longform.yml`
  (`tests/test_disabled_channels_stay_off.py`, `ON_BUT_GATED`).
- The pro producer and its modes (`preview`, `pro`, `batch`, `schedule`) are
  untouched and manual-only.
