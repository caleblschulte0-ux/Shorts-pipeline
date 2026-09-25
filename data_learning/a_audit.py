"""AUDIT THE A STYLE — every machine, every frame, measured.

The illustrated arm (B) got a verifier that refuses a scene before it is
used. The current look (A) never had one, and the showrunner kept blocking it
for the same three things on nearly every render (2026-09-08..24):

  unreadable         Data's body over a label ("'11.7%' split by the mascot's
                     legs"), labels clipped by the frame edge, grey-on-navy
  decorative_mascot  Data perches beside the data
  empty_void         most of the frame is empty

This renders every A machine through the real renderer and records every text
draw (its box, colour, how visible) and every place Data is composited, frame
by frame, so those defects are counted as a CLASS rather than found one video
at a time. `audit()` returns problems per machine; the tests hold it at zero.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

W, H = 1080, 1920

#: Text drawn at this opacity or more is text a viewer is meant to read.
VISIBLE_ALPHA = 0.35
#: A label counts as covered when this much of its box is under Data.
COVER_FRAC = 0.25
#: Two different labels collide when their boxes share this much of the
#: smaller one: "'clears it by 1.7' prints on top of '65-city average 8'".
COLLIDE_FRAC = 0.15
#: Luminance gap (0..255) between a text colour and what it sits on, below
#: which it is "grey on navy".
MIN_CONTRAST = 70.0


def _lum(rgb) -> float:
    r, g, b = [float(c) for c in rgb[:3]]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _inter(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def cases():
    """(name, builder, insight) for every A machine, with realistic data."""
    from data_learning import viz_scene as vs
    from data_learning.insights import Insight
    from data_learning.sources.base import DataPoint, Source
    src = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-24")

    def ins(pairs, unit="count", base=None,
            topic="largest container ship capacity by year"):
        i = Insight(kind="scene", topic=topic,
                    main_insight="m",
                    items=[DataPoint(label=str(a), value=float(b)) for a, b in pairs],
                    source=src, unit=unit, highlight_label=str(pairs[0][0]))
        if base:
            i.baseline = DataPoint(label=base[0], value=float(base[1]))
        return i
    years = [(str(2015 + k), 100 + k * 22) for k in range(12)]
    cities = [("San Jose", 11.3), ("Los Angeles", 9.7), ("Miami", 8.2),
              ("Seattle", 6.8), ("Denver", 5.4)]
    stages = [("Applied", 12000), ("Screened", 9800), ("Interviewed", 2100),
              ("Offered", 1700), ("Hired", 1500)]
    zig = [(str(2016 + k), v) for k, v in enumerate([99, 101, 97, 100, 98, 101, 97, 99])]
    return [
        ("tower", vs.tower_scene, ins(years)),
        ("staircase", vs.staircase_scene, ins(years)),
        ("race", vs.race_scene, ins(cities)),
        ("hurdle", vs.hurdle_scene, ins([("San Jose", 11.3)], base=("US average", 5.9))),
        ("bottleneck", vs.bottleneck_scene, ins(stages)),
        ("leaky", vs.leaky_scene, ins([("Enrolled", 4800), ("Finished", 860)])),
        ("inout", vs.inout_scene, ins([("Inflow", 1840), ("Outflow", 1310)])),
        ("sorter", vs.sorter_scene, ins([("Housing", 4200), ("Transit", 2600),
                                         ("Parks", 1400), ("Admin", 900)])),
        ("chain", vs.chain_scene, ins([("Wafer", 940), ("Assembly", 720),
                                       ("Test", 210), ("Ship", 880)])),
        ("spinner", vs.spinner_scene, ins([("Rain", 23.0)], unit="percent")),
        ("doors", vs.doors_scene, ins([("Match", 4.0)], unit="percent")),
        ("fan", vs.fan_scene, ins([(str(2016 + k), 62 + k * 3.1) for k in range(8)]
                                  + [("2040", 108.0)])),
        ("gears", vs.gears_scene, ins([("Median rent", 2400), ("Median wage", 3100)])),
        ("slider", vs.slider_scene, ins([("Top speed", 82), ("Range", 148)])),
        ("density", vs.density_scene, ins([("Manila", 46000), ("Houston", 1400)])),
        ("nest", vs.nest_scene, ins([("Alaska", 1723000), ("New Jersey", 22600)])),
        ("chairs", vs.chairs_scene, ins([("Applicants", 41000), ("Homes", 1200)])),
        ("hourglass", vs.hourglass_scene, ins([("San Jose", 11.3), ("Detroit", 2.4)])),
        ("trophies", vs.trophies_scene, ins([("Djokovic", 24), ("Nadal", 22),
                                             ("Federer", 20)])),
        ("basket", vs.basket_scene, ins([("1999", 34), ("2026", 19)])),
        ("hole", vs.hole_scene, ins([("September estimate", 45.4),
                                     ("Revised estimate", 34.4)],
                                    topic="why coffee supply keeps shrinking")),
        ("copies", vs.copies_scene, ins([("February 2024", 2.0),
                                         ("February 2025", 4.41)],
                                        topic="how much coffee prices have doubled")),
        ("bridge", vs.bridge_scene, ins([("Now", 76)], base=("Target", 100))),
        ("burden", vs.burden_scene, ins([(str(2016 + k), 22.0 + k * 1.6)
                                         for k in range(8)])),
        ("centre", vs.centre_scene, ins(cities)),
        ("coaster", vs.coaster_scene, ins(zig)),
        ("conveyor", vs.conveyor_scene, ins([("Parcels", 1400)])),
        ("darts", vs.darts_scene, ins([("A", 100), ("B", 102), ("C", 101),
                                       ("D", 99), ("E", 100), ("F", 101)])),
        ("elevator", vs.elevator_scene, ins([(str(2016 + k), 96.0 - k * 7)
                                             for k in range(8)])),
        ("funnel", vs.funnel_scene, ins(stages)),
        ("gauge", vs.gauge_scene, ins([("Rate", 22.9)])),
        ("pipes", vs.pipes_scene, ins([("Rent", 34), ("Food", 22), ("Transit", 18),
                                       ("Other", 26)])),
        ("queue", vs.queue_scene, ins([(str(2016 + k), 200.0 + k * 180)
                                       for k in range(8)])),
        ("road", vs.road_scene, ins([(str(2016 + k), 50.0 + (k % 2) * 0.2)
                                     for k in range(8)])),
        ("skyline", vs.skyline_scene, ins([("Tokyo", 37.4), ("Delhi", 9.2),
                                           ("Cairo", 7.8), ("Lima", 4.1)])),
        ("spotlight", vs.spotlight_scene, ins(zig)),
        ("tape", vs.tape_scene, ins([("2016", 42), ("2026", 97)])),
        ("thermometer", vs.thermometer_scene, ins([("Now", 88)], base=("Limit", 100))),
        ("wheel", vs.wheel_scene, ins([(str(2016 + k), v) for k, v in
                                       enumerate([10, 60, 12, 58, 11, 62, 13, 59])])),
        ("balance", getattr(vs, "balance_scene", None),
         ins([("1990", 1.2), ("2022", 25.8)])),
    ]


def audit_one(build, insight, frames: int = 24) -> dict:
    """Render one machine and return {"covered", "clipped", "faint"}: lists of
    (frame, text) — each a label a viewer cannot read."""
    from PIL import Image, ImageDraw
    from data_learning import charts
    from data_learning import viz_scene as vs
    ev = []                                  # (frame, kind, payload) in draw order
    state = {"frame": 0}
    real_text = ImageDraw.ImageDraw.text
    real_comp = Image.Image.alpha_composite
    real_host = vs.scene_host
    real_save = Image.Image.save

    def text(self, xy, text, fill=None, font=None, anchor=None, *a, **k):
        try:
            if self.im.size == (W, H) and str(text).strip():
                bb = self.textbbox(xy, str(text), font=font, anchor=anchor)
                alpha = (fill[3] / 255.0) if isinstance(fill, tuple) and len(fill) == 4 else 1.0
                rgb = fill[:3] if isinstance(fill, tuple) else (255, 255, 255)
                ev.append((state["frame"], "text",
                           (str(text), bb, alpha, rgb,
                            id(getattr(self, "_image", None) or self))))
        except Exception:  # noqa: BLE001 — auditing must never break a render
            pass
        return real_text(self, xy, text, fill, font, anchor, *a, **k)

    # ART DRAWN OVER A LABEL. Data is not the only thing that lands on text:
    # a tray row falling through "2021 $2.55" (coffee hook, 2026-09-24) was
    # a rounded rectangle and an icon, invisible to a check that only knew
    # about the mascot. Every opaque shape or image drawn AFTER a label on the
    # same canvas is measured against it.
    real_shapes = {n: getattr(ImageDraw.ImageDraw, n)
                   for n in ("rectangle", "rounded_rectangle", "ellipse", "polygon")}

    def _shape(name):
        real = real_shapes[name]

        def draw(self, xy, *a, **k):
            try:
                fill = k.get("fill", a[1] if name == "rounded_rectangle" and len(a) > 1
                             else (a[0] if a and name != "rounded_rectangle" else None))
                alpha = (fill[3] / 255.0) if isinstance(fill, tuple) and len(fill) == 4 \
                    else (1.0 if fill is not None else 0.0)
                if self.im.size == (W, H) and alpha >= 0.6:
                    pts = list(xy)
                    if pts and isinstance(pts[0], (tuple, list)):
                        xs = [p[0] for p in pts]
                        ys = [p[1] for p in pts]
                    else:
                        xs, ys = pts[0::2], pts[1::2]
                    ev.append((state["frame"], "art",
                               (min(xs), min(ys), max(xs), max(ys),
                                id(getattr(self, "_image", None) or self))))
            except Exception:  # noqa: BLE001
                pass
            return real(self, xy, *a, **k)
        return draw

    def host(*a, **k):
        img = real_host(*a, **k)
        if img is not None:
            try:
                img.info["__data__"] = True
            except Exception:  # noqa: BLE001
                pass
        return img

    def comp(self, im, dest=(0, 0), source=(0, 0)):
        try:
            if (not im.info.get("__data__") and self.size == (W, H)
                    and im.size != (W, H)):
                bb = im.getchannel("A").point(lambda v: 255 if v > 150 else 0).getbbox()
                if bb:
                    x, y = dest[0], dest[1]
                    ev.append((state["frame"], "art",
                               (x + bb[0], y + bb[1], x + bb[2], y + bb[3], id(self))))
            if im.info.get("__data__") and self.size == (W, H):
                x, y = dest[0], dest[1]
                # his body, not the transparent margin of the sprite
                bb = im.getbbox() or (0, 0, im.width, im.height)
                ev.append((state["frame"], "data",
                           (x + bb[0], y + bb[1], x + bb[2], y + bb[3], id(self))))
        except Exception:  # noqa: BLE001
            pass
        return real_comp(self, im, dest, source)

    frames_png = []

    def save(self, fp, *a, **k):
        r = real_save(self, fp, *a, **k)
        if self.size == (W, H):
            frames_png.append(Path(str(fp)))
            state["frame"] += 1
        return r

    _fit = getattr(vs, "_fit", None)

    def fit(img, *a, **k):                   # the host is resized before it lands
        out = _fit(img, *a, **k)
        try:
            if img.info.get("__data__"):
                out.info["__data__"] = True
        except Exception:  # noqa: BLE001
            pass
        return out

    ImageDraw.ImageDraw.text = text
    for _n in real_shapes:
        setattr(ImageDraw.ImageDraw, _n, _shape(_n))
    Image.Image.alpha_composite = comp
    Image.Image.save = save
    vs.scene_host = host
    if _fit:
        vs._fit = fit
    try:
        insight.scene = build(insight)
        if not insight.scene:
            return {"covered": [], "clipped": [], "faint": [], "collide": [],
                    "skipped": True}
        with tempfile.TemporaryDirectory() as td:
            charts.FULLFRAME_RENDERERS["scene"](insight, Path(td), "a", frames)
            imgs = {i: Image.open(p).convert("RGB") for i, p in enumerate(frames_png)
                    if p.exists()}
            return _judge(ev, imgs)
    finally:
        ImageDraw.ImageDraw.text = real_text
        for _n, _f in real_shapes.items():
            setattr(ImageDraw.ImageDraw, _n, _f)
        Image.Image.alpha_composite = real_comp
        Image.Image.save = real_save
        vs.scene_host = real_host
        if _fit:
            vs._fit = _fit


def _glyph_contrast(im, bb, rgb):
    """Luminance gap between the text's own pixels and what is behind them,
    INSIDE its box — not a ring around it, which picked up the neighbouring
    bar and called a white label on black "faint". None when too few glyph
    pixels are visible to judge (covered, or not drawn yet)."""
    x0, y0 = max(0, int(bb[0])), max(0, int(bb[1]))
    x1, y1 = min(W, int(bb[2])), min(H, int(bb[3]))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    px = list(im.crop((x0, y0, x1, y1)).getdata())
    def d2(c):
        return sum((float(c[i]) - float(rgb[i])) ** 2 for i in range(3))
    glyph = [c for c in px if d2(c) < 45 ** 2]
    back = [c for c in px if d2(c) >= 45 ** 2]
    if len(glyph) < max(12, len(px) * 0.04) or len(back) < len(px) * 0.2:
        return None
    bg = sorted(_lum(c) for c in back)[len(back) // 2]
    return abs(_lum(rgb) - bg)


def _hides(tb, hb) -> bool:
    from data_learning import charts
    return charts.hides(tb, hb)


def _judge(ev, imgs) -> dict:
    covered, clipped, faint, collide, truncated = set(), set(), set(), set(), set()
    overdrawn = set()
    texts_so_far: dict = {}
    for frame, kind, p in ev:
        if kind == "text":
            s, bb, alpha, rgb = p[:4]
            canvas = p[4] if len(p) > 4 else None
            if alpha >= VISIBLE_ALPHA:
                # another label already on THIS canvas, in this frame — the
                # renderer probes a machine on a scratch canvas first, so
                # only text sharing a canvas can be seen together
                for q in texts_so_far.get(frame, []):
                    if (q[0] == s or q[2] < VISIBLE_ALPHA
                            or (len(q) > 4 and q[4] != canvas)):
                        continue
                    small = max(1.0, min((bb[2] - bb[0]) * (bb[3] - bb[1]),
                                         (q[1][2] - q[1][0]) * (q[1][3] - q[1][1])))
                    if _inter(bb, q[1]) / small > COLLIDE_FRAC:
                        collide.add(" / ".join(sorted((q[0], s))))
            texts_so_far.setdefault(frame, []).append(p)
            if alpha < VISIBLE_ALPHA:
                continue
            if bb[0] < 0 or bb[2] > W or bb[1] < 0 or bb[3] > H:
                clipped.add(s)
            if s.rstrip().endswith(("…", "...")):
                truncated.add(s)        # "Formerly redli…" — a claim, cut
            im = imgs.get(frame)
            if im is not None and bb[2] > bb[0] and bb[3] > bb[1]:
                c = _glyph_contrast(im, bb, rgb)
                if c is not None and c < MIN_CONTRAST:
                    faint.add(s)
        elif kind == "art":                 # a shape or image over a label
            for s, bb, alpha, *_rest in texts_so_far.get(frame, []):
                if _rest[1:] and _rest[1] != p[4]:
                    continue
                if alpha >= VISIBLE_ALPHA and _hides(bb, p[:4]):
                    overdrawn.add(s)
        else:                               # Data lands on top of what is drawn
            for s, bb, alpha, *_rest in texts_so_far.get(frame, []):
                if _rest[1:] and len(p) > 4 and _rest[1] != p[4]:
                    continue                # a different canvas (the probe)
                if alpha >= VISIBLE_ALPHA and _hides(bb, p[:4]):
                    covered.add(s)
    return {"covered": sorted(covered), "clipped": sorted(clipped),
            "faint": sorted(faint), "collide": sorted(collide),
            "truncated": sorted(truncated), "overdrawn": sorted(overdrawn)}


#: STRESS SHAPES. One dataset per machine found three defects; the same
#: machines on the shapes production actually sends found six more, all of
#: them the judge's own words: values close together ("'clears it by 1.7'
#: prints on top of '65-city average 8'"), figures in the millions
#: ("19378…" on a step), and names longer than "Tokyo" ("Formerly
#: redli…", "labels cut off"). Every machine is audited on all of them.
STRESS = ("close", "huge", "long")
_LONG = ["Greater Los Angeles metro", "Dallas-Fort Worth-Arlington",
         "Riverside-San Bernardino", "Minneapolis-St. Paul area",
         "Virginia Beach-Norfolk", "Salt Lake City region",
         "Oklahoma City metro", "Kansas City (both states)",
         "Sacramento-Roseville", "Charlotte-Concord"]


def stressed(ins, how: str):
    """A copy of `ins` reshaped the way real data is awkward."""
    import copy
    i = copy.deepcopy(ins)
    vals = [p.value for p in i.items]
    m = sum(vals) / len(vals) if vals else 1.0
    for k, p in enumerate(i.items):
        if how == "close":
            p.value = round(m + (p.value - m) * 0.08, 1)
        elif how == "huge":
            p.value = p.value * 13457.3
        elif how == "long" and not str(p.label).isdigit():
            p.label = _LONG[k % len(_LONG)]
    b = getattr(i, "baseline", None)
    if b is not None:
        if how == "close":
            b.value = round(m + (b.value - m) * 0.08, 1)
        elif how == "huge":
            b.value *= 13457.3
        elif how == "long":
            b.label = "65-city national average"
    i.highlight_label = str(i.items[0].label)
    return i


def _audit_index(args):
    """One machine on one data shape, by its index in cases() — a worker
    process rebuilds the case itself, so nothing unpicklable crosses the
    process boundary."""
    k, frames, how = args if len(args) == 3 else (*args, None)
    name, build, ins = cases()[k]
    label = f"{name}:{how}" if how else name
    if build is None:
        return label, None
    try:
        return label, audit_one(build, stressed(ins, how) if how else ins, frames)
    except Exception as e:  # noqa: BLE001
        return label, {"error": f"{type(e).__name__}: {e}"}


def audit(frames: int = 12, workers: int | None = None,
          shapes=(None,) + STRESS) -> dict:
    """{machine: problems} for every A machine with any problem. Machines are
    audited in parallel: one per core, because rendering all of them one at a
    time pushed the test suite past CI's limit."""
    import os
    from concurrent.futures import ProcessPoolExecutor
    n = len(cases())
    jobs = [(k, frames, how) for k in range(n) for how in shapes]
    workers = workers or max(1, min(4, os.cpu_count() or 1))
    if workers == 1:
        results = [_audit_index(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_audit_index, jobs))
    out = {}
    for name, r in results:
        if r and (r.get("error") or any(r.get(k) for k in ("covered", "clipped", "faint", "collide", "truncated",
                                    "overdrawn"))):
            out[name] = r
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(audit(), indent=1))


# ------------------------------------------------------------ card charts --
#
# The OTHER half of the A look: matplotlib cards (a race, a trend line, bars,
# bubbles) with Data baked in as an artist. Most of the blocks the judge
# wrote about A came from here — "'11.7%' split by the mascot's legs",
# "labels clipped off the left frame edge". Audited from inside matplotlib,
# frame by frame, before each one is written: every visible text artist
# against Data's artist wherever he is drawn ABOVE it, and against the card.

def chart_cases():
    from data_learning.insights import Insight
    from data_learning.sources.base import DataPoint, Source
    src = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-24")

    def ins(kind, pairs, unit="count", topic="largest container ship capacity by year"):
        return Insight(kind=kind, topic=topic, main_insight="m",
                       items=[DataPoint(label=str(a), value=float(b)) for a, b in pairs],
                       source=src, unit=unit, highlight_label=str(pairs[-1][0]))
    years = [("1996", 6600), ("2006", 12500), ("2013", 18000), ("2019", 24000)]
    ranking = [("Tirzepatide (Zepbound)", 20.9), ("Semaglutide (Wegovy)", 14.9),
               ("Liraglutide (early GLP-1)", 8.0), ("Diet & exercise alone", 2.4)]
    long_trend = [(str(2015 + k), 11.7 - k * 0.45) for k in range(10)]
    duel = [("1990", 1.2), ("2022", 25.8)]
    share = [("By sea", 80), ("Everything else", 20)]
    return [
        ("pictorial_race", ins("pictorial_race", years)),
        ("rank", ins("rank", ranking, unit="percent")),
        ("trend", ins("trend", long_trend, unit="percent")),
        ("comparison", ins("comparison", duel)),
        ("bubbles", ins("bubbles", share, unit="percent")),
        ("stack", ins("stack", share, unit="percent")),
        ("share", ins("share", share, unit="percent")),
        ("waffle_grid", ins("waffle_grid", share, unit="percent")),
        ("pictograph", ins("pictograph", years)),
        ("bignum", ins("bignum", [("2019", 24000)])),
    ]


def audit_chart(insight, frames: int = 12) -> dict:
    """{"covered", "clipped"} for one card chart, measured inside matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.offsetbox import AnnotationBbox
    from matplotlib.text import Text
    from data_learning import charts
    covered, clipped, collide = set(), set(), set()
    real = Figure.savefig

    def savefig(fig, *a, **k):
        try:
            fig.canvas.draw()
            r = fig.canvas.get_renderer()
            fw, fh = fig.bbox.width, fig.bbox.height
            hosts = [(h.get_zorder(), h.get_window_extent(r))
                     for h in fig.findobj(AnnotationBbox)
                     if h.get_zorder() >= charts.HOST_Z and h.get_visible()]
            seen = []
            for t in fig.findobj(Text):
                s = t.get_text().strip()
                if not s or not t.get_visible() or (t.get_alpha() is not None
                                                   and t.get_alpha() < VISIBLE_ALPHA):
                    continue
                bb = t.get_window_extent(r)
                if bb.width < 2 or bb.height < 2:
                    continue
                if bb.x0 < -1 or bb.x1 > fw + 1 or bb.y0 < -1 or bb.y1 > fh + 1:
                    clipped.add(s)
                area = bb.width * bb.height
                for s2, b2 in seen:
                    if s2 == s:
                        continue
                    ix = max(0.0, min(bb.x1, b2.x1) - max(bb.x0, b2.x0))
                    iy = max(0.0, min(bb.y1, b2.y1) - max(bb.y0, b2.y0))
                    if ix * iy / max(1.0, min(area, b2.width * b2.height)) > COLLIDE_FRAC:
                        collide.add(" / ".join(sorted((s2, s))))
                seen.append((s, bb))
                for z, hb in hosts:
                    if z <= t.get_zorder():
                        continue
                    if charts.hides((bb.x0, bb.y0, bb.x1, bb.y1),
                                    (hb.x0, hb.y0, hb.x1, hb.y1)):
                        covered.add(s)
        except Exception:  # noqa: BLE001 — auditing must never break a render
            pass
        return real(fig, *a, **k)

    Figure.savefig = savefig
    try:
        with tempfile.TemporaryDirectory() as td:
            charts.render_story_build(insight, Path(td), "c", frames=frames)
    finally:
        Figure.savefig = real
    return {"covered": sorted(covered), "clipped": sorted(clipped),
            "collide": sorted(collide)}


def audit_charts(frames: int = 12) -> dict:
    out = {}
    for name, ins in chart_cases():
        try:
            r = audit_chart(ins, frames)
        except Exception as e:  # noqa: BLE001
            r = {"error": f"{type(e).__name__}: {e}"}
        if r.get("error") or r.get("covered") or r.get("clipped") or r.get("collide"):
            out[name] = r
    return out


# ------------------------------------------------------------ empty void --
#
# "four small icons in the top fifth with the entire bottom two-thirds
# empty", "the top 60% of frame empty above a single line of text" — the
# judge's `empty_void`, on most A renders. Measured the way it is seen: the
# frame as the video shows it, at the three moments the judge samples a beat,
# as the share of the CONTENT area (below the title, above the captions) that
# is bare ground.

CONTENT_Y = (150, 1540)
BLOCK = 24


def empty_share(im) -> float:
    """The tallest band of the content area with NOTHING in it, as a share of
    the content height. Gaps between bars are the look; a band the width of
    the frame with nothing in it is the void the judge names ("the entire
    bottom two-thirds empty")."""
    g = im.convert("L")
    y0, y1 = CONTENT_Y
    rows = []
    for y in range(y0, y1 - BLOCK + 1, BLOCK):
        empty = True
        for x in range(0, W - BLOCK + 1, BLOCK):
            px = list(g.crop((x, y, x + BLOCK, y + BLOCK)).getdata())
            if max(px) - min(px) >= 14 or max(px) >= 60:
                empty = False
                break
        rows.append(empty)
    best = run = 0
    for e in rows:
        run = run + 1 if e else 0
        best = max(best, run)
    return best / max(1, len(rows))


def void_machine(build, insight, frames: int = 24) -> list:
    """Empty share at the judge's three sample points for one machine."""
    from PIL import Image
    from data_learning import charts
    insight.scene = build(insight)
    if not insight.scene:
        return []
    with tempfile.TemporaryDirectory() as td:
        charts.FULLFRAME_RENDERERS["scene"](insight, Path(td), "v", frames)
        fs = sorted(Path(td).glob("*.png"))
        if not fs:
            return []
        return [round(empty_share(Image.open(fs[min(len(fs) - 1, int(f * len(fs)))])
                                  .convert("RGB")), 3) for f in (0.25, 0.55, 0.85)]


def void_chart(insight, frames: int = 12) -> list:
    """The same for a card chart, composited where the video puts it."""
    from PIL import Image
    from data_learning import charts, studio_render as R
    with tempfile.TemporaryDirectory() as td:
        charts.render_story_build(insight, Path(td), "v", frames=frames)
        from shared.fsutil import frames_in_order
        fs = frames_in_order(Path(td).glob("v_build*.png"))
        out = []
        for f in (0.25, 0.55, 0.85):
            p = fs[min(len(fs) - 1, int(f * len(fs)))]
            card = Image.open(p).convert("RGBA").resize((R.CHART_W, R.CHART_H))
            frame = Image.new("RGBA", (W, H), (8, 10, 30, 255))
            frame.alpha_composite(card, (R.CHART_X, R.CHART_Y))
            out.append(round(empty_share(frame.convert("RGB")), 3))
        return out


def audit_void() -> dict:
    out = {}
    for name, build, ins in cases():
        if build is not None:
            out["machine:" + name] = void_machine(build, ins)
    for name, ins in chart_cases():
        out["chart:" + name] = void_chart(ins)
    return out
