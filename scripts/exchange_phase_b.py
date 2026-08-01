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

from shared import exchange_bundle as xb           # noqa: E402
from shared import punchup_guard                   # noqa: E402
from shared.fsutil import atomic_write_json        # noqa: E402

MEDIA_CACHE = ROOT / "cache" / "exchange"


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
    """
    import hashlib
    import io
    import urllib.request

    # Already on disk from a previous run?
    for ext in ("png", "jpg", "jpeg", "webp", "mp4"):
        p = MEDIA_CACHE / f"{request_id}.{ext}"
        if p.exists() and p.stat().st_size:
            return p

    if not isinstance(entry, dict) or entry.get("status") not in ("fulfilled",
                                                                  "partial"):
        return None
    drive = entry.get("drive") or {}
    img = entry.get("image") or {}
    fid = (drive.get("file_id") or "").strip()
    claim = (img.get("sha256") or "").strip().lower()

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
    # (Wikipedia article images, Commons, Openverse; keyless).
    try:
        from funnel import topic_media
        urls = topic_media.search(entity, angle) or []
        for url in urls:
            if url:
                print(f"[phase-b] self-fill lane=topic shot={shot_index}")
                return url
    except Exception:                                # noqa: BLE001
        pass

    return None


def cover_authored(pkg: dict, report: dict, *, no_self_fill: bool = False
                   ) -> None:
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
        local = fetch_media(xb.request_key(slug, i, "authored"), pointer)
        if local:
            shot["image_url"] = str(local)
            shot["media_origin"] = "chatgpt_authored"
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
    from_chatgpt = sum(1 for s in shots
                       if s.get("media_origin") == "chatgpt_authored")
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
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

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
            bundle = {"schema": "rescue", "date": str(args.date),
                      "mode": "author", "packages": [], "requests": [],
                      "rescue": True}
        else:
            print(f"[phase-b] no bundle for {args.date}, nothing authored "
                  f"and no packages on disk — nothing to apply")
            return 2

    done = xb.is_done(args.date)
    print(f"[phase-b] {args.date}: DONE marker "
          f"{'present' if done else 'ABSENT (proceeding — Policy A)'}")
    if args.require_done and not done:
        print("[phase-b] --require-done set and no marker — deferring")
        return 2

    response = xb.read_response(args.date)
    idx = xb.response_index(response)
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

    sys.path.insert(0, str(ROOT / "scripts"))

    # AUTHORING TAKEOVER, step 2. If the bundle carried an authoring request,
    # ChatGPT may have written the day's packages itself. Promote them BEFORE
    # loading the slate — validated first, so a malformed package is
    # quarantined with reasons instead of reaching a renderer.
    authored = {"promoted": [], "rejected": []}
    if not args.no_ingest:
        from ingest_authored import (ingest, ingest_curiosity,  # noqa: E402
                                     ingest_explainer)
        authored = ingest(args.date, args.channel,
                          target=int(bundle.get("authoring_request", {})
                                     .get("target", 6)),
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
    # Packages ChatGPT just wrote were not around when Phase A found media,
    # so they carry no `requests` and no `image_url` anywhere. Cover them
    # here or they render as bare keyword stock.
    new_slugs = {Path(p).stem.split("_", 1)[-1]
                 for p in authored.get("promoted") or []}
    if bundle.get("rescue"):
        # No bundle means no `requests`, so the normal media loop below has
        # nothing to iterate. Everything on disk is uncovered — treat the
        # whole slate as freshly authored so it all goes through the media
        # pass instead of rendering on bare keyword stock.
        new_slugs |= set(packages)

    report = {"date": str(args.date), "channel": args.channel,
              "done_marker": done, "had_response": response is not None,
              "authored": {"promoted": len(authored.get("promoted") or []),
                           "rejected": len(authored.get("rejected") or [])},
              "media": {"fulfilled": 0, "self_filled": 0, "unfilled": 0},
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

        local = fetch_media(rid, idx["media"].get(rid))
        if local:
            shots[sidx]["image_url"] = str(local)
            shots[sidx]["media_origin"] = "chatgpt"
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
        cover_authored(pkg, report, no_self_fill=args.no_self_fill)

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
          f"{m['self_filled']} self-filled, {m['unfilled']} unfilled")
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

    for slug, pkg in packages.items():
        path = pkg.pop("_path", None)
        if not path:
            continue
        try:
            atomic_write_json(Path(path), pkg)
        except Exception as exc:                     # noqa: BLE001
            print(f"[phase-b] WARN could not write {slug}: {exc}")

    out = xb.bundle_dir(args.date) / "phase_b_report.json"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out, report)
        print(f"[phase-b] wrote {out.relative_to(ROOT)} — ready to render")
    except Exception:                                # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
