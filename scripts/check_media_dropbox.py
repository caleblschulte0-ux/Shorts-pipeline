#!/usr/bin/env python3
"""Verify a ChatGPT media drop against the request that asked for it.

Fetches the `media-dropbox` orphan branch, reads
`drops/<date>/drop_manifest.json`, and checks every request in
`state/media_requests/<date>*.json` was answered: manifest entry present,
files actually committed, format allowed, size within the cap.

An honest `unsupported`/`failed` status counts as ANSWERED (it tells us what
the connector can do). A request with no manifest entry at all is a MISS.

    python scripts/check_media_dropbox.py --date 2026-07-29
    python scripts/check_media_dropbox.py --date 2026-07-29 --branch media-dropbox

Exit 0 = every request answered and every claimed file present.
Exit 1 = something is missing or malformed. Exit 2 = no drop found yet.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

BRANCH = "media-dropbox"
REQUEST_DIR = "state/media_requests"
ANSWERED = {"fulfilled", "partial", "unsupported", "failed"}


def run(*args: str) -> tuple[int, str]:
    p = subprocess.run(args, capture_output=True, text=True)
    return p.returncode, (p.stdout or p.stderr).strip()


def load_request(date: str) -> dict:
    hits = sorted(glob.glob(os.path.join(REQUEST_DIR, f"{date}*.json")))
    if not hits:
        sys.exit(f"no request manifest matching {REQUEST_DIR}/{date}*.json")
    with open(hits[0], encoding="utf-8") as fh:
        req = json.load(fh)
    req["_path"] = hits[0]
    return req


def load_drop(branch: str, date: str) -> tuple[dict | None, dict[str, int]]:
    """Return (drop_manifest, {path: size}) from the dropbox branch."""
    run("git", "fetch", "origin", f"{branch}:refs/remotes/origin/{branch}", "--force")
    ref = f"origin/{branch}"
    rc, _ = run("git", "rev-parse", "--verify", ref)
    if rc != 0:
        return None, {}

    rc, raw = run("git", "show", f"{ref}:drops/{date}/drop_manifest.json")
    manifest = json.loads(raw) if rc == 0 else None

    sizes: dict[str, int] = {}
    rc, listing = run("git", "ls-tree", "-r", "-l", ref, f"drops/{date}/")
    if rc == 0:
        for line in listing.splitlines():
            parts = line.split(maxsplit=4)
            if len(parts) == 5 and parts[3].isdigit():
                sizes[parts[4]] = int(parts[3])
    return manifest, sizes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--branch", default=BRANCH)
    args = ap.parse_args()

    req = load_request(args.date)
    manifest, sizes = load_drop(args.branch, args.date)

    print(f"request : {req['_path']}  ({len(req.get('requests', []))} asked)")

    if manifest is None:
        print(f"drop    : NONE — no drops/{args.date}/drop_manifest.json on {args.branch}")
        if sizes:
            print(f"          (but {len(sizes)} file(s) present — manifest missing)")
            for path, size in sorted(sizes.items()):
                print(f"          {size:>9,}B  {path}")
        return 2

    results = {r.get("request_id"): r for r in manifest.get("results", [])}
    print(f"drop    : {len(results)} result(s), {len(sizes)} file(s) on {args.branch}\n")

    problems: list[str] = []
    for entry in req.get("requests", []):
        rid = entry["id"]
        got = results.get(rid)
        if got is None:
            print(f"  MISS       {rid} — no entry in drop manifest")
            problems.append(f"{rid}: unanswered")
            continue

        status = got.get("status", "?")
        if status not in ANSWERED:
            problems.append(f"{rid}: unknown status {status!r}")

        files = got.get("files", [])
        print(f"  {status.upper():<10} {rid}  ({len(files)} file(s))")

        fmt = got.get("format")
        accepts = entry.get("accepts", [])
        if status in {"fulfilled", "partial"} and fmt and accepts and fmt not in accepts:
            problems.append(f"{rid}: format {fmt!r} not in accepts {accepts}")

        cap = entry.get("max_bytes")
        for path in files:
            size = sizes.get(path)
            if size is None:
                print(f"             MISSING FILE  {path}")
                problems.append(f"{rid}: claimed file not committed — {path}")
                continue
            flag = ""
            if cap and size > cap:
                flag = f"  OVER CAP ({cap:,}B)"
                problems.append(f"{rid}: {path} is {size:,}B > cap {cap:,}B")
            print(f"             {size:>9,}B  {path}{flag}")

        if status in {"fulfilled", "partial"} and not files:
            problems.append(f"{rid}: status {status} but no files listed")

        if got.get("notes"):
            print(f"             note: {got['notes']}")

    claimed = {p for r in results.values() for p in r.get("files", [])}
    for stray in sorted(set(sizes) - claimed - {f"drops/{args.date}/drop_manifest.json"}):
        print(f"  STRAY      {stray} — committed but not in manifest")

    print()
    if problems:
        print(f"FAIL — {len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("PASS — every request answered, every claimed file present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
