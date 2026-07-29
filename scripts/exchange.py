#!/usr/bin/env python3
"""exchange — the file-based mailbox between the GitHub agent and ChatGPT.

The repo is the channel: one side commits a request, the other reads it off
GitHub, does the work, drops the asset in Google Drive, and commits a response
pointing at it. See exchange/README.md for the protocol.

    exchange.py request --brief "..." [--purpose ...] [--push]
    exchange.py list [--all]
    exchange.py show <id>
    exchange.py respond <id> --drive-url URL [--filename f] [--notes n] [--push]
    exchange.py fetch <id> [--out PATH]

Assets never enter git — `fetch` writes into cache/exchange/ (gitignored).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOX = REPO / "exchange"
REQ, RES = BOX / "requests", BOX / "responses"
CACHE = REPO / "cache" / "exchange"

_FILE_ID = re.compile(r"/d/([A-Za-z0-9_-]{10,})|[?&]id=([A-Za-z0-9_-]{10,})")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _rel(p: Path) -> str:
    """Display path, tolerant of a redirected box (tests point it at /tmp)."""
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return str(p)


def _write(p: Path, doc: dict) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2) + "\n")
    return p


def drive_file_id(url_or_id: str) -> str | None:
    """Pull the file id out of any of Drive's URL shapes, or accept a bare id."""
    s = (url_or_id or "").strip()
    if not s:
        return None
    m = _FILE_ID.search(s)
    if m:
        return m.group(1) or m.group(2)
    # A bare id. Real Drive ids are long and mix letters with digits, so
    # require both — otherwise ordinary words like "not-a-link" sail through
    # and we write a response pointing at nothing.
    if (re.fullmatch(r"[A-Za-z0-9_-]{20,}", s)
            and re.search(r"[A-Za-z]", s) and re.search(r"\d", s)):
        return s
    return None


def new_id(kind: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{kind}-{stamp}"


# ------------------------------------------------------------------ commands
def cmd_request(a) -> int:
    rid = a.id or new_id(a.kind)
    if (REQ / f"{rid}.json").exists():
        print(f"refusing to overwrite existing request {rid}", file=sys.stderr)
        return 2
    doc = {
        "id": rid,
        "created_at": _now(),
        "from": a.sender,
        "to": a.recipient,
        "kind": a.kind,
        "brief": a.brief,
        "purpose": a.purpose or "",
        "constraints": {"aspect": a.aspect, "style": a.style},
    }
    p = _write(REQ / f"{rid}.json", doc)
    print(f"asked for {a.kind}: {rid}\n  {a.brief}\n  -> {_rel(p)}")
    if a.push:
        _git_push([p], f"exchange: request {rid}")
    return 0


def cmd_list(a) -> int:
    reqs = sorted(REQ.glob("*.json")) if REQ.exists() else []
    if not reqs:
        print("nothing in the box")
        return 0
    for p in reqs:
        d = _read(p) or {}
        rid = d.get("id", p.stem)
        answered = (RES / f"{rid}.json").exists()
        if answered and not a.all:
            continue
        mark = "ANSWERED" if answered else "open    "
        print(f"{mark}  {rid}  {str(d.get('brief',''))[:60]}")
    return 0


def cmd_show(a) -> int:
    req = _read(REQ / f"{a.id}.json")
    if req is None:
        print(f"no such request: {a.id}", file=sys.stderr)
        return 2
    print(json.dumps(req, indent=2))
    res = _read(RES / f"{a.id}.json")
    print("\n-- response --")
    print(json.dumps(res, indent=2) if res else "(still open)")
    return 0


def cmd_respond(a) -> int:
    if not (REQ / f"{a.id}.json").exists():
        print(f"no such request: {a.id}", file=sys.stderr)
        return 2
    fid = drive_file_id(a.drive_url)
    if not fid:
        print("could not find a Drive file id in that link — pass the share "
              "URL or the bare file id", file=sys.stderr)
        return 2
    doc = {
        "id": a.id,
        "answered_at": _now(),
        "by": a.sender,
        "drive_url": a.drive_url,
        "drive_file_id": fid,
        "filename": a.filename or "",
        "notes": a.notes or "",
    }
    p = _write(RES / f"{a.id}.json", doc)
    print(f"answered {a.id} -> {_rel(p)}  (file {fid})")
    if a.push:
        _git_push([p], f"exchange: response {a.id}")
    return 0


def cmd_fetch(a) -> int:
    res = _read(RES / f"{a.id}.json")
    if res is None:
        print(f"{a.id} has no response yet", file=sys.stderr)
        return 1
    fid = res.get("drive_file_id") or drive_file_id(res.get("drive_url", ""))
    if not fid:
        print("response has no usable Drive file id", file=sys.stderr)
        return 2
    dest = Path(a.out) if a.out else (
        CACHE / f"{a.id}_{res.get('filename') or 'asset'}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://drive.google.com/uc?export=download&id={fid}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=60) as r:
            head = r.read(400_000_000 if a.big else 80_000_000)
            ctype = r.headers.get("Content-Type", "")
    except Exception as e:  # noqa: BLE001
        print(f"could not download {fid}: {str(e)[:120]}", file=sys.stderr)
        return 1
    # Drive hands back an HTML interstitial when a file is not link-shared
    if head[:15].lstrip().lower().startswith(b"<!doctype") or \
            "text/html" in ctype:
        print("Drive returned a web page, not the file — it is almost "
              "certainly not shared as 'anyone with the link can view'.",
              file=sys.stderr)
        return 1
    dest.write_bytes(head)
    print(f"{a.id}: {len(head):,} bytes -> {dest}")
    return 0


# ------------------------------------------------------------------- plumbing
def _git_push(paths: list[Path], msg: str) -> None:
    try:
        subprocess.run(["git", "add", *[str(p) for p in paths]],
                       cwd=REPO, check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=REPO, check=True)
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                cwd=REPO, capture_output=True, text=True
                                ).stdout.strip()
        subprocess.run(["git", "push", "-u", "origin", branch], cwd=REPO,
                       check=True)
        print(f"pushed to {branch}")
    except subprocess.CalledProcessError as e:
        print(f"git step failed ({e}) — the file is written, push it yourself",
              file=sys.stderr)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("request", help="ask the other side for something")
    r.add_argument("--brief", required=True, help="what to make")
    r.add_argument("--purpose", default="", help="why we want it")
    r.add_argument("--kind", default="image")
    r.add_argument("--aspect", default="16:9")
    r.add_argument("--style", default="photographic, no text in frame")
    r.add_argument("--id", default=None)
    r.add_argument("--sender", default="github")
    r.add_argument("--recipient", default="chatgpt")
    r.add_argument("--push", action="store_true")
    r.set_defaults(fn=cmd_request)

    l = sub.add_parser("list", help="what is still open")
    l.add_argument("--all", action="store_true")
    l.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="one exchange in full")
    s.add_argument("id")
    s.set_defaults(fn=cmd_show)

    p = sub.add_parser("respond", help="point a request at a Drive file")
    p.add_argument("id")
    p.add_argument("--drive-url", required=True, help="share link or file id")
    p.add_argument("--filename", default="")
    p.add_argument("--notes", default="")
    p.add_argument("--sender", default="chatgpt")
    p.add_argument("--push", action="store_true")
    p.set_defaults(fn=cmd_respond)

    f = sub.add_parser("fetch", help="pull the answered asset into cache/")
    f.add_argument("id")
    f.add_argument("--out", default=None)
    f.add_argument("--big", action="store_true", help="allow >80MB")
    f.set_defaults(fn=cmd_fetch)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
