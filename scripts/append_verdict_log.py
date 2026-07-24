#!/usr/bin/env python3
"""Append one compact verdict record to the running preview verdict log.

Called from the preview_explainer workflow as:

    python3 scripts/append_verdict_log.py output/story_<slug>.showrunner.json >> verdicts-log.jsonl

Kept as a committed helper (not an inline heredoc) so the workflow YAML stays
valid. Emits a single JSON line to stdout; on any read/parse error it prints
nothing and exits 0 so the render publish step never fails on a bad verdict.
"""
from __future__ import annotations

import datetime
import json
import sys


def main() -> int:
    if len(sys.argv) < 2:
        return 0
    path = sys.argv[1]
    try:
        with open(path) as fh:
            v = json.load(fh)
    except Exception:
        return 0
    slug = (path.split("/")[-1]
            .replace(".showrunner.json", "")
            .replace("story_", ""))
    rec = {
        "ts": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "slug": slug,
        "score": v.get("score"),
        "verdict": v.get("verdict"),
        "dimensions": v.get("dimensions"),
        "temporal": v.get("temporal"),
        "auto_fails": v.get("auto_fails"),
        "judge": v.get("judge"),
    }
    print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
