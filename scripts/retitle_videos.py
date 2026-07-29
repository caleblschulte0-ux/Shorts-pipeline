#!/usr/bin/env python3
"""Retitle already-uploaded YouTube videos through the channel's title floor.

Built for 2026-07-29, when four third-channel clips uploaded with the
clipper's raw hype as their public titles ("WWWW", "w max") because both
author brains were down. They were scheduled, not yet public, so the titles
were still fixable in place.

A new title comes from the real author brain, given the clip's transcript
(re-transcribed from source with --retranscribe when the ledger is gone).
If the brain is unavailable it falls to author.fallback_title(), which
makes no specific claim rather than guessing at one.

    python scripts/retitle_videos.py --channel third            # dry run
    python scripts/retitle_videos.py --channel third --apply

Without --apply nothing is written: it prints the old -> new mapping so a
human can look before anything changes on the channel. On --apply it also
records the new titles in the posted log, which must be committed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOGS = {"third": "state/third_posted_log.json",
        "explainer": "state/explainer_posted_log.json",
        "daily": "state/posted_log.json"}


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _vid_id(url: str) -> str:
    return (url or "").rstrip("/").split("/")[-1].split("?")[0]


def _candidates(channel: str, date_prefix: str) -> list[dict]:
    """Posted-log entries for the day whose recorded title is low-signal."""
    from third_capture import author
    log = json.loads((ROOT / LOGS[channel]).read_text())["posted"]
    out = []
    for slug, v in log.items():
        if v.get("qa_rejected") or not v.get("url"):
            continue
        if date_prefix and not str(v.get("ts", "")).startswith(date_prefix):
            continue
        title = v.get("title", "")
        if not author.title_is_low_signal(title):
            continue
        out.append({"slug": slug, "vid": _vid_id(v["url"]),
                    "old": title, "streamer": v.get("streamer", ""),
                    "url": v["url"], "source_url": v.get("source_url", "")})
    return out


def _transcript_for(slug: str) -> str:
    """The recorded transcript for a slug, if its ledger survived."""
    for p in (ROOT / "output" / "third").glob(f"{slug}.ledger.json"):
        try:
            led = json.loads(p.read_text())
            return " ".join(w.get("w", "") for w in (led.get("words") or []))
        except Exception:  # noqa: BLE001
            return ""
    return ""


def _transcript_from_source(url: str, work: Path, model: str = "small") -> str:
    """Re-fetch and re-transcribe the source clip.

    Renders die with the runner, so by the time anyone retitles, the ledger
    is usually gone and every video would collapse to the same neutral line
    — three identical titles in one day is its own kind of bad. Going back
    to the source keeps each title specific and, as ever, quotes only what
    was actually said. Best-effort: returns "" on any failure."""
    from third_capture import clip_edit
    try:
        info = clip_edit.download(url, work)
        words = clip_edit.transcribe_words(Path(info["path"]), model)
        return " ".join(w.get("w", "") for w in (words or []))
    except Exception as e:  # noqa: BLE001
        print(f"[retitle] re-transcribe failed for {url}: {str(e)[:120]}",
              file=sys.stderr)
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="third", choices=sorted(LOGS))
    ap.add_argument("--date", default="",
                    help="only entries whose ts starts with this (YYYY-MM-DD)")
    ap.add_argument("--apply", action="store_true",
                    help="actually write to YouTube (default: dry run)")
    ap.add_argument("--retranscribe", action="store_true",
                    help="re-fetch the source clip when the ledger is gone, "
                         "so titles stay specific instead of all collapsing "
                         "to the same neutral line")
    a = ap.parse_args()

    from third_capture import author
    rows = _candidates(a.channel, a.date)
    if not rows:
        print(f"[retitle] nothing low-signal on {a.channel} "
              f"{a.date or '(all dates)'} — nothing to do")
        return 0

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        for r in rows:
            tr = _transcript_for(r["slug"])
            if not tr and a.retranscribe and r["source_url"]:
                tr = _transcript_from_source(r["source_url"], Path(td))
            # With a transcript in hand, ask the real author brain — that is
            # the only thing that can pick the INTERESTING moment out of a
            # transcript. It was down during the original upload; by the time
            # anyone retitles it usually is not. fallback_title is the floor
            # if it is still down.
            meta = None
            if tr:
                try:
                    meta = author.author_package(
                        r["streamer"], r["old"], tr, 0)
                except Exception as e:  # noqa: BLE001
                    print(f"[retitle] authoring failed for {r['vid']}: "
                          f"{str(e)[:120]}", file=sys.stderr)
            if meta and meta.get("title"):
                r["new"], r["sourced"] = meta["title"], "authored"
            else:
                r["new"] = author.fallback_title(r["streamer"], r["old"], tr)
                r["sourced"] = "neutral"

    if all(r["sourced"] == "neutral" for r in rows):
        print("::warning::[retitle] every title is a neutral fallback — the "
              "author brain is still down; these are safe but generic",
              flush=True)

    print(f"[retitle] {len(rows)} low-signal title(s) on {a.channel}:")
    for r in rows:
        print(f"  {r['vid']}  {r['old']!r}\n            -> {r['new']!r} "
              f"[{r['sourced']}]")
    if not a.apply:
        print("\n[retitle] DRY RUN — pass --apply to write these to YouTube")
        return 0

    from uploaders import YouTubeUploader
    svc = YouTubeUploader(channel=a.channel)._service()
    bad = 0
    for r in rows:
        try:
            # snippet updates REPLACE the resource, so read the live snippet
            # and change only the title — categoryId is required on write.
            cur = svc.videos().list(part="snippet", id=r["vid"]).execute()
            items = cur.get("items") or []
            if not items:
                print(f"[retitle] {r['vid']} not found — skipped",
                      file=sys.stderr)
                bad += 1
                continue
            snip = items[0]["snippet"]
            snip["title"] = r["new"]
            svc.videos().update(
                part="snippet", body={"id": r["vid"], "snippet": snip}
            ).execute()
            r["written"] = True
            r["at"] = _now()
            print(f"RETITLED {r['vid']} -> {r['new']!r}")
        except Exception as e:  # noqa: BLE001
            print(f"[retitle] failed for {r['vid']}: {str(e)[:160]}",
                  file=sys.stderr)
            print(f"MANUAL https://studio.youtube.com/video/{r['vid']}/edit")
            bad += 1
            r["written"] = False
    _sync_log(a.channel, [r for r in rows if r.get("written")])
    print(f"[retitle] done — {len(rows) - bad} updated, {bad} need a human")
    return 0


def _sync_log(channel: str, rows: list[dict]) -> None:
    """Record the new titles in the posted log.

    Without this the log keeps the hype title while YouTube shows the new
    one: a later run would find the entry low-signal and retitle it AGAIN
    (churning a live title), and the analytics loop would correlate
    retention against a title nobody ever saw. `title_original` keeps what
    actually shipped first, so the record stays honest about the repair.

    Only the title fields are touched — the log is append-only dedupe
    state and no entry is ever removed or rekeyed."""
    if not rows:
        return
    p = ROOT / LOGS[channel]
    d = json.loads(p.read_text())
    n = 0
    for r in rows:
        e = d["posted"].get(r["slug"])
        if not e or e.get("title") == r["new"]:
            continue
        e.setdefault("title_original", e.get("title", ""))
        e["title"] = r["new"]
        e["retitled_at"] = r.get("at", "")
        n += 1
    # indent=2 + default ensure_ascii, matching how the pipeline writes it —
    # anything else reformats the whole file and churns the diff.
    p.write_text(json.dumps(d, indent=2) + "\n")
    print(f"[retitle] posted log updated for {n} entr(ies) — commit it so "
          f"the next run does not retitle them again")


if __name__ == "__main__":
    sys.exit(main())
