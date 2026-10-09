#!/usr/bin/env python3
"""Which streamers is the Twitch channel MISSING?

Operator, 2026-10-09: *"I feel like we might be missing some other ones. I
just don't know. I don't watch streams like that."* Nobody here watches
streams, so ask Twitch: the most-viewed English clips of the last N days in
the top categories (plus Just Chatting), totalled per broadcaster, minus
everyone already in `capture.sources.twitch`. Prints a table; changes
nothing. Run by the manual `twitch-roster-scout.yml`.

    python scripts/twitch_roster_scout.py --days 30 --games 25
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from third_capture import clip_edit  # noqa: E402

JUST_CHATTING = "509658"
HELIX = "https://api.twitch.tv/helix"


def tally(clips: list[dict], have: set[str]) -> list[dict]:
    """Per-broadcaster clip views, English only, minus the roster; best
    first. A streamer counts by their total and their best clip."""
    by: dict[str, dict] = {}
    for c in clips:
        if str(c.get("language", "en")).lower()[:2] != "en":
            continue
        bid = str(c.get("broadcaster_id") or "")
        if not bid:
            continue
        r = by.setdefault(bid, {"id": bid,
                                "name": c.get("broadcaster_name", ""),
                                "views": 0, "clips": 0, "best": 0,
                                "best_title": "", "games": set()})
        v = int(c.get("view_count") or 0)
        r["views"] += v
        r["clips"] += 1
        if v > r["best"]:
            r["best"], r["best_title"] = v, c.get("title", "")
        if c.get("game"):
            r["games"].add(c["game"])
    out = [r for r in by.values()
           if str(r["name"]).lower() not in have]
    return sorted(out, key=lambda r: -r["views"])


def _get(path, params):
    import requests
    r = requests.get(f"{HELIX}/{path}", params=params,
                     headers=clip_edit._helix_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--games", type=int, default=25)
    ap.add_argument("--show", type=int, default=40)
    a = ap.parse_args(argv)
    if not clip_edit._helix_creds():
        print("TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET not set")
        return 1
    spec = json.loads((ROOT / "state" / "third_packages" /
                       "default_clip.json").read_text())["capture"]
    have = {s.lower().rstrip("_") for s in spec["sources"]["twitch"]}
    have |= {s.lower() for s in spec["sources"]["twitch"]}
    games = {JUST_CHATTING: "Just Chatting"}
    for g in _get("games/top", {"first": a.games}).get("data", []):
        games[g["id"]] = g["name"]
    since = (datetime.now(timezone.utc) - timedelta(days=a.days)
             ).strftime("%Y-%m-%dT%H:%M:%SZ")
    clips = []
    for gid, gname in games.items():
        try:
            d = _get("clips", {"game_id": gid, "first": 100,
                               "started_at": since})
        except Exception as e:  # noqa: BLE001
            print(f"  {gname}: {type(e).__name__}")
            continue
        for c in d.get("data", []):
            c["game"] = gname
        clips += d.get("data", [])
        print(f"  {gname}: {len(d.get('data', []))} clips", flush=True)
    rows = tally(clips, have)
    ids = [r["id"] for r in rows[:a.show]]
    logins = {}
    for i in range(0, len(ids), 100):
        for u in _get("users", [("id", x) for x in ids[i:i + 100]]
                      ).get("data", []):
            logins[u["id"]] = u["login"]
    print(f"\n## Not on our list: top {a.show} by English clip views, "
          f"last {a.days} days ({len(clips)} clips, {len(games)} categories)")
    print("| login | clip views | clips | best clip | categories |")
    print("|---|---|---|---|---|")
    for r in rows[:a.show]:
        login = logins.get(r["id"], r["name"])
        if login.lower() in have:
            continue
        print(f"| {login} | {r['views']:,} | {r['clips']} | "
              f"{r['best']:,} \"{r['best_title'][:50]}\" | "
              f"{', '.join(sorted(r['games']))[:60]} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
