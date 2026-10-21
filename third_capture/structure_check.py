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
# the weaker clips opened on these and reached the point 15s+ later
FILLER = re.compile(
    r"^(?:um+|uh+|so+|okay so|ok so|alright so|anyway[s]?|you know what|"
    r"let me (?:tell|explain)|so basically|basically|listen)\b", re.I)


def _words(led: dict) -> list[dict]:
    return sorted((w for w in led.get("final_words") or []
                   if "s" in w and "e" in w), key=lambda w: float(w["s"]))


def opening_line(led: dict, n: int = 8) -> str:
    return " ".join(str(w["w"]).strip() for w in _words(led)[:n])


def check(led: dict, proven_source: str = "") -> list[str]:
    """The cut's measured defects. `led` is `story.render_story`'s ledger
    (final_words on the cut's own clock, beats with source_id and their
    place on it, duration_s); `proven_source` is the source_id of the clip
    the audience picked."""
    out: list[str] = []
    dur = float(led.get("duration_s") or 0.0)
    ws = _words(led)
    if not MIN_S <= dur <= MAX_S:
        out.append(f"length {dur:.0f}s outside {MIN_S:.0f}-{MAX_S:.0f}s")
    if not ws:
        return out + ["nobody speaks"]
    if float(ws[0]["s"]) > OPEN_BY_S:
        out.append(f"opens on {float(ws[0]['s']):.1f}s of silence")
    if FILLER.match(opening_line(led)):
        out.append(f"opens on filler: {opening_line(led)!r}")
    gaps = [(float(b["s"]) - float(a["e"]), float(a["e"]))
            for a, b in zip(ws, ws[1:])]
    gaps.append((dur - float(ws[-1]["e"]), float(ws[-1]["e"])))
    for g, at in gaps[:-1]:
        if g > MAX_GAP_S:
            out.append(f"{g:.1f}s of dead air at {at:.0f}s")
            break
    last = str(ws[-1]["w"]).rstrip("\"'”’)")
    if not last.endswith((".", "!", "?")) and gaps[-1][0] < 0.35:
        out.append(f"ends mid-sentence on {ws[-1]['w']!r}")
    if proven_source:
        mine = [b for b in led.get("beats") or []
                if b.get("source_id") == proven_source]
        if not mine:
            out.append("the moment the audience picked is not in the cut")
        else:
            end = max(float(b.get("out_end", dur)) for b in mine)
            if dur - end > TAIL_AFTER_PROVEN_S:
                out.append(f"trails {dur - end:.0f}s past the picked moment")
    return out
