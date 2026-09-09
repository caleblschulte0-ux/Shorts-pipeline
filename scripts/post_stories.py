#!/usr/bin/env python3
"""Post the curated data-explainer STORY shorts to a single channel.

This is a separate, self-contained path from the trending daily pipeline
(scripts/run_trending_daily.py) so the existing channel is never touched.
It renders each story slug with studio_render and uploads it with the
YouTubeUploader — which enforces YOUTUBE_EXPECTED_CHANNEL, so a wrong token
can never post to the wrong account.

Auth (env, set in the workflow from repo secrets):
    YOUTUBE_CLIENT_SECRETS_JSON   shared OAuth client (same app is fine)
    YOUTUBE_TOKEN_JSON            the TARGET channel's token
    YOUTUBE_EXPECTED_CHANNEL      e.g. "short_explainer67" (hard guard)

Usage:
    python scripts/post_stories.py --dry-run            # render only, no upload
    python scripts/post_stories.py                      # render + upload (public)
    python scripts/post_stories.py --slugs debt-trap grocery-squeeze
    python scripts/post_stories.py --every-hours 6      # schedule, spaced out
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# studio_render (and its Pillow/matplotlib/numpy deps) is imported lazily
# inside the render loop so --check-channel works with only the google libs.

CONFIG = REPO / "data_learning" / "niche.config.json"
OUTPUT_DIR = REPO / "output"
STATE_DIR = REPO / "state"
# Deliberately a DIFFERENT log file from the trending pipeline's
# state/posted_log.json so the two channels never collide. Sibling channels
# (e.g. curiosity) pass --config/--log to get their own story config and
# posted-log; these module-level paths stay the explainer defaults.
LOG_PATH = STATE_DIR / "explainer_posted_log.json"


def _recent_gate_blocks(hours: int = 48) -> set:
    """Slugs the showrunner BLOCKED within the last `hours`, read from its
    durable ledger. Used only to reorder the default queue — a blocked story
    keeps its place in line, at the back. Any unreadable line or timestamp
    is skipped: this must never be able to fail a posting run.

    The window MUST exceed the gap between same-slot runs (~24h cron), or
    the rotation never fires for the run that needs it: at 20h, the 08-22
    evening blocks (19:52-21:53Z) had all expired by the 08-23 evening run
    (cutoff 23:49Z the day before), so the two daily slots each promoted
    the other's freshly-blocked slugs to the front — the same four stories
    re-rendered and re-blocked ~18 times over two days while ~40 untried
    stories waited. 48h covers both slots seeing both days' blocks."""
    out: set = set()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        ledger = STATE_DIR / "showrunner_verdicts.jsonl"
        for line in ledger.read_text().splitlines():
            try:
                row = json.loads(line)
                if row.get("verdict") != "block" or not row.get("slug"):
                    continue
                ts = datetime.fromisoformat(str(row.get("ts")))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    out.add(str(row["slug"]))
            except Exception:  # noqa: BLE001 — one bad row is not a blocker
                continue
    except OSError:
        pass
    return out


def _load_log(path: Path = LOG_PATH) -> dict:
    # FAIL CLOSED on corruption (fsutil.CorruptStateError): this dict is the
    # explainer channel's only dedupe state, and the old JSONDecodeError
    # swallow meant a truncated file read as "nothing posted" — every slug
    # re-uploads and _save_log then overwrites the real history. Missing
    # file = first run = honest empty default, unchanged.
    from shared.fsutil import load_state_json
    return load_state_json(path, {"posted": {}}, expect_type=dict)


def _save_log(log: dict, path: Path = LOG_PATH) -> None:
    from shared.fsutil import atomic_write_json
    atomic_write_json(path, log)


# Evergreen hashtags every data-explainer Short carries, on top of whatever the
# story config specifies. Kept relevant (no spammy #viral/#fyp) so YouTube
# doesn't discard them, and deliberately short — YouTube IGNORES ALL hashtags in
# a description once there are more than 15, so we cap hard below.
BASE_HASHTAGS = ["shorts", "facts", "didyouknow", "data", "explained",
                 "education", "interesting"]
# Required attribution for the CC-BY music bed (Kevin MacLeod / incompetech).
ATTRIBUTION = ("Music by Kevin MacLeod (incompetech.com), licensed under "
               "Creative Commons: By Attribution 4.0 "
               "(creativecommons.org/licenses/by/4.0/)")


def _dedupe(seq):
    """Order-preserving, case-insensitive dedupe."""
    seen, out = set(), []
    for x in seq:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _merged_tags(cfg: dict) -> list[str]:
    """Story hashtags first (most specific), then evergreen base. For the API
    `tags` field, capped at YouTube's 30 (well within the 500-char limit for
    these short tags)."""
    return _dedupe(list(cfg.get("hashtags", [])) + BASE_HASHTAGS)[:30]


def _human_body(cfg: dict) -> str:
    """The prose part of the description (caption, or hook + closing)."""
    cap = (cfg.get("caption") or "").strip()
    if cap:
        parts = [cap]
    else:
        parts = [cfg.get("hook", "").strip()]
        if cfg.get("closing"):
            parts += ["", cfg["closing"].strip()]
    return "\n".join(p for p in parts if p)


def _desc_suffix(cfg: dict) -> str:
    """The non-prose tail appended to EVERY description (English and localized):
    a hashtag block (<=15 so YouTube keeps them) + the CC-BY attribution."""
    tags = _merged_tags(cfg)[:15]
    block = " ".join(f"#{t}" for t in tags)
    return (f"\n\n{block}" if block else "") + f"\n\n{ATTRIBUTION}"


def _description(cfg: dict) -> str:
    return (_human_body(cfg) + _desc_suffix(cfg))[:5000]


def _creative_facts(slug: str, sc: dict, mp4: Path, verdict: dict | None) -> dict:
    """What this video WAS, recorded beside the fact that it posted.

    The channel has been writing its creative decisions into
    state/video_ledger.json for 92 videos — hook_type, words_first_10s,
    scene_changes_before_5s, depictions, ending_type — and every one of those
    rows has `video_id: null`. Meanwhile fetch_analytics reads structure off
    the POSTED LOG entry (`e.get("hook")`, `e.get("n_beats")`, ...), and the
    explainer log only ever stored url/title/at/publish_at. So retention could
    never be attributed to anything: 92 videos of creative bookkeeping that
    could not be joined to a single outcome.

    Both files are keyed by SLUG, so the join needs no new plumbing — the facts
    just have to be written down at the moment of upload. Field names match
    what fetch_analytics already carries, so the existing analytics and retro
    machinery pick them up with no change.

    Never raises: a video that just went public must be logged even if we
    cannot describe it.
    """
    facts: dict = {}
    try:
        segs = sc.get("segments") or []
        facts["n_beats"] = len(segs)
        kinds = [str(sg.get("viz") or
                     ("scene" if isinstance(sg.get("scene"), dict) else "auto"))
                 for sg in segs]
        facts["story_structure"] = "+".join(kinds) or None
        if verdict:
            # The gate's own score, so "did the reviewer's opinion predict the
            # audience's?" becomes an answerable question.
            facts["narrative_score"] = verdict.get("score")
        # duration decides view PERCENTAGE, which is the metric Shorts ranks on
        try:
            import subprocess as _sp
            r = _sp.run(["ffprobe", "-v", "error", "-show_entries",
                         "format=duration", "-of", "csv=p=0", str(mp4)],
                        capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                facts["duration_s"] = round(float(r.stdout.strip()), 1)
        except Exception:  # noqa: BLE001 — duration is a bonus, not a blocker
            pass
        # the creative decisions the director already recorded for this slug
        try:
            ledger = json.loads((STATE_DIR / "video_ledger.json").read_text())
            for row in reversed(ledger.get("videos", [])):
                if row.get("slug") == slug:
                    facts["hook"] = row.get("hook_type")
                    facts["topic_category"] = row.get("topic_category")
                    facts["ending_type"] = row.get("ending_type")
                    facts["depictions"] = row.get("depictions")
                    facts["words_first_10s"] = row.get("words_first_10s")
                    facts["scene_changes_before_5s"] = \
                        row.get("scene_changes_before_5s")
                    break
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        print(f"[{slug}] could not describe the video for analytics: {e}",
              flush=True)
    return {k: v for k, v in facts.items() if v is not None}


def _persist_posted_log_now(log_path: Path, slug: str,
                            why: str = "posted") -> None:
    """Push the posted log to git IMMEDIATELY. Best effort.

    Called TWICE per upload now: once to claim the slot before the API call,
    and once to record the URL after it. The claim is the important one — see
    the comment at the call site.

    An upload is irreversible and external: the video is on YouTube the moment
    the API returns. The record of it has to be just as durable, and until now
    it was not — `_save_log` writes the runner's LOCAL disk, and the git push
    lived in a final workflow step. When a runner is reclaimed mid-job (GitHub
    did exactly that to the 09:32 run on 2026-09-04) the disk goes with it, so
    videos already live on the channel disappear from the dedupe log and the
    next run posts them again.

    CLAUDE.md calls the posted logs sacred for this reason: "losing an entry
    means a duplicate upload". This closes the window from "the rest of the
    run" to "one upload".

    Never raises. The upload already happened; failing here must not abort the
    run or mask the URL we just printed. The end-of-run persist still runs and
    is now a no-op in the happy path.
    """
    import os as _os
    import subprocess as _sp
    if not _os.environ.get("GITHUB_ACTIONS"):
        return
    script = REPO / "scripts" / "ci_commit_state.sh"
    if not script.exists():
        return
    try:
        r = _sp.run(["bash", str(script),
                     f"explainer: {why} {slug} [skip ci]", str(log_path)],
                    capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            print(f"[{slug}] WARNING: could not persist the posted log now "
                  f"(rc={r.returncode}); the end-of-run persist must catch it: "
                  f"{(r.stderr or r.stdout)[-200:]}", flush=True)
    except Exception as e:  # noqa: BLE001 — never break a run over bookkeeping
        print(f"[{slug}] WARNING: posted-log persist raised: {e}", flush=True)


# --------------------------------------------------------------------------
# NEAR-DUPLICATE GUARD
# --------------------------------------------------------------------------
# The posted log deduped on SLUG and nothing else, so two stories that were
# different rows in the config but the same VIDEO to a viewer both shipped.
# Auditing the log found 25 such pairs, including straight repeats:
#
#   2026-06-28  Human Brain Capacity          (posted twice the same day)
#   2026-06-28 / 2026-07-07  Space Debris Removal
#   2026-07-01 / 2026-07-10  Space Exploration Milestones
#   2026-08-21  World Hydropower Fell Below Its 1990 Level
#   2026-08-25  World Coal Power Fell Below Its 1990 Level
#
# That last pair is the shape the current forge produces: one template, one
# noun swapped. YouTube's repetitious-content policy is aimed squarely at it,
# and the operator is being penalised right now.
#
# Two measures, because they fail differently. Sequence ratio catches a
# reworded title; a significant-word overlap catches the template-with-one-swap
# that reads as a low ratio because the swapped word is long. Calibrated
# against the real 234-upload log: this refuses 16 of them (7%), which is the
# repeats and not the legitimately distinct stories.
# Calibrated against the real 234-upload log. 0.80/0.70 refused 16 (7%) but let
# "Human Memory Capacity" through four days after "Human Brain Capacity";
# 0.75/0.60 refuses 24 (10%) and catches it. The extra eight it takes are all
# one template with a noun swapped — "Caffeine Content Revealed" after "Sugar
# Content Revealed", "Longest Rivers On Earth" after "Tallest Trees on Earth" —
# which is exactly the pattern being penalised, even when the underlying data
# is genuinely different. The error costs are not symmetric: a false refusal
# costs one video from a queue that holds hundreds, a false accept costs
# channel standing.
_DUP_SEQ = 0.75
_DUP_JACCARD = 0.60
_DUP_STOP = frozenset(
    "the a an of in on to for is are and or its it how why what when we you "
    "your our new most all than that this has have was were be been at by "
    "with from about into over under more less just now still".split())


def _sig_words(title: str) -> set:
    words = re.sub(r"[^a-z0-9 ]", " ", (title or "").lower()).split()
    return {w for w in words if w not in _DUP_STOP and len(w) > 2}


def duplicate_of(title: str, posted_titles) -> str | None:
    """The already-posted title this one repeats, or None.

    Returns the OTHER title rather than a bool so the hold can name it — a
    refusal that says which video it collided with is actionable; one that says
    "too similar" sends someone reading the whole log.
    """
    if not (title or "").strip():
        return None
    mine = _sig_words(title)
    for other in posted_titles:
        if not (other or "").strip():
            continue
        if difflib.SequenceMatcher(None, title.lower(),
                                   other.lower()).ratio() >= _DUP_SEQ:
            return other
        theirs = _sig_words(other)
        union = mine | theirs
        if union and len(mine & theirs) / len(union) >= _DUP_JACCARD:
            return other
    return None


# Outcomes a run can have. A gate HOLD is the fail-closed review working as
# designed; it is not a fault and must never be reported as one.
HELD_REASONS = {"editorial_hold", "showrunner_block", "duplicate_hold"}


def classify_results(results: list[dict]) -> dict:
    """Split a run's per-story results into posted / held / faults / dry.

    This exists as a named function because the exit code used to be
    `0 if ok == len(results) else 1`: one story held by the review gate turned
    a three-video day red, so every run looked the same and a genuinely dead
    run (2026-09-04, runner reclaimed mid-job) was indistinguishable from a
    healthy one. The rule is now explicit and tested.
    """
    posted = [r for r in results
              if r.get("ok") and str(r.get("url", "")).startswith("http")]
    held = [r for r in results
            if not r.get("ok") and r.get("error") in HELD_REASONS]
    faults = [r for r in results
              if not r.get("ok") and r.get("error") not in HELD_REASONS]
    dry = [r for r in results if r.get("ok") and r not in posted]
    return {"posted": posted, "held": held, "faults": faults, "dry": dry}


def exit_code_for(buckets: dict) -> int:
    """1 means SOMETHING IS BROKEN. Nothing else."""
    if buckets["faults"]:
        return 1
    if buckets["posted"] or buckets["held"] or buckets["dry"]:
        return 0
    # Nothing uploaded, nothing held, nothing rendered: the run did nothing and
    # cannot say why. That is a fault.
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="*",
                    help="story slugs to post (default: every story in config)")
    ap.add_argument("--channel", default="explainer",
                    help="channel slug for token routing: 'explainer' reads "
                         "YOUTUBE_TOKEN_JSON_EXPLAINER (default); '' uses the "
                         "original YOUTUBE_TOKEN_JSON")
    ap.add_argument("--check-channel", action="store_true",
                    help="print which channel the token maps to and exit "
                         "(read-only, posts nothing)")
    ap.add_argument("--dry-run", action="store_true",
                    help="render but do not upload")
    ap.add_argument("--publish", action="store_true",
                    help="EXPLICITLY opt in to uploading. Without this (and "
                         "without PUBLISH_ENABLED=1) publishing is FROZEN: the "
                         "pipeline renders + reviews but never uploads. The "
                         "channel's fail-closed kill-switch.")
    ap.add_argument("--force", action="store_true",
                    help="re-post even if the slug is in the posted log")
    ap.add_argument("--every-hours", type=float, default=0.0,
                    help="schedule uploads this many hours apart (private until "
                         "publishAt); 0 = publish immediately")
    ap.add_argument("--start-in-hours", type=float, default=1.0,
                    help="when scheduling, how long from now the first one posts")
    ap.add_argument("--config", type=Path, default=CONFIG,
                    help="story config JSON (default: data_learning/"
                         "niche.config.json; sibling channels pass their own)")
    ap.add_argument("--log", type=Path, default=LOG_PATH,
                    help="posted-log JSON (default: state/"
                         "explainer_posted_log.json)")
    ap.add_argument("--repair", type=int, default=2,
                    help="on a showrunner BLOCK, restructure the weakest scene "
                         "and re-render this many times before giving up "
                         "(0 = never repair)")
    ap.add_argument("--max-per-run", type=int, default=0,
                    help="render at most N new videos this run (0 = all); the "
                         "rest wait for the next run. Guards the CI job cap now "
                         "that each 3D render is slow.")
    args = ap.parse_args()

    if args.check_channel:
        from shared.uploaders import YouTubeUploader
        me = YouTubeUploader(channel=args.channel).whoami()
        print(f"token maps to channel: title={me['title']!r} "
              f"handle={me['handle']!r} id={me['id']}")
        return 0

    cfg = json.loads(args.config.read_text())
    stories = {s["slug"]: s for s in cfg.get("stories", [])}
    slugs = args.slugs or list(stories)
    # ROTATE PAST THE STICKY LOSERS. The default candidate list is config
    # order, and --max-per-run renders only its first N unposted entries —
    # THE SAME N EVERY RUN until one posts. On 2026-08-15 the four lead
    # candidates scored 39-48, got re-rendered and re-blocked by three
    # consecutive runs, and the channel posted NOTHING while ~40 untried
    # stories waited behind them. A story the showrunner blocked in the
    # last day is sent to the BACK of the queue — never skipped (the
    # standing ruling: it goes through and tries again; if everything was
    # recently blocked the order degrades to exactly the old behaviour),
    # just no longer allowed to starve stories that have never had a turn.
    if not args.slugs:
        recently_blocked = _recent_gate_blocks()
        if recently_blocked:
            slugs.sort(key=lambda s: s in recently_blocked)  # stable sort
            print(f"[post_stories] {len(recently_blocked)} recently-blocked "
                  f"stor(y/ies) rotated to the back of the queue", flush=True)
    unknown = [s for s in slugs if s not in stories]
    if unknown:
        print(f"unknown slugs: {unknown}\navailable: {list(stories)}",
              file=sys.stderr)
        return 2

    log = _load_log(args.log)
    results = []
    uploader = None
    # `posted` gates the SLATE (what the registry asks for); `attempts`
    # bounds the cost. A block costs a story, never the day — see the loop.
    posted = 0
    attempts = 0
    # Three tries per slot before the run gives up. Wide enough to survive a
    # bad patch in the queue (this morning four in a row were held), narrow
    # enough that a systematically broken render does not walk the catalogue.
    attempt_cap = max(6, (args.max_per_run or 4) * 3)
    when = datetime.now(timezone.utc) + timedelta(hours=args.start_in_hours)

    # PER-DAY cap, not just per-RUN. `--max-per-run` alone cannot hold the
    # registry's daily count when the workflow fires twice in a day (a cron
    # AND a chained trigger, or a manual re-run after a partial): the posted
    # log dedupes SLUGS, so a second run simply posts the NEXT four stories
    # — different videos, same day, 8/4. Count what already went out today
    # and shrink this run's budget by it. `--force` re-posts are exempt: an
    # operator explicitly re-shipping a fixed video is not a scheduling bug.
    if args.max_per_run and not args.force:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        posted_today = sum(
            1 for e in log["posted"].values()
            if str(e.get("at", "")).startswith(today))
        if posted_today:
            budget = max(0, args.max_per_run - posted_today)
            print(f"[post_stories] {posted_today} already posted today — "
                  f"this run's budget is {budget} (per-day cap "
                  f"{args.max_per_run})", flush=True)
            args.max_per_run = budget
            if budget == 0:
                print("[post_stories] the day is full — nothing to do",
                      flush=True)
                return 0

    # FAIL-CLOSED publish control. Publishing is FROZEN unless explicitly opted
    # into; nothing here can silently upload. See scripts/editorial_gate.py.
    from scripts import editorial_gate as _eg
    frozen = not args.dry_run and not _eg.publish_enabled(args.publish)
    if frozen:
        print("[post_stories] PUBLISH FROZEN — rendering + reviewing only, NOT "
              "uploading. Pass --publish (or set PUBLISH_ENABLED=1) to upload.",
              flush=True)

    for slug in slugs:
        sc = stories[slug]
        if not args.force and slug in log["posted"]:
            _rec = log["posted"][slug]
            if _rec.get("state") == "uploading" or _rec.get("url") is None:
                # A CLAIM WITH NO URL. Some previous run reached the upload
                # call and never came back to record the result — the video
                # may well be live. Re-posting is the one action that cannot
                # be undone, so this stays held until a person looks.
                print(f"[{slug}] HELD — a previous run claimed this slot at "
                      f"{_rec.get('claimed_at')} and never confirmed a URL. "
                      f"The video may already be on the channel. Check it, "
                      f"then either delete it or add the URL to the log; "
                      f"--force overrides.")
                results.append({"slug": slug, "ok": False,
                                "error": "unconfirmed_upload_hold"})
                continue
            print(f"[{slug}] already posted -> {_rec.get('url')}, "
                  f"skipping (use --force to repost)")
            continue

        # NEAR-DUPLICATE OF SOMETHING ALREADY UP. Checked before the render
        # budget and before the editorial gate: it costs nothing, it can never
        # become un-true later in the run, and a repeat is the one refusal that
        # protects the CHANNEL rather than the video.
        if not args.force:
            _dup = duplicate_of(
                sc.get("title") or slug,
                [e.get("title") for e in log["posted"].values()])
            if _dup:
                print(f"[{slug}] NOT POSTING — too close to a video already "
                      f"up: {_dup!r}. The story is fine; the PACKAGING "
                      f"repeats. Retitle it and it ships.")
                results.append({"slug": slug, "ok": False,
                                "error": "duplicate_hold", "duplicate_of": _dup})
                continue

        # Check the run's render budget FIRST — before the editorial gate.
        # `pre_render_verdict` is an LLM call (rate-limited on the free Groq
        # tier); running it on every backlog story ahead of this check burns
        # the whole run's rate-limit budget reviewing stories that get
        # deferred anyway, and starves the ones that would actually render
        # (see the 2026-08-06/07 explainer.yml failures: "done: 0/5 ok"
        # after dozens of "[groq] 429 rate-limited" retries). Deferred
        # stories still get reviewed — on the run where they're actually up.
        # THE SLATE COUNTS WHAT POSTED, NOT WHAT WAS ATTEMPTED.
        #
        # Operator, 2026-09-09: "the gates can block stuff but then we try
        # again — no, never posting."
        #
        # `rendered` was incremented BEFORE the render and before the
        # showrunner, so a BLOCK consumed a slot exactly as if it had posted.
        # That morning's run rendered four stories, the gate held all four,
        # the budget hit zero, and all 79 remaining stories in the queue
        # printed "deferred to next run". The channel went dark for a day
        # with a full queue and a working pipeline — the gates were right
        # every time and it still cost the whole slate.
        #
        # A block costs a STORY. It must never cost the day. So the slate is
        # gated on `posted`, and a separate, larger cap bounds the ATTEMPTS
        # so a systematically broken run still stops instead of grinding
        # through the whole catalogue.
        if args.max_per_run and posted >= args.max_per_run:
            print(f"[{slug}] slate full ({posted}/{args.max_per_run} posted)")
            continue
        if attempts >= attempt_cap:
            print(f"[{slug}] deferred to next run — {attempts} attempts made "
                  f"for {posted} post(s), attempt cap {attempt_cap} reached",
                  flush=True)
            continue

        # PRE-RENDER editorial gate (#2 real data, #3 premise bar). A story that
        # can never publish — synthetic numbers, or a searchable-noun premise —
        # is HELD before we spend a render on it. Previews (--dry-run) still
        # render so the result can be eyeballed, but the verdict is printed.
        pre = _eg.pre_render_verdict(sc)
        if not pre["ok"]:
            print(f"[{slug}] EDITORIAL HOLD (pre-render): "
                  + "; ".join(pre["reasons"][:8]), flush=True)
            if not args.dry_run:
                results.append({"slug": slug, "ok": False,
                                "error": "editorial_hold",
                                "reasons": pre["reasons"]})
                continue
        attempts += 1
        out = OUTPUT_DIR / f"story_{slug}.mp4"
        print(f"[{slug}] rendering -> {out}", flush=True)
        from data_learning import studio_render       # lazy: needs Pillow etc.
        studio_render.render(slug, out, config_path=args.config)

        # SHOWRUNNER gate  (see the repair loop below: a BLOCK is a diagnosis
        # to act on, not the end of the story) — the editor with a veto. A headless Claude actually
        # WATCHES the finished video (extracts frames + reads the transcript)
        # and grades it against docs/DIRECTOR.md. Its verdict is authoritative.
        #
        # Fail direction depends on intent: on a PUBLISH run the gate fails
        # CLOSED — if the reviewer can't run (no key, API/ffmpeg error, timeout)
        # we do NOT know the video is good, so we HOLD it. Only a preview/frozen
        # run fails open (so iteration isn't blocked by infra). "If this is not
        # clearly good, it does not publish."
        will_upload = not args.dry_run and not frozen
        ctx = {"slug": slug, "title": sc.get("title"),
               "hook": sc.get("hook"), "closing": sc.get("closing"),
               "segments": [s.get("say") or s.get("topic")
                            for s in sc.get("segments", [])][:8]}
        # The policy — fail CLOSED on a publish run, SHOWRUNNER=off refused on
        # a publish run, a BLOCK is sovereign — moved to
        # `shared/showrunner_gate.py` so the trending channel (6 videos a day,
        # previously unwatched) runs the SAME gate rather than a second copy
        # of it. See docs/SYSTEM_AUDIT.md §D.
        from shared import showrunner_gate as _gate
        gate = _gate.run(out, slug=slug, context=ctx, will_upload=will_upload)
        _gate.log(gate, slug)
        blocked = gate["blocked"]
        verdict = gate["verdict"]

        # ---- BOUNDED SELF-REPAIR ------------------------------------------
        # The gate's verdict names the weakest scene and why. Rather than drop
        # the video there, restructure that ONE scene (scene_repair picks a
        # claim-compatible depiction, objective-gated then vision-ranked),
        # re-render, and let the gate judge again. The gate still decides —
        # this only gives it a better cut to judge. Bounded: a cut only ever
        # uploads on a SHIP verdict, so a repair that lands worse simply keeps
        # the video held, exactly as before.
        repairs = 0
        while (blocked and repairs < args.repair
               and (verdict or {}).get("score") is not None):
            repairs += 1
            try:
                from scripts import scene_repair as _sr2
                plan = _sr2.propose(slug, verdict, apply_plan=True)
                print(f"[{slug}] repair {repairs}/{args.repair}: seg "
                      f"{plan.get('seg')} -> {plan.get('chosen')}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[{slug}] repair {repairs} could not plan a fix: "
                      f"{str(e)[:120]}", flush=True)
                break
            # KEEP THE BEST CUT, NOT THE LAST ONE.
            #
            # This re-rendered over `out` and replaced the verdict
            # unconditionally, so a repair that landed WORSE threw away a
            # better video — and the docstring above ("a repair that lands
            # worse simply keeps the video held, exactly as before") was
            # describing behaviour the code did not have. Measured on the
            # 2026-08-12 explainer slate, where repair moved:
            #
            #     urban   53 -> 48      hydro   48 -> 39
            #     hunger  44 -> 35      macao   56 -> 69
            #
            # three of four downhill, each one discarding the better cut.
            # The gate still decides everything; we just stop throwing away
            # its best judgment. A repair only sticks if it scores higher.
            import shutil as _sh
            _prev_score = (verdict or {}).get("score")
            _keep = out.with_suffix(".prerepair.mp4")
            try:
                _sh.copy2(out, _keep)
            except Exception:                        # noqa: BLE001
                _keep = None
            studio_render.render(slug, out, config_path=args.config)
            new_gate = _gate.run(out, slug=slug, context=ctx,
                                 will_upload=will_upload)
            _new_score = (new_gate.get("verdict") or {}).get("score")
            _better = (_new_score is not None and _prev_score is not None
                       and _new_score > _prev_score)
            if _better or _prev_score is None:
                gate, blocked = new_gate, new_gate["blocked"]
                verdict = new_gate["verdict"]
                print(f"[{slug}] after repair {repairs}: "
                      f"{'BLOCK' if blocked else 'SHIP'} "
                      f"score={_new_score} — "
                      f"{verdict.get('one_line') or gate['reason']}",
                      flush=True)
            else:
                print(f"[{slug}] repair {repairs} scored {_new_score} vs "
                      f"{_prev_score} — REVERTING to the better cut",
                      flush=True)
                if _keep and _keep.exists():
                    _sh.move(str(_keep), str(out))
                    _gate.log(gate, slug)      # re-assert the kept verdict
            if _keep and Path(_keep).exists():
                Path(_keep).unlink(missing_ok=True)

        if args.dry_run:
            print(f"[{slug}] dry-run: rendered, not uploading")
            results.append({"slug": slug, "ok": True,
                            "url": "(dry-run)" if not blocked
                                   else "(dry-run, showrunner BLOCK)"})
            posted += 1        # a preview fills its slot; nothing is uploaded
            continue

        if blocked:
            print(f"[{slug}] NOT POSTING — held by the review gate as not up to "
                  f"standard. See {out.name}.showrunner.json.", flush=True)
            results.append({"slug": slug, "ok": False,
                            "error": "showrunner_block"})
            continue

        if frozen:
            print(f"[{slug}] rendered + reviewed OK, but PUBLISH FROZEN — not "
                  f"uploading. Re-run with --publish to release.", flush=True)
            results.append({"slug": slug, "ok": True, "url": "(frozen)"})
            posted += 1        # it cleared every gate; publishing is frozen
            continue

        publish_at = None
        if args.every_hours > 0:
            publish_at = when.replace(microsecond=0).isoformat().replace(
                "+00:00", "Z")
            when += timedelta(hours=args.every_hours)

        if uploader is None:                 # lazy import → clear error if deps
            from shared.uploaders import YouTubeUploader
            uploader = YouTubeUploader(channel=args.channel)
        print(f"[{slug}] uploading"
              + (f" (scheduled {publish_at})" if publish_at else " (public now)"),
              flush=True)
        # studio_render writes a title-aligned thumbnail next to the mp4.
        thumb = out.with_suffix(".jpg")
        # Localized titles/descriptions (best-effort; English always ships).
        try:
            from shared.localize import localize_meta
            localizations = localize_meta(
                sc.get("title", slug), _human_body(sc), _desc_suffix(sc))
        except Exception as e:  # noqa: BLE001 — never let i18n block a post
            print(f"[{slug}] localization skipped: {e}", flush=True)
            localizations = {}
        # Upload is the one step that legitimately fails mid-batch (YouTube's
        # daily upload cap, a transient 5xx, a single bad video). Don't let one
        # failure abort the rest — record it and move on. The one exception is
        # the daily upload-limit: once hit, EVERY remaining upload will fail the
        # same way, so stop early rather than burn render time on videos that
        # physically can't post until the cap resets.
        # CLAIM THE SLOT BEFORE UPLOADING.
        #
        # The record used to be written AFTER `upload()` returned. The video
        # is live on YouTube the moment the API accepts it, so every failure
        # mode in between — a read timeout on the response, a connection
        # reset, a retry inside the client, the runner being reclaimed —
        # leaves a video on the channel that NOTHING recorded. The next run
        # sees the slug as un-posted and uploads it again.
        #
        # That is what happened on 2026-09-07: two of the same video on the
        # data channel, one entry in the log. The old comment here closed the
        # window between one upload and the NEXT RENDER; it never closed the
        # window around the upload itself, which is the only one that matters.
        #
        # An orphan is strictly better than a duplicate: a claim with no URL
        # says "check this slug by hand", and a duplicate says nothing at all
        # until a person notices it on the channel. `run_third.py` has claimed
        # its slot this way since 2026-08; this brings the explainer in line.
        _claim = {
            "claimed_at": datetime.now(timezone.utc).isoformat(),
            "title": sc.get("title"), "publish_at": publish_at,
            "url": None, "state": "uploading",
        }
        log["posted"][slug] = _claim
        log.setdefault("uploads", []).append(dict(_claim, slug=slug))
        _save_log(log, args.log)
        _persist_posted_log_now(args.log, slug, why="claim upload slot")
        try:
            res = uploader.upload(
                file_path=out,
                title=sc.get("title", slug)[:100],
                description=_description(sc),
                tags=_merged_tags(sc),
                publish_at=publish_at,
                thumbnail=thumb if thumb.exists() else None,
                localizations=localizations,
            )
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            limit_hit = ("uploadLimitExceeded" in msg
                         or "exceeded the number of videos" in msg)
            print(f"[{slug}] UPLOAD FAILED: {msg}", flush=True)
            # Release the claim ONLY for errors that cannot have put a video
            # on the channel. A timeout or a reset may well have — the upload
            # is accepted server-side before the response comes back — so
            # those keep the claim and the slug stays held until a person
            # looks. Refusing to post again is the safe side of this.
            _certain = ("uploadLimitExceeded" in msg
                        or "exceeded the number of videos" in msg
                        or "quotaExceeded" in msg
                        or "Unauthorized" in msg or "401" in msg
                        or "403" in msg)
            if _certain:
                log["posted"].pop(slug, None)
                log["uploads"] = [u for u in (log.get("uploads") or [])
                                  if not (u.get("slug") == slug
                                          and u.get("url") is None)]
                _save_log(log, args.log)
            else:
                print(f"[{slug}] the claim STAYS — this error can leave a "
                      f"video live, and a duplicate is worse than a gap. "
                      f"Check the channel for {slug!r}.", flush=True)
            results.append({"slug": slug, "ok": False, "error": msg})
            if limit_hit:
                print("[post_stories] YouTube daily upload cap reached — "
                      "stopping; remaining stories will retry next run.",
                      flush=True)
                break
            continue
        url = getattr(res, "url", None) or str(res)
        print(f"[{slug}] uploaded -> {url}", flush=True)
        log["posted"][slug] = {
            "url": url, "title": sc.get("title"),
            "at": datetime.now(timezone.utc).isoformat(),
            "publish_at": publish_at,
            "state": "posted",
            # WHAT IT WAS, not just that it happened — see _creative_facts.
            **_creative_facts(slug, sc, out, verdict),
        }
        # EVERY upload, append-only. `posted` is keyed by SLUG, so a second
        # upload of the same slug overwrites the first and the log cannot even
        # REPRESENT the duplicate — which is why 2026-09-07 read as one upload
        # while two were live. This list can, so a duplicate is detectable
        # instead of invisible.
        for _u in reversed(log.get("uploads") or []):
            if _u.get("slug") == slug and _u.get("url") is None:
                _u["url"] = url
                _u["state"] = "posted"
                _u["at"] = log["posted"][slug]["at"]
                break
        _save_log(log, args.log)
        # Durable BEFORE the next render starts — a reclaimed runner between
        # here and the end of the run would otherwise cost a duplicate upload.
        _persist_posted_log_now(args.log, slug)
        posted += 1                     # the slate counts THIS, not attempts
        results.append({"slug": slug, "ok": True, "url": url})

    # ------------------------------------------------------------------ #
    # HONEST OUTCOME. This used to be `0 if ok == len(results) else 1`, so a
    # run that uploaded three videos and had a fourth HELD BY THE GATE exited
    # red — identical, at a glance, to a run that crashed in the first minute.
    # Every explainer run was red for days; on 2026-09-04 a run genuinely died
    # (the GitHub runner was reclaimed mid-job) and nothing distinguished it
    # from the healthy ones.
    #
    # A gate hold is the system WORKING — it is the whole point of the
    # fail-closed review. It is not a fault and must not be reported as one.
    # The exit code now means "something is broken", nothing else. Whether the
    # channel actually posted today is a separate question, asked separately
    # (see the workflow's day-level check), because a quiet day and a broken
    # day need different reactions.
    # ------------------------------------------------------------------ #
    _b = classify_results(results)
    posted, held, faults, dry = (_b["posted"], _b["held"],
                                 _b["faults"], _b["dry"])

    print(f"\ndone: {len(posted)} posted, {len(held)} held by the gate, "
          f"{len(faults)} faults"
          + (f", {len(dry)} dry-run/frozen" if dry else ""))
    for r in held:
        print(f"   held  {r['slug']}: {r.get('error')}")
    for r in faults:
        print(f"   FAULT {r['slug']}: {str(r.get('error'))[:160]}")

    # GitHub annotations + a run summary, so the Actions page tells the truth
    # without anyone opening the log.
    import os as _os
    if _os.environ.get("GITHUB_ACTIONS"):
        for r in faults:
            print(f"::error title=post-failed::{r['slug']}: "
                  f"{str(r.get('error'))[:200]}")
        if held and not posted:
            print("::warning title=all-held::the review gate held every story "
                  "this run — nothing published, nothing broken")
        summary = _os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as fh:
                fh.write(f"### explainer: {len(posted)} posted, {len(held)} "
                         f"held, {len(faults)} faults\n\n")
                for r in posted:
                    fh.write(f"- posted **{r['slug']}** — {r['url']}\n")
                for r in held:
                    fh.write(f"- held `{r['slug']}` ({r.get('error')})\n")
                for r in faults:
                    fh.write(f"- **FAULT** `{r['slug']}` — "
                             f"{str(r.get('error'))[:160]}\n")

    return exit_code_for(_b)


if __name__ == "__main__":
    sys.exit(main())
