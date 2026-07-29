#!/usr/bin/env python3
"""Verify a ChatGPT media drop against the request that asked for it.

Fetches the `media-dropbox` orphan branch, reads
`drops/<date>/drop_manifest.json`, and checks every request in
`state/media_requests/<date>*.json` was answered: manifest entry present,
files actually committed, format allowed, size within the cap.

An honest `unsupported`/`failed` status counts as ANSWERED (it tells us what
the connector can do). A request with no manifest entry at all is a MISS.

Because ChatGPT's GitHub writer is UTF-8 text only, raster images arrive one of
two ways, and both are checked here: a `.b64` text file (decoded and validated
as a real image, dimensions reported), or a `urls` array we fetch ourselves.
Either satisfies a `fulfilled` status.

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
DECODE_DIR = "cache/dropbox"   # gitignored; decoded images land here


def decode_b64(ref: str, path: str) -> tuple[str, int, str]:
    """Decode a committed .b64 text file to a real image. -> (status, bytes, detail)"""
    import base64
    import binascii

    rc, raw = run("git", "show", f"{ref}:{path}")
    if rc != 0:
        return "error", 0, "could not read from branch"

    payload = raw.strip()
    if payload.startswith("data:"):          # tolerate a data: URI prefix
        payload = payload.split(",", 1)[-1]
    payload = "".join(payload.split())       # strip newlines/whitespace
    try:
        blob = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        return "error", 0, f"not valid base64: {exc}"
    if not blob:
        return "error", 0, "decoded to zero bytes"

    os.makedirs(DECODE_DIR, exist_ok=True)
    out = os.path.join(DECODE_DIR, os.path.basename(path).removesuffix(".b64"))
    with open(out, "wb") as fh:
        fh.write(blob)

    try:
        from PIL import Image
        with Image.open(out) as im:
            return "ok", len(blob), f"{im.format} {im.width}x{im.height} -> {out}"
    except Exception as exc:                  # noqa: BLE001 - any decode failure is the signal
        return "error", len(blob), f"decoded but not a readable image: {exc}"


def probe_url(url: str) -> str:
    """HEAD/GET a handed-back image URL to see if it is actually fetchable."""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "shorts-pipeline/dropbox-check"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            head = resp.read(2_000_000)
            ctype = resp.headers.get("Content-Type", "?")
            return f"REACHABLE {resp.status} {ctype} {len(head):,}B read"
    except urllib.error.HTTPError as exc:
        return f"HTTP {exc.code} — {exc.reason} (expired or auth-gated?)"
    except Exception as exc:                  # noqa: BLE001
        return f"UNREACHABLE — {type(exc).__name__}: {exc}"


def run(*args: str) -> tuple[int, str]:
    p = subprocess.run(args, capture_output=True, text=True)
    return p.returncode, (p.stdout or p.stderr).strip()


def load_request(date: str, explicit: str | None) -> dict:
    if explicit:
        hits = [explicit]
    else:
        hits = sorted(glob.glob(os.path.join(REQUEST_DIR, f"{date}*.json")))
    if not hits:
        sys.exit(f"no request manifest matching {REQUEST_DIR}/{date}*.json")
    if len(hits) > 1:
        print(f"note: {len(hits)} manifests match {date} — using {hits[0]} "
              f"(override with --request)")
    with open(hits[0], encoding="utf-8") as fh:
        req = json.load(fh)
    req["_path"] = hits[0]
    return req


def load_drop(branch: str, drop_dir: str) -> tuple[dict | None, dict[str, int]]:
    """Return (drop_manifest, {path: size}) from the dropbox branch."""
    run("git", "fetch", "origin", f"{branch}:refs/remotes/origin/{branch}", "--force")
    ref = f"origin/{branch}"
    rc, _ = run("git", "rev-parse", "--verify", ref)
    if rc != 0:
        return None, {}

    rc, raw = run("git", "show", f"{ref}:{drop_dir}drop_manifest.json")
    manifest = json.loads(raw) if rc == 0 else None

    sizes: dict[str, int] = {}
    rc, listing = run("git", "ls-tree", "-r", "-l", ref, drop_dir)
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
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip network probes of handed-back image URLs")
    ap.add_argument("--request", help="explicit request manifest path")
    args = ap.parse_args()

    req = load_request(args.date, args.request)
    drop_dir = req.get("drop_path") or f"drops/{args.date}/"
    if not drop_dir.endswith("/"):
        drop_dir += "/"
    manifest, sizes = load_drop(args.branch, drop_dir)

    print(f"request : {req['_path']}  ({len(req.get('requests', []))} asked)")
    print(f"expect  : {drop_dir} on {args.branch}")

    if manifest is None:
        print(f"drop    : NONE — no {drop_dir}drop_manifest.json on {args.branch}")
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
        urls = got.get("urls", []) or []
        print(f"  {status.upper():<10} {rid}  ({len(files)} file(s), {len(urls)} url(s))")

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

            if path.endswith(".b64"):
                state, nbytes, detail = decode_b64(f"origin/{args.branch}", path)
                label = "decoded" if state == "ok" else "B64 FAIL"
                print(f"             {label}: {nbytes:,}B  {detail}")
                if state != "ok":
                    problems.append(f"{rid}: base64 payload unusable — {detail}")

        for url in urls:
            print(f"             url: {url}")
            if not args.no_fetch:
                print(f"                  {probe_url(url)}")

        if status in {"fulfilled", "partial"} and not files and not urls:
            problems.append(f"{rid}: status {status} but no files and no urls")

        if got.get("notes"):
            print(f"             note: {got['notes']}")

        for step, verdict in (got.get("diagnostics") or {}).items():
            print(f"             step {step}: {verdict}")

    claimed = {p for r in results.values() for p in r.get("files", [])}
    for stray in sorted(set(sizes) - claimed - {f"{drop_dir}drop_manifest.json"}):
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
