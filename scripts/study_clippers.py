"""Study a clip channel that WORKS: what its best shorts are, and what is in them.

Operator, 2026-10-18, of the Twitch channel's stories: *"does this thing know
what a good clip is? What's it basing that off of?"* and *"go watch, like,
Stable Ronaldo. The clips he posts, those are good clips. He's good at, like,
putting a story together."* Our posted log could only say what OUR clips
earned. This reads a channel the audience already rewards.

For each channel (an @handle or a UC... id) it lists every upload through the
YouTube Data API (`YOUTUBE_API_KEY`, ~1 unit a page, no search calls), keeps
the shorts, and ranks them by views. The TOP `--top` and the BOTTOM `--bottom`
of the shorts old enough to judge are fetched through `funnel/yt_convert`
(YouTube refuses yt-dlp from runners), transcribed with word times, and cut
into a one-frame-a-second contact sheet. Everything lands in `--out`:
`index.json` (every short's numbers, the studied ones' transcripts) and a
`<id>.jpg` sheet per studied short.

No brain is called: the point is evidence a person (or a session) reads, and
it spends nothing on the Claude subscription. It never uploads anything.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

API = "https://www.googleapis.com/youtube/v3/"
SHORT_MAX_S = 180
MATURE_DAYS = 7
MAX_PAGES = 20          # 1,000 uploads per channel


def _get(path: str, **q) -> dict:
    q["key"] = os.environ["YOUTUBE_API_KEY"]
    url = API + path + "?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def iso_seconds(d: str) -> int:
    """`PT1M5S` -> 65."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    dd, h, mi, s = (int(x or 0) for x in m.groups())
    return dd * 86400 + h * 3600 + mi * 60 + s


def channel(ref: str) -> dict | None:
    q = {"part": "snippet,statistics,contentDetails"}
    if ref.startswith("UC"):
        q["id"] = ref
    else:
        q["forHandle"] = ref if ref.startswith("@") else "@" + ref
    items = _get("channels", **q).get("items") or []
    return items[0] if items else None


def uploads(ch: dict) -> list[dict]:
    pl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    for _ in range(MAX_PAGES):
        q = {"part": "contentDetails", "playlistId": pl, "maxResults": 50}
        if token:
            q["pageToken"] = token
        j = _get("playlistItems", **q)
        ids += [i["contentDetails"]["videoId"] for i in j.get("items") or []]
        token = j.get("nextPageToken")
        if not token:
            break
    return videos(ids)


def videos(ids: list[str]) -> list[dict]:
    now = datetime.now(timezone.utc)
    out = []
    for i in range(0, len(ids), 50):
        j = _get("videos", part="snippet,statistics,contentDetails",
                 id=",".join(ids[i:i + 50]))
        for v in j.get("items") or []:
            sec = iso_seconds(v["contentDetails"].get("duration", ""))
            pub = datetime.fromisoformat(
                v["snippet"]["publishedAt"].replace("Z", "+00:00"))
            st = v.get("statistics") or {}
            out.append({
                "id": v["id"], "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"],
                "age_days": round((now - pub).total_seconds() / 86400, 1),
                "seconds": sec, "views": int(st.get("viewCount") or 0),
                "likes": int(st.get("likeCount") or 0),
                "comments": int(st.get("commentCount") or 0),
                "channel": v["snippet"].get("channelTitle", ""),
                "channel_id": v["snippet"].get("channelId", ""),
                "description": (v["snippet"].get("description") or "")[:300],
            })
    return out


def search(query: str, pages: int = 2) -> list[dict]:
    """The most-viewed short videos ANYONE posted for `query` — where a
    streamer's best clips actually live is usually other people's channels.
    100 quota units a page."""
    ids, token = [], None
    for _ in range(pages):
        q = {"part": "id", "type": "video", "q": query, "order": "viewCount",
             "videoDuration": "short", "maxResults": 50}
        if token:
            q["pageToken"] = token
        j = _get("search", **q)
        ids += [i["id"]["videoId"] for i in j.get("items") or []]
        token = j.get("nextPageToken")
        if not token:
            break
    return videos(ids)


def pick_studied(ranked: list[dict], top: int, bottom: int) -> list[dict]:
    """The best `top` and the worst `bottom`, never the same short twice."""
    best = ranked[:top]
    rest = ranked[len(best):]
    return best + (rest[-bottom:] if bottom else [])


def contact_sheet(video: Path, out: Path, cols: int = 6) -> bool:
    """One frame a second, tiled, each 180px wide, with its second burnt in."""
    vf = (f"fps=1,scale=180:-2,drawtext=fontfile=/usr/share/fonts/truetype/"
          f"dejavu/DejaVuSans-Bold.ttf:text='%{{pts\\:gmtime\\:0\\:%M\\\\\\:%S}}'"
          f":x=4:y=4:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,"
          f"tile={cols}x12")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video),
                        "-vf", vf, "-frames:v", "1", "-q:v", "4", str(out)],
                       capture_output=True, timeout=300)
    return r.returncode == 0 and out.exists()


def study(video_meta: dict, out: Path) -> dict:
    from funnel import yt_convert
    from third_capture import clip_edit
    vid = video_meta["id"]
    mp4 = out / "src" / f"{vid}.mp4"
    # one dropped connection marks a converter dead for the whole run;
    # the 2026-10-21 study lost 8 of 16 clips to a single loader.to drop
    yt_convert._DEAD.clear()
    got = yt_convert.fetch(f"https://www.youtube.com/shorts/{vid}", mp4,
                           max_s=SHORT_MAX_S + 5)
    if not got:
        return {**video_meta, "fetched": False}
    words = []
    try:
        words = clip_edit.transcribe_words(mp4)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::transcribe {vid}: {e}", flush=True)
    lines = transcript_lines(words)
    sheet = contact_sheet(mp4, out / f"{vid}.jpg")
    return {**video_meta, "fetched": True, "via": got.get("via"),
            "transcript": lines, "sheet": f"{vid}.jpg" if sheet else None}


RUBRICS = ("narrative", "audience")


def judge(v: dict, out: Path) -> dict:
    """Our own story critic (`story_director.review_rough_cut`, the gate a
    story must clear at 80) on a video whose real views we know, once per
    rubric. If a rubric cannot rank a 91M-view clip above a 9-view one, its
    score is not evidence of a good story and no amount of tuning the cuts
    toward it will help."""
    from third_capture import story_director
    edl = {"premise": v["title"], "central_question": "",
           "structure": "single moment",
           "beats": [{"source_id": v["id"], "start": 0.0,
                      "end": float(v["seconds"]), "role": "whole",
                      "purpose": "the posted short, as published",
                      "context_overlay": ""}]}
    sheet = out / v["sheet"] if v.get("sheet") else None
    verdicts = {}
    for rubric in RUBRICS:
        try:
            r = story_director.review_rough_cut(
                edl, "\n".join(v.get("transcript") or []),
                str(sheet) if sheet else None, float(v["seconds"]),
                rubric=rubric)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::judge {v['id']} {rubric}: {e}", flush=True)
            continue
        verdicts[rubric] = r
        print(f"[judge] {rubric:9} {v['views']:>10} views  score "
              f"{r.get('story_score')} publish={r.get('publish')}  "
              f"{v['title'][:50]!r}", flush=True)
    return {**v, "critic": verdicts.get("narrative"), "critics": verdicts}


def spearman(a: list[float], b: list[float]) -> float | None:
    """Rank correlation; None under three pairs."""
    if len(a) < 3:
        return None

    def ranks(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        for k, i in enumerate(order):
            r[i] = float(k)
        return r
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra)
           * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return round(num / den, 3) if den else None


def calibration(studied: list[dict], rubric: str = "narrative") -> dict:
    """How one rubric's scores line up with the views the audience gave:
    its rank correlation with views, and how often it would publish each
    group (top = known winners, bottom/ours = known losers)."""
    def verdict(v):
        return (v.get("critics") or {}).get(rubric) or (
            v.get("critic") if rubric == "narrative" else None)
    scored = [v for v in studied
              if (verdict(v) or {}).get("story_score", -1) >= 0]
    groups = {}
    for v in scored:
        g = groups.setdefault(v.get("group", "?"), [0, 0])
        g[0] += 1
        g[1] += bool(verdict(v).get("publish"))
    return {"judged": len(scored),
            "would_publish": sum(p for _, p in groups.values()),
            "publish_by_group": {k: f"{p}/{n}" for k, (n, p)
                                 in sorted(groups.items())},
            "score_vs_views": spearman(
                [verdict(v)["story_score"] for v in scored],
                [v["views"] for v in scored])}


def transcript_lines(words: list[dict]) -> list[str]:
    """clip_edit's [{w, s, e}] words -> "[  3.2] a line of speech" lines."""
    lines, cur, start = [], [], None
    for w in words:
        if start is None:
            start = w.get("s", 0)
        cur.append(str(w.get("w", "")).strip())
        if len(cur) >= 12 or str(cur[-1]).endswith((".", "?", "!")):
            lines.append(f"[{start:5.1f}] " + " ".join(cur))
            cur, start = [], None
    if cur:
        lines.append(f"[{start or 0:5.1f}] " + " ".join(cur))
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channels", default="")
    ap.add_argument("--search", default="",
                    help="also study the most-viewed shorts anyone posted "
                         "for these words (comma-separated queries)")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--bottom", type=int, default=4)
    ap.add_argument("--out", default="study")
    ap.add_argument("--ids", default="",
                    help="also study these video ids (e.g. our own worst "
                         "posts, as known losers)")
    ap.add_argument("--ids-group", default="ours")
    ap.add_argument("--judge", action="store_true",
                    help="also run our story critic on each studied short")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {"generated": datetime.now(timezone.utc).isoformat(),
              "channels": []}
    for ref in [c.strip() for c in a.channels.split(",") if c.strip()]:
        ch = channel(ref)
        if not ch:
            print(f"::warning::no channel for {ref}", flush=True)
            report["channels"].append({"ref": ref, "found": False})
            continue
        vids = uploads(ch)
        shorts = sorted((v for v in vids if 0 < v["seconds"] <= SHORT_MAX_S),
                        key=lambda v: -v["views"])
        mature = [v for v in shorts if v["age_days"] >= MATURE_DAYS]
        pick = pick_studied(mature, a.top, a.bottom)
        print(f"[study] {ref}: {len(vids)} uploads, {len(shorts)} shorts, "
              f"studying {len(pick)}", flush=True)
        studied = []
        for rank, v in enumerate(pick):
            v = {**v, "group": "top" if rank < a.top else "bottom"}
            studied.append(study(v, out))
        if a.judge:
            studied = [judge(v, out) if v.get("fetched") else v
                       for v in studied]
        report["channels"].append({
            "ref": ref, "found": True, "title": ch["snippet"]["title"],
            "subscribers": int((ch.get("statistics") or {})
                               .get("subscriberCount") or 0),
            "uploads": len(vids), "shorts": shorts, "studied": studied})
        (out / "index.json").write_text(json.dumps(report, indent=1))
    for query in [q.strip() for q in a.search.split(",") if q.strip()]:
        found = sorted((v for v in search(query)
                        if 0 < v["seconds"] <= SHORT_MAX_S),
                       key=lambda v: -v["views"])
        mature = [v for v in found if v["age_days"] >= MATURE_DAYS]
        pick = pick_studied(mature, a.top, a.bottom)
        print(f"[study] search {query!r}: {len(found)} shorts, studying "
              f"{len(pick)}", flush=True)
        studied = [study({**v, "group": "top" if i < a.top else "bottom"}, out)
                   for i, v in enumerate(pick)]
        if a.judge:
            studied = [judge(v, out) if v.get("fetched") else v
                       for v in studied]
        entry = {"query": query, "shorts": found, "studied": studied}
        report.setdefault("searches", []).append(entry)
        (out / "index.json").write_text(json.dumps(report, indent=1))
    if a.ids:
        # known losers with real views: our own posts, or any list of ids
        ids = [i.strip() for i in a.ids.split(",") if i.strip()]
        theirs = [{**v, "group": a.ids_group}
                  for v in sorted(videos(ids), key=lambda v: -v["views"])
                  if 0 < v["seconds"] <= SHORT_MAX_S]
        print(f"[study] {len(theirs)} listed shorts", flush=True)
        studied = [study(v, out) for v in theirs]
        if a.judge:
            studied = [judge(v, out) if v.get("fetched") else v
                       for v in studied]
        report["listed"] = {"group": a.ids_group, "studied": studied}
    if a.judge:
        every = [v for e in report.get("searches", []) for v in e["studied"]]
        every += [v for c in report["channels"] for v in c.get("studied", [])]
        every += (report.get("listed") or {}).get("studied", [])
        report["calibration"] = {r: calibration(every, r) for r in RUBRICS}
        for r, c in report["calibration"].items():
            print(f"[judge] calibration {r}: {c}", flush=True)
        (out / "index.json").write_text(json.dumps(report, indent=1))
    (out / "index.json").write_text(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
