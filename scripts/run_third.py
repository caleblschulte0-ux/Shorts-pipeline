#!/usr/bin/env python3
"""Proof Mode ("third" channel) orchestrator: capture -> compose -> upload.

Fully isolated from the shared trending/explainer pipelines
(THIRD_BRAIN.md §13): reads packages from state/third_packages/YYYYMMDD/,
logs to state/third_posted_log.json, uploads with channel="third" so the
uploader reads YOUTUBE_TOKEN_JSON_THIRD, and honors YOUTUBE_EXPECTED_CHANNEL.

Each package's `capture` block is EXECUTED for real (capture_cli) and the
resulting proof ledger drives every number the composer puts on screen.
If the capture fails (non-zero exit), the package is killed, not
improvised — THIRD_BRAIN.md §7.

Usage:
    python scripts/run_third.py --dry-run            # render only
    python scripts/run_third.py                      # render + upload
    python scripts/run_third.py --date 20260707
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from third_capture import capture_cli  # noqa: E402
from third_capture import compose as composer  # noqa: E402
from third_capture import author  # noqa: E402  (title safety choke)

PACKAGE_DIR = REPO / "state" / "third_packages"
LOG_PATH = REPO / "state" / "third_posted_log.json"
OUTPUT_DIR = REPO / "output"

# Run-level banger cache: {clip_url: (banger 0-1, why)}. The brain scores a
# clip's shareability once per process; later slots reuse it instead of
# paying another brain call on a shortlist that overlaps heavily with the
# previous slot's (same board minus what we just posted).
_BANGER_CACHE: dict = {}

# ------------------------------------------------------------- judges
# Several brains judge every slot — the banger ranker, the transcript-aware
# content gate, the story director, the vision critic, the render_qa engine
# — and until now their reasoning existed ONLY in the CI log, which expires
# and takes ~1200 lines to read. Answering "why was this clip rejected?" a
# day later meant log archaeology. These verdicts are recorded per slot and
# persisted into state/third_qa_stats.json, where `scripts/judges.py`
# renders them. Kept deliberately small (reasons truncated) — state/ is for
# small JSON only (docs/STORAGE_AUDIT.md).
_JUDGES: dict = {}


# ------------------------------------------------- source health
# A source that fails every run is silent lost supply: it costs an API
# call and a log line each time and contributes nothing. rumble:AdinLive
# has failed on BOTH url shapes every run for days and nobody could see it
# without reading the log. Recording per-source outcomes turns "is this
# allowlist any good?" into data — dead handles become prunable, and a
# widened allowlist can be judged on what it actually returns.
_SOURCE_HEALTH: dict = {}


def _source_health(platform: str, ch: str, *, ok: bool,
                   clips: int = 0, err: str = "") -> None:
    try:
        k = f"{platform}:{ch}"
        e = _SOURCE_HEALTH.setdefault(k, {"ok": 0, "fail": 0, "clips": 0})
        e["ok" if ok else "fail"] += 1
        e["clips"] += int(clips)
        if err:
            e["err"] = err[:60]
    except Exception:  # noqa: BLE001
        pass


def _any_judgment() -> bool:
    """Did ANY content judge actually evaluate this slot's clip?

    Reads the verdicts recorded for the current slot. True when at least
    one of the three content judges produced a real opinion:
      - the banger ranker scored it (not the blind can't-score default)
      - the content gate returned a transcript-aware score
      - the vision critic looked at the frames
    Mechanical checks (preflight, render_qa) deliberately do NOT count:
    they prove the file isn't broken, never that the clip is worth posting.
    """
    j = _JUDGES
    # A RESCUED CLIP NEEDS A *PASSING* JUDGMENT, NOT MERELY A JUDGMENT.
    # The rescue exists precisely because the only opinion so far was
    # NEGATIVE — the ranker scored it under the posting floor. Counting
    # that negative score as "someone judged it" let a clip the ranker
    # rated 0.30 ("vague emote reaction") ship unopposed whenever no
    # second judge could be reached. That is the inverse of this gate's
    # purpose: treating a rejection as evidence to publish.
    if j.get("selection", {}).get("verdict") == "rescue":
        return (j.get("content", {}).get("verdict") == "pass"
                or j.get("vision", {}).get("verdict") == "pass")
    if not j.get("banger", {}).get("blind", True):
        return True
    if j.get("content", {}).get("verdict") in ("pass", "reject"):
        return True
    if j.get("vision", {}).get("verdict") in ("pass", "reject"):
        return True
    return False


def _story_verdict(label: str, outcome: str, why: str) -> None:
    """One cluster's fate at the story director's hands. Appends (a slot
    considers several clusters), so the record shows the whole deliberation
    — critically, WHETHER a story failed because no arc existed or because
    the analysis was starved. Those look identical in the posted log today
    and mean completely different things."""
    try:
        _JUDGES.setdefault("story_director", {}).setdefault(
            "clusters", []).append(
                {"cluster": str(label)[:60], "outcome": outcome,
                 "why": str(why)[:140]})
    except Exception:  # noqa: BLE001
        pass


def _judge(name: str, **fields) -> None:
    """Record what one judge thought about the CURRENT slot. Merges, so a
    judge that speaks twice (e.g. a retry) keeps its latest verdict. Never
    raises — an observability path must not be able to fail a render."""
    try:
        clean = {}
        for k, v in fields.items():
            if v is None or v == "":
                continue
            # Coerce to JSON-SAFE primitives here, at the door. Storing a
            # raw object survives this function but detonates later at the
            # json.dumps on attach — and that call sits outside the render's
            # try block, so a bad verdict value would kill the whole slot.
            # An observability path must not be able to do that.
            if isinstance(v, str):
                v = v[:160]
            elif isinstance(v, bool) or isinstance(v, int):
                pass
            elif isinstance(v, float):
                v = round(v, 3)
            elif isinstance(v, (list, tuple)):
                v = [str(x)[:160] for x in list(v)[:5]]
            else:
                v = str(v)[:160]
            clean[k] = v
        if clean:
            _JUDGES.setdefault(name, {}).update(clean)
    except Exception:  # noqa: BLE001
        pass


ANALYTICS_LATEST = REPO / "state" / "analytics_third" / "latest.json"
EVENTS_FILE = REPO / "state" / "third_events.json"


class _SkipSlot(Exception):
    """Raised to abandon a slot on purpose (e.g. nothing clears the quality
    floor) — caught as a clean skip, never an error or a blocklist entry."""


def _audit_dupes(log: dict) -> list:
    """Permanent tripwire on the channel's core law: scan the posted log for
    any source clip that's been posted under more than one slug and surface
    it LOUDLY every run. The upload guard + log-freshness sync prevent new
    dupes; this makes any that slip through (or already exist) impossible to
    miss instead of silently living on the channel. Returns the dup groups."""
    from collections import defaultdict
    by_key = defaultdict(list)
    for slug, v in log.get("posted", {}).items():
        if slug.startswith("rejected-") or v.get("qa_rejected"):
            continue
        k = _clip_key(v.get("source_url", ""))
        if k:
            by_key[k].append(slug)
    dups = [(k, s) for k, s in by_key.items() if len(s) > 1]
    if dups:
        print(f"::warning::[dedupe] {len(dups)} DUPLICATE clip(s) live in the "
              "posted log (same source, multiple posts):", flush=True)
        for k, slugs in dups:
            print(f"::warning::[dedupe]   {k} -> {', '.join(sorted(slugs))}",
                  flush=True)
    else:
        print("[dedupe] audit clean — no duplicate clips in the posted log",
              flush=True)
    return dups

# Cache the learned prior for the whole run (the snapshot doesn't change
# mid-run). None = not yet computed; {} = computed, nothing usable.
_PRIOR_CACHE: dict | None = None
_STORY_POOL: list | None = None   # run-wide wide-sweep discovery cache


def _learned_prior() -> dict:
    """Per-streamer performance multiplier learned from THIS channel's own
    YouTube results (state/analytics_third/latest.json, written by
    fetch_analytics.py --channel third). Velocity + banger judge a clip
    before we post it; this is the only signal that knows what actually
    RETAINED once it was a Short on our channel.

    Metric per posted video: retention (average_view_percentage) when the
    token carries the analytics scope, else views-per-hour — each expressed
    as a ratio to the channel baseline so 'good' means 'beat our own median'.
    Per streamer we average those ratios, shrink hard toward 1.0 by sample
    size (a lucky single clip barely moves it), and clamp to a GENTLE
    [0.70, 1.40] band: the prior breaks ties and buries a consistent flop,
    but can never by itself override a big fresh banger, and never starves a
    streamer we have too little data on. Returns {} (neutral) when there's
    no snapshot yet — the channel just runs on velocity+banger until data
    accrues. Never raises."""
    global _PRIOR_CACHE
    if _PRIOR_CACHE is not None:
        return _PRIOR_CACHE
    _PRIOR_CACHE = {}
    try:
        if not ANALYTICS_LATEST.exists():
            return _PRIOR_CACHE
        import math
        AVP_CAP = 200.0   # a looped 5-view clip reports 1500% — cap it
        MIN_PUBLIC_AGE = 24.0     # judge on 24h+ maturity, not 6h noise
        MIN_STREAMER_VIDS = 3     # 1-2 clips is not evidence about a streamer
        snap = json.loads(ANALYTICS_LATEST.read_text())
        # ELIGIBILITY: public, aged >=24h, and — for the retention signal —
        # enough views that AVP means something (usable_for_retention, the
        # views>=50 gate set in fetch_analytics). Scheduled/private videos
        # never carry usable_for_retention or is_public, so they're excluded
        # automatically.
        vids = [v for v in snap.get("videos", [])
                if v.get("streamer")
                and v.get("is_public", True)
                and (v.get("age_hours") or 0) >= MIN_PUBLIC_AGE
                # story compilations are a different FORMAT (60-120s multi
                # clip): their retention says nothing about how this
                # streamer's single clips perform — keep the prior clean
                and v.get("actual_structure") != "story"]
        if not vids:
            return _PRIOR_CACHE
        # Channel baselines (capped AVP; velocity from aged videos only).
        vph = sorted(v["views_per_hour"] for v in vids
                     if v.get("views_per_hour", 0) > 0)
        vph_med = vph[len(vph) // 2] if vph else 0.0
        rets = [min(v["average_view_percentage"], AVP_CAP) for v in vids
                if v.get("usable_for_retention")
                and v.get("average_view_percentage") is not None]
        ret_mean = (sum(rets) / len(rets)) if rets else 0.0

        def _ratio(v):
            """Return (ratio, weight) or None. Retention only counts with a
            usable sample; weight by sqrt(engaged_views) so a 500-view result
            outweighs a 50-view one."""
            w = math.sqrt(max(1.0, v.get("engaged_views") or v.get("views", 0)))
            if (v.get("usable_for_retention")
                    and v.get("average_view_percentage") is not None
                    and ret_mean > 0):
                r = min(v["average_view_percentage"], AVP_CAP) / ret_mean
            elif vph_med > 0 and v.get("views_per_hour", 0) >= 0:
                r = v["views_per_hour"] / vph_med
            else:
                return None
            return max(0.3, min(3.0, r)), w

        from collections import defaultdict
        buckets: dict = defaultdict(list)
        for v in vids:
            rw = _ratio(v)
            if rw is not None:
                buckets[str(v["streamer"]).lower()].append(rw)

        K = 4.0  # shrinkage strength: n/(n+K) weight on observed deviation
        prior = {}
        for streamer, rws in buckets.items():
            n = len(rws)
            if n < MIN_STREAMER_VIDS:   # too few clips to trust a prior
                continue
            wsum = sum(w for _, w in rws) or 1.0
            mean_r = sum(r * w for r, w in rws) / wsum   # engagement-weighted
            eff = 1.0 + (mean_r - 1.0) * (n / (n + K))
            mult = max(0.70, min(1.40, eff))
            if abs(mult - 1.0) >= 0.02:  # skip no-op entries
                prior[streamer] = round(mult, 3)
        _PRIOR_CACHE = prior
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[prior] learned prior unavailable ({e})",
              flush=True)
        _PRIOR_CACHE = {}
    return _PRIOR_CACHE


_GUIDANCE_CACHE: str | None = None


def _opening_guidance() -> str:
    """A directive for the director brain, learned from our own retention
    CURVES: if recent Shorts systematically bleed viewers in the first ~2s
    (the swipe-away happens in the hook, never the payoff), tell the brain to
    open tighter. Empty when openings are healthy or there's no curve data
    yet — so the brain's normal 'include the setup' rule stands unchanged
    until the channel proves it's losing people early. Never raises."""
    global _GUIDANCE_CACHE
    if _GUIDANCE_CACHE is not None:
        return _GUIDANCE_CACHE
    _GUIDANCE_CACHE = ""
    try:
        if not ANALYTICS_LATEST.exists():
            return _GUIDANCE_CACHE
        snap = json.loads(ANALYTICS_LATEST.read_text())
        op = (snap.get("summary") or {}).get("opening") or {}
        med = op.get("median_early_retention")
        n = op.get("videos_with_curve", 0)
        # Need a real sample and a real problem. 0.80 = a fifth of the
        # audience already gone before the moment even lands.
        if med is None or n < 3 or med >= 0.80:
            return _GUIDANCE_CACHE
        lost = round((1.0 - med) * 100)
        _GUIDANCE_CACHE = (
            f"Our recent Shorts lost ~{lost}% of viewers in the first 2 "
            "seconds. Open TIGHTER: set edit.cut.start at the first genuinely "
            "engaging beat — trim slow lead-in, dead air, and throat-clearing "
            "BEFORE the setup. Keep only the minimum context needed to "
            "understand the moment, then get to it fast. Make the hook land "
            "in the first second. Do NOT open on a calm/quiet ramp.")
        print(f"[guidance] opening steer active (median early retention "
              f"{med:.2f} over {n} clips): tighten openings", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[guidance] unavailable ({e})", flush=True)
        _GUIDANCE_CACHE = ""
    return _GUIDANCE_CACHE


def _feedback_status() -> dict:
    """Report whether the feedback-loop brains are ALIVE or DARK, and why —
    so we never silently build on a data source that isn't flowing. Reads the
    same snapshot selection reads and calls the same prior/guidance helpers,
    so the banner reflects exactly what this run will actually use. Three
    features hang off retention data (streamer prior, opening steer) or the
    posted log (banger); this surfaces which are live. Returns a compact dict
    (also stored in the learning-loop stats) and prints a banner. Never
    raises."""
    st: dict = {"snapshot": False, "prior_streamers": 0,
                "opening_steer": False, "retention_scope": False,
                "videos": 0, "with_retention": 0, "with_curve": 0}
    try:
        if ANALYTICS_LATEST.exists():
            snap = json.loads(ANALYTICS_LATEST.read_text())
            st["snapshot"] = True
            vids = snap.get("videos", [])
            summ = snap.get("summary") or {}
            st["videos"] = len(vids)
            st["with_retention"] = sum(
                1 for v in vids
                if v.get("average_view_percentage") is not None)
            st["with_curve"] = (summ.get("opening") or {}).get(
                "videos_with_curve", 0)
            st["retention_scope"] = st["with_retention"] > 0
            st["fetched_at"] = snap.get("fetched_at")
        # These reflect what selection will actually apply this run.
        st["prior_streamers"] = len(_learned_prior())
        st["opening_steer"] = bool(_opening_guidance())
    except Exception as e:  # noqa: BLE001 — status never fails a run
        st["error"] = f"{type(e).__name__}: {e}"

    def _mark(on): return "ACTIVE" if on else "dark"
    print("[feedback] velocity=ACTIVE (always) | "
          f"banger=ACTIVE (brain) | "
          f"streamer-prior={_mark(st['prior_streamers'])}"
          f"({st['prior_streamers']} streamers) | "
          f"opening-steer={_mark(st['opening_steer'])}", flush=True)
    if not st["snapshot"]:
        print("[feedback] ::warning:: no analytics_third snapshot yet — the "
              "retention brains are DARK; selection runs on velocity+banger "
              "only. Confirm the 'Fetch third analytics' workflow step ran.",
              flush=True)
    elif not st["retention_scope"]:
        print("[feedback] ::warning:: snapshot present but 0 videos carry "
              "retention — the token likely lacks the yt-analytics.readonly "
              "scope (or no post has enough watch data yet). Streamer-prior "
              "runs on views/hour; opening-steer stays DARK until curves "
              "arrive. Re-auth via setup_youtube.py on the third account to "
              "unlock retention.", flush=True)
    else:
        print(f"[feedback] retention scope ACTIVE — {st['with_retention']}/"
              f"{st['videos']} videos with retention, {st['with_curve']} with "
              "an opening curve.", flush=True)
    return st


def _clip_key(url: str) -> str:
    """Canonical clip identity for dedupe. Twitch serves one clip as both
    `clips.twitch.tv/SLUG` and `twitch.tv/<ch>/clip/SLUG`; both reduce to
    SLUG here, so the same clip can never post twice regardless of the URL
    form it was discovered under. Falls back to the trimmed URL."""
    if not url:
        return ""
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    # A VOD-MINED moment is `vodmine://<video_id>/<offset>`. Taking the
    # last segment would key it on the OFFSET alone, so two moments at the
    # same second of two different VODs would collide — in the posted log,
    # where a collision means a duplicate upload. Key on the whole
    # identity instead.
    if path.startswith("vodmine://"):
        return path.lower()
    seg = path.rsplit("/", 1)[-1]
    return seg.lower() or path.lower()


def _load_log() -> dict:
    if LOG_PATH.exists():
        try:
            log = json.loads(LOG_PATH.read_text())
        except json.JSONDecodeError as e:
            # FAIL CLOSED. This used to `pass` and return {"posted": {}} —
            # so an unparseable ledger (a truncated write, a mis-resolved
            # merge, a hand-edit) meant the run proceeded with ZERO dedupe
            # state: _audit_dupes prints "clean", posted_keys is empty,
            # every slot re-posts an already-published clip, and then
            # _save_log writes the 4-entry dict OVER 168 real entries and
            # ci_commit_state pushes it. merge_posted_log only runs on a
            # push race, so on a clean push the ledger is gone for good.
            # A missing file is a first run; a corrupt file is an
            # emergency, and the two must never be confused.
            raise SystemExit(
                f"FATAL: {LOG_PATH} is not valid JSON ({e}). Refusing to "
                f"run with no dedupe state — that re-posts the whole "
                f"catalogue and then overwrites the ledger. Restore it "
                f"from git history before running again.")
        if not isinstance(log, dict) or not isinstance(
                log.get("posted"), dict):
            raise SystemExit(
                f"FATAL: {LOG_PATH} parsed but is not a posted log "
                f"(expected {{'posted': {{...}}}}). Refusing to run.")
        return log
    return {"posted": {}}


def _save_log(log: dict) -> None:
    from shared.fsutil import atomic_write_json
    atomic_write_json(LOG_PATH, log)


def _blocklist(log: dict, key: str, entry: dict) -> None:
    """Record a rejected clip AND PERSIST IT IMMEDIATELY.

    Four paths write `rejected-*` entries (preflight, the content gate,
    director incompleteness, QA) and none of them used to hit disk: the
    only _save_log call site was inside the successful-upload branch, so a
    run that shipped nothing discarded every rejection it had paid for.
    2026-07-31 ran four times; runs 2-4 each re-downloaded, re-transcribed
    and re-judged the exact clips run 1 had already turned down hours
    earlier — ~9 wasted whisper passes per run, and the direct reason the
    reject reasons repeat verbatim across those runs."""
    log["posted"][key] = entry
    try:
        _save_log(log)
    except Exception as e:  # noqa: BLE001
        print(f"[blocklist] could not persist {key}: {e}", flush=True)


# Wall-clock budget for the whole run, well inside third.yml's
# timeout-minutes: 120. See _deadline_passed().
_BUDGET_MIN = float(os.environ.get("THIRD_BUDGET_MIN", "85"))
_T_START = time.time()


def elapsed_min() -> float:
    return (time.time() - _T_START) / 60.0


def _deadline_passed() -> bool:
    return elapsed_min() >= _BUDGET_MIN


_SWEEP_CACHE: dict = {}


def _sweep(clip_edit, sources: dict, window: str, top: int) -> list:
    """Discover across every allowlisted handle for one window — ONCE.

    This was inline in process(), so it re-ran from scratch on every slot
    and every retry: 67 handles x 2 windows x (4 slots x 3 attempts) is
    ~1,600 discovery calls per run, and third_qa_stats.json recorded the
    proof — every source's health entry read "ok": 18, i.e. eighteen hits
    per handle in one run. At ~1s each (helix) that is 20 minutes; on the
    yt-dlp path it is closer to an hour, and the job ceiling is 120
    minutes with a run already killed on that wall. The top-clip board for
    a channel does not change inside one 90-minute job, and every filter
    that makes a retry pick a DIFFERENT clip (posted_keys, the blocklist,
    the variety caps) runs downstream of this — so caching the pool costs
    nothing in selection freshness.

    Fanned out too: the calls are independent and each one's failure is
    already caught per-handle, so a serial loop over 67 handles was pure
    latency. The story arm already cached its own sweep (_STORY_POOL);
    the clip arm was the one paying full price."""
    key = (window, top, tuple(sorted(
        (p, tuple(c)) for p, c in sources.items())))
    if key in _SWEEP_CACHE:
        pool = _SWEEP_CACHE[key]
        print(f"[discover] window {window}: {len(pool)} clip(s) from cache "
              f"(swept once this run)", flush=True)
        return list(pool)

    from concurrent.futures import ThreadPoolExecutor
    jobs = [(p, ch) for p, chans in sources.items() for ch in chans]

    def _one(job):
        platform, ch = job
        try:
            got = clip_edit.discover(platform, ch, top=top, range_=window)
            _source_health(platform, ch, ok=True, clips=len(got))
            return got
        except Exception as e:  # noqa: BLE001
            # keep yt-dlp's own message: the exception TYPE alone made
            # rumble undiagnosable for days (see clip_edit's rumble
            # handler). It was computed, printed to the CI log — which
            # expires — and then NOT passed to _source_health, so the
            # durable record stored the bare class name, which is exactly
            # the thing that was undiagnosable.
            d = (getattr(e, "output", "") or "").strip()
            d = d.splitlines()[-1][:160] if d else ""
            _source_health(platform, ch, ok=False,
                           err=f"{type(e).__name__}: {d}" if d
                           else f"{type(e).__name__}")
            print(f"::warning::discover {platform}:{ch} failed "
                  f"({type(e).__name__}) {d} — skipped", flush=True)
            return []

    pool: list = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        for got in ex.map(_one, jobs):
            pool += got
    _SWEEP_CACHE[key] = list(pool)
    print(f"[discover] window {window}: {len(pool)} clip(s) across "
          f"{len(jobs)} handle(s)", flush=True)
    return pool


def _clamp_publish_at(publish_at, lead_min: int = 15):
    """Never hand YouTube a publishAt that has already passed.

    Returns the original string when it is still comfortably in the
    future, otherwise now+lead_min. None passes through (no schedule)."""
    if not publish_at:
        return publish_at
    try:
        dt = datetime.fromisoformat(str(publish_at).replace("Z", "+00:00"))
    except ValueError:
        return publish_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    floor = datetime.now(timezone.utc) + timedelta(minutes=lead_min)
    if dt >= floor:
        return publish_at
    fixed = floor.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"::warning::[schedule] publish_at {publish_at} is in the past by "
          f"the time this slot reached upload — clamped to {fixed}. The run "
          f"took longer than the 30-minute scheduling lead.", flush=True)
    return fixed


def _checkpoint_log(why: str) -> None:
    """Push the posted log to main MID-RUN, from CI only.

    The workflow commits state in its final step. A run killed at the
    120-minute wall (or by a hard runner death, as on 2026-07-25) never
    reaches it — so videos already live on YouTube have no entry anywhere
    in git, the next run's dedupe sync pulls a log that does not contain
    them, and it re-posts them. ci_commit_state.sh union-merges on a push
    race, so a checkpoint can only ever ADD entries, never lose one."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    import subprocess
    try:
        subprocess.run(
            ["bash", str(REPO / "scripts" / "ci_commit_state.sh"),
             f"third: checkpoint posted log ({why}) [skip ci]",
             "state/third_posted_log.json"],
            cwd=str(REPO), timeout=120, check=False)
    except Exception as e:  # noqa: BLE001
        print(f"[checkpoint] {why}: {e}", flush=True)


def run_capture(pkg: dict, work: Path) -> Path:
    """Execute the package's real task and write the proof ledger."""
    spec = pkg["capture"]
    if spec["kind"] != "cli":
        raise RuntimeError(f"unsupported capture kind {spec['kind']!r}")
    if spec.get("fixture"):
        importlib.import_module(spec["fixture"]).main()
    inp = REPO / spec["input"]
    out = REPO / spec["output"]
    # Run from the fixture dir with basenames so the typed command and the
    # replayed output show the same short filenames (cosmetic only —
    # THIRD_BRAIN.md §7 allows path shortening, never command changes).
    argv = [a.format(input=inp.name, output=out.name)
            for a in spec["argv_template"]]
    cap = capture_cli.capture(argv, cwd=inp.parent,
                              shell_line=spec["shell_line"])
    if cap.exit_code != 0:
        raise RuntimeError(
            f"capture failed (exit {cap.exit_code}) — killing package, "
            "never improvising claims")
    capture_cli.record_file(cap, "input", inp)
    capture_cli.record_file(cap, "output", out)
    return capture_cli.save_ledger(cap, work / f"{pkg['slug']}.ledger.json")


def _fmt_from_ledger(led: dict) -> dict:
    if led.get("kind") in ("twitch_clip", "story"):
        # the authored title beats the raw clip title ("v", "W"...)
        return {"clip_title": led.get("authored_title") or led["clip_title"],
                "streamer": led["streamer"]}
    if led.get("kind") == "sim":
        return {"peak": f"{led['peak_multiplier']:.1f}"}
    n_in = led["files"]["input"]["rows"]
    n_out = led["files"]["output"]["rows"]
    return {"n_in": f"{n_in:,}", "n_out": f"{n_out:,}",
            "removed": f"{n_in - n_out:,}", "wall": f"{led['wall_time_s']:.2f}"}


def _hashtags(pkg: dict, led: dict) -> list[str]:
    """Description hashtags: the brain's relevant tags first, PADDED to a
    hard minimum of 5 (operator requirement) from an evergreen, streamer-
    aware fallback pool, capped at 7. Deduped, lowercase, alnum-only."""
    def _n(t: str) -> str:
        return re.sub(r"[^a-z0-9]", "", str(t).lower())

    tags = list(led.get("authored_tags") or []) or \
        list(pkg.get("hashtags") or [])
    seen, out = set(), []
    for t in tags:
        n = _n(t)
        if n and 2 <= len(n) <= 30 and n not in seen:
            seen.add(n)
            out.append(n)
    # pad to the 5-tag floor from an evergreen pool (streamer name variants
    # first for clip posts, then broad tags) so a thin/failed author never
    # drops us below the minimum.
    s = _n(led.get("streamer") or "")
    pool = ([s, f"{s}clips", f"{s}clip"] if s else []) + [
        _n(led.get("series") or ""), "streamerclips", "twitchclips",
        "clips", "gaming", "livestream", "shorts", "twitch"]
    for t in pool:
        if len(out) >= 5:
            break
        if t and 2 <= len(t) <= 30 and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:7]


def _yt_tags(pkg: dict, led: dict) -> list[str]:
    """The tags FIELD (not hashtags): sparse, mostly name variants —
    YouTube says tags play a minimal role beyond misspellings."""
    if led.get("kind") == "story":
        s = led.get("streamer", "")
        return [*led.get("who", []), f"{s} clips", "streamer clips",
                "full story", "streamer drama"][:10]
    if led.get("kind") != "twitch_clip":
        return list(pkg.get("hashtags") or [])[:10]
    s = led["streamer"]
    return [s, f"{s} clips", f"{s} stream", "streamer clips",
            *(led.get("authored_tags") or [])][:10]


def _crosspost(mp4: Path, title: str, description: str,
               tags: list[str]) -> dict:
    """Cross-post the SAME rendered clip to the feed-first platforms where a
    small channel can actually break out. Our own scrape of this exact niche
    shows sub-10k-follower accounts hitting MILLIONS on the TikTok FYP, while
    YouTube's Shorts feed structurally starves a cold channel (79% of our
    views are search, <10% is the feed). YouTube stays the primary upload;
    this is pure additive reach.

    Guarded + best-effort: a platform is attempted ONLY if its token is
    configured, and ANY failure is logged and swallowed so cross-posting can
    never break the YouTube post. Returns {platform: url} for whatever landed.
    TikTok needs only TIKTOK_ACCESS_TOKEN_THIRD (chunked file upload); IG
    Reels additionally needs META_ACCESS_TOKEN + IG_USER_ID + REELS_PUBLIC_HOST
    (a public URL Meta can fetch the file from)."""
    out: dict = {}
    if os.environ.get("TIKTOK_ACCESS_TOKEN_THIRD") or \
            os.environ.get("TIKTOK_ACCESS_TOKEN"):
        try:
            from shared.uploaders import TikTokUploader
            up = TikTokUploader(channel="third").upload(
                file_path=mp4, title=title, description=description, tags=tags)
            out["tiktok"] = getattr(up, "url", str(up))
            print(f"[crosspost] tiktok -> {out['tiktok']}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[crosspost] tiktok failed ({e})", flush=True)
    if all(os.environ.get(k) for k in
           ("META_ACCESS_TOKEN", "IG_USER_ID", "REELS_PUBLIC_HOST")):
        try:
            from shared.uploaders import InstagramUploader
            up = InstagramUploader().upload(
                file_path=mp4, title=title, description=description, tags=tags)
            out["instagram"] = getattr(up, "url", str(up))
            print(f"[crosspost] instagram -> {out['instagram']}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[crosspost] instagram failed ({e})", flush=True)
    if not out:
        print("[crosspost] no TikTok/Reels token set — YouTube only. Set "
              "TIKTOK_ACCESS_TOKEN_THIRD to reach the FYP where small accounts "
              "break out (the deep dive's #1 lever).", flush=True)
    return out


def _public_source(url: str) -> str:
    """A source URL a VIEWER CAN OPEN.

    VOD mining invents `vodmine://<video_id>/<offset>` so the pipeline can
    key and dedupe a moment no clipper cut. That scheme is internal — it
    was reaching the public YouTube description as
    `Source: vodmine://2412345678/4180` on a channel whose entire
    legitimacy rests on attribution. Render it as the real Twitch VOD
    deep-link with the timestamp, which is exactly where the moment is."""
    from funnel import vod_miner
    if not vod_miner.is_mined(url):
        return str(url or "")
    try:
        vid, off = str(url).split("://", 1)[1].rsplit("/", 1)
        s = int(float(off))
        h, m, sec = s // 3600, (s % 3600) // 60, s % 60
        return (f"https://www.twitch.tv/videos/{vid}"
                f"?t={h:02d}h{m:02d}m{sec:02d}s")
    except (ValueError, IndexError):
        return ""


def _description(pkg: dict, led: dict) -> str:
    tags = " ".join(f"#{t}" for t in _hashtags(pkg, led))
    note = pkg.get("description_note", "")
    if led.get("kind") == "story":
        # multi-clip compilation: CTA up top (the feed promotes on
        # comments), one human line, then credit EVERY member source (each
        # beat is someone's clip — full attribution, always)
        lead = led.get("authored_caption") \
            or led.get("authored_title") or led.get("clip_title", "")
        cta = led.get("authored_cta", "")
        head = f"{cta}\n\n{lead}" if cta else lead
        srcs = "\n".join(
            f"Source: {u}" for u in
            (_public_source(b.get("source_url", ""))
             for b in led.get("beats", [])) if u)
        credit = ("Every moment belongs to the streamers — full credit.\n"
                  + srcs)
        return f"{head}\n\n{credit}\n\n{tags}"
    if led.get("kind") == "twitch_clip":
        # the public caption: one human sentence, credit, tags — never
        # internal pipeline jargon
        lead = led.get("authored_caption") \
            or led.get("authored_title") or led["clip_title"]
        # Comment-bait CTA leads the description (feed-engagement lever): the
        # Shorts feed promotes on comments, and our analytics show ~0 per
        # video. A take-provoking question up top is the cheapest way to
        # earn that signal. Falls away cleanly when the author omits it.
        cta = led.get("authored_cta", "")
        head = f"{cta}\n\n{lead}" if cta else lead
        src = _public_source(led.get("source_url", ""))
        credit = f"Clip from {led['credit']} — full credit to the streamer."
        if src:
            credit += f"\nSource: {src}"
        # "Clipped by vod-mined" is not a person to credit — this moment
        # was pulled straight from the streamer's own VOD, so the streamer
        # credit above is the whole of it.
        from funnel import vod_miner
        if led.get("clipper") and not vod_miner.is_mined(
                led.get("source_url", "")):
            credit += f"\nClipped by {led['clipper']}."
        if note:
            credit += f"\n{note}"
        return f"{head}\n\n{credit}\n\n{tags}"
    if led.get("kind") == "sim":
        detail = (f"Simulation: {led['theme']}, one continuous speed ramp "
                  f"to x{led['peak_multiplier']} — the on-screen speed "
                  "counter is the sim's actual clock multiplier.")
    else:
        detail = (f"Measured: {led['wall_time_s']:.2f}s wall time, "
                  f"{led['files']['input']['rows']} rows in, "
                  f"{led['files']['output']['rows']} rows out.")
    return f"{pkg['proof_plan']}\n\n{note}\n\n{detail}\n\n{tags}"


def _story_guidance() -> str:
    """Channel evidence for the story director (spec §22/Phase Three) —
    which structures/lengths actually retain ON OUR CHANNEL. Empty until
    the story arm has >=25 mature posts: creative decisions are never
    optimized before coherence is proven (§23). Never raises."""
    try:
        if not ANALYTICS_LATEST.exists():
            return ""
        snap = json.loads(ANALYTICS_LATEST.read_text())
        ss = (snap.get("summary") or {}).get("story_structures") or {}
        if not ss.get("enough_data"):
            return ""
        parts = []
        for st, x in sorted((ss.get("structures") or {}).items(),
                            key=lambda kv: -(kv[1].get("median_vph") or 0)):
            parts.append(
                f"{st}: n={x['n_mature']}, median_vph={x['median_vph']}"
                + (f", avg_retention={x['avg_retention']}%"
                   if x.get("avg_retention") is not None else ""))
        return ("structure performance on this channel (mature posts): "
                + "; ".join(parts)) if parts else ""
    except Exception:  # noqa: BLE001
        return ""


def _load_events() -> dict:
    """Event records (STORY_DIRECTOR_PLAYBOOK §5): a developing story
    survives between runs so new developments extend it instead of being
    rediscovered from scratch. Small JSON in state/, committed with the
    posted log."""
    try:
        if EVENTS_FILE.exists():
            return json.loads(EVENTS_FILE.read_text())
    except Exception:  # noqa: BLE001
        pass
    return {"events": {}}


_EVENT_STOP = set(
    "the a an and or but to of in on at is was are get gets got this that "
    "his her him them they he she it for with his was were be been being "
    "after before then now his her "
    # generic streamer/reaction vocabulary (reviewer #11): these are the
    # words that FALSELY merge unrelated same-people clips — every streamer
    # clip is a 'reaction' on 'stream' from a 'video'. Stored as STEMS
    # because tokens are stemmed before this lookup (react == reacts ==
    # reaction == reacting).
    "react stream clip live video watch chat guy today moment thing "
    "play game talk show tell said say make made take back time going "
    "know think want look come went".split())

# suffix stems, longest first, so react/reacts/reaction/reacting collapse to
# one token — this cuts the "same event, different wording" false SEPARATION
# the lexical approach suffers (reviewer #11). Conservative: never stems a
# token below 4 chars, so short words are left intact.
_STEM_SUF = ("ations", "ation", "ings", "ing", "ers", "ion", "ed", "es",
             "er", "s")


def _stem(w: str) -> str:
    for suf in _STEM_SUF:
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[:-len(suf)]
    return w


def _event_fingerprint(who: list[str], reports: list[dict]) -> tuple:
    """Semantic event identity (reviewer #2): people are ONE feature, not
    the whole key. Distinct incidents between the same pair in the same
    month (an argument on the 3rd, a gift on the 15th) must NOT collapse
    into one record. Fingerprint = sorted people + the salient ACTION
    tokens shared across the cluster's scene summaries + an ISO-week bucket,
    so a different incident (different actions and/or a different week) gets
    its own event id."""
    toks: dict[str, int] = {}
    for r in reports:
        text = (str(r.get("summary", "")) + " "
                + str(r.get("title", ""))).lower()
        for t in re.findall(r"[a-z]{4,}", text):
            t = _stem(t)
            if t not in _EVENT_STOP:
                toks[t] = toks.get(t, 0) + 1
    salient = sorted(sorted(toks), key=lambda t: -toks[t])[:4]
    # ISO week groups a developing incident's clips while separating a
    # fresh incident weeks later
    dates = sorted(str(r.get("date", "")) for r in reports if r.get("date"))
    wk = ""
    if dates and dates[-1][:10].count("-") == 2:
        try:
            y, m, d = (int(x) for x in dates[-1][:10].split("-"))
            wk = f"{y}w{datetime(y, m, d).isocalendar().week:02d}"
        except Exception:  # noqa: BLE001
            wk = dates[-1][:7]
    return (tuple(sorted(w.lower() for w in who)), tuple(sorted(salient)), wk)


def _upsert_event(events: dict, who: list[str], reports: list[dict],
                  urls: list[str]) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    people, actions, wk = _event_fingerprint(who, reports)
    eid = ("-".join(people) + "-" + "-".join(actions[:2]) + "-" + wk).strip("-")
    eid = re.sub(r"[^a-z0-9-]", "", eid.lower()) or "event"
    ev = events["events"].setdefault(eid, {
        "event_id": eid, "people": sorted(who), "actions": list(actions),
        "event_type": "storyline", "first_seen": today,
        "known_claims": [], "candidate_sources": [],
        "published_versions": []})
    ev["last_updated"] = today
    seen = set(ev["candidate_sources"])
    ev["candidate_sources"] = (ev["candidate_sources"]
                               + [u for u in urls if u not in seen])[-40:]
    return ev


def _report_tokens(rep: dict) -> set:
    """The salient ACTION vocabulary of ONE source, from its own scene
    summary+title (stop-words removed, top 6). Per-source — unlike a whole-
    pile fingerprint it does NOT drift as other sources are added, which is
    what made the pile fingerprint unstable (reviewer #8)."""
    toks: dict[str, int] = {}
    text = (str(rep.get("summary", "")) + " "
            + str(rep.get("title", ""))).lower()
    for t in re.findall(r"[a-z]{4,}", text):
        t = _stem(t)                     # react == reacts == reaction
        if t not in _EVENT_STOP:
            toks[t] = toks.get(t, 0) + 1
    return set(sorted(sorted(toks), key=lambda t: -toks[t])[:6])


def _report_week(rep: dict):
    """A monotone ISO-week ordinal (year*53 + week) for one source, or None.
    Monotone so an incident straddling a Sun/Mon boundary is one week apart,
    not a wraparound of ~51."""
    d = str(rep.get("date", ""))[:10]
    if d.count("-") != 2:
        return None
    try:
        y, m, dd = (int(x) for x in d.split("-"))
        iso = datetime(y, m, dd).isocalendar()
        return iso[0] * 53 + iso[1]
    except Exception:  # noqa: BLE001
        return None


def _semantic_subclusters(reports: list[dict]) -> list[list[dict]]:
    """Split a PEOPLE cluster into ACTUAL events (reviewer #8).

    storyline.find_clusters() groups clips by shared people, so an argument
    on the 3rd and a reconciliation on the 15th between the same streamers
    land in ONE pile. Naming that pile with a fingerprint does not split it.
    Now that every source has a scene report, we can: single-linkage group
    sources that share >=2 salient action tokens AND fall within the same
    ISO week (+-1 week, so a boundary-crossing incident stays whole). Each
    component is one semantic event → one event record → one director call.

    Deliberately split-happy: sources with no shared action vocabulary form
    separate components (dropped if <2), because compiling two unrelated
    same-people clips into a fake 'story' is the worse error (spec §21)."""
    n = len(reports)
    if n <= 1:
        return [list(reports)] if reports else []
    toks = [_report_tokens(r) for r in reports]
    weeks = [_report_week(r) for r in reports]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            wi, wj = weeks[i], weeks[j]
            week_ok = wi is None or wj is None or abs(wi - wj) <= 1
            shared = len(toks[i] & toks[j])
            if week_ok and shared >= 2:
                parent[find(j)] = find(i)

    groups: dict[int, list[dict]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(reports[i])
    # largest event first, ties broken by earliest date (deterministic)
    return sorted(groups.values(),
                  key=lambda g: (-len(g),
                                 min(str(r.get("date", "")) for r in g)))


def _story_attempt(pkg: dict, log: dict, work: Path, out_mp4: Path,
                   slug: str) -> dict | None:
    """STORY DIRECTOR pipeline (STORY_DIRECTOR_PLAYBOOK §4):

    discovery/cluster -> event record -> multimodal scene analysis (full
    transcripts + frames, with VOD context expansion for incomplete
    sources) -> eligibility + structure + story EDL (the director owns the
    timeline) -> dedicated rough-cut render (no cards, overlays on
    footage) -> narrative review -> ONE revision -> mechanical QA.

    Returns a ledger dict, or None on ANY miss so the slot falls back to a
    normal clip. A good standalone clip beats a fake narrative (§21).
    Never raises."""
    try:
        from third_capture import clip_edit, clip_qa, storyline
        from third_capture import scene_analysis, story_director
        from third_capture import story as story_mod
        from shared.fsutil import atomic_write_json
        spec = pkg["capture"]
        sources_cfg = spec.get("sources") or \
            {"twitch": spec.get("channels", [])}
        known = [ch for chans in sources_cfg.values() for ch in chans]
        corpus = storyline.corpus_from_log(
            log, days=int(spec.get("story_lookback_days", 30)))
        global _STORY_POOL
        if _STORY_POOL is None:
            pool: list[dict] = []
            for window in ("7d", "30d"):
                for platform, chans in sources_cfg.items():
                    for ch in chans:
                        try:
                            pool += clip_edit.discover(
                                platform, ch,
                                top=int(spec.get("story_top", 6)),
                                range_=window)
                        except Exception as e:  # noqa: BLE001
                            print(f"::warning::[story] discover "
                                  f"{platform}:{ch} {window} failed "
                                  f"({type(e).__name__})", flush=True)
            _STORY_POOL = pool
        pool_by_url = {c.get("url"): c for c in _STORY_POOL}
        corpus += storyline.from_discovery(_STORY_POOL)
        clusters = storyline.find_clusters(corpus, known)
        if not clusters:
            print("[story] no candidate storylines in the corpus",
                  flush=True)
            return None
        shipped = {v.get("story_key") for v in log["posted"].values()
                   if v.get("story_key")}
        shipped_members = [v.get("member_keys") or []
                           for v in log["posted"].values()
                           if v.get("story_key")]
        wmodel = spec.get("whisper_model", "small")
        events = _load_events()
        s_min = float(spec.get("story_dur_min", 25.0))
        s_max = float(spec.get("story_dur_max", 90.0))

        vod_expansions = 0
        max_vod = int(spec.get("story_max_vod_expansions", 2))
        for cluster in clusters[:int(spec.get("story_max_clusters", 3))]:
            # THE STORY ARM IS THE RUN'S UNBOUNDED TAIL. Worst case it is
            # 3 clusters x 6 sources x 2 scene analyses = 36 whisper passes
            # and 36 Claude vision calls in ONE slot, each VOD expansion
            # adding a ~3-minute whisper on top — and _story_attempt is
            # called from inside process(), so all of it repeats on every
            # slot retry. That is the shape of the 113-minute run and of
            # the 2026-07-25 job that died on the wall. Stop between
            # clusters when the budget is gone; a clean fallback to the
            # clip arm is a video, a cancelled job is nothing.
            if _deadline_passed():
                print(f"::warning::[story] out of run budget after "
                      f"{elapsed_min():.0f} min — falling back to the clip "
                      f"arm", flush=True)
                return None
            who = "+".join(cluster["who"])
            urls = [c["source_url"] for c in cluster["clips"]]
            if storyline.story_key(urls) in shipped:
                continue
            if storyline.near_dup(urls, shipped_members):
                print(f"[story] {who}: near-duplicate of a shipped story"
                      " — skipped", flush=True)
                continue

            # ---- multimodal scene analysis (§7), with VOD context
            # expansion (§6) for sources the analysis marks incomplete
            snip_dir = work / "story_scenes"
            reports = []
            for c in cluster["clips"][:6]:
                try:
                    info = clip_edit.download(c["source_url"], snip_dir)
                except Exception as e:  # noqa: BLE001
                    print(f"::warning::[story] download failed "
                          f"{c.get('title', '?')[:40]!r} "
                          f"({type(e).__name__})", flush=True)
                    continue
                src = Path(info["path"])
                if not src.is_absolute():
                    src = REPO / src
                if clip_qa.preflight(src):
                    continue
                rep = scene_analysis.analyze_source(
                    src, {**c, "source_url": c["source_url"]},
                    snip_dir, whisper_model=wmodel)
                if not rep:
                    continue
                # §6 expansion triggers: mid-sentence start, missing
                # payoff, or flagged missing context — and helix gave us
                # the VOD coordinates
                helix = pool_by_url.get(c["source_url"], {})
                # Each expansion is a ~390s re-encoded download plus a
                # whisper pass over three minutes plus another vision call
                # — 4-7 minutes apiece, with nothing capping how many fire.
                if (rep.get("opens_mid_sentence")
                        or not rep.get("payoff_shown")
                        or rep.get("missing_context")) and \
                        helix.get("video_id") \
                        and vod_expansions < max_vod \
                        and not _deadline_passed():
                    vod_expansions += 1
                    vod = clip_edit.maybe_vod_window(
                        {**helix, "duration": rep["duration_s"]},
                        snip_dir)
                    if vod:
                        rep2 = scene_analysis.analyze_source(
                            Path(vod["path"]),
                            {**c, "source_url": c["source_url"]},
                            snip_dir, whisper_model=wmodel)
                        if rep2:
                            rep = rep2
                            rep["path"] = vod["path"]
                            rep["used_vod"] = True     # per-SOURCE, not per-pile
                rep["date"] = c.get("date", "")
                reports.append(rep)
            if len(reports) < 2:
                print(f"[story] {who}: <2 analyzable sources", flush=True)
                _story_verdict(who, "starved",
                               f"<2 analyzable sources ({len(reports)}) — "
                               "scene analysis could not read the clips")
                continue

            # ---- semantic subclustering (reviewer #8): the people cluster
            # may hold several DISTINCT events. Split it into real events and
            # try each independently — one event record + one director call
            # per event, not one call over a mixed pile.
            for sub in _semantic_subclusters(reports):
                if len(sub) < 2:
                    continue      # a lone source is not a story
                sub_urls = [r["source_id"] for r in sub]
                # event record keyed on a SEMANTIC fingerprint (people +
                # actions + week) of THIS event's sources only
                event = _upsert_event(events, cluster["who"], sub, sub_urls)
                elbl = f"{who}/{event['event_id']}"

                # ---- eligibility + structure + story EDL (§8-10)
                edl = story_director.plan_story(
                    sub, event, guidance=_story_guidance())
                if not edl:
                    print(f"[story] {elbl}: director says not a story",
                          flush=True)
                    _story_verdict(elbl, "not_a_story",
                                   "director found no genuine arc")
                    continue
                plan_urls = [b["source_id"] for b in edl["beats"]]
                if storyline.story_key(plan_urls) in shipped or \
                        storyline.near_dup(plan_urls, shipped_members):
                    print(f"[story] {elbl}: planned arc already shipped/"
                          "near-dup — skipped", flush=True)
                    continue

                # ---- rough cut via the dedicated renderer (§11)
                src_map = {r["source_id"]: r for r in sub}
                story_work = work / f"story_{slug}"
                revision_count = 0
                try:
                    led = story_mod.render_story(edl, src_map, out_mp4,
                                                 story_work)
                except Exception as e:  # noqa: BLE001
                    print(f"::warning::[story] {elbl}: render failed ({e})"
                          " — next event", flush=True)
                    continue

                # ---- narrative review + ONE revision (§18-19)
                sheet = story_work / "rough.qa.jpg"
                sheet_ok = clip_qa.contact_sheet(out_mp4, sheet) is not None
                tlines = scene_analysis._dialogue_lines(led["final_words"])
                review = story_director.review_rough_cut(
                    edl, tlines, str(sheet) if sheet_ok else None,
                    led["duration_s"])
                if not review["publish"] and review["problems"]:
                    edl2 = story_director.revise_edl(
                        edl, review["problems"], sub)
                    if edl2:
                        revision_count = 1
                        try:
                            led = story_mod.render_story(
                                edl2, src_map, out_mp4, story_work)
                            edl = edl2
                            tlines = scene_analysis._dialogue_lines(
                                led["final_words"])
                            sheet_ok = clip_qa.contact_sheet(
                                out_mp4, sheet) is not None
                            review = story_director.review_rough_cut(
                                edl, tlines,
                                str(sheet) if sheet_ok else None,
                                led["duration_s"])
                        except Exception as e:  # noqa: BLE001
                            print(f"::warning::[story] {elbl}: revision "
                                  f"render failed ({e})", flush=True)
                            continue
                if not review["publish"]:
                    print(f"[story] {elbl}: narrative review failed after "
                          f"{revision_count} revision(s) "
                          f"(score={review['story_score']}) — abandoned",
                          flush=True)
                    continue

                # ---- dedupe on the ACTUAL rendered members + duration band
                skey = storyline.story_key(led["member_keys"])
                if skey in shipped or \
                        storyline.near_dup(led["member_keys"],
                                           shipped_members):
                    continue
                if not (s_min <= led["duration_s"] <= s_max):
                    print(f"::warning::[story] {elbl}: "
                          f"{led['duration_s']:.0f}s outside "
                          f"{s_min:.0f}-{s_max:.0f}s — next event",
                          flush=True)
                    continue

                # ---- mechanical QA (§20 floor; coherence judged above)
                qa = clip_qa.review(out_mp4, {
                    "authored_title": edl["title"],
                    "hook": edl["hook_overlay"], "series": "story"}, work)
                hard = [p for p in qa["problems"] if "duration" not in p]
                if qa["verdict"] == "fail" and hard:
                    print(f"::warning::[story] {elbl}: QA failed "
                          f"({'; '.join(hard)[:140]}) — next event",
                          flush=True)
                    continue

                lead = led["beats"][0].get("streamer") or cluster["who"][0]
                led.update({
                    "authored_title": edl["title"] or
                    f"The Full {who.title()} Story",
                    "clip_title": edl["title"] or who,
                    "authored_caption": author.scrub_text(
                        f"The full story, beginning to end: "
                        f"{edl['premise']}"),
                    "authored_cta": "Rate this arc 1-10",
                    "streamer": lead, "series": "story",
                    "who": cluster["who"], "event_id": event["event_id"],
                    "story_key": skey, "experiment_arm": "story",
                    "structure": "story", "self_healed": False,
                    # per-SUBCLUSTER (reviewer #11): only True when a source in
                    # THIS event was VOD-expanded, not when some unrelated
                    # source elsewhere in the original people-pile was
                    "used_vod_expansion": any(r.get("used_vod") for r in sub),
                    "revision_count": revision_count,
                    "narrative_score": review["story_score"],
                    "qa": {k: qa[k] for k in ("verdict", "problems",
                                              "vision")},
                })
                event["published_versions"].append(skey)
                try:
                    atomic_write_json(EVENTS_FILE, events)
                except Exception:  # noqa: BLE001
                    pass
                print(f"[story] built {elbl} {edl['structure']} story: "
                      f"{led['n_beats']} beats, {led['duration_s']}s, "
                      f"narrative={review['story_score']} — "
                      f"{edl['title']!r}", flush=True)
                return led
        print("[story] no cluster passed the director", flush=True)
        try:
            atomic_write_json(EVENTS_FILE, events)
        except Exception:  # noqa: BLE001
            pass
        return None
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[story] attempt failed ({type(e).__name__}: {e})"
              " — clip fallback", flush=True)
        return None


def process(pkg: dict, pkg_path: Path | None, *,
            dry_run: bool, publish_at, log: dict) -> dict:
    slug = pkg["slug"]
    result = {"slug": slug, "ok": False}
    _JUDGES.clear()          # verdicts are per-slot
    if slug in log["posted"]:
        result.update(ok=True, skipped="already posted")
        return result
    work = OUTPUT_DIR / "third"
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    # SCOPING LAW (live incident 2026-07-23): `author` is the MODULE-LEVEL
    # import — never re-import it inside this function. A function-local
    # `from ... import author` anywhere in the body makes the name local to
    # the WHOLE function, so any path that skips that statement (the story
    # branch did) dies with UnboundLocalError at the final safe_title choke.
    try:
        out_mp4 = work / f"third_{slug}.mp4"
        # STORY ARM: a story slot tries to compile a detected narrative arc.
        # The walrus makes fallback automatic — when no genuine story exists
        # (or the build/QA misses), _story_attempt returns None and this
        # branch doesn't take, so the slot flows into the normal single-clip
        # path below. Event-driven and quality-gated by design: a forced
        # story on thin material is worse than a good clip.
        if pkg["capture"]["kind"] == "twitch_clip" and pkg.get("story_mode") \
                and (led := _story_attempt(pkg, log, work, out_mp4,
                                           slug)) is not None:
            ledger_path = work / f"{slug}.ledger.json"
            ledger_path.write_text(json.dumps(led, indent=2) + "\n")
            result["experiment_arm"] = result["structure"] = "story"
            result["n_beats"] = led.get("n_beats")
        elif pkg["capture"]["kind"] == "twitch_clip":
            from third_capture import clip_edit
            spec = pkg["capture"]
            if spec.get("clip_url"):
                # An explicitly-authored package: a human (or the Routine)
                # picked this exact clip, so it never meets the ranker. That
                # IS a judgment — record it, or the unjudged gate below
                # would skip a deliberately-chosen clip.
                _judge("banger", source="operator-specified", blind=False)
                info = clip_edit.download(spec["clip_url"], work)
                platform = spec.get("platform", "twitch")
                streamer = spec["credit"]
            else:
                # Dedupe on a CANONICAL clip key (the slug), not the raw
                # URL: Twitch serves the same clip as both
                # clips.twitch.tv/SLUG and twitch.tv/<ch>/clip/SLUG, so
                # string-comparing URLs can miss a repeat. _clip_key
                # normalizes any form to the slug so the same clip is
                # never posted twice, even across a ledger hiccup.
                posted_keys = {_clip_key(v.get("source_url", ""))
                               for v in log["posted"].values()}
                # sources: {"twitch": [...], "kick": [...], "rumble": [...]}
                # (legacy "channels" list = twitch). A platform that's
                # blocked/unreachable logs a warning and never kills the
                # run — the other platforms carry the day.
                sources = spec.get("sources") \
                    or {"twitch": spec.get("channels", [])}
                # SUPPLY LADDER: try the hot window first, then widen to 7
                # days. The spec's range is the FIRST RUNG, never a pin —
                # and the ladder widens when the FULLY-FILTERED pool comes
                # up empty (dedupe + variety + views), not merely when the
                # window has unposted dregs: a batch of never-posted 300-view
                # clips must not block reaching a 50k clip from 3 days ago.
                # The never-repeat law lives in posted_keys, window-agnostic.

                # VARIETY (operator law): cap clips PER STREAMER per day
                # (default 2) and hard-limit 1 clip of the same EVENT per
                # day, so one hot moment can't flood the channel.
                per_streamer = spec.get("max_per_streamer", 2)
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                # ONLY THINGS THAT ACTUALLY SHIPPED count against the
                # variety caps. This used to include blocklist entries,
                # which carry both `ts` and `streamer` — so with
                # max_per_streamer=2, two REJECTIONS of one streamer today
                # banned that streamer from the whole candidate pool even
                # though nothing shipped. The streamer producing the day's
                # best material is exactly the one the gate rejects from
                # most, so this starved supply hardest on the days it
                # mattered most. _same_event had the same bug: a rejected
                # clip's title blocked every clip that shared two tokens
                # with it.
                posted_today = [v for k, v in log["posted"].items()
                                if str(v.get("ts", "")).startswith(today)
                                and not k.startswith("rejected-")
                                and not v.get("qa_rejected")]
                from collections import Counter
                streamer_counts = Counter(v.get("streamer")
                                          for v in posted_today)
                used_titles = [str(v.get("title", "")).lower()
                               for v in posted_today]

                def _same_event(title: str) -> bool:
                    toks = {t for t in re.findall(r"[a-z]{5,}",
                                                  title.lower())}
                    return any(len(toks & set(re.findall(r"[a-z]{5,}", u)))
                               >= 2 for u in used_titles)

                min_v = spec.get("min_views", 2500)
                floor = spec.get("min_views_floor", 800)
                windows = []
                for w in (spec.get("range") or "24hr", "7d"):
                    if w not in windows:
                        windows.append(w)
                # widen not just when the window is EMPTY but when it's THIN:
                # a handful of low-view 24h clips must not block reaching the
                # fuller 7d board (the thin-Twitch day that starved the slate
                # on 2026-07-13 and forced b=0.20 duds through). Keep the
                # LARGEST pool seen so a failing wider window never regresses
                # a good narrower one.
                min_pool = spec.get("min_pool", 8)
                cands = []
                best = []
                for window in windows:
                    pool = _sweep(clip_edit, sources, window,
                                  int(spec.get("top", 8)))
                    fresh = [c for c in pool
                             if _clip_key(c["url"]) not in posted_keys]
                    varied = [c for c in fresh
                              if streamer_counts[c["channel"]] < per_streamer
                              and not _same_event(c["title"])]
                    if varied:
                        fresh = varied
                    elif fresh:
                        print("::warning::variety rules exhausted the pool "
                              "— allowing repeats", flush=True)
                    cands = [c for c in fresh
                             if c["views"] == 0 or c["views"] >= min_v]
                    if not cands:
                        cands = [c for c in fresh if c["views"] >= floor]
                        if cands:
                            print(f"::warning::thin day — relaxed min_views "
                                  f"{min_v} -> floor {floor}", flush=True)
                    if len(cands) > len(best):
                        best = cands
                    if len(best) >= min_pool or window == windows[-1]:
                        break
                    print(f"::warning::window {window}: only {len(best)} "
                          f"postable clip(s) (<{min_pool}) — widening",
                          flush=True)
                cands = best
                cands.sort(key=lambda c: -c["views"])
                if not cands:
                    raise RuntimeError("no fresh clip across the allowlist")
                # THIN-DAY VOD MINING (2026-07-31): clip discovery only
                # ever sees what a human chose to clip. When even the
                # widened window comes up short, mine the VOD NEIGHBOURHOOD
                # of the anchors we do have — the moment a clipper missed
                # is very often 90s after the one they caught. One bounded
                # extra download per anchor; each mined moment is extracted
                # as a short mp4 so whisper, the content gate, render and
                # QA all treat it exactly like a normal clip. It earns its
                # slot on the same transcript bar as anything else.
                if len(cands) < min_pool:
                    try:
                        from funnel import vod_miner
                        anchors = [c for c in cands[:3]
                                   if c.get("video_id")
                                   and c.get("vod_offset") is not None]
                        mined = []
                        for a in anchors:
                            mined += vod_miner.maybe_mine(a, work)
                            if len(cands) + len(mined) >= min_pool:
                                break
                        if mined:
                            print(f"::warning::[vodmine] thin pool "
                                  f"({len(cands)}<{min_pool}) — mined "
                                  f"{len(mined)} unclipped moment(s) from "
                                  f"{len(anchors)} anchor(s)", flush=True)
                            cands += mined
                        else:
                            print(f"[vodmine] thin pool ({len(cands)}<"
                                  f"{min_pool}) but mining returned nothing "
                                  f"from {len(anchors)} anchor(s)",
                                  flush=True)
                    except ImportError:
                        pass
                else:
                    # say so explicitly: "did mining run?" was otherwise
                    # unanswerable from the log, and a supply feature that
                    # silently never fires looks identical to one that
                    # fires and finds nothing.
                    print(f"[vodmine] pool is healthy ({len(cands)}>="
                          f"{min_pool}) — not mining", flush=True)
                # VELOCITY-FIRST SHORTLIST (diagnosis #4): the viral/feed
                # signal is views/HOUR, not raw views. The old code shortlisted
                # the top 8 by raw views and only THEN measured velocity within
                # them — so a clip climbing fast from a lower view count (the
                # exact thing the Shorts feed rewards) was buried before it
                # could compete. Now probe age across a WIDE pool (top
                # `age_probe` by views: helix carries age for free, yt-dlp costs
                # one metadata call each so it's capped), score everything by
                # velocity, and only then take the top 8 into banger scoring.
                core = set(spec.get("core", []))
                # softened from the old hard 0.45: a non-core streamer's clip
                # is a mild deprioritization, not a near-veto — feed reach comes
                # from broad-appeal MOMENTS, not just our proven search names.
                non_core = float(spec.get("non_core_penalty", 0.75))
                age_probe = int(spec.get("age_probe", 20))

                def _fit(ch):
                    return 1.0 if not core or ch in core else non_core
                for c in cands[:age_probe]:
                    # helix candidates carry exact age; yt-dlp ones probe
                    age = c.get("age_h") or clip_edit.fetch_age_hours(c["url"])
                    c["vph"] = c["views"] / max(age, 0.5) if age else \
                        c["views"] / 24.0
                    c["score"] = c["vph"] * _fit(c["channel"])
                # candidates past the probe window keep a raw-view proxy (age
                # unknown -> assume ~24h) so a thin day can still surface them,
                # but a measured fast-climber always outranks the proxy.
                for c in cands[age_probe:]:
                    c["vph"] = c["views"] / 24.0
                    c["score"] = c["vph"] * _fit(c["channel"])
                cands.sort(key=lambda c: -c["score"])
                shortlist = cands[:8]
                # BANGER PRE-SCORER (playbook §banger): velocity says a clip
                # is spreading, not that a stranger will watch it to the end.
                # The brain reads the titles and rates shareability 0-1; we
                # blend it multiplicatively so a genuinely funny/shocking clip
                # can beat a boring viral one, obvious duds (giveaway/subathon
                # spam, sponsor reads, "just chatting") get buried, and an
                # unknown/garbage title stays neutral (0.5) instead of killed.
                # Cached run-wide; pure-velocity fallback when the brain is
                # unreachable (returns {}), so a token outage never blocks a
                # post.
                to_score = [c for c in shortlist
                            if c["url"] not in _BANGER_CACHE]
                if to_score:
                    try:
                        _BANGER_CACHE.update(author.rank_clips(to_score))
                    except Exception as e:  # noqa: BLE001
                        print(f"::warning::[banger] rank failed ({e}) — "
                              "velocity only", flush=True)
                # LEARNED PRIOR (feedback loop): nudge by how this streamer's
                # clips have actually retained on OUR channel, not just how
                # they spread on Twitch. Neutral (1.0) until analytics_third
                # accrues data, so a cold start runs pure velocity+banger.
                prior = _learned_prior()
                for c in shortlist:
                    c["banger"], c["banger_why"] = \
                        _BANGER_CACHE.get(c["url"], (0.5, ""))
                    if c.get("mined"):
                        # A MINED MOMENT HAS NO TITLE — nobody wrote one,
                        # that is the whole point. Handing `title=''` to a
                        # title judge puts it in the low band by
                        # construction, so the candidates we mine precisely
                        # BECAUSE the day is thin were structurally
                        # disadvantaged by a judge with nothing to read.
                        # Park them at neutral and let the transcript +
                        # vision gate downstream — which CAN see them — be
                        # the one that decides.
                        c["banger"] = max(c["banger"], 0.5)
                        c["banger_why"] = "mined moment — no title to judge"
                    # 0.25 floor: even a low-banger clip keeps a quarter of its
                    # velocity weight, so the brain deprioritizes but never
                    # single-handedly vetoes a hugely viral clip.
                    c["score"] = c["score"] * (0.25 + 0.75 * c["banger"])
                    c["prior"] = prior.get(str(c["channel"]).lower(), 1.0)
                    c["score"] = c["score"] * c["prior"]
                shortlist.sort(key=lambda c: -c["score"])
                for c in shortlist[:5]:
                    print(f"[pick] {c['channel']:>14} {c['views']:>7}v "
                          f"{c['vph']:>8.0f}v/h b={c['banger']:.2f} "
                          f"p={c['prior']:.2f} score={c['score']:>7.0f} "
                          f"{c['title'][:38]!r} {c.get('banger_why','')!r}",
                          flush=True)
                # QUALITY FLOOR (post fewer > post duds): the banger scorer
                # explicitly buckets giveaway / subathon / sponsor / insider /
                # "just chatting" clips into the LOW band (<0.35). On a starved
                # day those can be all that's left — but a b=0.20 "insider WoW"
                # clip should never ship (live incident 2026-07-13). Skip the
                # slot: three good clips beat five with two duds, and an empty
                # slot beats a bad upload. Unknown/garbage titles sit at 0.5
                # and still pass — a bad title often hides a great clip.
                min_banger = spec.get("min_banger", 0.50)
                postable = [c for c in shortlist if c["banger"] >= min_banger]
                if not postable:
                    best_b = max((c["banger"] for c in shortlist), default=0.0)
                    # ESCALATE, DON'T GIVE UP (2026-07-31). An empty slot is
                    # a failure this used to report as success. Worse, the
                    # banger score judges the clipper's TWITCH TITLE, not the
                    # clip — the day's rejects read 'sadge' -> "vague emote
                    # reaction" and 'foams' -> "vague title, no discernible
                    # payoff". Those are verdicts on a one-word title, and we
                    # were binning the clip without ever downloading or
                    # transcribing it.
                    #
                    # A STRICTER judge already sits downstream: the content
                    # gate re-scores on the real transcript at 0.70. So when
                    # nothing clears the title floor, hand the best material
                    # to that judge instead of skipping. If it rejects, the
                    # slot's existing retry blocklists the clip and tries the
                    # next candidate. The bar goes UP (0.70 transcript vs
                    # 0.50 title) and the evidence gets better — this is more
                    # work, not a weaker gate.
                    rescue_floor = float(spec.get("rescue_floor", 0.25))
                    rescue = [c for c in shortlist
                              if c["banger"] >= rescue_floor]
                    if not rescue:
                        # everything is transparent spam (giveaway/subathon/
                        # sponsor bait sits <0.25) — a transcript pass on
                        # that is wasted runner time, not a missed video.
                        _judge("selection", verdict="skip",
                               why=f"best title score {best_b:.2f} < hard "
                                   f"floor {rescue_floor} across "
                                   f"{len(shortlist)} candidates")
                        raise _SkipSlot(
                            f"quality floor: best banger {best_b:.2f} < "
                            f"{rescue_floor} (hard floor) across "
                            f"{len(shortlist)} candidates — nothing worth "
                            "transcribing")
                    print(f"::warning::[rescue] nothing clears the title "
                          f"floor ({best_b:.2f} < {min_banger}) — escalating "
                          f"{len(rescue)} candidate(s) to the TRANSCRIPT "
                          f"judge rather than skipping the slot", flush=True)
                    _judge("selection", verdict="rescue",
                           why=f"best title score {best_b:.2f} < "
                               f"{min_banger}; escalated to the transcript "
                               f"judge (bar 0.70) instead of skipping")
                    postable = rescue
                pick = postable[0]
                # FINAL DEDUPE GUARD (never post the same clip twice): the
                # shortlist was already filtered by posted_keys, so this only
                # fires if a future refactor lets a posted clip slip through —
                # a loud, cheap backstop on the channel's core law.
                if _clip_key(pick["url"]) in posted_keys:
                    raise _SkipSlot(
                        f"dedupe guard: {_clip_key(pick['url'])} already "
                        "posted — refusing a duplicate")
                # what the ranking brain thought of the clip we CHOSE. A
                # 0.5 with no reason is the can't-score default — i.e. the
                # pick was made on raw velocity, blind. Recording it makes
                # a blindly-ranked slate visible after the fact.
                _judge("banger", score=pick.get("banger"),
                       why=pick.get("banger_why"),
                       blind=(not pick.get("banger_why")
                              and pick.get("banger") == 0.5))
                if pick.get("mined"):
                    # already extracted by the miner — no download, and no
                    # clipper title (the brain authors one from what's said)
                    info = {"path": pick["path"], "url": pick["url"],
                            "views": pick.get("views", 0),
                            "title": pick.get("title", ""),
                            "clipper": pick.get("clipper", "vod-mined")}
                else:
                    info = clip_edit.download(pick["url"], work)
                platform, streamer = pick["platform"], pick["channel"]

            # PRE-FLIGHT (§16, cheap end): validate the source in ~2s before
            # whisper/author/render spend 100s+ on it. A bad source is
            # blocklisted exactly like a QA rejection so it can't re-eat
            # slots this run or any future run.
            from third_capture import clip_qa
            pf = clip_qa.preflight(Path(REPO / info["path"])
                                   if not Path(info["path"]).is_absolute()
                                   else Path(info["path"]))
            if pf:
                # blocklist by CLIP KEY (not slug) so a slot's retries each
                # exclude a distinct failed clip instead of overwriting.
                _blocklist(log, f"rejected-{_clip_key(info['url']) or slug}", {
                    "source_url": info["url"], "streamer": streamer,
                    "title": info["title"], "qa_rejected": True,
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
                raise RuntimeError("preflight: " + "; ".join(pf)[:180])

            # transcribe once, then let the Groq author write the
            # packaging from what's actually said in the clip
            wmodel = spec.get("whisper_model", "small")
            has_cut = spec.get("start") or spec.get("end")
            words = None if has_cut else \
                clip_edit.transcribe_words(info["path"], wmodel)
            meta = None
            if words is not None:
                try:
                    clip_dur = float(subprocess.check_output(
                        ["ffprobe", "-v", "quiet", "-show_entries",
                         "format=duration", "-of", "csv=p=0",
                         str(info["path"])], text=True, timeout=30).strip())
                except Exception:  # noqa: BLE001
                    clip_dur = words[-1]["e"] if words else 0.0
                meta = author.author_package(
                    streamer, info["title"],
                    " ".join(w["w"] for w in words), info["views"],
                    words=words, clip_dur=clip_dur,
                    guidance=_opening_guidance())
            hook = (meta or {}).get("hook") or pkg.get("hook", "")
            series = (meta or {}).get("series", "chaos")

            # CONTENT-AWARE QUALITY GATE (reviewer rail #5, second stage):
            # the shortlist floor judged a TITLE; now the transcript exists,
            # re-score with what's actually said — a lying title gets
            # caught here, a great clip behind a garbage title gets
            # confirmed. Playbook-aligned floor (post at ~0.70+). Fails
            # OPEN: no transcript, no brain, or no score for this clip
            # never blocks a post — this gate only acts on real evidence.
            # `words is not None` — NOT `if words`. transcribe_words drops
            # segments over no_speech_prob 0.66 and words under 0.35
            # confidence, so a clip that is music, crowd noise, screaming
            # or pure physical comedy returns [] — falsy — and the ENTIRE
            # gate, contact sheet included, was skipped. The vision judge
            # built specifically to stop the transcript-only bias against
            # visual clips was itself gated behind having a transcript.
            # Worse, the clip then shipped with no content judgment at all
            # and _any_judgment() was satisfied by the title-based banger
            # score, so the unjudged backstop did not fire either. A
            # speechless clip is precisely the one that needs eyes.
            if words is not None:
                snip = " ".join(w["w"] for w in words[:40])
                # GIVE THE GATE EYES (2026-07-31). It judged `words[:40]`
                # and nothing else, and every rejection all day was about
                # TALK — "rambling chat talk", "vague ramble", "routine
                # gameplay narration". None mentioned anything visual,
                # because it could not see. On a clips channel that is a
                # systematic bias against the content that travels: a fail,
                # a reaction face, physical comedy all read as "rambling
                # chat" from the transcript alone. A contact sheet of the
                # SOURCE costs a couple of ffmpeg seconds and lets the same
                # rubric judge what actually happens.
                sheet = work / f"{slug}.content.jpg"
                try:
                    have_sheet = clip_qa.contact_sheet(
                        Path(info["path"]), sheet) is not None
                except Exception:  # noqa: BLE001
                    have_sheet = False
                cb, cwhy, saw = author.judge_content(
                    streamer, info["title"], snip,
                    sheet=str(sheet) if have_sheet else "",
                    views=info.get("views", 0))
                content_floor = float(spec.get("min_banger_content", 0.70))
                _judge("content", score=cb, why=cwhy, floor=content_floor,
                       saw_frames=saw,
                       verdict=("unavailable" if cb is None else
                                "reject" if cb < content_floor else "pass"))
                if cb is not None and cb < content_floor:
                    _blocklist(log, f"rejected-{_clip_key(info['url']) or slug}", {
                        "source_url": info["url"], "streamer": streamer,
                        "title": info["title"], "qa_rejected": True,
                        # WHY it was rejected, not just THAT it was — the
                        # blocklist entry is the durable record a human or a
                        # later brain reads back.
                        "rejected_by": "content gate",
                        "rejected_why": f"{cb:.2f} < {content_floor} "
                                        f"({cwhy or 'no reason given'})"[:180],
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })
                    raise RuntimeError(
                        f"content gate: transcript-aware score {cb:.2f} < "
                        f"{content_floor} ({cwhy or 'no reason'})")
                # A RESCUED clip (one that failed the title floor and was
                # escalated here) fails CLOSED. Normally this gate fails
                # open so a flaky brain never costs a good clip — but a
                # rescue has ALREADY been judged weak once, so an
                # unavailable transcript judge means nothing credible has
                # vouched for it. Shipping then is exactly the "post shit"
                # outcome the escalation exists to avoid. Retry the slot:
                # the next candidate may score, or the brain may recover.
                if cb is None and _JUDGES.get(
                        "selection", {}).get("verdict") == "rescue":
                    # BLOCKLIST BEFORE RAISING. The escalation's own
                    # promise is "the slot's existing retry blocklists the
                    # clip and tries the next candidate" — the score-too-low
                    # branch above does that; this one did not. So the
                    # retry re-entered process(), found posted_keys and the
                    # run-wide _BANGER_CACHE unchanged and the shortlist
                    # sort deterministic, and picked THE SAME CLIP: same
                    # download, same whisper pass, same two 240s CLI
                    # timeouts, three times over, and the slot ended empty
                    # anyway. Exactly when the brain is already unreachable
                    # and time is scarcest.
                    _blocklist(log,
                               f"rejected-{_clip_key(info['url']) or slug}", {
                                   "source_url": info["url"],
                                   "streamer": streamer,
                                   "title": info["title"],
                                   "qa_rejected": True,
                                   "rejected_by": "rescue fail-closed",
                                   "rejected_why":
                                       "weak title + no transcript judge "
                                       "reachable — nothing vouched for it",
                                   "ts": datetime.now(
                                       timezone.utc).isoformat(),
                               })
                    raise RuntimeError(
                        "rescue needs the transcript judge and it is "
                        "unavailable — a weak-title clip must EARN its slot, "
                        "retrying with another candidate")

            # DIRECTOR COMPLETENESS GATE (§9): if the brain judges the clip
            # starts mid-action with no context OR its payoff is cut off,
            # skip it — a confusing clip is worse than a lost slot. Blocklist
            # so it can't be re-picked (same as a QA rejection).
            if meta and meta.get("edit", {}).get("complete") is False:
                _blocklist(log, f"rejected-{_clip_key(info['url']) or slug}", {
                    "source_url": info["url"], "streamer": streamer,
                    "title": info["title"], "qa_rejected": True,
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
                raise RuntimeError(
                    "director: clip incomplete (no setup / payoff cut off)")

            # Render + QA gate (playbook §16-18), with SELF-HEAL: if the
            # full auto-edit fails QA, re-render once as the plain simple
            # look and re-inspect — "a clean basic clip is better than an
            # ambitious broken clip" (§18). Only after the clean retry also
            # fails is the clip rejected (slug stays unposted; a different
            # clip competes next run).
            from third_capture import clip_qa
            auto_first = spec.get("auto_edit", True)
            # A/B arm for this slot: the montage "edit" render vs the current
            # "clip" render. Selection + packaging are identical either way.
            edit_mode = bool(pkg.get("edit_mode"))
            attempts = [True, False] if auto_first else [False]
            for auto_flag in attempts:
                led = clip_edit.edit(
                    info["path"], out_mp4,
                    credit=clip_edit.credit_label(platform, streamer),
                    hook=hook, words=words,
                    start=spec.get("start", 0.0), end=spec.get("end", 0.0),
                    whisper_model=wmodel,
                    auto=auto_flag, series=series,
                    direct=(meta or {}).get("edit"),
                    edit_mode=edit_mode)
                if meta:
                    _judge("title", source="authored", title=meta["title"])
                    led["authored_title"] = meta["title"]
                    led["authored_tags"] = meta["hashtags"]
                    led["authored_caption"] = author.scrub_text(
                        meta.get("caption", ""))
                    led["authored_cta"] = author.scrub_text(
                        meta.get("cta", ""))
                    led["series"] = meta.get("series", "chaos")
                led["source_url"] = info["url"]
                led["source_views"] = info["views"]
                # The raw Twitch clip title is the fallback the public title,
                # description, and posted-log all reach for when authoring is
                # rejected — and it's streamer-authored text we don't control.
                # Sanitise it HERE, at the one place it enters the ledger, so
                # an unsafe raw title can NEVER reach any public surface (live
                # incident: "Silky Calls Him Gay" shipped via this path).
                # safe_title alone only blocks UNSAFE text — it happily passed
                # "WWWW" and "w max" through as public titles on 2026-07-29.
                # fallback_title adds the quality floor, using the transcript
                # (what was actually said) when the clipper's title is noise.
                led["clip_title"] = author.fallback_title(
                    streamer, info["title"],
                    " ".join(w["w"] for w in (words or [])))
                if not (meta or {}).get("title"):
                    # authoring produced nothing — say which floor tier the
                    # public title came from, so a generic batch is legible
                    # in the record instead of looking intentional
                    _judge("title", source="floor",
                           title=led["clip_title"], raw=info["title"],
                           kept_raw=(led["clip_title"] == author.safe_title(
                               info["title"], streamer)))
                led["clipper"] = info["clipper"]
                led["streamer"] = streamer
                led["platform"] = platform
                led["self_healed"] = (auto_first and not auto_flag)
                # A/B tag — ASSIGNMENT vs ACTUAL OUTPUT. `experiment_arm` is
                # what the slot was assigned; `structure` is what actually
                # rendered. A self-healed slot ships the SIMPLE render even
                # though edit_mode was on — labelling that "edit" corrupts the
                # comparison, so it becomes "simple_fallback".
                led["experiment_arm"] = "edit" if edit_mode else "clip"
                led["structure"] = (
                    "simple_fallback" if led["self_healed"]
                    else "edit" if (edit_mode and led.get("auto_edit"))
                    else "clip")
                qa = clip_qa.review(out_mp4, led, work)
                led["qa"] = {k: qa[k] for k in
                             ("verdict", "problems", "vision")}
                # Split the two critics apart: the free mechanical engine
                # and the paid vision judge fail for very different reasons
                # and deserve separate verdicts in the record.
                _judge("render_qa", verdict=qa["verdict"],
                       problems=[p for p in qa["problems"]
                                 if not p.startswith("vision:")])
                _vis = qa.get("vision")
                _judge("vision",
                       verdict=("unavailable" if not _vis else
                                "pass" if _vis.get("publish") else "reject"),
                       confidence=(_vis or {}).get("confidence"),
                       problems=(_vis or {}).get("problems"))
                ledger_path = work / f"{slug}.ledger.json"
                ledger_path.write_text(json.dumps(led, indent=2) + "\n")
                if qa["verdict"] != "fail":
                    break
                if auto_flag:
                    print(f"::warning::[qa] {slug} failed "
                          f"({'; '.join(qa['problems'])[:140]}) — "
                          "self-healing with the simple render", flush=True)
            result["render_level"] = led.get("render_level")
            result["layout"] = (led.get("shot_plan") or {}).get("layout")
            result["self_healed"] = led["self_healed"]
            result["experiment_arm"] = led.get("experiment_arm", "clip")
            result["structure"] = led.get("structure", "clip")
            if qa["verdict"] == "fail":
                result["qa"] = led["qa"]
                result["video_path"] = str(out_mp4.relative_to(REPO))
                result["ledger"] = str(ledger_path.relative_to(REPO))
                # BLOCKLIST the broken clip: without this, the next slot
                # re-picks the exact same clip and breaks the same way
                # (live incident: one 2s clip ate four slots back to back).
                # Rides log["posted"] so posted_keys excludes it for the
                # rest of this run and — once any later slot saves the log
                # — for every future run too.
                _blocklist(log, f"rejected-{_clip_key(led['source_url']) or slug}", {
                    "source_url": led["source_url"],
                    "streamer": led["streamer"],
                    "title": (led.get("authored_title")
                              or led["clip_title"]),
                    "qa_rejected": True,
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
                raise RuntimeError(
                    "qa_rejected: " + "; ".join(qa["problems"])[:200])
        elif pkg["capture"]["kind"] == "sim":
            from third_capture import sim_video
            led = sim_video.compose_sim(pkg, out_mp4)
            ledger_path = work / f"{slug}.ledger.json"
            ledger_path.write_text(json.dumps(led, indent=2) + "\n")
        else:
            ledger_path = run_capture(pkg, work)
            led = json.loads(ledger_path.read_text())
            if pkg_path is None:
                raise RuntimeError("cli/sim packages must exist on disk")
            composer.compose(pkg_path, ledger_path, out_mp4)
        result["video_path"] = str(out_mp4.relative_to(REPO))
        result["ledger"] = str(ledger_path.relative_to(REPO))
        # UNJUDGED GATE (2026-07-30): every CONTENT quality gate in this
        # pipeline fails OPEN when its judge is unreachable, and on that
        # date all three were down at once, so three clips shipped that
        # nothing had judged:
        #   1. selection floor — the can't-score default is 0.5 and
        #      min_banger is 0.5, so `banger >= min_banger` is True by
        #      exactly zero margin: a blind run always clears the floor.
        #   2. content gate — `if cb is not None and cb < floor` skips
        #      entirely when the brain returns nothing.
        #   3. vision critic — `bool(vision and not vision["publish"])` is
        #      False when vision is None.
        # Each fail-open is defensible alone (never lose a good clip to a
        # flaky brain). Together they mean a clip can reach the channel
        # with ZERO content judgment behind it. This is the backstop: if
        # not one judge could evaluate it, don't publish it. A single
        # working judge is enough to ship — this only fires when the slate
        # would otherwise be chosen on raw view count alone.
        # Skip (not error): retrying would just fetch another unjudged clip.
        if led.get("kind") == "twitch_clip" and not _any_judgment():
            raise _SkipSlot(
                "unjudged: no content judge could evaluate this clip "
                "(ranker blind, content gate and vision both unavailable) "
                "— refusing to publish on view count alone")
        # Final safety choke: no matter which path produced it (authored,
        # raw fallback, sim/cli template), the public title is scrubbed one
        # last time before it can reach an uploader.
        title = author.safe_title(
            pkg["title"].format(**_fmt_from_ledger(led)),
            led.get("streamer", ""))[:100]
        result["title"] = title
        if dry_run:
            result.update(ok=True, video_url="(dry-run)")
            if led.get("kind") == "twitch_clip":
                # in-memory only (never saved): keeps the next package in
                # this run from re-picking the clip, streamer, or event
                log["posted"][slug] = {
                    "source_url": led["source_url"],
                    "streamer": led["streamer"],
                    "title": led.get("authored_title") or led["clip_title"],
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
            elif led.get("kind") == "story":
                # same in-memory guard for stories: a second story slot in
                # this run must not rebuild the exact same arc
                log["posted"][slug] = {
                    "story_key": led.get("story_key"),
                    "streamer": led.get("streamer"),
                    "title": led.get("authored_title", ""),
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
        else:
            from shared.uploaders import YouTubeUploader
            description = _description(pkg, led)
            # every language: extended locale set (clipper content is
            # visual-first, so localized metadata travels worldwide)
            localizations = None
            try:
                from shared.localize import translate_metadata, ALL_LANGS
                localizations = translate_metadata(title, description,
                                                   langs=ALL_LANGS)
            except Exception as e:  # noqa: BLE001
                print(f"[localize] extended set skipped: {e}", flush=True)
            # ---- CLAIM THE SLOT BEFORE SENDING BYTES ------------------
            # The resumable upload can commit on YouTube's side and THEN
            # fail (dropped connection, transient 5xx on the last chunk).
            # The exception used to unwind past log["posted"][slug] and
            # _save_log, so the video existed and NOTHING recorded it —
            # and main() then retried the slot, re-ranked the identical
            # candidate board, and uploaded the same clip a second time to
            # the same publish_at. The FINAL DEDUPE GUARD could not help:
            # it reads posted_keys, which never learned about upload #1.
            #
            # So persist an in-flight claim FIRST. If the upload dies for
            # any reason the claim survives, posted_keys excludes the clip
            # key, and the retry picks something else. Worst case we lose
            # one clip; the alternative is two videos on the channel from
            # one slot, which is the one failure this log exists to stop.
            _claim = {
                "pending": True,
                "source_url": led.get("source_url", ""),
                "story_key": led.get("story_key"),
                "streamer": led.get("streamer", ""),
                "title": title,
                "kind": led.get("kind", "cli"),
                "ts": datetime.now(timezone.utc).isoformat(),
                "note": "upload started; entry is upgraded on success and "
                        "left pending if the upload died mid-flight",
            }
            log["posted"][slug] = _claim
            _save_log(log)
            _checkpoint_log("claim upload slot")
            # publish_at was computed at run START with only a 30-minute
            # lead on slot 0, then frozen. Everything between then and here
            # — discovery over 66 handles, VOD mining, download, whisper,
            # authoring, the vision gate, the render, QA, up to 3 retries,
            # and on a story slot six more downloads and whisper passes —
            # can easily eat 30 minutes. A past publishAt with
            # privacyStatus=private is either a hard API rejection after
            # the full render is paid for, or a video that sits private
            # and NEVER GOES LIVE while the posted log records a URL that
            # says it shipped. Both are invisible. Clamp at send time.
            publish_at = _clamp_publish_at(publish_at)
            try:
                up = YouTubeUploader(channel="third").upload(
                    file_path=out_mp4, title=title,
                    description=description,
                    tags=_yt_tags(pkg, led),
                    publish_at=publish_at,
                    localizations=localizations,
                )
            except Exception:
                print(f"::warning::[upload] {slug} failed mid-flight — the "
                      f"pending claim STAYS in the posted log. If the video "
                      f"did land on YouTube it is now deduped; if it did "
                      f"not, this clip is retired rather than risked twice.",
                      flush=True)
                raise
            result.update(ok=True, video_url=getattr(up, "url", str(up)))
            # ADDITIVE REACH: same clip → TikTok FYP (+ Reels if configured),
            # where a small channel can actually get distributed. Never breaks
            # the YouTube post.
            xposts = _crosspost(out_mp4, title, description,
                                _hashtags(pkg, led))
            if xposts:
                result["crossposts"] = xposts
            entry = {
                "url": result["video_url"], "title": title,
                "kind": led.get("kind", "cli"),
                "ts": datetime.now(timezone.utc).isoformat(),
                # SCHEDULED-ANALYTICS FIX: record BOTH the upload moment and
                # the scheduled go-live. fetch_analytics ages a video from its
                # real public publish time, never the upload stamp, so a clip
                # scheduled hours out is not mistaken for an old zero-view flop.
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "publish_at": publish_at,
            }
            if xposts:
                entry["crossposts"] = xposts
            if led.get("kind") == "twitch_clip":
                entry["source_url"] = led["source_url"]
                entry["streamer"] = led["streamer"]
                # Instrumentation for the retention feedback loop: record the
                # editorial choices so a later run can correlate opening style
                # against this video's measured early-retention curve.
                entry["series"] = led.get("series") or series
                entry["hook"] = hook
                # A/B: assigned arm + what ACTUALLY rendered (self-heal ships
                # the simple clip even under edit_mode → "simple_fallback").
                entry["experiment_arm"] = led.get("experiment_arm", "clip")
                entry["structure"] = led.get("structure", "clip")
                entry["actual_structure"] = led.get("structure", "clip")
                entry["self_healed"] = led.get("self_healed", False)
                entry["source_views"] = led.get("source_views")
                entry["banger"] = (locals().get("pick") or {}).get("banger")
                _cut = (meta or {}).get("edit", {}).get("cut")
                if _cut:
                    entry["cut"] = _cut
                    entry["director_cut"] = True
            elif led.get("kind") == "story":
                # NOTE: no `source_url` on a story entry — that's what keeps
                # member clips out of posted_keys, so a clip inside a
                # compilation stays legal for single-slot use (and vice
                # versa). The story's own never-repeat law rides story_key.
                entry["story_key"] = led.get("story_key")
                entry["member_keys"] = led.get("member_keys")
                entry["streamer"] = led.get("streamer")
                entry["who"] = led.get("who")
                entry["series"] = "story"
                entry["experiment_arm"] = "story"
                entry["structure"] = "story"
                entry["actual_structure"] = "story"
                entry["n_beats"] = led.get("n_beats")
                entry["story_structure"] = led.get("story_structure")
                entry["duration_s"] = led.get("duration_s")
                entry["narrative_score"] = led.get("narrative_score")
                entry["revision_count"] = led.get("revision_count")
                entry["used_vod_expansion"] = led.get("used_vod_expansion")
                entry["used_narration"] = led.get("used_narration")
                entry["context_overlay_count"] = \
                    led.get("context_overlay_count")
                entry["replay_count"] = led.get("replay_count")
            elif "files" in led:
                entry["ledger_sha_input"] = \
                    led["files"]["input"]["sha256"][:16]
            log["posted"][slug] = entry
            _save_log(log)
    except _SkipSlot as e:
        # a deliberate "post nothing here" — NOT a failure and NOT a
        # blocklist (no specific bad clip; the whole slate was too weak).
        result.update(ok=False, skipped=str(e))
        print(f"[skip] {slug}: {e}", flush=True)
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"
    # Attach on BOTH paths: a rejected clip's verdicts are the interesting
    # ones, and they used to die with the CI log. Belt-and-braces — _judge
    # already coerces to JSON-safe primitives, and this runs OUTSIDE the
    # render's try, so it must not be able to raise either.
    try:
        if _JUDGES:
            result["judges"] = json.loads(json.dumps(_JUDGES, default=str))
    except Exception as e:  # noqa: BLE001
        print(f"[judges] not recorded for {slug}: {e}", flush=True)
    result["took_s"] = round(time.time() - t0, 1)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc)
                    .strftime("%Y%m%d"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-schedule", action="store_true",
                    help="publish immediately instead of next 17:00 UTC slot")
    args = ap.parse_args()

    # Loop health FIRST: say plainly whether each selection brain is alive or
    # dark before a single clip is picked, so a silently-dead data source is
    # impossible to miss in the run log.
    feedback = _feedback_status()

    day_dir = PACKAGE_DIR / args.date
    paths = sorted(day_dir.glob("*.json")) if day_dir.is_dir() else []
    packages: list[tuple[dict, Path | None]] = \
        [(json.loads(p.read_text()), p) for p in paths]
    if not packages:
        # self-sufficient cron: synthesize the day's slate from the
        # default template so no one has to author packages daily
        template = PACKAGE_DIR / "default_clip.json"
        if template.exists():
            base = json.loads(template.read_text())
            n = int(base.pop("count", 3))
            # A/B STRUCTURE SPLIT: `story_count` of the n daily slots try the
            # multi-clip STORY arm (auto-detected narrative arcs — the format
            # the deep dive says the feed actually rewards); the rest stay the
            # "clip" structure. A story slot that finds no genuine arc falls
            # back to a normal clip (event-driven, quality-gated — a forced
            # story on thin material is worse than none). Slots are chosen by
            # a DATE-SEEDED shuffle so the story arm isn't permanently
            # correlated with the same posting times (arm vs daypart
            # confound). `story_count` supersedes the earlier `edit_count`
            # montage arm, per the operator's call to replace it.
            import random as _rnd
            story_count = min(int(base.pop("story_count",
                                           base.pop("edit_count", 0))), n)
            base.pop("edit_count", None)
            _slots = list(range(1, n + 1))
            _rnd.Random(f"third-ab-{args.date}").shuffle(_slots)
            story_slots = set(_slots[:story_count])
            for i in range(1, n + 1):
                pkg = json.loads(json.dumps(base))
                pkg["slug"] = f"clip-{args.date}-{i}"
                pkg["story_mode"] = i in story_slots
                packages.append((pkg, None))
            print(f"no authored packages — synthesized {n} from template "
                  f"({story_count} story-arm slots: "
                  f"{sorted(s for s in story_slots if s <= n)})")
        else:
            print(f"no packages under {day_dir}")
            return 0
    # Slot cadence: with a higher daily count we tighten spacing so the extra
    # volume concentrates in US prime time (17:00 UTC = 1pm ET) instead of
    # spilling into dead overnight hours. 90 min × 8 slots ≈ 17:00→03:30 UTC.
    slot_gap = timedelta(minutes=90)
    log = _load_log()
    publish_base = None
    if not args.no_schedule and not args.dry_run:
        now = datetime.now(timezone.utc)
        publish_base = now.replace(hour=17, minute=0, second=0,
                                   microsecond=0)
        # start at least 30 min out (roll forward a slot at a time if late)
        while publish_base < now + timedelta(minutes=30):
            publish_base += slot_gap
        # ...AND PAST EVERYTHING TODAY ALREADY CLAIMS.
        # `slot` restarts at 0 every run while publish_base is recomputed
        # from THIS run's clock, and an already-posted slug does not
        # advance `slot` — so the first UNPOSTED slot always got
        # publish_base + 0. Live example: the 13:01 run posts slot 1 at
        # 17:00Z; the 14:19 run recomputes publish_base = 17:00 (still
        # >= 14:49, no roll), skips the posted slot 1 without advancing,
        # and hands slot 2 publish_at = 17:00Z — an exact collision, two
        # Shorts live in the same minute. The workflow fires up to 4x a
        # day, so this is the normal configuration, not an edge case.
        _claimed = []
        for _v in log.get("posted", {}).values():
            _p = str(_v.get("publish_at") or "")
            if not _p:
                continue
            try:
                _dt = datetime.fromisoformat(_p.replace("Z", "+00:00"))
            except ValueError:
                continue
            if _dt.tzinfo is None:
                _dt = _dt.replace(tzinfo=timezone.utc)
            if _dt > now - timedelta(hours=6):
                _claimed.append(_dt)
        if _claimed:
            _hi = max(_claimed)
            while publish_base <= _hi:
                publish_base += slot_gap
            print(f"[schedule] a prior run already claimed up to "
                  f"{_hi.isoformat()} — this run starts at "
                  f"{publish_base.isoformat()}", flush=True)

    _audit_dupes(log)   # loud tripwire — surfaces any dup every run
    # uploaders.upload wants publish_at as an RFC3339 string, not datetime.
    # Slot index only advances for packages that will actually post, so
    # already-posted slugs don't leave gaps in the schedule.
    results, slot = [], 0
    # RESILIENCE: one bad clip must NEVER kill a slot. When a candidate fails
    # (preflight / render / QA), it's blocklisted (by clip key, so it can't be
    # re-picked) and the slot RETRIES — re-selecting the next-best fresh clip —
    # until one ships or we run dry. A deliberate skip (quality floor / dedupe
    # guard) is not a failure and does not retry. Failures fail fast (the dark
    # gate + preflight reject bad sources in ~2s), so retries are cheap.
    # 3 attempts now buy MORE than they used to: a slot whose shortlist
    # fails the title floor no longer skips instantly — it escalates each
    # candidate to the transcript judge, so these attempts get spent on
    # real inspection instead of going unused. Held at 3 deliberately: each
    # attempt costs a download + whisper pass (~90s) and the job's ceiling
    # is 120 min (a run died on that wall on 2026-07-25).
    MAX_SLOT_ATTEMPTS = 3
    for pkg, path in packages:
        # WALL-CLOCK DEADLINE. third.yml's ceiling is 120 minutes and a run
        # was killed on it (2026-07-25) — with three videos already live on
        # YouTube and the commit step never reached, so nothing in git knew
        # they existed. A cancelled job is the worst outcome available: no
        # stats, no verdicts, and a dedupe log that has to be reconstructed
        # from the channel. Stopping cleanly with three slots filled beats
        # being killed with three-and-a-bit. Skips, not errors, so the run
        # still exits 0 and the workflow still commits.
        if _deadline_passed():
            print(f"::warning::[budget] {_BUDGET_MIN} min elapsed — stopping "
                  f"before {pkg['slug']} so the run finishes cleanly instead "
                  f"of being killed at the job's 120-minute wall. Remaining "
                  f"slots go to the next run.", flush=True)
            results.append({"slug": pkg["slug"], "ok": False,
                            "skipped": "run budget reached"})
            continue
        # BRAIN-HEALTH GATE: on 2026-07-29 every rank/author/scene call
        # failed for ~90 min and the run still shipped 4 clips — picked by
        # raw view count (banger pinned at 0.5), no scene analysis, fallback
        # titles. Each per-call fallback degraded "gracefully"; nothing saw
        # the pattern. Once the brain is provably down (3+ tasks, zero
        # successes), stop filling slots: the remaining slugs stay unposted
        # and the next run (cron/chain) retries them when the brain is back.
        # Slots already shipped this run stay shipped and get committed.
        if author.brain_down() and not os.environ.get("THIRD_ALLOW_BLIND"):
            h = author.brain_health()
            print(f"::error::[brain] DOWN ({h['fail']} failed brain tasks, "
                  f"0 ok) — refusing to publish a blind slate. Remaining "
                  f"slots left for the next run. Set THIRD_ALLOW_BLIND=1 "
                  f"to override.", flush=True)
            results.append({"slug": pkg["slug"], "ok": False,
                            "skipped": "brain down — blind-slate gate"})
            continue
        publish_at = None
        if publish_base and pkg["slug"] not in log["posted"]:
            publish_at = (publish_base + slot_gap * slot) \
                .strftime("%Y-%m-%dT%H:%M:%SZ")
            slot += 1
        r = None
        for attempt in range(1, MAX_SLOT_ATTEMPTS + 1):
            r = process(pkg, path, dry_run=args.dry_run,
                        publish_at=publish_at, log=log)
            if r.get("ok") or r.get("skipped"):
                break
            r["attempts"] = attempt
            if _deadline_passed():
                print(f"::warning::[budget] out of time after attempt "
                      f"{attempt} on {pkg['slug']} — not retrying",
                      flush=True)
                break
            if attempt < MAX_SLOT_ATTEMPTS:
                print(f"::warning::[slot] {pkg['slug']} attempt {attempt} "
                      f"failed ({str(r.get('error',''))[:70]}) — retrying "
                      "with a fresh clip", flush=True)
        results.append(r)
    print(json.dumps(results, indent=2))

    # Learning loop (playbook §20): persist a compact per-run record —
    # layouts chosen, render levels, QA verdicts, self-heals — so recurring
    # failure categories are visible across batches and turn into rules,
    # not one-off fixes. Kept small (last 30 runs) per storage doctrine.
    try:
        stats_path = REPO / "state" / "third_qa_stats.json"
        hist = []
        if stats_path.exists():
            hist = json.loads(stats_path.read_text()).get("runs", [])
        hist.append({
            "date": args.date, "dry_run": args.dry_run,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "feedback": feedback,
            # How the brains actually fared this run. A run where every
            # brain task failed picked its clips on raw view count; one
            # where they half-failed picked SOME blind. Neither was
            # legible before — `ok`/`fail` counts make it a one-line read.
            "brain": author.brain_health(),
            # Only the sources that PRODUCED NOTHING are worth keeping —
            # a healthy source is uninteresting and 60+ entries would bloat
            # state/ (small-JSON rule, docs/STORAGE_AUDIT.md). This is the
            # prune list: handles that cost an API call and returned zero.
            "dead_sources": {k: v for k, v in _SOURCE_HEALTH.items()
                             if v.get("clips", 0) == 0},
            "clips": [{k: r.get(k) for k in
                       ("slug", "ok", "skipped", "render_level", "layout",
                        "self_healed", "error", "judges", "took_s")
                       if r.get(k) is not None}
                      for r in results],
        })
        from shared.fsutil import atomic_write_json
        atomic_write_json(stats_path, {"runs": hist[-30:]})
    except Exception as e:  # noqa: BLE001 — stats never fail the run
        print(f"[stats] skipped: {e}", flush=True)
    # Whatever else happened, the blocklist and any pending upload claims
    # must reach disk — those are what stop the next run re-judging clips
    # this one already rejected, and re-uploading a video this one may
    # already have published. The workflow's commit step reads the file.
    try:
        _save_log(log)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[log] final save failed: {e}", flush=True)

    # SAY WHETHER THE CHANNEL ACTUALLY PRODUCED ANYTHING.
    # An already-posted slug counts as ok=True (the slot is legitimately
    # satisfied), so a run that shipped ZERO new videos exited 0 with a
    # green checkmark. On 2026-07-31 the 14:19, 16:18 and 22:27 runs each
    # produced nothing and each looked fine in the Actions tab, because
    # slot 1 was already posted from the morning. Partial success is still
    # success — but "shipped nothing new" has to be legible.
    shipped = [r for r in results
               if r.get("ok") and not r.get("skipped")]
    if not shipped:
        print(f"::warning::[run] NO NEW VIDEOS. {len(results)} slot(s): "
              + "; ".join(f"{r.get('slug')}="
                          + str(r.get('skipped') or r.get('error')
                                or 'ok')[:60] for r in results),
              flush=True)
    else:
        print(f"[run] shipped {len(shipped)} new video(s): "
              + ", ".join(str(r.get("slug")) for r in shipped), flush=True)
    # partial success is success: a late-day slot finding no fresh clip
    # must not fail the run (that skips the posted-log commit and desyncs
    # dedupe state). Fail only when NOTHING succeeded.
    return 0 if any(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
