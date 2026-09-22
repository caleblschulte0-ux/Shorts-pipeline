#!/usr/bin/env python3
"""Claim ChatGPT's rewrites for held explainer stories — or file the backlog.

    python scripts/claim_rewrites.py claim            # validate + apply answers
    python scripts/claim_rewrites.py claim --dry-run
    python scripts/claim_rewrites.py sweep            # file a request for every
                                                      # un-posted story the gate
                                                      # holds for word reasons

Contract and the ChatGPT round: docs/REVIEW_MAILBOX.md. The rules that
decide are in `shared/rewrite_mailbox.py`; nothing here trusts an answer.
Exit code 0 always — a rejected rewrite is a settled request, not a fault.
Prints `applied=N` last so a workflow can decide whether to persist without
`[skip ci]` (an applied rewrite is new content: the explainer's push
trigger should render it).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from shared import rewrite_mailbox as rm                    # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", choices=["claim", "sweep"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config", type=Path,
                    default=REPO / "data_learning" / "niche.config.json")
    ap.add_argument("--log", type=Path,
                    default=REPO / "state" / "explainer_posted_log.json")
    args = ap.parse_args()
    if args.mode == "sweep":
        cfg = json.loads(args.config.read_text())
        stories = {s.get("slug"): s for s in cfg.get("stories") or []}
        try:
            posted = set(json.loads(args.log.read_text()).get("posted") or {})
        except Exception:  # noqa: BLE001
            posted = set()
        filed = rm.sweep(stories, posted)
        print(f"[rewrites] sweep: {len(filed)} request(s) open for "
              f"{len([s for s in stories if s not in posted])} un-posted stories")
        return 0
    rep = rm.claim_all(args.config, dry_run=args.dry_run)
    for r in rep["rejected"]:
        print(f"[rewrites] rejected {r['id']}: {r['problems'][0]}")
    print(f"[rewrites] open={rep['open']} rejected={len(rep['rejected'])} "
          f"applied={len(rep['applied'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
