#!/usr/bin/env python3
"""Seed the mechanic library with HAND-AUTHORED TIER-1 exemplars.

Operator, 2026-09-21: *"it's not about a specific animation, it's building a
system that can make good per-video animations without me."* And, on the
one that worked: *"that laser one ... those were sick."* Then, on a contact
sheet of six brain-written mechanics — a dog on a track, a seesaw with a
cat, two tubes, a timeline cross — *"everything in this image should be
considered a non-chart, not a video-specific animation."*

The brain learns by few-shot copying from `data_learning/viz_mechanics.json`
(`viz_director._mechanic_examples`). As of 2026-09-21 the 60-slot library
held ZERO mechanics the judge had graded tier 1, and the one the operator
named (the fusion bolt grid) had been evicted. A brain shown only tier-2 work
writes tier-2 work; the grade loop (`grade_mechanics`) will slowly sort the
shelf, but it can only rank what exists. This script puts four tier-1
teachers on the shelf so there is something to copy from day one.

Each exemplar is one of the four data shapes the channel actually ships —
a count to compare, a quantity over time, a share of a whole, two things
side by side — and each obeys the tier-1 test from `VIZ_BRAIN.md`:

    the picture is MADE OF the subject, and the subject's own physics
    carries the number. Swap the subject and the picture has to change.

    subject-strike-grid   units of the real subject arrive one at a time
                          and the COUNT is the number ("each = 0.2 MJ")
    subject-shore-recede  the subject's own AREA tracks the series; the
                          lost ground stays outlined; a tide line breathes
    subject-drain-share   a share LEAVES the real thing: it drains out as
                          a stream and collects below, and it adds up
    subject-true-scale    two subjects at TRUE relative size, and copies of
                          the smaller one stack on it up to the bigger one

EVERY exemplar is verified BY RENDERING, here, through the same sandbox and
the same motion probe the render path uses (`viz_scene.mechanic_dry_ok`,
which ends in the reviewer's own frame detector) — on every shape in
`score_mechanics.SHAPES`, with the subject image present AND with it
missing (the offline fallback), and `--sheet` writes a contact sheet so the
frames can be LOOKED AT. A mechanic that fails any of that is not seeded.
`--write` then records them starred (never evicted), graded
`{bespoke: 3, proves_claim: 3}` so `_mechanic_examples` ranks them first,
`moves: true` so the motion band admits them, and `exemplar: true` so a
later audit can tell a hand-authored teacher from a brain-written one.
Seeding is idempotent: an entry with the same signature is updated in
place, never duplicated.

    python scripts/seed_exemplars.py                 # verify, write nothing
    python scripts/seed_exemplars.py --sheet out.png # + contact sheet
    python scripts/seed_exemplars.py --write         # verify, then seed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

LIB = REPO / "data_learning" / "viz_mechanics.json"

#: The judge's own anchors for a 3 (`showrunner_review._GRADE_PROMPT`): the
#: picture is MADE OF the subject and its physics carries the number, and a
#: viewer sees the number's meaning without reading it.
EXEMPLAR_GRADE = {"bespoke": 3, "proves_claim": 3, "kind": "bespoke",
                  "note": "hand-authored tier-1 exemplar; rendered and verified "
                          "on every shape by scripts/seed_exemplars.py"}

# ---------------------------------------------------------------------------
# The four teachers. Each `code` is the BODY the sandbox runs once per frame
# (see `viz_scene._run_mechanic_frame` for every name in scope). They are
# written the way the kit prompt asks the brain to write: no imports, no
# while, no underscores in names, every number through fmt(), every label
# through the measured text(), the ONE accent on the subject, REST for
# everything that supports it. The comments inside are part of the lesson —
# the brain copies them along with the code.
# ---------------------------------------------------------------------------

STRIKE_GRID = r'''
# TIER 1: every cell is ONE UNIT OF THE REAL SUBJECT and the COUNT is the
# number. "each = 0.2 MJ" was the fusion bolt grid; here "each = fmt(per)".
# Swap the subject and the picture changes, because the picture IS the
# subject, arriving one unit at a time. Rows are the items, strongest first.
sub = subject_image(labels[0] if n else 'laser')   # <- THIS story's subject
rows = min(n, 5)
# a clean unit per cell: 1, 2, 5 or 10 x 10^k, so the max is <= 48 cells
k = math.floor(math.log10(max(vmax, 1e-9) / 48.0))
per = 10.0 ** k
for cand in (1, 2, 5, 10):
    if vmax / (cand * 10.0 ** k) <= 48:
        per = cand * 10.0 ** k
        break
cols = 8 if rows <= 2 else (12 if rows <= 3 else 16)
cellrows = math.ceil(48 / cols)
top = RTOP + 130
band = (RBOT - 140 - top) / rows                # use the WHOLE safe box
cell = int(min((band - 80) / cellrows, (RX1 - RX0 - 220) / cols))
cell = max(cell, 24)
text('each ' + fmt(per), (RX0 + RX1) / 2, RTOP + 20, size=40, color=SUBTLE, center=True)
total = sum(min(values[i] / per, 48) for i in range(rows))
# LINEAR: a unit lands every few frames right up to the end of the beat, so
# the picture is still arriving at reveal 0.95 — an ease-out here finishes
# early and the motion probe reads the last quarter of the beat as a freeze
arrived = reveal * total                     # cells landed so far, over ALL rows
done = 0.0
for i in range(rows):
    y0 = top + i * band
    cnt = min(values[i] / per, 48)
    mine = clamp(arrived - done, 0, cnt)      # this row's landed cells
    done = done + cnt
    shown = fmt(values[i] * (mine / cnt if cnt else 1))
    text(labels[i], RX0, y0, size=40, color=TEXT)
    text(shown, RX1 - 130, y0 + 4, size=46, color=TEXT, center=True)
    gx0 = RX0
    gy0 = y0 + 66
    full = int(mine)
    for c in range(math.ceil(cnt)):
        cx = gx0 + (c % cols) * cell
        cy = gy0 + (c // cols) * cell
        if c < full:
            # LANDED: a real unit of the subject (or a solid block if the
            # image is missing — never an empty frame)
            if sub is not None:
                paste(sub, cx + 2, cy + 2, cell - 4, cell - 4)
            else:
                d.rounded_rectangle([cx + 3, cy + 3, cx + cell - 3, cy + cell - 3],
                                    radius=6, fill=rgba(HIGHLIGHT))
        elif c == full and mine - full > 0:
            # ARRIVING: the unit FLIES IN from the right edge of the frame
            # along a bolt line and lands in its slot; a last cell that is
            # only part of a unit lands as that honest fraction
            f = mine - full
            frac = min(1.0, cnt - c)          # a last cell can be a part-unit
            fx = lerp(RX1 + 60, cx, f)
            d.line([RX1 + 60, cy + cell / 2, fx + cell, cy + cell / 2],
                   fill=rgba(HIGHLIGHT, 200), width=6)
            d.ellipse([fx - 10, cy - 10, fx + cell + 10, cy + cell + 10],
                      fill=rgba(HIGHLIGHT, 150))
            if sub is not None:
                fill_image(sub, frac, fx + 2, cy + 2, cell - 4, cell - 4,
                           direction='right')
            else:
                d.rounded_rectangle([fx + 3, cy + 3, fx + 3 + (cell - 6) * frac,
                                     cy + cell - 3], radius=6, fill=rgba(HIGHLIGHT))
        else:
            # NOT YET: the slot it will land in, so the total is visible
            d.rounded_rectangle([cx + 3, cy + 3, cx + cell - 3, cy + cell - 3],
                                radius=6, outline=rgba(REST, 110), width=2)
'''

SHORE_RECEDE = r'''
# TIER 1: the subject's own AREA is the number. The picture starts at the
# first value and its shoreline recedes (or advances) through EVERY point
# of the series to the last; the ground it lost stays outlined in REST and
# a tide line breathes on the current edge. "A lake whose shoreline recedes
# to the lost area" is the judge's own anchor for a 3.
sub = subject_image('lake')                       # <- THIS story's subject
first = values[0] if n else 1.0
peak = max(vmax, 1e-9)
pos = reveal * max(n - 1, 0)                        # walk the series
i = min(int(pos), max(n - 2, 0))
t = pos - i if n > 1 else 1.0
cur = lerp(values[i], values[min(i + 1, n - 1)], t) if n > 1 else first
cx = (RX0 + RX1) / 2
cy = RTOP + 640
big = 760                                            # the peak's extent
s0 = math.sqrt(max(first, 0) / peak)                 # area, not length
s1 = math.sqrt(max(cur, 0) / peak)
w0 = big * s0
w1 = big * s1
# what there WAS: the starting extent, ghosted — the lost ground is the story
d.rounded_rectangle([cx - w0 / 2, cy - w0 / 2, cx + w0 / 2, cy + w0 / 2],
                    radius=int(w0 * 0.12), fill=rgba(REST, 60))
d.rounded_rectangle([cx - w0 / 2, cy - w0 / 2, cx + w0 / 2, cy + w0 / 2],
                    radius=int(w0 * 0.12), outline=rgba(REST, 200), width=3)
# what there IS: the subject at its current area
if sub is not None and w1 > 8:
    paste(sub, cx - w1 / 2, cy - w1 / 2, w1, w1)
elif w1 > 8:
    d.ellipse([cx - w1 / 2, cy - w1 / 2, cx + w1 / 2, cy + w1 / 2], fill=rgba(HIGHLIGHT))
# the tide line: the current edge, breathing — it is the thing that MOVES
# between adjacent frames even where the series plateaus
pts = []
for q in range(60):
    a = q / 60.0 * 2 * math.pi
    r = w1 / 2 + 10 + 9 * math.sin(6 * a + reveal * 40)
    pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
pts.append(pts[0])
d.line(pts, fill=rgba(HIGHLIGHT), width=5)
# the series under it: every point marked, the current one lit
ty = RBOT - 250
for j in range(n):
    x = lerp(RX0 + 60, RX1 - 60, j / max(n - 1, 1))
    lit = j <= pos + 1e-6
    d.ellipse([x - 9, ty - 9, x + 9, ty + 9], fill=rgba(HIGHLIGHT if lit else REST))
    text(labels[j], x, ty + 26, size=30, color=TEXT if lit else SUBTLE, center=True)
if n > 1:
    d.line([RX0 + 60, ty, RX1 - 60, ty], fill=rgba(REST, 160), width=3)
    xh = lerp(RX0 + 60, RX1 - 60, pos / max(n - 1, 1))
    d.line([RX0 + 60, ty, xh, ty], fill=rgba(HIGHLIGHT), width=5)
text(fmt(cur), cx, RTOP + 20, size=88, color=TEXT, center=True)
if n > 1 and first > 0:
    chg = (cur - first) / first * 100
    text(('+' if chg >= 0 else '') + str(int(round(chg))) + '% since ' + labels[0],
         cx, RTOP + 120, size=40, color=SUBTLE, center=True)
'''

DRAIN_SHARE = r'''
# TIER 1: a share LEAVES THE REAL THING. The subject drains from the bottom
# — a stream of its own units falling fast — and what left collects in the
# vessel below, so what is gone and what stayed are both on screen and they
# add up. Draining/filling is the physics of every share: used, wasted,
# lost, converted. The stream runs almost the whole beat, so the picture is
# never still.
sub = subject_image('pizza')                     # <- THIS story's subject
sink = subject_image('trash can')                # <- where the share GOES
whole = 100.0 if n == 1 else max(sum(values), 1e-9)   # a lone % is of 100;
share = clamp(values[0] / whole if whole else 0, 0, 1)  # else of the TOTAL
w = 560
x = (RX0 + RX1) / 2 - w / 2
y = RTOP + 170
prog = clamp(reveal / 0.97)                      # drains until the last frame
gone = share * prog
left = 1 - gone
# what there was: the whole subject's box, ghosted; the hole is the story
d.rounded_rectangle([x, y, x + w, y + w], radius=60, fill=rgba(REST, 40),
                    outline=rgba(REST, 150), width=3)
if sub is not None:
    fill_image(sub, left, x, y, w, w, direction='up')      # the level drops
else:
    d.rounded_rectangle([x, y + w * (1 - left), x + w, y + w], radius=40,
                        fill=rgba(REST))
# the stream: units of the share, falling fast from the subject's bottom
sw = 340
sx = (RX0 + RX1) / 2 - sw / 2
sy = RBOT - 220 - sw
if prog < 1 and share > 0:
    for q in range(7):
        fy = y + w + (reveal * 3600 + q * 90) % (sy - y - w)
        d.ellipse([x + w / 2 - 16, fy - 16, x + w / 2 + 16, fy + 16],
                  fill=rgba(HIGHLIGHT))
# where it goes: the vessel, filling to exactly the share, in the accent
if sink is not None:
    paste(sink, sx, sy, sw, sw)
    fill_image(sink, gone, sx, sy, sw, sw, direction='up', color=HIGHLIGHT)
else:
    d.rounded_rectangle([sx, sy, sx + sw, sy + sw], radius=30,
                        outline=rgba(REST, 160), width=3)
    d.rounded_rectangle([sx, sy + sw * (1 - gone), sx + sw, sy + sw], radius=30,
                        fill=rgba(HIGHLIGHT))
text(fmt(values[0] * prog), sx + sw + 40, sy + sw / 2 - 40, size=72, color=TEXT)
text(labels[0], sx + sw + 40, sy + sw / 2 + 44, size=36, color=SUBTLE)
# what is still in the subject, counting DOWN to what stays
text(fmt(whole * left), x + w + 30, y + 40, size=48, color=TEXT)
text('stays' if n == 1 else (labels[1] if n == 2 else 'the rest'),
     x + w + 30, y + 100, size=32, color=SUBTLE)
'''

TRUE_SCALE = r'''
# TIER 1: two subjects at TRUE RELATIVE SIZE, and copies of the smaller one
# DROP ONTO IT until the stack reaches the bigger one's top — "it takes N
# of these to make one of those". The subject is both the picture and the
# measuring stick; swap it and everything changes. Size is value in HEIGHT,
# because the stack is the ruler: N copies of the small one reach the big
# one's top exactly, and the ratio is printed so nobody has to judge area.
a = 0 if n < 2 else (0 if values[0] >= values[1] else 1)   # the bigger one
b = 1 - a if n >= 2 else 0
subA = subject_image(labels[a] if n else 'elephant')
subB = subject_image(labels[b] if n > 1 else 'cow')
va = values[a] if n else 1.0
vb = values[b] if n > 1 else va
peak = max(va, 1e-9)
ground = RBOT - 300
grow = clamp(reveal / 0.3)                     # 0..0.3: both rise to size
ease = grow                                    # LINEAR: an ease-out's tail is
big = 600                                      # a sub-pixel glide = a freeze
sa = va / peak * big * ease
unit = max(vb, 0) / peak * big                 # the small one's full height
sb = unit * ease
xa = RX0 + 40
xb = RX1 - 40 - unit                           # the small one's column
d.line([RX0, ground, RX1, ground], fill=rgba(REST, 160), width=3)
if sa > 6:
    if subA is not None:
        paste(subA, xa, ground - sa, sa, sa)   # the subject wears the accent
    else:
        d.rounded_rectangle([xa, ground - sa, xa + sa, ground], radius=30, fill=rgba(HIGHLIGHT))
if sb > 6:
    if subB is not None:
        paste(subB, xb + (unit - sb) / 2, ground - sb, sb, sb)
    else:
        d.rounded_rectangle([xb, ground - sb, xb + unit, ground], radius=30, fill=rgba(REST))
# the ruler: the small one is the first unit; copies of it fall onto it,
# one after another, and the last is only as much of a copy as the
# remainder needs. Every copy falls from just above the frame FAST (about
# 900px in under a second — a real drop, and fast enough that the
# reviewer's frame detector sees it move; a slow glide it reads as a
# freeze) and hops once on landing. It starts ON SCREEN: a copy that
# begins 1200px up spends the first half of its fall invisible.
ratio = va / max(vb, 1e-9)
more = max(ratio - 1, 0)
parts = [1.0] * int(min(more, 40))
if more - int(more) > 0.05 and more < 40:
    parts.append(more - int(more))
cnt = len(parts)
win = min(0.33, 0.55 / max(cnt, 1))            # one fall, as a share of the beat
landed = 1.0 if grow >= 1 else 0.0
allin = 0.3 + win * cnt                        # when the last copy lands
if unit > 6 and grow >= 1 and cnt:
    base = ground - unit
    for i in range(cnt):
        hgt = unit * parts[i]
        slot = base - hgt
        t = clamp((reveal - 0.3 - i * win) / win)
        if t <= 0:
            break
        hop = clamp((reveal - 0.3 - (i + 1) * win) / 0.12)
        ty = lerp(-hgt, slot, t) - 140 * math.sin(hop * math.pi)
        landed = landed + parts[i] * t
        if t < 1:
            d.line([xb + unit / 2, ty - 400, xb + unit / 2, ty], fill=rgba(HIGHLIGHT, 170), width=6)
        if subB is not None:
            fill_image(subB, parts[i], xb, ty - (unit - hgt), unit, unit, direction='up')
        else:
            d.rounded_rectangle([xb, ty, xb + unit, ty + hgt], radius=8, fill=rgba(REST))
        base = slot
# the level band: the stack has reached the top of the big one; it sweeps
# across for the rest of the beat so the picture is never still
sweep = clamp((reveal - allin - 0.12) / max(0.95 - allin - 0.12, 0.1)) if cnt else clamp((reveal - 0.3) / 0.6)
if sweep > 0 and grow >= 1:
    d.line([xa, ground - sa, lerp(xa, xb + unit, sweep), ground - sa],
           fill=rgba(HIGHLIGHT), width=28)
text(fmt(va), xa + sa / 2, ground + 24, size=54, color=TEXT, center=True)
text(labels[a], xa + sa / 2, ground + 92, size=36, color=SUBTLE, center=True)
if n > 1:
    text(fmt(vb), xb + unit / 2, ground + 24, size=54, color=TEXT, center=True)
    text(labels[b], xb + unit / 2, ground + 92, size=36, color=SUBTLE, center=True)
    if landed > 0:
        lab = (str(int(round(landed))) if abs(landed - round(landed)) < 0.05
               else str(round(landed, 1))) + 'x'
        text(lab, (RX0 + RX1) / 2, RTOP + 20, size=88, color=TEXT, center=True)
'''

EXEMPLARS = [
    {"mechanic": "subject-strike-grid",
     "concept": "Units of the real subject arrive one at a time, each worth "
                "a stated amount, and the count IS the number (the fusion "
                "bolt grid, generalised: each = fmt(per)).",
     "code": STRIKE_GRID.strip("\n"),
     "shapes": ("rank", "duel")},
    {"mechanic": "subject-shore-recede",
     "concept": "The subject's own area tracks the series through every "
                "point; the ground it lost stays outlined; a tide line "
                "breathes on the current edge.",
     "code": SHORE_RECEDE.strip("\n"),
     "shapes": ("falling", "rising")},
    {"mechanic": "subject-drain-share",
     "concept": "A share LEAVES the real thing: it drains out of the subject "
                "as a stream of its own units and collects in the vessel "
                "below, so what left and what stayed both show and add up.",
     "code": DRAIN_SHARE.strip("\n"),
     "shapes": ("duel", "rank")},
    {"mechanic": "subject-true-scale",
     "concept": "Two subjects at true relative size, and copies of the "
                "smaller one drop onto it until the stack reaches the "
                "bigger one's top — the subject is the measuring stick.",
     "code": TRUE_SCALE.strip("\n"),
     "shapes": ("duel", "rank")},
]


def sig_of(spec: dict) -> str:
    """The library's dedup key — identical to `viz_director._record_mechanic`."""
    return hashlib.sha1((spec.get("mechanic", "") + spec.get("code", ""))
                        .encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Verification: render through the REAL sandbox, offline.
# ---------------------------------------------------------------------------

def _offline(vs):
    """Keep the probe deterministic and network-free: photos are never
    fetched (None) and a cut-out is the offline Twemoji icon or None."""
    from PIL import Image
    from data_learning import icons

    def cutout(subject, slug, tag):
        cp = icons.icon_png(subject, 512)
        try:
            return Image.open(cp).convert("RGBA") if cp else None
        except Exception:  # noqa: BLE001
            return None

    vs._load_photo = lambda *a, **k: None
    vs._load_cutout = cutout


def _no_images(vs):
    """The worst day: no icon, no photo, no cut-out for anything."""
    vs._load_photo = lambda *a, **k: None
    vs._load_cutout = lambda *a, **k: None


def _motion_points(vs, spec, insight) -> int:
    """How many of the probe's sample points move between ADJACENT frames —
    the same measurement as `mechanic_motion_ok`, reported as a count so the
    check can demand better than the gate's floor of one."""
    from PIL import Image
    from scripts.showrunner_review import BLOCK_MOTION_THRESH, _max_block_diff
    code_obj = compile(spec["code"], "<mechanic>", "exec")
    base = vs._mechanic_env(insight, "seed")

    def shot(r):
        canvas = Image.new("RGBA", (vs.W, vs.H), (0, 0, 0, 0))
        vs._run_mechanic_frame(code_obj, canvas, base, max(0.0, min(1.0, r)))
        small = canvas.convert("L").resize(
            (vs._DETECTOR_W, int(vs.H * vs._DETECTOR_W / vs.W)))
        return list(getattr(small, "get_flattened_data", small.getdata)())

    step = 1.0 / (vs._MOTION_SAMPLE_FPS * vs._MOTION_BEAT_S)
    return sum(1 for r in vs._MOTION_AT
               if _max_block_diff(shot(r), shot(r + step), vs._DETECTOR_W)
               >= BLOCK_MOTION_THRESH)


def _moving_fraction(vs, spec, insight, points: int = 20) -> float:
    """Fraction of the beat in VISIBLE motion: the same adjacent-frame test
    as the gate, sampled at `points` places instead of five. The gate needs
    one point; a TEACHER is held to `_TEACHER_MOTION` of the beat, because
    a mechanic still for half its beat spends half the video's duplicate-
    frame budget (0.45, `_MOTION_MIN_POINTS` docstring) on one scene."""
    from PIL import Image
    from scripts.showrunner_review import BLOCK_MOTION_THRESH, _max_block_diff
    code_obj = compile(spec["code"], "<mechanic>", "exec")
    base = vs._mechanic_env(insight, "seed")

    def shot(r):
        canvas = Image.new("RGBA", (vs.W, vs.H), (0, 0, 0, 0))
        vs._run_mechanic_frame(code_obj, canvas, base, max(0.0, min(1.0, r)))
        small = canvas.convert("L").resize(
            (vs._DETECTOR_W, int(vs.H * vs._DETECTOR_W / vs.W)))
        return list(getattr(small, "get_flattened_data", small.getdata)())

    step = 1.0 / (vs._MOTION_SAMPLE_FPS * vs._MOTION_BEAT_S)
    moved = 0
    for q in range(points):
        r = (q + 0.5) / points
        if _max_block_diff(shot(r), shot(r + step), vs._DETECTOR_W) >= BLOCK_MOTION_THRESH:
            moved += 1
    return moved / points


#: A teacher must be in visible motion for at least this much of its beat
#: on the shapes it is written for.
_TEACHER_MOTION = 0.75


def verify(exemplars: list, verbose: bool = True) -> list:
    """Every exemplar, on every shape, with and without images. Returns the
    failures as (mechanic, shape, mode, why); an empty list is a pass."""
    import matplotlib
    matplotlib.use("Agg")
    from data_learning import viz_scene as vs
    from scripts.score_mechanics import SHAPES, _insight
    fails = []
    for ex in exemplars:
        spec = {"mechanic": ex["mechanic"], "concept": ex["concept"],
                "code": ex["code"]}
        if not vs.validate_mechanic(spec):
            fails.append((ex["mechanic"], "-", "-", "validate_mechanic refused it"))
            continue
        for mode, setup in (("icons", _offline), ("no-images", _no_images)):
            setup(vs)
            for shape, pairs in SHAPES.items():
                ins = _insight(ex["mechanic"], pairs)
                ok = vs.mechanic_dry_ok(spec, ins)
                pts = _motion_points(vs, spec, ins) if ok else 0
                frac = _moving_fraction(vs, spec, ins) if ok else 0.0
                if verbose:
                    print(f"  {ex['mechanic']:<22} {mode:<10} {shape:<8} "
                          f"{'ok' if ok else 'REFUSED'}  gate {pts}/{len(vs._MOTION_AT)}"
                          f"  in motion {frac:.0%} of the beat")
                if not ok:
                    fails.append((ex["mechanic"], shape, mode, "mechanic_dry_ok refused"))
                elif shape in ex["shapes"] and frac < _TEACHER_MOTION:
                    # on the shapes it is FOR, a teacher is held to a higher
                    # bar than the gate's floor of one moving point
                    fails.append((ex["mechanic"], shape, mode,
                                  f"in motion only {frac:.0%} of the beat"))
    return fails


def contact_sheet(exemplars: list, out: Path, reveals=(0.15, 0.45, 0.75, 1.0)):
    """One row per exemplar on its first shape, frames across the reveal."""
    from PIL import Image
    from data_learning import viz_scene as vs
    from scripts.score_mechanics import SHAPES, _insight
    _offline(vs)
    tw, th = 270, 480
    sheet = Image.new("RGB", (tw * len(reveals), th * len(exemplars)), (12, 16, 24))
    for row, ex in enumerate(exemplars):
        spec = {"mechanic": ex["mechanic"], "code": ex["code"]}
        code_obj = compile(spec["code"], "<mechanic>", "exec")
        ins = _insight(ex["mechanic"], SHAPES[ex["shapes"][0]])
        base = vs._mechanic_env(ins, "seed")
        for col, r in enumerate(reveals):
            canvas = Image.new("RGBA", (vs.W, vs.H), (0, 0, 0, 0))
            try:
                vs._run_mechanic_frame(code_obj, canvas, base, r)
            except Exception as e:  # noqa: BLE001
                print(f"  {ex['mechanic']} @ {r}: {type(e).__name__}: {e}")
            bg = Image.new("RGBA", canvas.size, (12, 16, 24, 255))
            bg.alpha_composite(canvas)
            sheet.paste(bg.convert("RGB").resize((tw, th)), (col * tw, row * th))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def seed(exemplars: list, lib_path: Path) -> int:
    """Write the verified exemplars into the library, in place, idempotently."""
    try:
        lib = json.loads(lib_path.read_text())
    except Exception:  # noqa: BLE001
        lib = []
    by_sig = {m.get("sig"): m for m in lib}
    n = 0
    for ex in exemplars:
        spec = {"mechanic": ex["mechanic"], "concept": ex["concept"], "code": ex["code"]}
        s = sig_of(spec)
        row = {"sig": s, "mechanic": ex["mechanic"], "concept": ex["concept"],
               "code": ex["code"], "topic": "exemplar: " + ex["mechanic"],
               "starred": True, "moves": True, "moves_on": list(ex["shapes"]),
               "exemplar": True,
               "grade": dict(EXEMPLAR_GRADE,
                             ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))}
        if s in by_sig:
            by_sig[s].update(row)
        else:
            lib.append(row)
            by_sig[s] = row
        n += 1
    lib_path.write_text(json.dumps(lib, indent=1, ensure_ascii=False) + "\n")
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true", help="seed the library")
    ap.add_argument("--sheet", default="", help="write a contact sheet PNG here")
    ap.add_argument("--lib", default=str(LIB))
    args = ap.parse_args()

    print(f"verifying {len(EXEMPLARS)} exemplars through the real sandbox...")
    fails = verify(EXEMPLARS)
    if args.sheet:
        print(f"contact sheet -> {contact_sheet(EXEMPLARS, Path(args.sheet))}")
    if fails:
        print(f"\n{len(fails)} FAILURE(S) — nothing seeded:")
        for f in fails:
            print("   ", *f)
        return 1
    print(f"\nall exemplars render, are in motion >= {_TEACHER_MOTION:.0%} of "
          "the beat on their shapes, and survive a missing image")
    if args.write:
        n = seed(EXEMPLARS, Path(args.lib))
        print(f"seeded {n} exemplar(s) -> {args.lib}")
    else:
        print("(report only — pass --write to seed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
