from __future__ import annotations

from html import escape
from math import sin, pi
from typing import Mapping

W, H = 1080, 1920
BG, CARD, TEXT = "#07101E", "#111C31", "#F8FAFC"
MUTED, ACCENT, CYAN, RED, GREEN = "#9FB0C8", "#F2C14E", "#63D8E8", "#F06464", "#66D18F"


def _p(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _ease(value: float) -> float:
    value = _p(value)
    return 1 - (1 - value) ** 3


def _svg(body: str, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<title>{escape(title)}</title><rect width="{W}" height="{H}" fill="{BG}"/>'
            '<defs><filter id="shadow"><feDropShadow dx="0" dy="16" stdDeviation="18" flood-opacity=".35"/></filter>'
            '<filter id="glow"><feGaussianBlur stdDeviation="10" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
            f'{body}</svg>')


def _text(x: float, y: float, text: str, size: int, color: str = TEXT, opacity: float = 1, anchor: str = "middle") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="Arial,sans-serif" '
            f'font-size="{size}" font-weight="800" fill="{color}" opacity="{opacity:.3f}">{escape(text)}</text>')


def _bean(x: float, y: float, scale: float, lean: float = 0, face: str = "O") -> str:
    return (f'<g transform="translate({x:.1f},{y:.1f}) rotate({lean:.1f}) scale({scale:.3f})" filter="url(#shadow)">'
            '<ellipse cx="0" cy="-60" rx="75" ry="98" fill="#5FD0C7" stroke="#17272E" stroke-width="10"/>'
            '<line x1="-54" y1="-42" x2="-118" y2="-5" stroke="#17272E" stroke-width="15" stroke-linecap="round"/>'
            '<line x1="54" y1="-42" x2="118" y2="-5" stroke="#17272E" stroke-width="15" stroke-linecap="round"/>'
            '<line x1="-25" y1="20" x2="-45" y2="112" stroke="#17272E" stroke-width="17" stroke-linecap="round"/>'
            '<line x1="25" y1="20" x2="45" y2="112" stroke="#17272E" stroke-width="17" stroke-linecap="round"/>'
            '<circle cx="-27" cy="-80" r="8" fill="#17272E"/><circle cx="27" cy="-80" r="8" fill="#17272E"/>'
            f'<text x="0" y="-34" font-size="35" text-anchor="middle" fill="#17272E">{face}</text></g>')


def _money(value: float) -> str:
    return f"${value:,.0f}"


def render_receipt_roll(progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    p = _ease(progress)
    start, end = data[0], data[-1]
    paper_h = 300 + 930 * p
    tear = 18 * sin(p * pi * 6)
    body = _text(540, 190, "THE RECEIPT KEPT GROWING", 48, MUTED)
    body += f'<path d="M230 300 L850 300 L850 {300+paper_h:.1f} L820 {318+paper_h+tear:.1f} L790 {300+paper_h:.1f} L760 {318+paper_h-tear:.1f} L730 {300+paper_h:.1f} L700 {318+paper_h+tear:.1f} L670 {300+paper_h:.1f} L640 {318+paper_h-tear:.1f} L610 {300+paper_h:.1f} L580 {318+paper_h+tear:.1f} L550 {300+paper_h:.1f} L520 {318+paper_h-tear:.1f} L490 {300+paper_h:.1f} L460 {318+paper_h+tear:.1f} L430 {300+paper_h:.1f} L400 {318+paper_h-tear:.1f} L370 {300+paper_h:.1f} L340 {318+paper_h+tear:.1f} L310 {300+paper_h:.1f} L280 {318+paper_h-tear:.1f} L230 {300+paper_h:.1f} Z" fill="#FFF9EB" filter="url(#shadow)"/>'
    body += _text(540, 420, str(start["label"]), 50, "#4B5563") + _text(540, 520, _money(float(start["value"])), 82, "#111827")
    if p > .35:
        body += '<line x1="300" y1="650" x2="780" y2="650" stroke="#B8B1A2" stroke-width="4" stroke-dasharray="15 12"/>'
        body += _text(540, 780, str(end["label"]), 50, "#4B5563", (p-.35)/.65)
        body += _text(540, 910, _money(float(end["value"])), 104, RED, (p-.35)/.65)
    body += _bean(820, min(1490, 420+paper_h), .78, 12, "O")
    body += _text(540, 1600, f"+{_money(float(end['value'])-float(start['value']))}", 92, ACCENT, max(0, (p-.6)/.4))
    return _svg(body, "receipt roll")


def render_cart_overflow(progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    p = _ease(progress)
    delta = abs(float(data[-1]["value"]) - float(data[0]["value"]))
    body = _text(540, 190, title.upper(), 44, MUTED)
    cart_y = 1120 + 70 * p
    body += f'<path d="M210 {cart_y-260:.1f} L820 {cart_y-260:.1f} L760 {cart_y+100:.1f} L290 {cart_y+100:.1f} Z" fill="#63D8E8" stroke="#17272E" stroke-width="14"/>'
    body += f'<line x1="210" y1="{cart_y-260:.1f}" x2="150" y2="{cart_y-370:.1f}" stroke="#17272E" stroke-width="18" stroke-linecap="round"/>'
    body += f'<circle cx="350" cy="{cart_y+150:.1f}" r="45" fill="#17272E"/><circle cx="700" cy="{cart_y+150:.1f}" r="45" fill="#17272E"/>'
    items = 12
    visible = max(2, int(items*p+.99))
    colors = (ACCENT, RED, GREEN, "#A78BFA", "#FB923C")
    for i in range(visible):
        col = i % 4
        row = i // 4
        x = 315 + col*145 + sin((i+1)*2.2)*18
        y = cart_y-300-row*125
        r = 45 + (i%3)*12
        body += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{colors[i%len(colors)]}" stroke="#17272E" stroke-width="8"/>'
    body += _bean(900, cart_y-110, .76, 22*p, "⌢")
    body += _text(540, 1545, f"THE EXTRA {_money(delta)}", 78, RED, max(0, (p-.45)/.55))
    body += _text(540, 1650, "doesn't fit quietly", 44, MUTED, max(0, (p-.55)/.45))
    return _svg(body, "cart overflow")


def render_share_squeeze(progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    p = _ease(progress)
    values = [float(d["value"]) for d in data]
    total = sum(values) or 100
    share = max(values)/total
    filled = int(100*share*p)
    body = _text(540, 190, title.upper(), 46, MUTED)
    x0, y0, size, gap = 140, 380, 70, 12
    for i in range(100):
        row, col = divmod(i, 10)
        color = ACCENT if i < filled else CARD
        body += f'<rect x="{x0+col*(size+gap)}" y="{y0+row*(size+gap)}" width="{size}" height="{size}" rx="14" fill="{color}" stroke="#26344D" stroke-width="3"/>'
    squeeze_x = x0 + min(9, filled%10)*(size+gap)
    body += _bean(min(920, max(180, squeeze_x)), 1320, .72, -14*p, "O")
    body += _text(540, 1490, f"{share*100:.0f}% TAKES THE FRAME", 78, ACCENT, max(0, (p-.45)/.55))
    return _svg(body, "share squeeze")


def render_rank_race(progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    p = _ease(progress)
    ranked = sorted(data, key=lambda d: float(d["value"]), reverse=True)
    vmax = max(float(d["value"]) for d in ranked) or 1
    body = _text(540, 190, title.upper(), 46, MUTED)
    for i, item in enumerate(ranked[:5]):
        y = 430 + i*225
        length = 140 + 720*(float(item["value"])/vmax)*p
        color = ACCENT if i == 0 else CYAN if i == 1 else "#45627F"
        body += f'<rect x="120" y="{y}" width="{length:.1f}" height="130" rx="65" fill="{color}" filter="url(#shadow)"/>'
        body += _text(145, y+86, str(item["label"]), 46, TEXT, anchor="start")
        body += _text(min(950, 145+length), y+86, f"{float(item['value']):g}", 50, TEXT, anchor="end")
    leader_x = 120 + 140 + 720*p
    body += _bean(min(930, leader_x), 480, .60, 18, "⌣")
    body += _text(540, 1600, "THE GAP IS THE FINISH", 74, ACCENT, max(0, (p-.6)/.4))
    return _svg(body, "rank race")


def render_scale_collision(progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    p = _ease(progress)
    ranked = sorted(data, key=lambda d: float(d["value"]))
    low, high = ranked[0], ranked[-1]
    ratio = abs(float(high["value"])/float(low["value"])) if float(low["value"]) else 1
    lx = 150 + 350*p
    hx = 930 - 350*p
    hit = max(0, (p-.72)/.28)
    body = _text(540, 190, title.upper(), 46, MUTED)
    body += f'<circle cx="{lx:.1f}" cy="820" r="100" fill="{CYAN}" filter="url(#shadow)"/>'
    body += f'<circle cx="{hx:.1f}" cy="820" r="{160+40*min(3,ratio)/3:.1f}" fill="{ACCENT}" filter="url(#shadow)"/>'
    body += _text(lx, 835, str(low["label"]), 38, TEXT)
    body += _text(hx, 835, str(high["label"]), 44, "#17272E")
    if hit:
        for i in range(10):
            a = i*pi/5
            body += f'<line x1="540" y1="820" x2="{540+220*hit*sin(a):.1f}" y2="{820+220*hit*sin(a+pi/2):.1f}" stroke="{RED}" stroke-width="12"/>'
    body += _bean(540, 1190, .82, 20*hit, "O")
    body += _text(540, 1450, f"{ratio:.1f}× THE SIZE", 92, RED, hit)
    return _svg(body, "scale collision")


VARIANT_RENDERERS = {
    "receipt_roll": render_receipt_roll,
    "cart_overflow": render_cart_overflow,
    "share_squeeze": render_share_squeeze,
    "rank_race": render_rank_race,
    "scale_collision": render_scale_collision,
}


def render_variant(name: str, progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    renderer = VARIANT_RENDERERS.get(name)
    if renderer is None:
        raise ValueError(f"unsupported visible variant: {name}")
    return renderer(progress, data, title)
