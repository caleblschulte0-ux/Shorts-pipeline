#!/usr/bin/env python3
"""Creator-permission workflow (media doctrine M8, PERMISSION_GRANTED lane).

The one lane a machine can't finish alone: asking a human for their
footage. This tool does everything around the human step — drafts the
message, tracks the request, and registers the grant so renders may use
the asset with documentation.

  python3 scripts/request_permission.py draft <media_url> \
      --creator "@handle or name" --story <slug> [--platform tiktok]
  python3 scripts/request_permission.py list [--status pending]
  python3 scripts/request_permission.py grant <id> --terms "credit @x in description"
  python3 scripts/request_permission.py deny <id>

State: state/permission_requests.json (committed with the rest of state/).
An asset may only enter a render under PERMISSION_GRANTED after `grant`
records the terms — a drafted-but-unanswered request is NOT permission.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fsutil import atomic_write_json, load_json  # noqa: E402

LEDGER = ROOT / "state" / "permission_requests.json"

TEMPLATE = """\
Hi{creator_part} — I run {channel}, a YouTube channel that makes short
explainer videos. I'd love to include your {platform} post
({url}) in an upcoming video about {story}.

Specifically I'm asking for permission to:
  - include an excerpt of it in an edited, commentary-style video
  - on a monetized YouTube channel
  - with credit to you (tell me your preferred handle/name)

Happy to answer anything, and totally fine if you'd rather not.
If yes, a simple reply saying "yes, you may use it with credit to X"
is all I need. Thanks!
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft")
    d.add_argument("url")
    d.add_argument("--creator", default="")
    d.add_argument("--story", default="")
    d.add_argument("--platform", default="post")
    d.add_argument("--channel", default="our channel")
    ls = sub.add_parser("list")
    ls.add_argument("--status", default="")
    g = sub.add_parser("grant")
    g.add_argument("id")
    g.add_argument("--terms", required=True)
    dn = sub.add_parser("deny")
    dn.add_argument("id")
    a = ap.parse_args()

    ledger = load_json(LEDGER, {"requests": {}})
    reqs = ledger.setdefault("requests", {})

    if a.cmd == "draft":
        rid = hashlib.sha1(a.url.encode()).hexdigest()[:10]
        reqs[rid] = {"url": a.url, "creator": a.creator, "story": a.story,
                     "platform": a.platform, "status": "pending",
                     "drafted_at": _now()}
        atomic_write_json(LEDGER, ledger)
        creator_part = f" {a.creator}" if a.creator else ""
        print(TEMPLATE.format(creator_part=creator_part, url=a.url,
                              story=a.story or "a current story",
                              platform=a.platform, channel=a.channel))
        print(f"[permission] request {rid} recorded as PENDING — the asset "
              f"may NOT be used until `grant {rid}` records the reply.")
    elif a.cmd == "list":
        for rid, r in reqs.items():
            if a.status and r.get("status") != a.status:
                continue
            print(f"{rid}  {r.get('status', '?'):8s}  {r.get('url', '')[:70]}")
    elif a.cmd in ("grant", "deny"):
        r = reqs.get(a.id)
        if not r:
            print(f"unknown request id {a.id!r}")
            return 1
        if a.cmd == "grant":
            r.update(status="granted", terms=a.terms, granted_at=_now())
            print(f"[permission] {a.id} GRANTED — asset may enter renders "
                  f"under PERMISSION_GRANTED with terms: {a.terms}")
        else:
            r.update(status="denied", denied_at=_now())
            print(f"[permission] {a.id} denied — asset stays out.")
        atomic_write_json(LEDGER, ledger)
    return 0


if __name__ == "__main__":
    sys.exit(main())
