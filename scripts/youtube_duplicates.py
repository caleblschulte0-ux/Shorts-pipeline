#!/usr/bin/env python3
"""Find — and, when told to, remove — videos a channel has uploaded TWICE.

Operator, 2026-10-02: "why the fuck do we keep reposting the same videos?"
The channel's own analytics pull showed seven trending titles each live
under two video ids (2026-09-07 ×2, 09-27 ×3, 09-28, 09-29): every one from
two runs of the same day deciding against a ledger the other's upload had
not reached. The pipeline has been fixed twice since (claim-then-post on
09-29, a claim that must reach main on 10-02) — this script cleans up what
those days left on the channel, and is the check that it stays clean.

    python scripts/youtube_duplicates.py                 # trending, dry run
    python scripts/youtube_duplicates.py --channel explainer
    python scripts/youtube_duplicates.py --delete --yes  # remove the extras

Rules, so the cleanup can never be the next incident:
  * only EXACT title matches on ONE channel count as a duplicate;
  * the KEEPER is the copy with the most views, then the earliest published
    — the one the audience found; every other copy is an extra;
  * nothing is deleted without BOTH --delete and --yes, and the extras are
    printed first either way;
  * a token minted with only the upload scope cannot delete (YouTube needs
    the `youtube` or `youtube.force-ssl` scope); the 403 is reported with
    the re-auth it needs, never retried.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _norm(title: str) -> str:
    return " ".join((title or "").split()).casefold()


def list_uploads(svc) -> list[dict]:
    """Every video on the token's channel: id, title, publishedAt, views."""
    ch = svc.channels().list(part="contentDetails", mine=True).execute()
    items = ch.get("items") or []
    if not items:
        return []
    playlist = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    vids: list[dict] = []
    page = None
    while True:
        resp = svc.playlistItems().list(part="snippet,contentDetails",
                                        playlistId=playlist, maxResults=50,
                                        pageToken=page).execute()
        for it in resp.get("items") or []:
            sn = it.get("snippet") or {}
            vids.append({"id": it["contentDetails"]["videoId"],
                         "title": sn.get("title") or "",
                         "published_at": (it["contentDetails"].get("videoPublishedAt")
                                          or sn.get("publishedAt") or "")})
        page = resp.get("nextPageToken")
        if not page:
            break
    for k in range(0, len(vids), 50):
        batch = vids[k:k + 50]
        stats = svc.videos().list(part="statistics",
                                  id=",".join(v["id"] for v in batch)).execute()
        by_id = {x["id"]: x for x in stats.get("items") or []}
        for v in batch:
            v["views"] = int((by_id.get(v["id"], {}).get("statistics") or {})
                             .get("viewCount") or 0)
    return vids


def plan(videos: list[dict]) -> list[dict]:
    """[{title, keep: {...}, extras: [{...}]}] for every title live more
    than once. Pure: the decision is testable without a channel."""
    groups: dict[str, list[dict]] = {}
    for v in videos:
        if _norm(v.get("title")):
            groups.setdefault(_norm(v["title"]), []).append(v)
    out = []
    for key, vs in groups.items():
        if len(vs) < 2:
            continue
        ranked = sorted(vs, key=lambda v: (-int(v.get("views") or 0),
                                           v.get("published_at") or "~",
                                           v.get("id") or ""))
        out.append({"title": vs[0]["title"], "keep": ranked[0],
                    "extras": ranked[1:]})
    out.sort(key=lambda g: g["keep"].get("published_at") or "")
    return out


def _service(channel: str):
    from shared.uploaders import YouTubeUploader
    return YouTubeUploader(channel=channel)._service()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--channel", default="",
                    help='token route: "" (trending), "explainer", "third"')
    ap.add_argument("--delete", action="store_true",
                    help="remove the extra copies (needs --yes too)")
    ap.add_argument("--yes", action="store_true",
                    help="confirm the deletion")
    ap.add_argument("--json", action="store_true", help="print the plan as JSON")
    a = ap.parse_args(argv)
    svc = _service(a.channel)
    videos = list_uploads(svc)
    groups = plan(videos)
    if a.json:
        print(json.dumps(groups, indent=1))
    label = a.channel or "trending"
    print(f"[duplicates] {label}: {len(videos)} uploads, "
          f"{len(groups)} title(s) live more than once, "
          f"{sum(len(g['extras']) for g in groups)} extra cop(ies)")
    for g in groups:
        k = g["keep"]
        print(f"  {g['title']!r}")
        print(f"    keep   {k['id']}  {k.get('published_at', '')[:16]}  {k.get('views', 0)} views")
        for e in g["extras"]:
            print(f"    extra  {e['id']}  {e.get('published_at', '')[:16]}  {e.get('views', 0)} views")
    if not groups:
        return 0
    if not (a.delete and a.yes):
        print("[duplicates] dry run — pass --delete --yes to remove the extras")
        return 0
    removed, failed = 0, 0
    for g in groups:
        for e in g["extras"]:
            try:
                svc.videos().delete(id=e["id"]).execute()
                removed += 1
                print(f"[duplicates] deleted {e['id']}  {g['title']!r}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                msg = str(exc)
                hint = ""
                if "403" in msg or "insufficient" in msg.lower():
                    hint = (" — the token lacks the delete scope; re-auth with "
                            "scripts/setup_youtube.py granting "
                            "https://www.googleapis.com/auth/youtube")
                print(f"[duplicates] could not delete {e['id']}: {msg[:160]}{hint}")
    print(f"[duplicates] removed {removed}, failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
