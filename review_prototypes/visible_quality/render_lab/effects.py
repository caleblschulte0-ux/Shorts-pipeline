from __future__ import annotations

from html import escape
from math import sin, pi
from typing import Mapping

W, H = 1080, 1920
BG = "#07101E"
CARD = "#111C31"
TEXT = "#F8FAFC"
MUTED = "#9FB0C8"
ACCENT = "#F2C14E"
CYAN = "#63D8E8"
RED = "#F06464"


def _clamp(p: float) -> float:
    return max(0.0, min(1.0, float(p)))


def _ease(p: float) -> float:
    p = _clamp(p)
    return 1 - (1 - p) ** 3


def _svg(body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        f'<title>{escape(title)}</title><rect width="{W}" height="{H}" fill="{BG}"/>'
        '<defs><filter id="shadow"><feDropShadow dx="0" dy="18" stdDeviation="20" flood-opacity=".35"/></filter>'
        '<filter id="glow"><feGaussianBlur stdDeviation="12" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
        f'{body}</svg>'
    )


def _text(x: float, y: float, text: str, size: int, color: str = TEXT, anchor: str = "middle", weight: int = 800, opacity: float = 1) -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="Arial, sans-serif" '
            f'font-size="{size}" font-weight="{weight}" fill="{color}" opacity="{opacity:.3f}">{escape(text)}</text>')


def _mascot(x: float, y: float, scale: float, pose: str, expression: str = "strain") -> str:
    arm = 65 * scale
    body_h = 150 * scale
    lean = {"drag_line": -18, "hoist_stack": 0, "ride": 16, "push": 20, "point_at": -8}.get(pose, 0)
    eye = "○" if expression in {"shock", "strain"} else "•"
    mouth = "O" if expression == "shock" else ("⌢" if expression == "strain" else "⌣")
    return (
        f'<g transform="translate({x:.1f},{y:.1f}) rotate({lean}) scale({scale:.3f})" filter="url(#shadow)">'
        '<ellipse cx="0" cy="-62" rx="78" ry="100" fill="#5FD0C7" stroke="#17272E" stroke-width="10"/>'
        f'<line x1="-55" y1="-45" x2="{-55-arm}" y2="-20" stroke="#17272E" stroke-width="16" stroke-linecap="round"/>'
        f'<line x1="55" y1="-45" x2="{55+arm}" y2="-20" stroke="#17272E" stroke-width="16" stroke-linecap="round"/>'
        f'<line x1="-30" y1="20" x2="-45" y2="{body_h-35}" stroke="#17272E" stroke-width="18" stroke-linecap="round"/>'
        f'<line x1="30" y1="20" x2="45" y2="{body_h-35}" stroke="#17272E" stroke-width="18" stroke-linecap="round"/>'
        f'<text x="-28" y="-78" font-size="32" text-anchor="middle" fill="#17272E">{eye}</text>'
        f'<text x="28" y="-78" font-size="32" text-anchor="middle" fill="#17272E">{eye}</text>'
        f'<text x="0" y="-35" font-size="34" text-anchor="middle" fill="#17272E">{mouth}</text>'
        '</g>'
    )


def _money(v: float) -> str:
    return f"${v:,.0f}"


def render_before_after(progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    p = _ease(progress)
    start, end = data[0], data[-1]
    left_x = 540 - 310 * p
    right_x = 540 + 310 * p
    crack = 8 + 34 * p
    delta = float(end["value"]) - float(start["value"])
    body = (
        _text(540, 210, title.upper(), 44, MUTED, weight=700)
        + f'<rect x="70" y="350" width="440" height="720" rx="50" fill="{CARD}" filter="url(#shadow)"/>'
        + f'<rect x="570" y="350" width="440" height="720" rx="50" fill="#15243E" filter="url(#shadow)"/>'
        + _text(left_x, 560, str(start["label"]), 68, MUTED)
        + _text(right_x, 560, str(end["label"]), 68, CYAN)
        + _text(left_x, 760, _money(float(start["value"])), 112, TEXT)
        + _text(right_x, 760, _money(float(end["value"])), 112, ACCENT)
        + f'<path d="M540 330 L{540-crack} 650 L{540+crack} 870 L{540-10} 1150" stroke="{RED}" stroke-width="{10+10*p:.1f}" fill="none" opacity="{p:.3f}" filter="url(#glow)"/>'
        + _text(540, 1250, f"+{_money(abs(delta))}", 92, RED, opacity=p)
        + _mascot(540, 1090, 0.85, "drag_line", "shock")
    )
    return _svg(body, "before and after snap")


def render_trend_yank(progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    p = _ease(progress)
    vals = [float(d["value"]) for d in data]
    lo, hi = min(vals), max(vals)
    points = []
    for i, value in enumerate(vals):
        x = 130 + i * (820 / max(1, len(vals)-1))
        y = 1220 - (value-lo)/max(1, hi-lo) * 620
        points.append((x, y))
    seg = p * (len(points)-1)
    idx = min(int(seg), len(points)-2)
    frac = seg-idx
    active = points[:idx+1]
    hx = points[idx][0] + (points[idx+1][0]-points[idx][0])*frac
    hy = points[idx][1] + (points[idx+1][1]-points[idx][1])*frac
    active.append((hx, hy))
    path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x,y in active)
    area = path + f" L{hx:.1f},1320 L{active[0][0]:.1f},1320 Z"
    body = (
        _text(540, 210, title.upper(), 44, MUTED, weight=700)
        + f'<path d="{area}" fill="{CYAN}" opacity=".14"/>'
        + f'<path d="{path}" fill="none" stroke="{CYAN}" stroke-width="22" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/>'
        + f'<line x1="110" y1="1320" x2="970" y2="1320" stroke="#30405B" stroke-width="6"/>'
        + f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="30" fill="{ACCENT}" filter="url(#glow)"/>'
        + _mascot(hx-10, hy-65, 0.70, "drag_line", "strain")
        + _text(540, 1480, _money(vals[-1]), 92, ACCENT, opacity=max(0, (p-.55)/.45))
    )
    for x, y in points:
        body += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="{TEXT}" opacity=".55"/>'
    return _svg(body, "trend yanks mascot")


def render_burden_stack(progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    p = _ease(progress)
    delta = float(data[-1]["value"]) - float(data[0]["value"])
    blocks = 7
    visible = min(blocks, max(1, int(p * blocks + .99)))
    base_y = 1330
    body = _text(540, 210, title.upper(), 44, MUTED, weight=700)
    for i in range(visible):
        y = base_y - i * 112
        wobble = sin((p * 6 + i) * pi) * 8 * p
        body += (f'<g transform="translate({wobble:.1f},0)"><rect x="310" y="{y}" width="460" height="88" rx="20" '
                 f'fill="{ACCENT if i==visible-1 else CARD}" stroke="{ACCENT}" stroke-width="5" filter="url(#shadow)"/>'
                 + _text(540, y+59, f"+{_money(abs(delta)/blocks)}", 38, TEXT) + '</g>')
    body += _mascot(540, base_y+105, 0.88, "hoist_stack", "strain")
    body += _text(540, 1555, f"THE EXTRA {_money(abs(delta))}", 72, RED, opacity=max(0, (p-.45)/.55))
    body += _text(540, 1660, "has to come from somewhere", 42, MUTED, opacity=max(0, (p-.58)/.42))
    return _svg(body, "burden stack")


def render_callback(progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    p = _ease(progress)
    start, end = data[0], data[-1]
    bridge = 110 + 860 * p
    body = (
        _text(540, 210, "NOW THE OPENING MAKES SENSE", 42, MUTED, weight=700)
        + f'<rect x="80" y="420" width="330" height="420" rx="40" fill="{CARD}"/>'
        + f'<rect x="670" y="420" width="330" height="420" rx="40" fill="#15243E"/>'
        + _text(245, 560, str(start["label"]), 56, MUTED)
        + _text(835, 560, str(end["label"]), 56, CYAN)
        + _text(245, 710, _money(float(start["value"])), 78, TEXT)
        + _text(835, 710, _money(float(end["value"])), 78, ACCENT)
        + f'<path d="M245 990 C420 770, 610 1250, {bridge:.1f} 990" fill="none" stroke="{CYAN}" stroke-width="20" stroke-linecap="round" filter="url(#glow)"/>'
        + _mascot(min(835, bridge), 930, 0.72, "ride", "happy")
        + _text(540, 1380, title, 58, TEXT, opacity=max(0, (p-.25)/.75))
        + _text(540, 1490, "THE GAP IS THE STORY", 82, ACCENT, opacity=max(0, (p-.55)/.45))
    )
    return _svg(body, "callback bridge")


def render_generic(progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    p = _ease(progress)
    body = _text(540, 240, title.upper(), 46, MUTED)
    body += f'<circle cx="540" cy="890" r="{260+100*p:.1f}" fill="{CYAN}" opacity=".15"/>'
    body += f'<circle cx="540" cy="890" r="{90+50*p:.1f}" fill="{ACCENT}" filter="url(#glow)"/>'
    body += _mascot(540, 760, 0.9, "point_at", "shock")
    body += _text(540, 1330, "VISIBLE CHANGE", 80, TEXT, opacity=p)
    return _svg(body, "generic physical demonstration")


def render_event(event: str, progress: float, data: tuple[Mapping[str, object], ...], title: str) -> str:
    e = event.lower()
    if any(token in e for token in ("split_screen", "two_dates", "gap_opens")):
        return render_before_after(progress, data, title)
    if any(token in e for token in ("line_", "trend", "yanks_mascot")):
        return render_trend_yank(progress, data, title)
    if any(token in e for token in ("stack", "burden", "must_hold")):
        return render_burden_stack(progress, data, title)
    if any(token in e for token in ("callback", "opening_split", "full_trend_draws")):
        return render_callback(progress, data, title)
    return render_generic(progress, data, title)
