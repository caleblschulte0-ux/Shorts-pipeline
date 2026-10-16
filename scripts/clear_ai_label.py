#!/usr/bin/env python3
"""Clear YouTube's "altered or synthetic content" declaration on every
video a channel already uploaded.

Operator, 2026-10-16: *"Turn them off on all of them. I don't want to see
AI tags on any of our stuff."* Uploads used to send
containsSyntheticMedia=True on every channel; new uploads no longer do
(shared/uploaders.py). This fixes what is already live.

    python scripts/clear_ai_label.py --channel third          # dry run
    python scripts/clear_ai_label.py --channel third --apply

videos.update costs 50 quota units, so a big channel may need more than
one day's quota. The script is idempotent: it only touches videos still
declared, and stops cleanly on quotaExceeded so the next run picks up
where this one left off. A label YouTube applied ITSELF (C2PA metadata,
its own detection) cannot be removed through the API and is reported.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: status fields videos.update accepts; anything left out of the request
#: is RESET, so every one we were given goes back exactly as it was.
WRITABLE = ("privacyStatus", "publishAt", "selfDeclaredMadeForKids",
            "license", "embeddable", "publicStatsViewable")


def cleared_status(status: dict) -> dict:
    """The status to send: everything writable kept as it is, the
    synthetic-media declaration off. Pure, so it is testable."""
    out = {k: status[k] for k in WRITABLE if k in status}
    out.setdefault("selfDeclaredMadeForKids", False)
    out["containsSyntheticMedia"] = False
    return out


def _declared(svc, ids: list[str]) -> list[dict]:
    out = []
    for k in range(0, len(ids), 50):
        resp = svc.videos().list(part="status,snippet",
                                 id=",".join(ids[k:k + 50])).execute()
        for v in resp.get("items") or []:
            if (v.get("status") or {}).get("containsSyntheticMedia"):
                out.append(v)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--channel", default="",
                    help='token route: "" (trending), "explainer", "third"')
    ap.add_argument("--apply", action="store_true",
                    help="write the change (default: list only)")
    a = ap.parse_args(argv)
    from scripts.youtube_duplicates import _service, list_uploads
    svc = _service(a.channel)
    label = a.channel or "trending"
    uploads = list_uploads(svc)
    todo = _declared(svc, [v["id"] for v in uploads])
    print(f"[ai-label] {label}: {len(uploads)} uploads, "
          f"{len(todo)} declared synthetic", flush=True)
    if not a.apply:
        for v in todo[:20]:
            print(f"  {v['id']}  {v['snippet'].get('title', '')[:70]}")
        return 0
    done = refused = 0
    for v in todo:
        try:
            svc.videos().update(part="status", body={
                "id": v["id"], "status": cleared_status(v["status"])}).execute()
            done += 1
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "quotaExceeded" in msg or "quota" in msg.lower():
                print(f"[ai-label] {label}: quota spent after {done}; "
                      f"run again tomorrow for the other "
                      f"{len(todo) - done - refused}", flush=True)
                break
            refused += 1
            print(f"::warning::[ai-label] {v['id']} not cleared: {msg[:200]}",
                  flush=True)
    print(f"[ai-label] {label}: cleared {done}, refused {refused}, "
          f"left {len(todo) - done - refused}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
