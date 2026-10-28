"""Cut to footage of WHAT is being talked about, while the voice goes on.

Operator, 2026-10-17: *"maybe that clip can spark a couple more clips
that turns this not into just us stealing moments from the internet, but
making something of our own"* — any clip, not only a sad one.

Operator, 2026-10-17: *"when Russ is talking about KD and it's like all
sad ... show highlights of the two together"*. The author names it
(`edit.broll`: who, what the footage must show, the second it is said);
`plan` puts it on the cut's clock, `ready` finds the footage through the
SHARED finder (`funnel/find_footage.py`, checked by the brain), and
`overlay` lays it over the whole frame for its seconds. The clip's own
sound carries on under it; the mood (grey, the song) colours it too,
because it goes in under the camera and the colour.
"""
from __future__ import annotations

import re
from pathlib import Path

MAX_CUTS = 3
GAP = 4.0               # seconds between two cut-ins


def _num(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _text(v, n: int) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def parse(raw, clip_dur: float = 0.0) -> list[dict]:
    """The author's `broll` list, validated (the renderer re-plans it)."""
    out = []
    for r in (raw or [])[:4] if isinstance(raw, list) else []:
        if not isinstance(r, dict):
            continue
        who, at = _text(r.get("who"), 80), _num(r.get("at"), -1.0)
        if who and at >= 0:
            out.append({"who": who, "look": _text(r.get("look"), 90) or who,
                        "at": round(min(at, clip_dur) if clip_dur else at,
                                    2),
                        **({"said": _text(r.get("said"), 60)}
                           if r.get("said") else {})})
    return out


SNAP_S = 5.0            # how far from the author's second a mention counts
LEAD_S = 0.2            # the footage lands just as the word is said


def _tok(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9']+", str(s or "").lower())
            if len(t) >= 3]


def snap(items: list[dict], words: list[dict],
         offset: float = 0.0) -> list[dict]:
    """Each cut-in ON THE WORD that names it, or dropped (operator,
    2026-10-28: "if we're going to play a clip in the middle of a video
    that it times up right"). The author's "at" is a guess from the
    transcript; this puts it on the start of the closest word, within
    SNAP_S, that is in what the author says was `said` (else in the
    name of `who`). A cut-in with no such word near it is about nothing
    the person is saying then, and is not cut in. No transcript: as the
    author gave it. `words` are on the cut's clock, which starts at
    `offset` of the source the author's seconds are on."""
    if not words:
        return list(items or [])
    out = []
    for it in items or []:
        want = set(_tok(it.get("said"))) or set(_tok(it.get("who")))
        off = float(offset or 0.0)
        near = [w for w in words
                if abs(float(w.get("s", 0)) + off - float(it["at"])) <= SNAP_S
                and set(_tok(w.get("w"))) & want]
        if not near:
            print(f"[cut-in] {it.get('who')!r} @{it['at']}: nothing said "
                  "near it names it — not cut in", flush=True)
            continue
        w = min(near, key=lambda w: abs(float(w["s"]) + off
                                        - float(it["at"])))
        out.append({**it, "at": round(max(0.0, float(w["s"]) + off
                                          - LEAD_S), 2)})
    return out


def plan(items, dur: float, offset: float = 0.0) -> list[dict]:
    """The cut-ins this cut can carry, on the cut's clock. One said before
    the cut, in its first second, or too late to finish, is dropped."""
    from funnel.find_footage import SECS
    out: list[dict] = []
    for r in sorted(parse(items), key=lambda r: r["at"]):
        at = r["at"] - float(offset or 0.0)
        if at < 1.0 or at + SECS > dur - 0.8:
            print(f"[cut-in] {r['who']!r} @{r['at']}: outside the cut "
                  "— not cut in", flush=True)
            continue
        if any(abs(at - k["at"]) < GAP + SECS for k in out):
            print(f"[cut-in] {r['who']!r} @{r['at']}: too close to the "
                  "last — not cut in", flush=True)
            continue
        out.append({**r, "at": round(at, 2), "secs": SECS})
        if len(out) >= MAX_CUTS:
            break
    return out


def ready(items: list[dict], work: Path, title: str = "") -> list[dict]:
    """`plan` items that found footage, each with its `mp4`."""
    from funnel import find_footage
    out = []
    for it in items:
        hit = find_footage.find(it["who"], it["look"], secs=it["secs"],
                                work=work, title=title,
                                avoid=[{"url": o["url"], "from_s": o["from_s"]}
                                       for o in out])
        print(f"[cut-in] {it['who']!r} @{it['at']}: "
              f"{'cut in' if hit else 'no checked footage — not cut in'}",
              flush=True)
        if hit:
            out.append({**it, "mp4": hit["path"], "url": hit["url"],
                        "from_s": hit.get("from_s"),
                        "secs": min(it["secs"], hit.get("secs") or it["secs"])})
    return out


def overlay(cur: str, n: int, item: dict, w: int, h: int, out: str) -> str:
    """Filter fragment laying input `n` (the footage) over the whole of
    `[cur]` for the item's seconds, cut in hard. Laid out like the clip
    itself: the whole picture across the frame on a blur of itself, so
    two people side by side both stay in it."""
    a, b = item["at"], item["at"] + item["secs"]
    k = f"ci{out}"
    return (f"[{n}:v]setpts=PTS-STARTPTS+{a:.2f}/TB,setsar=1,"
            f"split=2[{k}b][{k}f];"
            f"[{k}b]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},gblur=sigma=24,eq=brightness=-0.03[{k}bd];"
            f"[{k}f]scale={w}:{h}:force_original_aspect_ratio=decrease"
            f"[{k}fs];"
            f"[{k}bd][{k}fs]overlay=(W-w)/2:(H-h)/2,format=yuv420p[{k}];"
            f"[{cur}][{k}]overlay=0:0:eof_action=pass:"
            f"enable='between(t,{a:.2f},{b:.2f})'[{out}]")
