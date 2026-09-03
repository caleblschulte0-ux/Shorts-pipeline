#!/usr/bin/env python3
"""Phase B — consume ChatGPT's answer, self-fill gaps, then render.

Triggered by ChatGPT committing `exchange/bundles/<date>/DONE` (with a
backstop cron so a no-show still ships the day). For each request in the
day's bundle it pulls the verified Drive media, pins it onto the shot, and
for anything unfulfilled runs a SELF-FILL pass so a missing ChatGPT never
costs us the day. Script punch-ups are applied only if they survive
`shared.punchup_guard` — facts and beat structure are non-negotiable.

    python scripts/exchange_phase_b.py --date 20260730 --channel trending
    python scripts/exchange_phase_b.py --date 20260730 --require-done
    python scripts/exchange_phase_b.py --date 20260730 --dry-run

Writes the updated packages in place (so the normal renderer picks them up)
and a per-day report at exchange/bundles/<date>/phase_b_report.json.

Exit 0 = ready to render. Exit 2 = no bundle / DONE required but absent.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import channel_registry as reg         # noqa: E402
from shared import exchange_bundle as xb           # noqa: E402
from shared import media_checkpoint as mc          # noqa: E402
from shared import punchup_guard                   # noqa: E402
from shared.fsutil import atomic_write_json        # noqa: E402

MEDIA_CACHE = ROOT / "cache" / "exchange"

# --------------------------------------------------------------------------
# The backstop window
# --------------------------------------------------------------------------
# GitHub crons are UTC. The ChatGPT finalizer is a LOCAL-time task at 7:00 AM
# America/Chicago, which is 12:00 UTC in summer (CDT) and 13:00 UTC in winter
# (CST) — it moves an hour twice a year and a fixed UTC cron does not.
#
# The old backstop sat at 12:45 UTC. In summer that is 7:45 Central, 45 minutes
# into the finalizer's run; in WINTER it is 6:45 Central, FIFTEEN MINUTES
# BEFORE THE FINALIZER EVEN STARTS. For half the year the backstop would have
# rendered an unfinished day — no punch-up, no authored packages, whatever
# media happened to have landed — and every workflow would have been green.
#
# Fixed by not trusting UTC at all: the workflow fires BOTH candidate hours and
# this gate decides in America/Chicago local time, which is correct in both
# halves of the year by construction. The backstop may only start once the
# finalizer has had its full window.
FINALIZER_HOUR_CENTRAL = 7
FINALIZER_WINDOW_MINUTES = 90        # 07:00 -> 08:30 Central, both seasons
# If response.json was written this recently and DONE has not landed yet, the
# finalizer is mid-commit (it commits the response, reads it back, THEN commits
# DONE). Starting on top of that reads a half-finished day.
FINALIZER_ACTIVE_MINUTES = 20
CENTRAL_TZ = "America/Chicago"


def backstop_status(date: str, now_utc=None) -> dict:
    """May a backstop run right now? Decided in Central time, never in UTC.

    Returns {ready, reason, local, earliest_local}. Fails OPEN on a broken
    clock or a missing tzdata: a backstop that never runs is how a no-show day
    ships nothing at all, which is the outcome the backstop exists to prevent.
    """
    from datetime import datetime, time, timedelta, timezone
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(CENTRAL_TZ)
    except Exception as exc:                             # noqa: BLE001
        return {"ready": True, "local": "?", "earliest_local": "?",
                "reason": f"no tzdata ({exc}) — proceeding rather than "
                          f"skipping the day"}

    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local = now.astimezone(tz)
    start = datetime.combine(local.date(),
                             time(FINALIZER_HOUR_CENTRAL, 0), tzinfo=tz)
    earliest = start + timedelta(minutes=FINALIZER_WINDOW_MINUTES)
    out = {"local": local.strftime("%Y-%m-%d %H:%M %Z"),
           "earliest_local": earliest.strftime("%H:%M %Z")}

    if local < earliest:
        out.update(ready=False, reason=(
            f"it is {out['local']} — the 07:00 Central finalizer has not had "
            f"its {FINALIZER_WINDOW_MINUTES}-minute window yet (earliest "
            f"{out['earliest_local']}). Rendering now would ship an "
            f"unfinished day."))
        return out

    d = xb.bundle_dir(date)
    resp, done = d / "response.json", d / "DONE"
    if resp.exists() and not done.exists():
        try:
            age = (now - datetime.fromtimestamp(resp.stat().st_mtime,
                                                tz=timezone.utc))
            if age < timedelta(minutes=FINALIZER_ACTIVE_MINUTES):
                out.update(ready=False, reason=(
                    f"response.json landed {int(age.total_seconds() / 60)} "
                    f"min ago and DONE has not — the finalizer is mid-commit. "
                    f"Deferring rather than reading a half-written day."))
                return out
        except Exception:                                # noqa: BLE001
            pass

    out.update(ready=True, reason=f"{out['local']} — the finalizer's window "
                                  f"closed at {out['earliest_local']}")
    return out


def fetch_media(request_id: str, entry: dict | None = None) -> Path | None:
    """Resolve one request's media to a verified local file.

    Takes the entry straight from the BUNDLE's response.json. An earlier
    version shelled out to fetch_exchange_media.py, which reads the older
    per-request `exchange/responses/<id>.json` layout — so on the bundle flow
    it found nothing, returned None, and Phase B silently self-filled over 23
    perfectly good ChatGPT images (2026-07-30: fulfilled=0, self_filled=24).
    The whole exchange delivered nothing while every workflow stayed green.

    Verification is not optional: SHA-256 against the producer's claim, a full
    pixel decode, and a placeholder check. A mismatch returns None so the
    caller self-fills rather than pinning a corrupt or substituted image.

    That same claim also gates reusing a file already on disk. Bundle
    request IDs are content-addressed from slug/shot/prompt (and an
    authored shot's ID from slug/shot alone) with NO DATE, so an identical
    ask on a later production day resolves to the same cache path even
    though the mutable Drive object behind it may since have changed. A
    cache hit used to be returned unconditionally, before the current
    entry's claimed hash was even read — so pin_verified_media would then
    stamp TODAY's Drive URL/hash onto the package as if today's bytes had
    been the ones downloaded and verified, when only yesterday's were. A
    cached file is now trusted only when it hashes to the CURRENT entry's
    claim; anything else — no current claim, or a hash that disagrees — is
    treated as no cache at all and re-fetched.
    """
    import hashlib
    import io
    import urllib.request

    valid_entry = (isinstance(entry, dict)
                   and entry.get("status") in ("fulfilled", "partial"))
    drive = (entry.get("drive") or {}) if valid_entry else {}
    img = (entry.get("image") or {}) if valid_entry else {}
    fid = (drive.get("file_id") or "").strip()
    claim = (img.get("sha256") or "").strip().lower()

    # Already on disk from a previous run — but only trust it against what
    # the CURRENT entry claims. See the docstring above for why the request
    # ID alone is not enough evidence.
    if valid_entry and claim:
        for ext in ("png", "jpg", "jpeg", "webp", "mp4"):
            p = MEDIA_CACHE / f"{request_id}.{ext}"
            if not (p.exists() and p.stat().st_size):
                continue
            try:
                cached_sha = hashlib.sha256(p.read_bytes()).hexdigest()
            except Exception as exc:                     # noqa: BLE001
                print(f"[phase-b] {request_id}: cached file unreadable "
                      f"({exc}) — refetching")
                continue
            if cached_sha == claim:
                return p
            print(f"[phase-b] {request_id}: cached file does not match "
                  f"today's claim (cached {cached_sha[:12]}…, claim "
                  f"{claim[:12]}…) — stale cache, refetching")

    if not valid_entry:
        return None

    urls = [u for u in (
        drive.get("download_url"),
        f"https://drive.google.com/uc?export=download&id={fid}" if fid else None,
        f"https://drive.usercontent.google.com/download?id={fid}"
        f"&export=download&confirm=t" if fid else None,
    ) if u]

    for url in urls:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "shorts-pipeline/exchange"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                blob = resp.read(32 * 1024 * 1024)
                ctype = resp.headers.get("Content-Type", "")
            # Drive serves an HTML permission page when a file is not
            # link-visible — never save that as an image.
            if b"<html" in blob[:2000].lower() or "text/html" in ctype:
                print(f"[phase-b] {request_id}: not link-visible (HTML page)")
                continue
            if not blob:
                continue

            got = hashlib.sha256(blob).hexdigest()
            if claim and got != claim:
                print(f"[phase-b] {request_id}: SHA MISMATCH "
                      f"(claimed {claim[:12]}…, got {got[:12]}…) — refusing")
                return None

            try:
                from PIL import Image
                im = Image.open(io.BytesIO(blob))
                im.load()
                colors = im.convert("RGB").getcolors(maxcolors=65536)
                if colors is not None and len(colors) <= 8:
                    print(f"[phase-b] {request_id}: {len(colors)}-colour "
                          f"placeholder — refusing")
                    return None
                ext = (im.format or "png").lower().replace("jpeg", "jpg")
            except Exception as exc:                     # noqa: BLE001
                print(f"[phase-b] {request_id}: not a decodable image ({exc})")
                return None

            MEDIA_CACHE.mkdir(parents=True, exist_ok=True)
            out = MEDIA_CACHE / f"{request_id}.{ext}"
            tmp = out.with_suffix(out.suffix + ".part")
            tmp.write_bytes(blob)
            os.replace(tmp, out)
            print(f"[phase-b] {request_id}: pinned {len(blob):,}B "
                  f"{ext} from ChatGPT (sha verified)")
            return out
        except Exception as exc:                         # noqa: BLE001
            print(f"[phase-b] {request_id}: {type(exc).__name__}: "
                  f"{str(exc)[:70]}")
    return None


def pin_verified_media(shot: dict, entry: dict, *, origin: str) -> None:
    """Persist a verified pointer in a form a *different runner* can use.

    Phase B and the renderer are separate GitHub Actions jobs.  The old code
    committed ``/home/runner/.../cache/exchange/foo.png`` into the package;
    that path only existed on Phase B's disposable VM, so the render job
    silently lost every ChatGPT image.  ``fetch_media`` still verifies the
    exact Drive object locally first, but the package now retains the public
    download URL plus its identity/hash instead of the temporary filename.

    Added by ChatGPT on 2026-08-02 after the first takeover production run
    exposed the cross-runner handoff bug.  Reverting this function and its two
    call sites restores the previous behaviour in one commit.
    """
    drive = entry.get("drive") or {}
    image = entry.get("image") or {}
    fid = str(drive.get("file_id") or "").strip()
    url = str(drive.get("download_url") or "").strip()
    if not url and fid:
        url = f"https://drive.google.com/uc?export=download&id={fid}"
    if not url:
        raise ValueError("verified media has no durable Drive URL")
    shot["image_url"] = url
    shot["media_origin"] = origin
    shot["media_file_id"] = fid
    shot["media_sha256"] = str(image.get("sha256") or "").strip().lower()
    shot["media_bytes"] = image.get("bytes")


# Renderers keep funnel candidates at score >= 0.4. Self-fill is the
# gloves-off pass: accept weaker-but-real media rather than ship nothing.
SELF_FILL_FLOOR = 0.15


def self_fill(pkg: dict, shot_index: int) -> str | None:
    """Gloves-off pass for a gap ChatGPT did not fill (Policy A).

    Three lanes, widest-net first: the 22-provider funnel at a lowered score
    floor, then the entity resolver, then the topic-image finder. Never
    raises; None means the shot renders with whatever it already had.
    """
    shots = pkg.get("shots") or []
    if shot_index >= len(shots):
        return None
    shot = shots[shot_index]
    entity = (shot.get("query") or shot.get("phrase") or "").strip()
    if not entity:
        return None
    angle = (pkg.get("title") or "").strip() or entity
    slug = str(pkg.get("slug") or "")

    # Lane 1 — the full funnel. Signature is search(story_angle, entities, ...)
    # and it returns Candidate dataclasses (.url/.score), not dicts.
    try:
        from funnel import media_funnel
        cands = media_funnel.search(angle, [entity], story_slug=slug,
                                    verbose=False) or []
        ranked = sorted(cands, key=lambda c: getattr(c, "score", 0.0),
                        reverse=True)
        for c in ranked:
            url = getattr(c, "url", None)
            if url and getattr(c, "score", 0.0) >= SELF_FILL_FLOOR:
                print(f"[phase-b] self-fill lane=funnel shot={shot_index} "
                      f"score={getattr(c, 'score', 0):.2f}")
                return url
    except Exception as exc:                         # noqa: BLE001
        print(f"[phase-b] self-fill funnel lane failed: "
              f"{type(exc).__name__}: {str(exc)[:70]}")

    # Lane 2 — entity resolver (Wikipedia/Commons; keyless).
    try:
        from funnel import entity_media
        url = entity_media.resolve_entity_media(entity, context=angle)
        if url:
            print(f"[phase-b] self-fill lane=entity shot={shot_index}")
            return url
    except Exception:                                # noqa: BLE001
        pass

    # Lane 3 — topic image finder: search(topic, context) -> list[str]
    # (Wikipedia article images, Commons, Openverse; keyless). This draws
    # from the SAME sources lane 2 just fed through url_is_image() and
    # rejected every candidate from, so it must clear the identical trust
    # boundary — otherwise it is a side door back to the dead/HTML/non-image
    # URLs lane 2 already refused (entity_media.url_is_image's own docstring:
    # "the trust boundary for routine-supplied image URLs").
    try:
        from funnel import entity_media, topic_media
        urls = topic_media.search(entity, angle) or []
        for url in urls:
            if url and entity_media.url_is_image(url):
                print(f"[phase-b] self-fill lane=topic shot={shot_index}")
                return url
    except Exception:                                # noqa: BLE001
        pass

    return None


def cover_authored(pkg: dict, report: dict, *, no_self_fill: bool = False,
                   date: str = "", rejected: dict | None = None) -> None:
    """Find media for a package ChatGPT authored after Phase A had already
    run. Same two lanes Phase A and Phase B already use — entity resolution
    first, then the gloves-off self-fill for whatever is still bare — so a
    takeover slate is illustrated the same way a normal one is.

    Formats without `shots` (text_card, graph_race) need nothing here: the
    renderer sources their b-roll from `broll_query` and draws the chart."""
    shots = pkg.get("shots") or []
    if not shots:
        return
    slug = str(pkg.get("slug") or "")

    # ORDER MATTERS. `enrich_package` writes `image_url: None` onto shots it
    # cannot resolve, so it must run BEFORE ChatGPT's pointers are pinned —
    # run it after and it silently erases them. That exact shape of bug
    # (a later pass quietly overwriting good ChatGPT media) already cost this
    # pipeline 23 verified images on 2026-07-30 with every workflow green.
    try:
        from funnel import entity_media
        entity_media.enrich_package(pkg, verbose=False)
    except Exception as exc:                         # noqa: BLE001
        print(f"[phase-b] entity media unavailable for {slug} "
              f"({exc}) — self-fill only")

    # ChatGPT's OWN media WINS over anything the entity pass found. On a
    # takeover day it authored the script and generated the pictures in the
    # same pass — an image made for this exact line beats a generic entity
    # photo. Verified by the same code path as a normal-day request: SHA-256
    # against the claim, full pixel decode, placeholder check. A pointer that
    # fails any of those is dropped and the shot falls through to self-fill.
    for i, shot in enumerate(shots):
        pointer = shot.pop("media", None)
        if not isinstance(pointer, dict):
            continue
        # The id the media worker used at 06:00, recomputed here from the
        # package on disk. Derived from slug + shot index ONLY, so it survives
        # the punch-up rewording that a content-addressed key would not.
        rid = mc.authored_shot_request_id(slug, i)
        why = (rejected or {}).get(rid)
        if why:
            print(f"[phase-b] {slug} shot {i}: REFUSED ChatGPT media — "
                  + "; ".join(why[:2]))
            report["media"]["refused"] = report["media"].get("refused", 0) + 1
            continue
        local = fetch_media(rid, pointer)
        if local:
            # The audit trail must be able to tell a pointer the finalizer
            # actually declared from one rebuilt out of a checkpoint after
            # the response omitted it — a day repaired by recovery should
            # say so, not read as if the envelope had been fine all along.
            origin = ("chatgpt_authored_recovered"
                      if pointer.get("recovered_from_checkpoint")
                      else "chatgpt_authored")
            pin_verified_media(shot, pointer, origin=origin)
            report["media"]["fulfilled"] += 1
        else:
            print(f"[phase-b] {slug} shot {i}: ChatGPT media pointer did not "
                  f"verify — falling through to self-fill")

    for i, shot in enumerate(shots):
        if shot.get("image_url"):
            continue
        if no_self_fill:
            report["media"]["unfilled"] += 1
            continue
        url = self_fill(pkg, i)
        if url:
            shot["image_url"] = url
            shot["media_origin"] = "self_fill_authored"
            report["media"]["self_filled"] += 1
        else:
            report["media"]["unfilled"] += 1
    filled = sum(1 for s in shots if s.get("image_url"))
    # Both declared and checkpoint-recovered pointers are ChatGPT's own
    # generated images — the origin suffix records HOW they arrived, not who
    # made them.
    from_chatgpt = sum(1 for s in shots
                       if str(s.get("media_origin") or "")
                       .startswith("chatgpt_authored"))
    print(f"[phase-b] authored {slug}: {filled}/{len(shots)} shots have "
          f"media ({from_chatgpt} generated by ChatGPT, "
          f"{filled - from_chatgpt} found by us)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True)
    ap.add_argument("--channel", default="trending")
    ap.add_argument("--require-done", action="store_true",
                    help="exit 2 unless ChatGPT wrote the DONE marker")
    ap.add_argument("--no-self-fill", action="store_true")
    ap.add_argument("--no-ingest", action="store_true",
                    help="skip promoting ChatGPT-authored packages")
    ap.add_argument("--no-punchup", action="store_true")
    ap.add_argument("--require-checkpoints", action="store_true",
                    help="force checkpoint enforcement even on a no-DONE "
                         "emergency backstop run")
    ap.add_argument("--backstop", action="store_true",
                    help="scheduled backstop: no-op unless the 07:00 Central "
                         "finalizer has had its full window")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.backstop:
        st = backstop_status(args.date)
        print(f"[phase-b] backstop check: {st['reason']}")
        if not st["ready"]:
            print("[phase-b] backstop deferring — the DONE push will fire "
                  "this run properly, or the next backstop hour will.")
            return 0

    bundle = xb.read_bundle(args.date)
    if not bundle:
        # RESCUE PATH. No bundle means Phase A never ran or died before
        # writing — which is precisely the day the takeover exists for, so
        # bailing here would be the wrong answer. If ChatGPT authored the
        # slate anyway (its instructions say to, bundle or no bundle), we
        # still have a day to ship: proceed in ingest-only mode with an
        # empty bundle. Only a day with NO bundle AND NO authored packages
        # is genuinely nothing to apply.
        sys.path.insert(0, str(ROOT / "scripts"))
        from exchange_phase_a import load_packages as _lp   # noqa: E402
        from ingest_authored import collect                 # noqa: E402
        authored_waiting = collect(args.date)
        already_there = _lp(args.channel, args.date)
        if authored_waiting or already_there:
            # Phase A never ran or died before writing. Two shapes land here
            # and BOTH still have a shippable day:
            #   · ChatGPT authored the slate anyway (its instructions say to)
            #   · Claude's packages exist but never got media/punch-up,
            #     because the thing that finds media IS Phase A
            # Bailing would throw away a whole day over a failed cron.
            print(f"[phase-b] NO BUNDLE for {args.date} — Phase A did not "
                  f"run. Rescuing: {len(authored_waiting)} authored by "
                  f"ChatGPT, {len(already_there)} already on disk.")
            print("::warning::Phase A produced no bundle; Phase B is "
                  "rescuing the day. Media was never searched for, so every "
                  "shot goes through self-fill.")
            # NO BUNDLE MEANS NO FROZEN CONTRACT, so resolve one live. This
            # is the ONLY path allowed to read the registry directly, and it
            # fails closed: guessing a historical mix here is how a retired
            # format reaches a slate on the one day nobody is watching.
            try:
                rescue_contract = reg.plan(args.date,
                                           {args.channel: already_there})
            except reg.RegistryError as exc:
                print(f"::error::no bundle AND the channel registry is "
                      f"unusable ({exc}). Refusing to guess a slate.")
                return 2
            print(f"[phase-b] rescue contract from registry rev "
                  f"{rescue_contract['registry_revision']}: "
                  f"{reg.mix_sentence(args.channel)}")
            bundle = {"schema": "rescue", "date": str(args.date),
                      "mode": "author", "packages": [], "requests": [],
                      "rescue": True, "contract": rescue_contract}
        else:
            print(f"[phase-b] no bundle for {args.date}, nothing authored "
                  f"and no packages on disk — nothing to apply")
            return 2

    done = xb.is_done(args.date)
    print(f"[phase-b] {args.date}: DONE marker "
          f"{'present' if done else 'ABSENT (proceeding — Policy A)'}")

    # CHECKPOINTS ARE MANDATORY ONCE DONE SAYS THE WORKERS FINISHED.
    #
    # DONE is ChatGPT's assertion that both workers ran to completion. If they
    # did, every image it points at has a checkpoint — writing one is the media
    # worker's whole job. A pointer with no checkpoint on a DONE run therefore
    # is not "a worker that skipped a step", it is an image nobody recorded
    # verifying, and accepting it with a warning is exactly the shape of
    # failure this contract was built to end: green everywhere, unverified
    # media on screen.
    #
    # The exception is the no-DONE emergency backstop. On that path ChatGPT
    # never finished — often never started — so there are no checkpoints to
    # require, and demanding them would turn "ChatGPT was late" into "the
    # channel posts nothing". Policy A still holds where it was meant to.
    require_cp = (done or args.require_checkpoints
                  or os.environ.get("EXCHANGE_REQUIRE_CHECKPOINTS") == "1")
    print(f"[phase-b] checkpoints are "
          f"{'REQUIRED' if require_cp else 'advisory'} on this run "
          f"({'DONE present' if done else 'no-DONE emergency backstop'})")

    if args.require_done and not done:
        print("[phase-b] --require-done set and no marker — deferring")
        return 2

    response = xb.read_response(args.date)
    idx = xb.response_index(response)

    # Computed here (not at its old spot, right before validate_response_media
    # below) because RECOVERY needs it too — a recovered checkpoint made for a
    # stale bundle revision must fail the identity check exactly like an
    # explicit response pointer would, and that requires knowing the current
    # bundle_id before recovery runs, not after.
    bundle_id = mc.bundle_identity(args.date)

    # RECOVER THE MEDIA WORKER'S OUTPUT FROM ITS CHECKPOINTS.
    #
    # Pointers used to come ONLY from response.json, which made every image
    # the 6:00 worker produced hostage to the 7:00 finalizer writing an
    # envelope for them. On 2026-08-09/10 the worker delivered 14-16 verified
    # images a day, the finalizer stopped closing, and Phase B discarded all
    # of it and self-filled with unrelated stock — which is precisely what
    # the showrunner then blocked trending's reddit stories for.
    #
    # A checkpoint is written at the moment the bytes verify and carries the
    # same file_id / sha256 / dimensions a pointer does, so it IS the
    # evidence. Recovered pointers fill only the gaps the response left, and
    # `recovered_media` puts each one through `checkpoint_problems` — the
    # same schema / date / bundle-identity / prompt / sharing / filename /
    # image checks an explicit pointer's checkpoint gets inside
    # `validate_response_media` — before it is ever merged in, so recovery
    # grants no extra trust; it only stops verified work from being thrown
    # away.
    _recovered_refused: dict[str, list[str]] = {}
    _recovered = mc.recovered_media(args.date, have=set(idx["media"]),
                                    bundle=bundle, bundle_id=bundle_id,
                                    refused_out=_recovered_refused)
    if _recovered:
        idx["media"].update(_recovered)
        print(f"[phase-b] recovered {len(_recovered)} media pointer(s) from "
              f"checkpoints (requests the response did not answer)")
    for rid, problems in _recovered_refused.items():
        print(f"::warning::[phase-b] REFUSED recovered checkpoint for "
              f"{rid}: {problems[0]}")
    if response is None:
        if done:
            # DONE says "I finished" but the payload will not parse. That is
            # a truncated or half-committed write, not a no-show, and on a
            # takeover day it means the ENTIRE day is missing. Never quiet.
            print("::error::DONE marker is present for "
                  f"{args.date} but response.json is missing or unparseable "
                  "— ChatGPT's work did not land. Commit response.json FIRST, "
                  "verify it, then commit DONE as a SEPARATE commit.")
        print("[phase-b] no response.json — ChatGPT contributed nothing; "
              "self-fill + originals only")

    # ---- checkpoint validation ------------------------------------------
    # Every media pointer in the response is a CLAIM. The checkpoint under
    # media-progress/ is the record of the moment those bytes were actually
    # verified, written by whichever worker did the work. Where both exist
    # they must agree exactly; where they disagree, something was edited
    # after the fact or two different images are in play, and neither is
    # something to put in a video.
    #
    # A MISSING checkpoint is a warning, not a rejection, unless
    # --require-checkpoints is set. The byte-level verification in
    # fetch_media (sha256 + full decode + placeholder check) is independent
    # and strong on its own, and hard-failing here would mean a worker that
    # skipped its checkpoints loses every image to stock self-fill — a
    # regression dressed up as strictness.
    validation = mc.validate_response_media(
        response, bundle, date=args.date, bundle_id=bundle_id,
        require_checkpoint=require_cp)
    refused = {r["request_id"]: r["problems"]
               for r in validation.get("rejected") or []}
    if validation.get("contract_problems"):
        # The whole response answers a different plan. Every pointer in it is
        # suspect, so none are used and the day self-fills.
        for why in validation["contract_problems"]:
            print(f"::error::[phase-b] CONTRACT MISMATCH — {why}")
        print("[phase-b] refusing every media pointer in this response: it "
              "was written against a different contract snapshot")
        for r in bundle.get("requests") or []:
            refused.setdefault(r["request_id"],
                               list(validation["contract_problems"]))
    for w in validation.get("warnings") or []:
        print(f"[phase-b] checkpoint warning {w['request_id']}: "
              f"{w['problem']}")
    for r in validation.get("rejected") or []:
        print(f"::warning::[phase-b] REFUSED media for "
              f"{r['request_id']} ({r['where']}): {r['problems'][0]}")
    c = validation.get("counts") or {}
    if c.get("checked"):
        print(f"[phase-b] checkpoints: {c.get('ok', 0)} usable, "
              f"{c.get('rejected', 0)} refused, "
              f"{c.get('warnings', 0)} unrecorded "
              f"(bundle identity {str(bundle_id or 'none')[:12]}…)")

    sys.path.insert(0, str(ROOT / "scripts"))

    # AUTHORING TAKEOVER, step 2. If the bundle carried an authoring request,
    # ChatGPT may have written the day's packages itself. Promote them BEFORE
    # loading the slate — validated first, so a malformed package is
    # quarantined with reasons instead of reaching a renderer.
    authored = {"promoted": [], "rejected": []}
    if not args.no_ingest:
        from ingest_authored import (ingest, ingest_curiosity,  # noqa: E402
                                     ingest_explainer)
        # THE TARGET COMES FROM THE DAY'S FROZEN CONTRACT. Not a literal,
        # and not the live registry: promotion has to agree with the plan the
        # workers were given, even if the registry moved since.
        contract = bundle.get("contract") or {}
        ch_plan = (contract.get("channels") or {}).get(args.channel) or {}
        target = ch_plan.get("target_count")
        if target is None:
            target = (bundle.get("authoring_request") or {}).get("target")
        if target is None:
            try:
                target = reg.target_count(args.channel)
            except reg.RegistryError as exc:
                print(f"::error::no contract in the bundle and the registry "
                      f"is unusable ({exc}) — refusing to guess a slate size")
                return 2
        print(f"[phase-b] promotion target {target} "
              f"(registry rev {contract.get('registry_revision', '?')})")
        authored = ingest(args.date, args.channel, target=int(target),
                          dry_run=args.dry_run)
        # The other channels ChatGPT can stand in for. Explainer gets WORDS
        # for stories whose numbers are already real (punch-up-guarded);
        # curiosity gets queue stock. Both no-op when ChatGPT sent nothing
        # for them, which is every normal day.
        other = {
            "explainer": ingest_explainer(args.date, dry_run=args.dry_run),
            "curiosity": ingest_curiosity(args.date, dry_run=args.dry_run),
        }
        for ch, rep in other.items():
            if rep.get("applied") or rep.get("rejected"):
                print(f"[phase-b] {ch}: {len(rep['applied'])} applied, "
                      f"{len(rep['rejected'])} rejected")
        authored["other_channels"] = {k: {"applied": len(v["applied"]),
                                          "rejected": len(v["rejected"])}
                                      for k, v in other.items()}

    from exchange_phase_a import load_packages      # noqa: E402
    packages = {p.get("slug"): p for p in
                load_packages(args.channel, args.date)}

    # IDEMPOTENT TAKEOVER REPAIR.  A second Phase B run used to see the
    # ChatGPT package already promoted, reject the duplicate candidate, and
    # therefore never revisit its media.  Reattach the response's media
    # pointers to the already-promoted package so a corrected checkpoint or
    # response can repair the day without deleting state first.
    response_authored = {
        str(p.get("slug") or ""): p
        for p in ((response or {}).get("authored") or [])
        if isinstance(p, dict) and p.get("slug")
    }
    for slug, pkg in packages.items():
        src = response_authored.get(str(slug))
        if not src or pkg.get("_authored_by") != "chatgpt-takeover":
            continue
        for dst_shot, src_shot in zip(pkg.get("shots") or [],
                                      src.get("shots") or []):
            if (isinstance(src_shot, dict)
                    and isinstance(src_shot.get("media"), dict)):
                dst_shot["media"] = dict(src_shot["media"])
    # Packages ChatGPT just wrote were not around when Phase A found media,
    # so they carry no `requests` and no `image_url` anywhere. Cover them
    # here or they render as bare keyword stock.
    new_slugs = {Path(p).stem.split("_", 1)[-1]
                 for p in authored.get("promoted") or []}
    new_slugs |= {
        str(slug) for slug, pkg in packages.items()
        if pkg.get("_authored_by") == "chatgpt-takeover"
        and str(slug) in response_authored
    }
    if bundle.get("rescue"):
        # No bundle means no `requests`, so the normal media loop below has
        # nothing to iterate. Everything on disk is uncovered — treat the
        # whole slate as freshly authored so it all goes through the media
        # pass instead of rendering on bare keyword stock.
        new_slugs |= set(packages)

    # AUTHORED-SHOT RECOVERY — the other half of the checkpoint-recovery
    # story above. `recovered_media` rebuilds BUNDLE-REQUEST pointers into
    # idx["media"], which only the bundle.requests loop reads; an
    # authored-shot checkpoint has no bundle request, and cover_authored
    # consumes only the `media` riding on a response-authored shot — so a
    # verified authored-shot checkpoint whose finalizer response omitted the
    # pointer was recovered into a map no consumer read, and the shot
    # self-filled with stock while its verified image sat on Drive (doctor
    # ee3bb63e4024). Recover those checkpoints type-aware, validated exactly
    # like an explicit authored pointer's checkpoint (request_kind,
    # package/shot identity, full checkpoint contract — see
    # `recovered_authored_media`), and attach each one to its shot BEFORE
    # cover_authored runs so it takes the identical byte-level fetch path
    # (sha256 + decode + placeholder). Recovery fills silence only: a shot
    # whose response pointer exists — or was refused — is never overridden.
    _auth_refused: dict[str, list[str]] = {}
    _auth_recovered = mc.recovered_authored_media(
        args.date, bundle_id=bundle_id, refused_out=_auth_refused)
    for _rid, problems in _auth_refused.items():
        print(f"::warning::[phase-b] REFUSED recovered authored-shot "
              f"checkpoint for {_rid}: {problems[0]}")
    if _auth_recovered:
        attached = 0
        for slug, pkg in packages.items():
            if pkg.get("_authored_by") != "chatgpt-takeover":
                # Authored-shot checkpoints exist only for packages ChatGPT
                # authored itself; one claiming a Claude package's slug is
                # not evidence about that package.
                continue
            for i, shot in enumerate(pkg.get("shots") or []):
                if not isinstance(shot, dict) or \
                        isinstance(shot.get("media"), dict):
                    continue        # the response spoke here — it wins
                rid = mc.authored_shot_request_id(slug, i)
                if rid in refused:
                    continue        # spoken AND refused — stays refused
                ptr = _auth_recovered.get(
                    mc.parse_authored_shot_request_id(rid))
                if ptr:
                    shot["media"] = dict(ptr)
                    # The whole point: a package whose response entry was
                    # missing entirely still gets its media pass.
                    new_slugs.add(str(slug))
                    attached += 1
        print(f"[phase-b] recovered {attached} authored-shot pointer(s) "
              f"from checkpoints (shots the response left bare)")

    report = {"date": str(args.date), "channel": args.channel,
              "done_marker": done, "had_response": response is not None,
              "authored": {"promoted": len(authored.get("promoted") or []),
                           "rejected": len(authored.get("rejected") or [])},
              "media": {"fulfilled": 0, "self_filled": 0, "unfilled": 0,
                        "refused": 0},
              "checkpoints": {"bundle_identity": bundle_id,
                              "required": require_cp,
                              **(validation.get("counts") or {}),
                              "rejected_detail": validation.get("rejected"),
                              "warnings_detail": validation.get("warnings")},
              "punchup": {"applied": 0, "kept": 0, "rejected": 0, "absent": 0},
              "details": []}

    # ---- media -----------------------------------------------------------
    for req in bundle.get("requests") or []:
        rid = req["request_id"]
        slug, sidx = req["slug"], req["shot_index"]
        pkg = packages.get(slug)
        if not pkg:
            continue
        shots = pkg.get("shots") or []
        if sidx >= len(shots):
            continue

        if rid in refused:
            # Refused on the checkpoint contract, before a byte is fetched.
            # Fall straight through to self-fill: a pointer we cannot trust
            # is worth exactly as much as no pointer at all.
            report["media"]["refused"] += 1
            report["details"].append({"request_id": rid,
                                      "outcome": "refused",
                                      "problems": refused[rid]})
            local = None
        else:
            local = fetch_media(rid, idx["media"].get(rid))
        if local:
            pin_verified_media(shots[sidx], idx["media"][rid],
                               origin="chatgpt")
            report["media"]["fulfilled"] += 1
            report["details"].append(
                {"request_id": rid, "outcome": "chatgpt", "path": str(local)})
            continue

        if not args.no_self_fill:
            url = self_fill(pkg, sidx)
            if url:
                shots[sidx]["image_url"] = url
                shots[sidx]["media_origin"] = "self_fill"
                report["media"]["self_filled"] += 1
                report["details"].append(
                    {"request_id": rid, "outcome": "self_fill", "url": url})
                continue

        report["media"]["unfilled"] += 1
        report["details"].append({"request_id": rid, "outcome": "unfilled"})

    # ---- media for freshly-authored packages -----------------------------
    # These missed Phase A entirely, so nothing has looked for their visuals.
    for slug in sorted(new_slugs):
        pkg = packages.get(slug)
        if not pkg:
            continue
        cover_authored(pkg, report, no_self_fill=args.no_self_fill,
                       date=args.date, rejected=refused)

    # ---- punch-up (guarded) ---------------------------------------------
    if not args.no_punchup:
        for slug, pkg in packages.items():
            rewrite = idx["scripts"].get(slug)
            if not rewrite:
                report["punchup"]["absent"] += 1
                continue
            if rewrite.get("kept"):
                # An explicit editorial keep — the script already lands.
                # Honest report category; nothing to merge or guard.
                report["punchup"]["kept"] += 1
                note = str(rewrite.get("editor_note") or "")[:120]
                print(f"[phase-b] punch-up KEPT for {slug}"
                      + (f" — {note}" if note else ""))
                continue
            merged = punchup_guard.apply(pkg, rewrite)
            if merged is None:
                ok, problems = punchup_guard.check(pkg, rewrite)
                report["punchup"]["rejected"] += 1
                report["details"].append({"slug": slug, "outcome":
                                          "punchup_rejected",
                                          "problems": problems})
                print(f"[phase-b] punch-up REJECTED for {slug}: "
                      + "; ".join(problems[:3]))
                continue
            packages[slug] = merged
            report["punchup"]["applied"] += 1
            print(f"[phase-b] punch-up applied to {slug}")

    m, p = report["media"], report["punchup"]
    print(f"[phase-b] media: {m['fulfilled']} from ChatGPT, "
          f"{m['self_filled']} self-filled, {m['unfilled']} unfilled, "
          f"{m.get('refused', 0)} refused on the checkpoint contract")
    print(f"[phase-b] punch-up: {p['applied']} applied, "
          f"{p.get('kept', 0)} kept (editor's call), "
          f"{p['rejected']} rejected, {p['absent']} not offered")
    # An editor that keeps EVERYTHING has stopped editing. That is usually
    # over-caution about the claim guard, which only protects numbers,
    # entities and beat structure — wording is free to change within them.
    offered = p["applied"] + p.get("kept", 0) + p["rejected"]
    if offered >= 3 and p["applied"] == 0 and p.get("kept", 0) == offered:
        print(f"::warning::punch-up: ChatGPT kept ALL {offered} scripts "
              f"unchanged. Check the editor_notes — a whole slate kept "
              f"usually means over-caution about the claim guard, not "
              f"{offered} scripts that all already landed.")
    if p["rejected"] and p["rejected"] >= p["applied"]:
        print(f"::warning::punch-up: {p['rejected']} rejected vs "
              f"{p['applied']} applied — the rewrites are breaking claims. "
              f"See the per-package problems above.")

    if args.dry_run:
        print("[phase-b] dry run — packages not written")
        return 0

    # ---- persist: every write must LAND before "ready to render" ---------
    # Exit 0 IS the contract ("Exit 0 = ready to render", module docstring):
    # daily.yml renders whatever is on disk the moment this returns. A
    # package write that failed here used to be a ::warning:: and a report
    # write that failed was silently discarded — so the renderer picked up
    # the STALE pre-Phase-B package (no verified media, no punch-up) and the
    # day shipped with no audit record, green the whole way. So: track every
    # intended write, and any failure flips the exit code and names the
    # path. The successful writes are left in place — they are individually
    # atomic and correct — but the phase as a whole refuses to call itself
    # ready.
    failed_writes: list[str] = []
    for slug, pkg in packages.items():
        path = pkg.pop("_path", None)
        if not path:
            continue
        try:
            atomic_write_json(Path(path), pkg)
        except Exception as exc:                     # noqa: BLE001
            print(f"::error::[phase-b] could not write package "
                  f"{slug} ({path}): {exc}")
            failed_writes.append(str(path))

    out = xb.bundle_dir(args.date) / "phase_b_report.json"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out, report)
    except Exception as exc:                         # noqa: BLE001
        # The report is the phase's only durable evidence of WHAT it did —
        # which pointers were refused, what self-filled, what the punch-up
        # guard rejected. Losing it silently is how a bad day becomes an
        # unexplainable day.
        print(f"::error::[phase-b] could not write audit record "
              f"{out}: {exc}")
        failed_writes.append(str(out))

    if failed_writes:
        print("::error::[phase-b] NOT ready to render — "
              f"{len(failed_writes)} write(s) failed: "
              + ", ".join(failed_writes))
        return 1
    print(f"[phase-b] wrote {out.relative_to(ROOT)} — ready to render")
    return 0


if __name__ == "__main__":
    sys.exit(main())
