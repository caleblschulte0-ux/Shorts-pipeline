#!/usr/bin/env python3
"""media_probe — answer, with evidence, WHY a provider returned nothing.

Three renders in a row credited zero Pexels and zero Pixabay clips while the
secrets were present in the repo and passed to the render step. "The keys are
missing" was a guess, and a wrong one. This probe replaces the guess with a
measurement: it calls every video provider live, with the same code the
renderer uses, and reports for each one whether the key is present, whether the
call succeeded, how many candidates came back, and the exact error if not.

It renders nothing and downloads no media — it is seconds, not hours, so the
media supply can be diagnosed without burning a full render.

    python scripts/media_probe.py [query ...]
    exit 0 always (a probe reports, it does not gate)
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Queries a real film actually asks for — human-scale beats, the exact kind the
# CC pools answer badly and the stock sites answer well.
DEFAULT_QUERIES = [
    "person walking outdoors sunset",
    "person sleeping in bed",
    "commuter traffic morning",
    "person looking at phone screen",
]


def _fingerprint(key: str | None) -> dict:
    """Describe a secret WITHOUT leaking it: presence, length, and whether it
    carries the whitespace/quoting damage that silently breaks auth headers."""
    if key is None:
        return {"present": False}
    return {
        "present": True,
        "length": len(key),
        "stripped_length": len(key.strip()),
        "has_surrounding_whitespace": key != key.strip(),
        "has_quotes": key.strip()[:1] in ("'", '"') or key.strip()[-1:] in ("'", '"'),
        "looks_placeholder": key.strip().lower() in (
            "", "none", "null", "changeme", "your_key_here"),
    }


def probe_provider(name: str, fn, query: str) -> dict:
    t0 = time.time()
    row = {"provider": name, "query": query}
    try:
        hits = fn(query, 8) or []
        row.update({"ok": True, "n": len(hits),
                    "sample": [str(h.get("title", ""))[:60] for h in hits[:3]],
                    "elapsed_s": round(time.time() - t0, 2)})
    except Exception as e:  # noqa: BLE001 — the whole point is to REPORT the error
        row.update({"ok": False, "n": 0,
                    "error_type": type(e).__name__,
                    "error": str(e)[:300],
                    "http_code": getattr(e, "code", None),
                    "traceback_tail": traceback.format_exc().strip().splitlines()[-1],
                    "elapsed_s": round(time.time() - t0, 2)})
    return row


def main(argv) -> int:
    queries = argv or DEFAULT_QUERIES
    from data_learning import stock

    report = {
        "keys": {
            "PEXELS_API_KEY": _fingerprint(os.environ.get("PEXELS_API_KEY")),
            "PIXABAY_API_KEY": _fingerprint(os.environ.get("PIXABAY_API_KEY")),
        },
        "access_report": stock.access_report(),
        "probes": [],
    }

    providers = [
        ("pexels", stock.search_pexels),
        ("pixabay", stock.search_pixabay),
        ("commons", stock.search_commons),
        ("archive", stock.search_archive),
    ]
    for q in queries:
        for name, fn in providers:
            report["probes"].append(probe_provider(name, fn, q))

    # the verdict, per provider, across every query
    summary = {}
    for name, _ in providers:
        rows = [r for r in report["probes"] if r["provider"] == name]
        total = sum(r["n"] for r in rows)
        errs = [r for r in rows if not r["ok"]]
        if not report["keys"].get(f"{name.upper()}_API_KEY", {}).get(
                "present", True) and name in ("pexels", "pixabay"):
            verdict = "NO KEY IN ENV — the secret never reached this step"
        elif errs:
            verdict = (f"CALL FAILED ({errs[0].get('error_type')}: "
                       f"{errs[0].get('error', '')[:120]})")
        elif total == 0:
            verdict = "REACHABLE but ZERO results for every query"
        else:
            verdict = f"WORKING — {total} candidates across {len(rows)} queries"
        summary[name] = verdict
    report["summary"] = summary

    out = REPO / "output"
    out.mkdir(exist_ok=True)
    (out / "media_probe.json").write_text(json.dumps(report, indent=2) + "\n")

    print("=== MEDIA PROBE ===")
    for k, v in report["keys"].items():
        print(f"{k}: {v}")
    print()
    for name, verdict in summary.items():
        print(f"{name:9} {verdict}")
    print()
    for r in report["probes"]:
        if not r["ok"] or r["n"] == 0:
            print(f"  [{r['provider']}] {r['query'][:40]!r} -> n={r['n']} "
                  f"{r.get('error_type', '')} {r.get('error', '')[:160]}")

    # a compact scoreboard in the run summary too
    dest = os.environ.get("GITHUB_STEP_SUMMARY")
    if dest:
        with open(dest, "a", encoding="utf-8") as fh:
            fh.write("## Media probe\n\n| provider | verdict |\n|---|---|\n")
            for name, verdict in summary.items():
                fh.write(f"| {name} | {verdict} |\n")
            fh.write("\n**Key presence** (never the value): ")
            fh.write(", ".join(
                f"`{k}` present={v.get('present')} len={v.get('length', '-')}"
                for k, v in report["keys"].items()))
            fh.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
