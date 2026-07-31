"""The one-pass exchange bundle — everything ChatGPT needs, in one artifact.

Phase A (4:30) writes ONE bundle per day containing the day's scripts, the
media we actually found, the judge's verdict on every shot, and the resulting
gap requests. ChatGPT answers all of it in a single pass: punched-up scripts
plus generated images/animations. Then Phase B renders once, with everything
final.

Why one bundle instead of separate script and media requests: the punch-up is
better when the writer can see what will be on screen, and media/line pairings
cannot drift if the script and the visuals are decided in the same breath.

    from shared import exchange_bundle as xb
    xb.write_bundle(date, packages, judge_reports)   # Phase A
    resp = xb.read_response(date)                     # Phase B
    xb.mark_ready(date)                               # Phase A signal
    xb.is_done(date)                                  # Phase B trigger check

Layout (all small JSON — image BYTES go to Drive, never to git):

    exchange/bundles/<date>/bundle.json      we write  (the ask)
    exchange/bundles/<date>/READY            we write  (Phase A finished)
    exchange/bundles/<date>/response.json    ChatGPT writes (scripts + pointers)
    exchange/bundles/<date>/DONE             ChatGPT writes (fires Phase B)

Never raises; every reader returns None/{} on trouble so a malformed bundle
degrades to "no ChatGPT help today" rather than breaking a run.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from shared import media_checkpoint as mc
from shared.fsutil import atomic_write_json

ROOT = Path(__file__).resolve().parent.parent
BUNDLE_ROOT = ROOT / "exchange" / "bundles"
SCHEMA = "chatgpt-exchange-bundle/v1"

# How many of the day's gaps may be requested as ANIMATION rather than a
# still. 0 = stills only (default until animation is proven on a channel).
ANIM_BUDGET_ENV = "CHATGPT_ANIM_BUDGET"
# Hard cap on requests per day, so one bad authoring night cannot ask for 200
# images and blow the task's budget.
MAX_REQUESTS_ENV = "CHATGPT_MAX_REQUESTS"
DEFAULT_MAX_REQUESTS = 24


def bundle_dir(date: str) -> Path:
    return BUNDLE_ROOT / str(date)


def request_key(slug: str, shot_index: int, prompt: str) -> str:
    """Stable, content-addressed id: the same subject asked twice reuses one
    generated image instead of burning a second generation."""
    h = hashlib.sha1(f"{slug}|{shot_index}|{prompt}".encode()).hexdigest()[:12]
    return f"{slug}-s{shot_index}-{h}"


def _anim_budget() -> int:
    try:
        return max(0, int(os.environ.get(ANIM_BUDGET_ENV, "0")))
    except Exception:
        return 0


def _max_requests() -> int:
    try:
        return max(1, int(os.environ.get(MAX_REQUESTS_ENV,
                                        str(DEFAULT_MAX_REQUESTS))))
    except Exception:
        return DEFAULT_MAX_REQUESTS


def build_bundle(date: str, packages: list[dict],
                 judge_reports: list[dict],
                 authoring_request: dict | None = None,
                 channel_requests: dict | None = None) -> dict:
    """Assemble the day's ask. Pure function — easy to test, no IO.

    `authoring_request` is the AUTHORING TAKEOVER brief (see
    `shared/authoring_brief.py`): present only when the day came up short of
    packages, which means the Claude Routine did not run and the reserve bank
    could not cover it. When present the bundle's `mode` flips to `"author"`
    and ChatGPT writes the missing packages itself. Both jobs can be live at
    once — 2 authored packages still want their media judged and punched up
    while the other 4 get written from scratch."""
    by_slug = {r.get("slug"): r for r in (judge_reports or [])}
    anim_left = _anim_budget()
    cap = _max_requests()

    items, requests = [], []
    for pkg in packages or []:
        slug = pkg.get("slug")
        report = by_slug.get(slug) or {}
        shots = pkg.get("shots") or []

        # Worst-first, so the cap spends itself on the weakest shots.
        gaps = sorted(report.get("gaps") or [],
                      key=lambda g: (g.get("score", 0.0),
                                     0 if g.get("verdict") == "missing" else 1))
        pkg_requests = []
        for gap in gaps:
            if len(requests) >= cap:
                break
            idx = gap.get("shot_index", 0)
            prompt = gap.get("ai_prompt") or ""
            if not prompt:
                continue
            kind = "image"
            if anim_left > 0:
                kind, anim_left = "animation", anim_left - 1
            rid = request_key(slug, idx, prompt)
            req = {
                "request_id": rid,
                # Published BEFORE either worker starts, which is the whole
                # reason an orphaned upload is recoverable: a file can only be
                # found by name if the name was agreed on in advance.
                "safe_request_id": mc.safe_request_id(rid),
                "drive_filename": mc.deterministic_filename(
                    date, rid, "mp4" if kind == "animation" else "png"),
                "prompt_sha256": mc.prompt_sha256(prompt),
                "checkpoint_path": (
                    f"exchange/bundles/{date}/{mc.PROGRESS_DIRNAME}/"
                    f"{mc.safe_request_id(rid)}.json"),
                "slug": slug,
                "shot_index": idx,
                "kind": kind,
                "prompt_verbatim": prompt,
                "negative": ["text", "watermarks", "logos", "user interfaces",
                             "screenshots", "code", "charts"],
                "width": 1080,
                "height": 1920 if kind == "animation" else 1080,
                "why": gap.get("reasons") or [],
                "verdict": gap.get("verdict"),
            }
            if kind == "animation":
                req["animation"] = {
                    "duration_seconds": 2,
                    "preferred": "frames_png",
                    "frames": {"count": 24, "fps": 12,
                               "naming": "frame_0001.png … frame_0024.png"},
                    "note": ("Numbered PNG frames are preferred — we compose "
                             "them with ffmpeg. Animated SVG or a real video "
                             "file are both acceptable alternatives."),
                }
            pkg_requests.append(rid)
            requests.append(req)

        items.append({
            "slug": slug,
            "title": pkg.get("title"),
            "script": pkg.get("script"),
            "shots": [{"shot_index": i,
                       "phrase": s.get("phrase"),
                       "query": s.get("query"),
                       "has_media": bool(s.get("image_url")),
                       "verdict": next((v.get("verdict") for v in
                                        report.get("verdicts") or []
                                        if v.get("shot_index") == i), "unknown"),
                       } for i, s in enumerate(shots)],
            "media_health": report.get("counts") or {},
            "strong_fraction": report.get("strong_fraction"),
            "requested": pkg_requests,
        })

    bundle = {
        "schema": SCHEMA,
        "date": str(date),
        "status": "open",
        "mode": ("author" if (authoring_request or channel_requests)
                 else "punch_up"),
        "response_path": f"exchange/bundles/{date}/response.json",
        "done_marker": f"exchange/bundles/{date}/DONE",
        "counts": {"packages": len(items), "requests": len(requests),
                   "animations": sum(1 for r in requests
                                     if r["kind"] == "animation"),
                   "to_author": (authoring_request or {}).get("write", 0)},
        "packages": items,
        "requests": requests,
        # The two-worker contract, as data. Two scheduled tasks an hour apart
        # cannot see each other's context — only this repo — so the checkpoint
        # files under media-progress/ are their entire shared memory.
        "media_protocol": mc.protocol_block(date),
        "instructions": {
            "read_first": "exchange/README.md",
            "who_runs_what": {
                "media_worker_0600": (
                    "MEDIA ONLY. Work `requests` (and, on a takeover, the "
                    "shots of the packages you author). Upload under the "
                    "`drive_filename` each request carries, verify the bytes, "
                    "and write a checkpoint the moment each image verifies — "
                    "one file per request, not one batch at the end. NEVER "
                    "write response.json and NEVER write DONE."),
                "finalizer_0700": (
                    "RECOVER FIRST: read media-progress/ before generating "
                    "anything — a verified checkpoint is an image that "
                    "already exists, and re-making it both burns the budget "
                    "and produces a different picture than the one recorded. "
                    "Then fill the gaps, punch up the scripts, do the "
                    "explainer/curiosity work (even if trending is full), "
                    "write response.json, verify it reads back, and only then "
                    "commit DONE as a SECOND commit."),
                "only_done_renders": (
                    "DONE is the single trigger for Phase B. Nothing else "
                    "starts the render — not a response.json push, not a "
                    "checkpoint push, not a package push."),
            },
            "two_jobs": [
                "1. MEDIA — for every entry in `requests`, generate the asset "
                "from `prompt_verbatim` word for word, upload it to the shared "
                "Drive folder under the request's `drive_filename`, verify the "
                "bytes, write its checkpoint, and report a verified pointer "
                "(drive.file_id, download_url, image.sha256, image.bytes).",
                "2. PUNCH-UP — act as the script EDITOR for every entry in "
                "`packages`. For each one make an editorial decision: punch "
                "it up, or keep it as-is because it already lands. Keeping is "
                "a legitimate call — but it is a DECISION you state, never a "
                "default. Returning scripts unchanged with no stated reason "
                "is a failed run. See `punchup_mission`.",
            ],
            "punchup_mission": {
                "the_ask": (
                    "These scripts are RESEARCHED and TRUE but they are often "
                    "written flat — a chronological who-did-what recap with no "
                    "point of view and a limp ending. That flatness, not the "
                    "imagery, is the single biggest reason a finished video "
                    "falls flat. Your job is to keep every fact and change how "
                    "it LANDS. If a script already lands — hook under 5 words "
                    "ending ?/!, real voice, kicker naming the story — say so "
                    "and keep it. Do not change for the sake of changing."),
                "per_package_verdict": (
                    "Every entry in your response's `packages` array carries "
                    "either the rewritten fields, or `\"kept\": true` plus a "
                    "one-line `editor_note` saying why it already works "
                    "(e.g. 'hook already 4 words + ?, voice present, kicker "
                    "names Gary'). An entry with neither is a skipped job. "
                    "MAKE A REAL DECISION PER PACKAGE: `kept` means you read "
                    "it and it already lands, not that the guard looked "
                    "strict. Keeping the whole slate is a red flag, not "
                    "caution — the guard only protects numbers, entities and "
                    "beat structure, and wording is yours to improve freely "
                    "within them. If you keep more than half a slate, say "
                    "why in each `editor_note`."),
                "levity": (
                    "LAND A JOKE when the subject allows one. The doctrine "
                    "has said 'dry wit' for months and this channel has "
                    "never once made anyone laugh, because an adjective is "
                    "not an instruction. Concretely: ONE dry aside per "
                    "script, placed after the fact it reacts to, never in "
                    "the first two seconds. The shapes that work — state "
                    "the absurd fact flat then react in 3-6 words ('Top "
                    "speed: twelve.'); name the one mundane detail amid "
                    "chaos ('still holding the salad'); understate the "
                    "disaster ('This did not go well for the bees'). NEVER "
                    "puns, setup-punchline, exclamation marks, 'wait for "
                    "it', or telling the viewer it was funny. And NEVER on "
                    "a script involving death, injury, crime victims, war "
                    "or illness — those stay completely straight. If "
                    "nothing genuinely occurs to you, ship it straight; a "
                    "forced joke is worse than none. See shared/levity.py."),
                "house_voice": (
                    "A deadpan, slightly incredulous friend telling you the "
                    "most ridiculous thing they read today. Dry wit, real "
                    "reactions, second person, contractions. It is allowed to "
                    "be amused, skeptical or appalled. Accuracy is "
                    "non-negotiable; attitude is MANDATORY."),
                "do_this": [
                    "HOOK: first sentence must be <=5 words and end with ? or "
                    "! — 'A kangaroo did WHAT?', 'Why fire 30,000?'. This "
                    "earns the 3-second hold; it is the highest-leverage line "
                    "in the video.",
                    "KICKER: last sentence must end with ? and name something "
                    "specific from the story — never a generic 'what do you "
                    "think?'.",
                    "REACT to the absurd instead of reporting it ('Cool, "
                    "weird, whatever — until a SECOND call comes in.').",
                    "Short punchy sentences, varied rhythm. Fragments are "
                    "fine. Em-dashes and hard stops make the TTS breathe "
                    "instead of drone.",
                    "Cut corporate hedging ('officials confirmed', "
                    "'authorities stated') and filler procedure. Use the "
                    "strongest concrete verb available.",
                    "Front-load the most surprising fact. If the best number "
                    "is in sentence four, move it up — reordering facts is "
                    "encouraged, changing them is not.",
                    "Keep 110-140 spoken words.",
                ],
                "the_numbers_are_yours_to_use": (
                    "Every number, date and name in the script was verified by "
                    "the writer — treat them as AMMUNITION, not as landmines. "
                    "Land them harder, put them earlier, give them a beat "
                    "before the payoff. The only rule is that the value itself "
                    "must survive unchanged."),
                "why_the_rules_below_exist": (
                    "The constraints in `punchup_rules` exist ONLY to stop "
                    "invented facts, because an earlier audit found 519 of 546 "
                    "datasets on a sibling channel were LLM-fabricated. They "
                    "are not a hint that you should play it safe with the "
                    "WRITING. Rewrite boldly; just do not manufacture."),
                "worked_example": {
                    "before": ("A sinkhole opened in Marshall, North Carolina "
                               "on Tuesday. Officials confirmed severe storms "
                               "caused the collapse."),
                    "after": ("A sinkhole opened WHERE? Tuesday's storms tore "
                              "through Marshall, North Carolina — and the road "
                              "outside a funeral home just gave up."),
                    "note": ("Same place, same day, same cause. Nothing was "
                             "invented. Only the delivery changed."),
                },
            },
            "punchup_rules": [
                "These are GUARDRAILS on the facts, not a reason to leave the "
                "writing alone. Read `punchup_mission` first — the rewrite is "
                "expected.",
                "NEVER change or invent a number, percentage, money amount, "
                "date or year. Every figure in the original must appear "
                "unchanged in your rewrite.",
                "NEVER add or remove a named entity (person, company, place).",
                "NEVER change the shot count or any shot's `query` — the "
                "media is already chosen against those.",
                "Stay within roughly 0.5x-1.8x the original word count.",
                "A rewrite that breaks any of these is rejected mechanically "
                "and the original ships, so the work is wasted.",
            ],
            "prompt_rules": [
                "You are reading a code repository. Do NOT let that leak into "
                "the imagery — never draw screenshots, terminals, editors, UI "
                "or code. The repo is where the instruction lives, never the "
                "subject.",
                "Use `prompt_verbatim` exactly; treat `negative` as exclusions.",
            ],
            "finish_with": (
                "Write exchange/bundles/<date>/response.json, then create "
                "exchange/bundles/<date>/DONE containing {\"date\": \"<date>\"}. "
                "The DONE marker is what triggers our render — write it LAST, "
                "and only after response.json is committed."),
            "honesty": (
                "If you cannot do something, say so in the response with the "
                "blocking step named. A fabricated pointer or an unverified "
                "hash is worse than an honest failure: our consumer "
                "recomputes every hash and rejects mismatches."),
        },
    }

    if channel_requests:
        # EVERY channel's ask in ONE file. The signal the operator asked for
        # is exactly this: if Claude worked, these are absent; if a channel
        # appears here, Claude left that channel nothing and ChatGPT is its
        # brain today. `authoring_request` stays as the trending alias so
        # nothing that already reads it breaks.
        bundle["authoring_requests"] = channel_requests
        bundle["counts"]["channels_needing_a_brain"] = len(channel_requests)

    if authoring_request or channel_requests:
        # TAKEOVER. Front of the bundle, and the two_jobs list is rewritten
        # so the authoring job cannot read as an optional extra bolted on
        # after the media/punch-up work.
        bundle["authoring_request"] = authoring_request
        if authoring_request:
            job_zero = (
                "0. AUTHOR THE DAY — READ `authoring_request` FIRST. The "
                "channel's own writing brain did not run today and the reserve "
                "bank could not cover it, so there is no slate. You are the "
                "brain: write the missing packages per the spec in "
                "`authoring_request.formats` and return them in this "
                "response's `authored` array. Without this the channel posts "
                "NOTHING today.")
        else:
            # TRENDING IS FULL, ANOTHER CHANNEL IS NOT. This branch exists
            # because the obvious reading of "six packages exist" is "nothing
            # to author", and that reading silently drops the explainer and
            # curiosity work — separate channels, separate asks, and a full
            # trending slate says nothing about either of them.
            job_zero = (
                "0. AUTHOR FOR THE OTHER CHANNELS — READ `authoring_requests` "
                "FIRST. Trending has its full slate today, but "
                + ", ".join(sorted(k for k in (channel_requests or {})
                                   if k != "trending"))
                + " do NOT: Claude left them nothing and you are their brain. "
                "A full trending slate is not permission to skip them.")
        bundle["instructions"]["two_jobs"] = (
            [job_zero] + [j for j in bundle["instructions"]["two_jobs"]])
        bundle["instructions"]["takeover_note"] = (
            "`packages` and `requests` cover whatever WAS authored before you "
            "— on a takeover day, usually nothing. YOU OWN THE WHOLE DAY: "
            "write the packages AND supply the media for every shot in them, "
            "in this one pass. Nothing downstream gets a second chance to ask "
            "you for anything — the next thing that runs is the renderer. "
            "Attach each shot's image to the shot itself as `media` (same "
            "Drive + sha256 pointer shape you use in the `media` array); see "
            "`authoring_request.media_contract`. Anything you leave without "
            "media we will try to fill from stock, which is the weaker "
            "outcome this exists to avoid.")
    return bundle


def write_bundle(date: str, packages: list[dict],
                 judge_reports: list[dict],
                 authoring_request: dict | None = None,
                 channel_requests: dict | None = None) -> Path | None:
    """Phase A: persist the day's bundle. Returns its path, or None."""
    try:
        bundle = build_bundle(date, packages, judge_reports,
                              authoring_request, channel_requests)
        d = bundle_dir(date)
        d.mkdir(parents=True, exist_ok=True)
        path = d / "bundle.json"
        atomic_write_json(path, bundle)
        return path
    except Exception:                                    # noqa: BLE001
        return None


def read_bundle(date: str) -> dict | None:
    try:
        return json.loads((bundle_dir(date) / "bundle.json").read_text())
    except Exception:                                    # noqa: BLE001
        return None


def mark_ready(date: str) -> Path | None:
    """Phase A signal: the ask is complete and committed."""
    try:
        d = bundle_dir(date)
        d.mkdir(parents=True, exist_ok=True)
        p = d / "READY"
        atomic_write_json(p, {"date": str(date), "phase": "a_complete"})
        return p
    except Exception:                                    # noqa: BLE001
        return None


def is_done(date: str) -> bool:
    """True once ChatGPT has written the DONE marker for THIS date. A marker
    for another day never fires this day's render."""
    try:
        p = bundle_dir(date) / "DONE"
        if not p.exists():
            return False
        try:
            payload = json.loads(p.read_text())
        except Exception:                                # noqa: BLE001
            return True          # marker present but unparseable — honor it
        stamped = str(payload.get("date") or "").strip()
        return (not stamped) or stamped == str(date)
    except Exception:                                    # noqa: BLE001
        return False


def read_response(date: str) -> dict | None:
    """Phase B: ChatGPT's answer, or None if absent/malformed."""
    try:
        return json.loads((bundle_dir(date) / "response.json").read_text())
    except Exception:                                    # noqa: BLE001
        return None


def response_index(response: dict | None) -> dict:
    """Normalize a response into {request_id: entry} and {slug: rewrite}."""
    media: dict[str, dict] = {}
    scripts: dict[str, dict] = {}
    if not isinstance(response, dict):
        return {"media": media, "scripts": scripts}
    for entry in response.get("media") or response.get("results") or []:
        rid = entry.get("request_id")
        if rid:
            media[str(rid)] = entry
    for entry in response.get("packages") or response.get("scripts") or []:
        slug = entry.get("slug")
        if slug:
            scripts[str(slug)] = entry
    return {"media": media, "scripts": scripts}
