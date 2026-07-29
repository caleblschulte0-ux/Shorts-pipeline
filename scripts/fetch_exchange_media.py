#!/usr/bin/env python3
"""Consume ChatGPT exchange responses: download from Drive, verify, hand off.

Reads `exchange/responses/*.json` (small pointer JSONs committed by a ChatGPT
scheduled task — see exchange/README.md), downloads each referenced Drive
file, and verifies it is the exact image that was promised:

  * SHA-256 recomputed over the downloaded bytes vs the claimed hash
  * full pixel decode (not just a header parse) via Pillow
  * dimensions and a colour-count floor, so a placeholder cannot pass

Verified files land in cache/exchange/<request_id>.<ext> (gitignored) and the
path is printed for the render to consume.

    python scripts/fetch_exchange_media.py                 # all pending
    python scripts/fetch_exchange_media.py --id <req_id>   # one
    python scripts/fetch_exchange_media.py --json          # machine-readable

Exit 0 = every response usable (or nothing pending). Exit 1 = at least one
unusable response. Exit 2 = nothing to do but a response was malformed.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESPONSE_DIR = ROOT / "exchange" / "responses"
REQUEST_DIR = ROOT / "exchange" / "requests"
OUT_DIR = ROOT / "cache" / "exchange"
ANSWERED = {"fulfilled", "partial", "unsupported", "failed"}
UA = "shorts-pipeline/exchange-consumer"
MAX_BYTES = 32 * 1024 * 1024


def _drive_urls(drive: dict) -> list[str]:
    """Candidate download URLs, best first. Drive's uc? endpoint serves
    link-visible files without credentials; confirm= handles the interstitial."""
    fid = (drive.get("file_id") or "").strip()
    urls = []
    if drive.get("download_url"):
        urls.append(drive["download_url"])
    if fid:
        urls.append(f"https://drive.google.com/uc?export=download&id={fid}")
        urls.append(f"https://drive.google.com/uc?export=download&confirm=t&id={fid}")
        urls.append(f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t")
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _download(urls: list[str], timeout: int = 60) -> tuple[bytes | None, str]:
    last = "no urls to try"
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ctype = resp.headers.get("Content-Type", "")
                blob = resp.read(MAX_BYTES)
            # Drive serves an HTML interstitial/permission page instead of
            # the bytes when a file is not link-visible — detect, don't save.
            if b"<html" in blob[:2000].lower() or "text/html" in ctype:
                last = f"{url} -> HTML page, not file bytes (not link-visible?)"
                continue
            if not blob:
                last = f"{url} -> empty body"
                continue
            return blob, url
        except urllib.error.HTTPError as exc:
            last = f"{url} -> HTTP {exc.code} {exc.reason}"
        except Exception as exc:                      # noqa: BLE001
            last = f"{url} -> {type(exc).__name__}: {exc}"
    return None, last


def _verify_image(path: Path, claimed: dict) -> list[str]:
    """Full decode + sanity checks. Returns a list of problems (empty = ok)."""
    problems: list[str] = []
    try:
        from PIL import Image
    except Exception:
        return ["Pillow unavailable — cannot verify image content"]
    try:
        with Image.open(path) as im:
            fmt, w, h = im.format, im.width, im.height
            im.load()                                  # force pixel decode
            colors = im.convert("RGB").getcolors(maxcolors=65536)
    except Exception as exc:                           # noqa: BLE001
        return [f"not a decodable image: {exc}"]

    if colors is not None and len(colors) <= 8:
        problems.append(f"only {len(colors)} distinct colours — placeholder, "
                        f"not a real render")
    for key, got in (("width", w), ("height", h)):
        want = claimed.get(key)
        if want and int(want) != got:
            problems.append(f"{key} {got} != claimed {want}")
    want_fmt = (claimed.get("format") or "").lower().lstrip(".")
    if want_fmt and fmt and want_fmt not in (fmt.lower(), "jpg" if fmt.lower() == "jpeg" else fmt.lower()):
        problems.append(f"format {fmt} != claimed {want_fmt}")
    return problems


def process(resp_path: Path, *, verbose: bool = True) -> dict:
    out = {"response": str(resp_path.relative_to(ROOT)), "ok": False,
           "problems": [], "local_path": None}
    try:
        data = json.loads(resp_path.read_text())
    except Exception as exc:                           # noqa: BLE001
        out["problems"].append(f"unreadable response JSON: {exc}")
        return out

    rid = data.get("request_id") or resp_path.stem
    out["request_id"] = rid
    status = data.get("status", "?")
    out["status"] = status

    if status not in ANSWERED:
        out["problems"].append(f"unknown status {status!r}")
    if status in {"unsupported", "failed"}:
        # An honest failure is a valid response — nothing to fetch, not an error.
        out["ok"] = True
        out["note"] = data.get("notes") or data.get("note") or "reported failure"
        return out

    req_file = REQUEST_DIR / f"{rid}.json"
    if not req_file.exists():
        out["problems"].append(f"no matching request {req_file.name} — "
                               f"unrequested drop, refusing")
        return out

    drive = data.get("drive") or {}
    claimed = data.get("image") or {}
    sha_claim = (claimed.get("sha256") or "").strip().lower()
    if not sha_claim:
        out["problems"].append("image.sha256 missing — cannot verify integrity")

    urls = _drive_urls(drive)
    if not urls:
        out["problems"].append("no drive.file_id or drive.download_url")
        return out

    blob, detail = _download(urls)
    if blob is None:
        out["problems"].append(f"download failed: {detail}")
        return out
    out["source_url"] = detail
    out["bytes"] = len(blob)

    got_sha = hashlib.sha256(blob).hexdigest()
    out["sha256"] = got_sha
    if sha_claim and got_sha != sha_claim:
        out["problems"].append(f"SHA-256 MISMATCH — claimed {sha_claim[:16]}…, "
                               f"got {got_sha[:16]}… (substituted or corrupted)")
    want_bytes = claimed.get("bytes")
    if want_bytes and int(want_bytes) != len(blob):
        out["problems"].append(f"size {len(blob):,} != claimed {int(want_bytes):,}")

    ext = (claimed.get("format") or "png").lower().lstrip(".")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    local = OUT_DIR / f"{rid}.{ext}"
    tmp = local.with_suffix(local.suffix + ".part")
    tmp.write_bytes(blob)
    os.replace(tmp, local)
    out["local_path"] = str(local)

    out["problems"].extend(_verify_image(local, claimed))
    out["ok"] = not out["problems"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--id", help="only this request_id")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    pattern = f"{args.id}.json" if args.id else "*.json"
    files = sorted(Path(p) for p in glob.glob(str(RESPONSE_DIR / pattern)))
    if not files:
        msg = (f"no responses matching exchange/responses/{pattern} "
               f"— nothing to consume yet")
        print(json.dumps({"results": [], "note": msg}) if args.json else msg)
        return 0

    results = [process(f) for f in files]
    if args.json:
        print(json.dumps({"results": results}, indent=2))
    else:
        for r in results:
            tag = "OK  " if r["ok"] else "FAIL"
            print(f"{tag} {r.get('request_id', '?')}  status={r.get('status')}")
            if r.get("local_path") and r["ok"]:
                print(f"     -> {r['local_path']}  {r.get('bytes', 0):,}B  "
                      f"sha {r.get('sha256', '')[:16]}…")
            if r.get("note"):
                print(f"     note: {r['note']}")
            for p in r["problems"]:
                print(f"     - {p}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
