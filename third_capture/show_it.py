"""Show the viewer the thing the streamer is talking about.

Operator, 2026-10-09: *"when for example xqc is talking about the rug pull
if we can we need to put a picture of the stock he is talking about as a
layover for a few seconds so they can get it. Internalize what [we're]
going for there not just that exact video."* What a stranger scrolling
past is missing is the THING: the coin that crashed, the game he's
raging about, the car, the person who isn't on stream. A repost editor
cuts a picture of it in for a few seconds at the moment it is named.

So the author (and the story director, per beat) names what is said but
not shown: `{"thing": "...", "look": "...", "kind": "coin|stock|thing",
"at": s}` — `look` is what the picture must SHOW ("HAWK coin chart after
the rug pull"). The picture comes from the SHARED finder
(`funnel/find_image.py`): every source the media funnel reaches (news,
Brave, Tavily, DuckDuckGo Images, Reddit, Bluesky, Imgur, YouTube,
Wikipedia...), downloaded and CHECKED by the brain against `look`. A
coin or a stock that no picture showed is drawn here from its real price
data, so a rug pull still looks like one.

A brief inset in commentary on something else is fair use (operator,
same night), so copyrighted pictures are admissible. A thing nobody can
find a checked picture of shows nothing: a wrong picture is worse than
none, and nothing here is ever generated. Every failure degrades to no
pop-up; a pop-up can never cost a clip its render.
"""
from __future__ import annotations

import io
import math
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONT = REPO / "assets" / "fonts" / "InterDisplay-Bold.ttf"

KINDS = {"coin", "stock", "thing"}
SHOW_S = 2.6           # on screen this long: "a few seconds so they can get it"
MAX_SHOWS = 2
SHOW_GAP = 3.0
CARD_W = 820
CARD_TOP = 300         # upper third: clear of the speech captions and the line

UP, DOWN = (46, 204, 113), (235, 64, 52)
PANEL, INK, SUB = (18, 18, 22), (255, 255, 255), (170, 170, 180)


# ---------------------------------------------------------------- plan --

def plan(items, dur: float, offset: float = 0.0) -> list[dict]:
    """The pop-ups this cut can carry, on the cut's clock. The author's
    seconds are CLIP time; `offset` is where the cut starts. A thing named
    before the cut, or too late to stay up, is dropped."""
    out: list[dict] = []
    for r in sorted((r for r in (items or []) if isinstance(r, dict)),
                    key=lambda r: _num(r.get("at"))):
        thing = clean_thing(r.get("thing"))
        kind = str(r.get("kind", "thing")).strip().lower()
        kind = kind if kind in KINDS else "thing"
        at = _num(r.get("at")) - float(offset or 0.0)
        if not thing or at < 0.3 or at > dur - 1.5:
            continue
        if any(abs(at - k["at"]) < SHOW_GAP or k["thing"].lower()
               == thing.lower() for k in out):
            continue
        out.append({"thing": thing, "kind": kind, "at": round(at, 2),
                    "secs": round(min(SHOW_S, dur - at - 0.2), 2),
                    "look": _look(r)})
        if len(out) >= MAX_SHOWS:
            break
    return out


def clean_thing(v) -> str:
    s = re.sub(r"\s+", " ", str(v or "")).strip().strip("\"'")
    return s[:40] if 1 <= len(s.split()) <= 5 else ""


def parse(raw, clip_dur: float = 0.0) -> list[dict]:
    """The author's `show` list, validated (the renderer re-plans it)."""
    out = []
    for r in (raw or [])[:4] if isinstance(raw, list) else []:
        if not isinstance(r, dict):
            continue
        thing = clean_thing(r.get("thing"))
        kind = str(r.get("kind", "thing")).strip().lower()
        at = _num(r.get("at"), -1.0)
        if thing and at >= 0:
            row = {"thing": thing,
                   "kind": kind if kind in KINDS else "thing",
                   "at": round(min(at, clip_dur) if clip_dur else at, 2)}
            if _look(r):
                row["look"] = _look(r)
            out.append(row)
    return out


def _look(r: dict) -> str:
    """What the picture must SHOW, in search words (the finder searches
    for it and the brain checks the picture against it)."""
    s = re.sub(r"\s+", " ", str(r.get("look") or "")).strip()
    return s[:90]


def _num(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


# -------------------------------------------------------------- cards --

def _font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(str(FONT), size)
    except OSError:
        return ImageFont.load_default()


def _money(v: float) -> str:
    if v >= 1000:
        return f"${v:,.0f}"
    if v >= 1:
        return f"${v:,.2f}"
    if v <= 0:
        return "$0"
    # three significant figures for a meme coin's fractions of a cent
    digits = min(10, max(2, 2 - int(math.floor(math.log10(v)))))
    return "$" + f"{v:.{digits}f}".rstrip("0").rstrip(".")


def chart_card(info: dict, out: Path) -> Path:
    """Logo, name, the move in big red or green, and the price line."""
    from PIL import Image, ImageDraw
    W, H, pad = CARD_W, 560, 40
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), 36, fill=PANEL + (255,),
                        outline=(255, 255, 255, 60), width=3)
    prices = [p for _, p in info["prices"]]
    first, last, peak = prices[0], prices[-1], max(prices)
    # a crash reads off its PEAK: "-90% from the top" is the rug pull
    ref = peak if (peak - last) > (last - first) and peak > first else first
    chg = (last - ref) / ref * 100 if ref else 0.0
    col = UP if chg >= 0 else DOWN
    x = pad
    if info.get("logo"):
        try:
            logo = Image.open(io.BytesIO(info["logo"])).convert("RGBA")
            logo = logo.resize((96, 96))
            m = Image.new("L", (96, 96), 0)
            ImageDraw.Draw(m).ellipse((0, 0, 95, 95), fill=255)
            img.paste(logo, (pad, pad), m)
            x = pad + 116
        except Exception:  # noqa: BLE001
            pass
    name = str(info.get("name") or "")[:22]
    sym = str(info.get("symbol") or "").upper()[:10]
    d.text((x, pad - 4), name, font=_font(54), fill=INK)
    d.text((x, pad + 58), f"${sym}" if sym else "", font=_font(34), fill=SUB)
    big = f"{'+' if chg >= 0 else ''}{chg:.0f}%"
    bf = _font(78)
    d.text((W - pad - d.textlength(big, font=bf), pad - 6), big, font=bf,
           fill=col)
    d.text((W - pad - d.textlength(_money(last), font=_font(34)), pad + 76),
           _money(last), font=_font(34), fill=SUB)
    # the line
    cx0, cy0, cx1, cy1 = pad, 190, W - pad, H - pad
    lo_p, hi_p = min(prices), max(prices)
    span = (hi_p - lo_p) or 1.0
    n = len(prices)
    pts = [(cx0 + (cx1 - cx0) * i / (n - 1),
            cy1 - (cy1 - cy0) * (p - lo_p) / span)
           for i, p in enumerate(prices)]
    fill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(fill).polygon(pts + [(cx1, cy1), (cx0, cy1)],
                                 fill=col + (55,))
    img = Image.alpha_composite(img, fill)
    ImageDraw.Draw(img).line(pts, fill=col + (255,), width=8, joint="curve")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def image_card(info: dict, out: Path) -> Path:
    """The picture with a white border and its name under it."""
    from PIL import Image, ImageDraw
    pic = Image.open(io.BytesIO(info["image"])).convert("RGB")
    iw = CARD_W - 24
    ih = min(int(pic.height * iw / pic.width), 760)
    pic = pic.resize((iw, int(pic.height * iw / pic.width)))
    pic = pic.crop((0, 0, iw, ih))
    label_h = 92
    W, H = CARD_W, ih + 24 + label_h
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), 28, fill=(255, 255, 255, 255))
    img.paste(pic, (12, 12))
    name = str(info.get("name") or "")[:30]
    f = _font(52)
    d.text(((W - d.textlength(name, font=f)) / 2, ih + 24 + 14), name,
           font=f, fill=(15, 15, 18))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def fetch(item: dict, work: Path, when: float | None = None) -> Path | None:
    """The pop-up PNG for one planned item, or None. Never raises. The
    picture comes from the SHARED finder (funnel/find_image.py: every
    source, checked by the brain); a coin or a stock that no picture
    showed is drawn from its real price data."""
    from funnel import find_image
    thing = item["thing"]
    out = Path(work) / f"show_{_norm(thing)[:24] or 'x'}.png"
    try:
        hit = find_image.find(thing, item.get("look") or thing,
                              kind=item["kind"], when=when, work=work)
        if not hit:
            return None
        if hit.get("chart"):
            return chart_card(hit["chart"], out)
        return image_card({"name": item.get("name") or thing,
                           "image": Path(hit["path"]).read_bytes()}, out)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[show] {thing!r} failed ({type(e).__name__})",
              flush=True)
        return None


def ready(items: list[dict], work: Path, when: float | None = None
          ) -> list[dict]:
    """`plan` items that found a picture, each with its `png`."""
    out = []
    for it in items:
        png = fetch(it, work, when)
        print(f"[show] {it['kind']} {it['thing']!r} @{it['at']}: "
              f"{'shown' if png else 'no exact picture — not shown'}",
              flush=True)
        if png:
            out.append({**it, "png": png})
    return out


def overlay(cur: str, n: int, item: dict, out: str) -> str:
    """Filter fragment laying input `n` (the PNG) over `[cur]` for the
    item's seconds, centred in the upper third. It cuts in hard, the way
    the reposts do; a one-frame PNG input holds for the whole window."""
    a, b = item["at"], item["at"] + item["secs"]
    return (f"[{cur}][{n}:v]overlay=(W-w)/2:{CARD_TOP}:"
            f"enable='between(t,{a:.2f},{b:.2f})'[{out}]")


def when_of(created_at) -> float | None:
    """A clip's created_at (ISO) as a unix time, else None."""
    try:
        return datetime.fromisoformat(str(created_at).replace(
            "Z", "+00:00")).astimezone(timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None
