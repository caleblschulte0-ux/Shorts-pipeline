#!/usr/bin/env python3
"""Set a YouTube channel's description (its "bio").

Operator, 2026-11-05, of Baller Bro: *"can you change my bio on my YouTube
channel to like something more fitting?"* The channel's own token already
carries the broad `youtube` scope, which `channels.update` takes.

`brandingSettings.channel` is replaced WHOLE by an update, so the run reads
it first and changes only `description`; the keywords, country and
everything else go back as they were. A dry run prints the old and new
text and changes nothing.

    python scripts/channel_about.py --channel trending --text "..." --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: YouTube's limit, and the two characters it refuses in a description.
MAX_CHARS = 1000


def problems(text: str) -> list[str]:
    out = []
    if not text.strip():
        out.append("empty")
    if len(text) > MAX_CHARS:
        out.append(f"{len(text)} characters (max {MAX_CHARS})")
    if "<" in text or ">" in text:
        out.append("YouTube refuses < and > in a description")
    return out


def token_slug(cid: str) -> str:
    """trending is the original token (`YOUTUBE_TOKEN_JSON`)."""
    return "" if cid == "trending" else cid


def with_description(branding: dict, text: str) -> dict:
    """The channel's branding with only its description changed."""
    ch = dict((branding or {}).get("channel") or {})
    ch["description"] = text
    return {"channel": ch}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    text = a.text.replace("\\n", "\n").strip()
    bad = problems(text)
    if bad:
        print(f"refused: {'; '.join(bad)}")
        return 2
    from googleapiclient.discovery import build
    from shared.uploaders import YouTubeUploader
    creds = YouTubeUploader(token_slug(a.channel))._credentials()
    svc = build("youtube", "v3", credentials=creds)
    items = svc.channels().list(part="snippet,brandingSettings",
                                mine=True).execute().get("items") or []
    if not items:
        print("no channel for this token")
        return 1
    me = items[0]
    print(f"channel: {me['snippet'].get('title')} ({me['id']})")
    print("before:\n" + (me["snippet"].get("description") or "(empty)"))
    print("after:\n" + text)
    if a.dry_run:
        print("dry run: nothing changed")
        return 0
    body = {"id": me["id"],
            "brandingSettings": with_description(me.get("brandingSettings"),
                                                 text)}
    svc.channels().update(part="brandingSettings", body=body).execute()
    got = svc.channels().list(part="snippet", id=me["id"]).execute()
    now = (got.get("items") or [{}])[0].get("snippet", {}).get("description")
    print("saved" if (now or "").strip() == text else
          f"saved, but YouTube reads back: {now!r}")
    print(json.dumps({"channel": a.channel, "id": me["id"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
