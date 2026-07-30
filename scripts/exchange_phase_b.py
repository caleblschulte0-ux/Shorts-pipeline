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
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import exchange_bundle as xb           # noqa: E402
from shared import punchup_guard                   # noqa: E402
from shared.fsutil import atomic_write_json        # noqa: E402

MEDIA_CACHE = ROOT / "cache" / "exchange"


def fetch_media(request_id: str) -> Path | None:
    """Hand off to the verified consumer (hash + pixel checks live there)."""
    try:
        run = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "fetch_exchange_media.py"),
             "--id", request_id, "--json"],
            capture_output=True, text=True, timeout=180, cwd=str(ROOT))
        payload = json.loads(run.stdout or "{}")
        for r in payload.get("results") or []:
            if r.get("ok") and r.get("local_path"):
                return Path(r["local_path"])
    except Exception:                                # noqa: BLE001
        pass
    # Already-downloaded fallback: trust nothing that isn't on disk.
    for ext in ("png", "jpg", "jpeg", "webp", "mp4"):
        p = MEDIA_CACHE / f"{request_id}.{ext}"
        if p.exists() and p.stat().st_size:
            return p
    return None


def self_fill(pkg: dict, shot_index: int) -> str | None:
    """Gloves-off second funnel pass for a gap ChatGPT did not fill.

    Widens the search and accepts weaker-but-real candidates. Never raises;
    None means the shot renders with whatever it already had."""
    try:
        from funnel import media_funnel
    except Exception:                                # noqa: BLE001
        return None
    shots = pkg.get("shots") or []
    if shot_index >= len(shots):
        return None
    shot = shots[shot_index]
    query = (shot.get("query") or shot.get("phrase") or "").strip()
    if not query:
        return None
    for fn_name, kwargs in (
        ("find_images", {"limit": 12}),
        ("search", {"limit": 12}),
        ("gather", {"limit": 12}),
    ):
        fn = getattr(media_funnel, fn_name, None)
        if fn is None:
            continue
        try:
            got = fn(query, **kwargs)                # type: ignore[misc]
        except TypeError:
            try:
                got = fn(query)                      # type: ignore[misc]
            except Exception:                        # noqa: BLE001
                continue
        except Exception:                            # noqa: BLE001
            continue
        for cand in (got or []):
            url = (cand.get("url") if isinstance(cand, dict) else None) or \
                  (cand if isinstance(cand, str) else None)
            if url:
                return url
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True)
    ap.add_argument("--channel", default="trending")
    ap.add_argument("--require-done", action="store_true",
                    help="exit 2 unless ChatGPT wrote the DONE marker")
    ap.add_argument("--no-self-fill", action="store_true")
    ap.add_argument("--no-punchup", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    bundle = xb.read_bundle(args.date)
    if not bundle:
        print(f"[phase-b] no bundle for {args.date} — nothing to apply")
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
        print("[phase-b] no response.json — ChatGPT contributed nothing; "
              "self-fill + originals only")

    sys.path.insert(0, str(ROOT / "scripts"))
    from exchange_phase_a import load_packages      # noqa: E402
    packages = {p.get("slug"): p for p in
                load_packages(args.channel, args.date)}

    report = {"date": str(args.date), "channel": args.channel,
              "done_marker": done, "had_response": response is not None,
              "media": {"fulfilled": 0, "self_filled": 0, "unfilled": 0},
              "punchup": {"applied": 0, "rejected": 0, "absent": 0},
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

        local = fetch_media(rid) if rid in idx["media"] or response else None
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

    # ---- punch-up (guarded) ---------------------------------------------
    if not args.no_punchup:
        for slug, pkg in packages.items():
            rewrite = idx["scripts"].get(slug)
            if not rewrite:
                report["punchup"]["absent"] += 1
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
          f"{p['rejected']} rejected, {p['absent']} not offered")

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
