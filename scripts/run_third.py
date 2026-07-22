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

ANALYTICS_LATEST = REPO / "state" / "analytics_third" / "latest.json"


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
                and (v.get("age_hours") or 0) >= MIN_PUBLIC_AGE]
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
    seg = path.rsplit("/", 1)[-1]
    return seg.lower() or path.lower()


def _load_log() -> dict:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"posted": {}}


def _save_log(log: dict) -> None:
    from fsutil import atomic_write_json
    atomic_write_json(LOG_PATH, log)


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
    if led.get("kind") == "twitch_clip":
        # the Groq author's title beats the raw clip title ("v", "W"...)
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
            from uploaders import TikTokUploader
            up = TikTokUploader(channel="third").upload(
                file_path=mp4, title=title, description=description, tags=tags)
            out["tiktok"] = getattr(up, "url", str(up))
            print(f"[crosspost] tiktok -> {out['tiktok']}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[crosspost] tiktok failed ({e})", flush=True)
    if all(os.environ.get(k) for k in
           ("META_ACCESS_TOKEN", "IG_USER_ID", "REELS_PUBLIC_HOST")):
        try:
            from uploaders import InstagramUploader
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


def _description(pkg: dict, led: dict) -> str:
    tags = " ".join(f"#{t}" for t in _hashtags(pkg, led))
    note = pkg.get("description_note", "")
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
        credit = (f"Clip from {led['credit']} — full credit to the "
                  f"streamer.\nSource: {led['source_url']}\n"
                  f"Clipped by {led['clipper']}.")
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


def process(pkg: dict, pkg_path: Path | None, *,
            dry_run: bool, publish_at, log: dict) -> dict:
    slug = pkg["slug"]
    result = {"slug": slug, "ok": False}
    if slug in log["posted"]:
        result.update(ok=True, skipped="already posted")
        return result
    work = OUTPUT_DIR / "third"
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        out_mp4 = work / f"third_{slug}.mp4"
        if pkg["capture"]["kind"] == "twitch_clip":
            from third_capture import clip_edit
            spec = pkg["capture"]
            if spec.get("clip_url"):
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
                posted_today = [v for v in log["posted"].values()
                                if str(v.get("ts", "")).startswith(today)]
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
                    pool = []
                    for platform, chans in sources.items():
                        for ch in chans:
                            try:
                                pool += clip_edit.discover(
                                    platform, ch, top=spec.get("top", 8),
                                    range_=window)
                            except Exception as e:  # noqa: BLE001
                                print(f"::warning::discover {platform}:{ch} "
                                      f"failed ({type(e).__name__}) — "
                                      "skipped", flush=True)
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
                from third_capture import author
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
                min_banger = spec.get("min_banger", 0.35)
                postable = [c for c in shortlist if c["banger"] >= min_banger]
                if not postable:
                    best_b = max((c["banger"] for c in shortlist), default=0.0)
                    raise _SkipSlot(
                        f"quality floor: best banger {best_b:.2f} < "
                        f"{min_banger} across {len(shortlist)} candidates — "
                        "posting fewer, not a dud")
                pick = postable[0]
                # FINAL DEDUPE GUARD (never post the same clip twice): the
                # shortlist was already filtered by posted_keys, so this only
                # fires if a future refactor lets a posted clip slip through —
                # a loud, cheap backstop on the channel's core law.
                if _clip_key(pick["url"]) in posted_keys:
                    raise _SkipSlot(
                        f"dedupe guard: {_clip_key(pick['url'])} already "
                        "posted — refusing a duplicate")
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
                log["posted"][f"rejected-{_clip_key(info['url']) or slug}"] = {
                    "source_url": info["url"], "streamer": streamer,
                    "title": info["title"], "qa_rejected": True,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                raise RuntimeError("preflight: " + "; ".join(pf)[:180])

            # transcribe once, then let the Groq author write the
            # packaging from what's actually said in the clip
            wmodel = spec.get("whisper_model", "small")
            has_cut = spec.get("start") or spec.get("end")
            words = None if has_cut else \
                clip_edit.transcribe_words(info["path"], wmodel)
            meta = None
            if words is not None:
                from third_capture import author
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

            # DIRECTOR COMPLETENESS GATE (§9): if the brain judges the clip
            # starts mid-action with no context OR its payoff is cut off,
            # skip it — a confusing clip is worse than a lost slot. Blocklist
            # so it can't be re-picked (same as a QA rejection).
            if meta and meta.get("edit", {}).get("complete") is False:
                log["posted"][f"rejected-{_clip_key(info['url']) or slug}"] = {
                    "source_url": info["url"], "streamer": streamer,
                    "title": info["title"], "qa_rejected": True,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
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
                led["clip_title"] = author.safe_title(info["title"], streamer)
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
                log["posted"][f"rejected-{_clip_key(led['source_url']) or slug}"] = {
                    "source_url": led["source_url"],
                    "streamer": led["streamer"],
                    "title": (led.get("authored_title")
                              or led["clip_title"]),
                    "qa_rejected": True,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
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
        else:
            from uploaders import YouTubeUploader
            description = _description(pkg, led)
            # every language: extended locale set (clipper content is
            # visual-first, so localized metadata travels worldwide)
            localizations = None
            try:
                from localize import translate_metadata, ALL_LANGS
                localizations = translate_metadata(title, description,
                                                   langs=ALL_LANGS)
            except Exception as e:  # noqa: BLE001
                print(f"[localize] extended set skipped: {e}", flush=True)
            up = YouTubeUploader(channel="third").upload(
                file_path=out_mp4, title=title,
                description=description,
                tags=_yt_tags(pkg, led),
                publish_at=publish_at,
                localizations=localizations,
            )
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
            # A/B STRUCTURE SPLIT: `edit_count` of the n daily slots render in
            # the new montage "edit" arm; the rest stay the current "clip"
            # structure. Same selection + packaging on both — only the render
            # style differs, so the test isolates STRUCTURE. The edit slots are
            # chosen by a DATE-SEEDED shuffle (not a fixed 2/5/8 every day) so
            # the edit arm isn't permanently correlated with the same posting
            # times — otherwise "edit vs clip" is confounded with daypart.
            import random as _rnd
            edit_count = min(int(base.pop("edit_count", 3)), n)
            _slots = list(range(1, n + 1))
            _rnd.Random(f"third-ab-{args.date}").shuffle(_slots)
            edit_slots = set(_slots[:edit_count])
            for i in range(1, n + 1):
                pkg = json.loads(json.dumps(base))
                pkg["slug"] = f"clip-{args.date}-{i}"
                pkg["edit_mode"] = i in edit_slots
                packages.append((pkg, None))
            print(f"no authored packages — synthesized {n} from template "
                  f"({edit_count} edit-arm slots: "
                  f"{sorted(s for s in edit_slots if s <= n)})")
        else:
            print(f"no packages under {day_dir}")
            return 0
    # Slot cadence: with a higher daily count we tighten spacing so the extra
    # volume concentrates in US prime time (17:00 UTC = 1pm ET) instead of
    # spilling into dead overnight hours. 90 min × 8 slots ≈ 17:00→03:30 UTC.
    slot_gap = timedelta(minutes=90)
    publish_base = None
    if not args.no_schedule and not args.dry_run:
        now = datetime.now(timezone.utc)
        publish_base = now.replace(hour=17, minute=0, second=0,
                                   microsecond=0)
        # start at least 30 min out (roll forward a slot at a time if late)
        while publish_base < now + timedelta(minutes=30):
            publish_base += slot_gap

    log = _load_log()
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
    MAX_SLOT_ATTEMPTS = 3
    for pkg, path in packages:
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
            "clips": [{k: r.get(k) for k in
                       ("slug", "ok", "skipped", "render_level", "layout",
                        "self_healed", "error") if r.get(k) is not None}
                      for r in results],
        })
        from fsutil import atomic_write_json
        atomic_write_json(stats_path, {"runs": hist[-30:]})
    except Exception as e:  # noqa: BLE001 — stats never fail the run
        print(f"[stats] skipped: {e}", flush=True)
    # partial success is success: a late-day slot finding no fresh clip
    # must not fail the run (that skips the posted-log commit and desyncs
    # dedupe state). Fail only when NOTHING succeeded.
    return 0 if any(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
