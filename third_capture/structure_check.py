"""What a finished story cut must MEASURE, with no judge's opinion in it.

Operator, 2026-10-18: *"does this thing know what a good clip is? What's it
basing that off of?"* It did not. On 2026-10-21 both critic rubrics were run
over 16 Stable Ronaldo clips (1.8M-31M views) and 10 of this channel's
worst posts (0-7 views) (`scripts/study_clippers.py`, run 39533057981):
the narrative critic passed none of them, the audience critic passed 1 of
the 12 biggest hits and scored a 0-view post 74, and BOTH scores ran
slightly AGAINST views (rank correlation -0.26 and -0.14). A brain reading
frames and a transcript cannot say whether people will like a clip. The
only signals measured to predict views are the audience's own (a clip's
Twitch views, its r/LivestreamFail upvotes).

So in the audience arm the AUDIENCE picks the moment, the director cuts it,
and these checks hold the cut to what every viral clip in the study shares:
it opens talking, the first line is not throat-clearing, there is no dead
air, it ends on a finished sentence, it runs about as long as theirs, and
the moment the audience picked is still IN it and near the end.

`check` returns a list of problems; [] passes. Pure: no brain, no files."""
from __future__ import annotations

import re

OPEN_BY_S = 2.5        # first word on screen by then (top clips: ~2s)
MAX_GAP_S = 4.0        # silence longer than this is dead air
MIN_S, MAX_S = 18.0, 75.0   # study median 31s; Stable top 16-62s
# what the proven moment may leave after it before the cut is "trailing on"
TAIL_AFTER_PROVEN_S = 15.0
# a picture that barely changes for this long in the opening seconds is a
# still or a blank screen (2026-10-21: Jynxzi's cut opened on an idle Xbox
# screen at 0.10 mean frame difference; the talking heads that passed sat
# at 0.40 and up)
STILL_YDIF, STILL_S, OPENING_S = 0.2, 2.0, 10.0
# the weaker clips opened on these and reached the point 15s+ later
FILLER = re.compile(
    r"^(?:um+|uh+|so+|okay so|ok so|alright so|anyway[s]?|you know what|"
    r"let me (?:tell|explain)|so basically|basically|listen)\b", re.I)


def _words(led: dict) -> list[dict]:
    return sorted((w for w in led.get("final_words") or []
                   if "s" in w and "e" in w), key=lambda w: float(w["s"]))


def opening_line(led: dict, n: int = 8) -> str:
    return " ".join(str(w["w"]).strip() for w in _words(led)[:n])


def motion(mp4) -> list[tuple[float, float]]:
    """(t, YDIF) per frame of the picture above the captions (top 60%):
    how much each frame differs from the one before it. [] on failure."""
    import subprocess
    try:
        out = subprocess.run(
            ["ffmpeg", "-v", "error", "-t", f"{OPENING_S:.0f}", "-i",
             str(mp4), "-an", "-vf",
             "crop=iw:ih*0.6:0:0,signalstats,metadata=print:"
             "key=lavfi.signalstats.YDIF:file=-", "-f", "null", "-"],
            capture_output=True, text=True, timeout=120).stdout
    except Exception:  # noqa: BLE001
        return []
    rows, t = [], None
    for ln in out.splitlines():
        if "pts_time:" in ln:
            try:
                t = float(ln.split("pts_time:")[1].split()[0])
            except (IndexError, ValueError):
                t = None
        elif "YDIF=" in ln and t is not None:
            try:
                rows.append((t, float(ln.split("=", 1)[1])))
            except ValueError:
                pass
    return rows


def still_opening(rows: list[tuple[float, float]]) -> float | None:
    """When a STILL_S stretch of near-frozen picture starts inside the
    opening, or None."""
    rows = [r for r in rows if r[0] <= OPENING_S]
    for i, (t0, _) in enumerate(rows):
        win = [y for t, y in rows[i:] if t < t0 + STILL_S]
        if rows[-1][0] >= t0 + STILL_S - 0.1 and win and \
                sum(win) / len(win) < STILL_YDIF:
            return t0
    return None


def problems(led: dict, proven_source: str = "",
             frames: list[tuple[float, float]] | None = None) -> list[dict]:
    """The cut's measured defects, each as a repair the director can act
    on ({type, at, fix}, the shape `story_director.revise_edl` reads).
    `led` is `story.render_story`'s ledger (final_words on the cut's own
    clock, beats with source_id and out_start/out_end, duration_s);
    `proven_source` is the source_id of the clip the audience picked."""
    out: list[dict] = []

    def bad(at, what, fix):
        out.append({"type": "structure", "at": float(at), "what": what,
                    "fix": f"{what}: {fix}"})
    dur = float(led.get("duration_s") or 0.0)
    ws = _words(led)
    if not MIN_S <= dur <= MAX_S:
        bad(dur, f"length {dur:.0f}s outside {MIN_S:.0f}-{MAX_S:.0f}s",
            "keep the picked clip whole and only as much before it as a "
            "stranger needs; the viral clips this copies run about 30s")
    if not ws:
        bad(0, "nobody speaks", "open and end on lines that are said")
        return out
    if float(ws[0]["s"]) > OPEN_BY_S:
        bad(0, f"opens on {float(ws[0]['s']):.1f}s of silence",
            "start on the first line that states the situation")
    if FILLER.match(opening_line(led)):
        bad(0, f"opens on filler: {opening_line(led)!r}",
            "start on the line that states the situation, not the run-up")
    for a, b in zip(ws, ws[1:]):
        if float(b["s"]) - float(a["e"]) > MAX_GAP_S:
            bad(a["e"], f"{float(b['s']) - float(a['e']):.1f}s of dead air "
                f"at {float(a['e']):.0f}s", "cut the stretch nobody talks in")
            break
    last = str(ws[-1]["w"]).rstrip("\"'”’)")
    if not last.endswith((".", "!", "?")) and dur - float(ws[-1]["e"]) < 0.35:
        bad(ws[-1]["e"], f"ends mid-sentence on {ws[-1]['w']!r}",
            "end after a finished line")
    if frames:
        at = still_opening(frames)
        if at is not None:
            bad(at, f"the picture stands still for {STILL_S:.0f}s at "
                f"{at:.0f}s", "open on the part where something is "
                "happening on screen, not a still or blank screen")
    if proven_source:
        mine = [b for b in led.get("beats") or []
                if b.get("source_id") == proven_source]
        if not mine:
            bad(0, "the moment the audience picked is not in the cut",
                "the clip viewers made is the story; it must be in it")
        else:
            end = max(float(b.get("out_end", dur)) for b in mine)
            if dur - end > TAIL_AFTER_PROVEN_S:
                bad(end, f"trails {dur - end:.0f}s past the picked moment",
                    "end on the picked clip's payoff or the reaction to it")
    return out


def check(led: dict, proven_source: str = "",
          frames: list[tuple[float, float]] | None = None) -> list[str]:
    """`problems` as plain sentences; [] passes."""
    return [p["what"] for p in problems(led, proven_source, frames)]
