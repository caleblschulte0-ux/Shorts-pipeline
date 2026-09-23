"""Sample A — illustrated 2D animation (Kurzgesagt-lite)."""
import math, random, cairo, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import *

rnd = random.Random(3)
STARS = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(0.6, 2.2), rnd.uniform(0, 6.28)) for _ in range(260)]
SNOW = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(1, 3.2), rnd.uniform(0.3, 1)) for _ in range(220)]
FISH = [(rnd.uniform(0, 1), rnd.uniform(0.35, 0.95), rnd.uniform(0.6, 1.2), rnd.choice([-1, 1])) for _ in range(9)]
GLOW = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(3, 9), rnd.uniform(0, 6.28),
         rnd.choice([(0.3, 1, 0.9), (0.5, 0.8, 1), (1, 0.5, 0.9)])) for _ in range(70)]


def vgrad(cr, stops, y0=0, y1=H, x0=0, x1=W):
    g = cairo.LinearGradient(0, y0, 0, y1)
    for p, c in stops:
        g.add_color_stop_rgba(p, *hexc(c))
    cr.set_source(g)
    cr.rectangle(x0, y0, x1 - x0, y1 - y0)
    cr.fill()


def glow(cr, x, y, r, rgb, a=1.0):
    g = cairo.RadialGradient(x, y, 0, x, y, r)
    g.add_color_stop_rgba(0, *rgb, a)
    g.add_color_stop_rgba(1, *rgb, 0)
    cr.set_source(g)
    cr.arc(x, y, r, 0, 2 * math.pi)
    cr.fill()


def mountain(cr, cx, base_y, w, h, alpha=1.0):
    """Everest: two-tone faces, snow cap, a secondary ridge."""
    top = (cx + w * 0.04, base_y - h)
    # back ridge
    cr.move_to(cx - w * 0.62, base_y)
    cr.line_to(cx - w * 0.28, base_y - h * 0.62)
    cr.line_to(cx - w * 0.02, base_y - h * 0.4)
    cr.line_to(cx + w * 0.6, base_y)
    cr.close_path()
    cr.set_source_rgba(*hexc("#3b3f6e", alpha))
    cr.fill()
    # lit face
    cr.move_to(cx - w * 0.5, base_y)
    cr.line_to(*top)
    cr.line_to(cx + w * 0.12, base_y)
    cr.close_path()
    cr.set_source_rgba(*hexc("#8f93c9", alpha))
    cr.fill()
    # shadow face
    cr.move_to(cx + w * 0.12, base_y)
    cr.line_to(*top)
    cr.line_to(cx + w * 0.5, base_y)
    cr.close_path()
    cr.set_source_rgba(*hexc("#5a5e98", alpha))
    cr.fill()
    # snow cap
    sx, sy = top
    cr.move_to(sx, sy)
    cr.line_to(sx - w * 0.16, sy + h * 0.30)
    cr.line_to(sx - w * 0.08, sy + h * 0.24)
    cr.line_to(sx - w * 0.02, sy + h * 0.33)
    cr.line_to(sx + w * 0.05, sy + h * 0.25)
    cr.line_to(sx + w * 0.13, sy + h * 0.31)
    cr.close_path()
    cr.set_source_rgba(1, 1, 1, alpha)
    cr.fill()
    cr.move_to(sx, sy)
    cr.line_to(sx + w * 0.05, sy + h * 0.25)
    cr.line_to(sx + w * 0.13, sy + h * 0.31)
    cr.close_path()
    cr.set_source_rgba(*hexc("#cfd3f5", alpha))
    cr.fill()
    return top


def fish(cr, x, y, s, d, rgb, a=1):
    cr.save()
    cr.translate(x, y)
    cr.scale(d * s, s)
    cr.set_source_rgba(*rgb, a)
    cr.move_to(-30, 0)
    cr.curve_to(-10, -16, 20, -14, 30, 0)
    cr.curve_to(20, 14, -10, 16, -30, 0)
    cr.fill()
    cr.move_to(-26, 0)
    cr.line_to(-44, -12)
    cr.line_to(-44, 12)
    cr.close_path()
    cr.fill()
    cr.restore()


# ------------------------------------------------------------ beat 1
SURF = 250
FLOOR = 520
TRENCH = 1045
PX_PER_M = (TRENCH - SURF) / 10935
EV_H = 8849 * PX_PER_M


def seafloor(cr):
    cr.move_to(0, FLOOR)
    cr.line_to(640, FLOOR + 10)
    cr.curve_to(760, FLOOR + 30, 800, TRENCH, 900, TRENCH)
    cr.line_to(1460, TRENCH)
    cr.curve_to(1560, TRENCH, 1600, FLOOR + 30, 1720, FLOOR + 6)
    cr.line_to(W, FLOOR)
    cr.line_to(W, H)
    cr.line_to(0, H)
    cr.close_path()
    g = cairo.LinearGradient(0, FLOOR, 0, H)
    g.add_color_stop_rgba(0, *hexc("#2a2350"))
    g.add_color_stop_rgba(1, *hexc("#120d24"))
    cr.set_source(g)
    cr.fill()
    # rim light on the floor edge
    cr.set_line_width(4)
    cr.set_source_rgba(*hexc("#5d4fb0", 0.8))
    cr.move_to(0, FLOOR)
    cr.line_to(640, FLOOR + 10)
    cr.curve_to(760, FLOOR + 30, 800, TRENCH, 900, TRENCH)
    cr.stroke()


def scene_everest(cr, t):
    vgrad(cr, [(0, "#1b1f5c"), (0.55, "#6a4fa3"), (0.85, "#f39a6b"), (1, "#ffd08a")])
    glow(cr, 1500, 760, 380, (1, 0.8, 0.5), 0.55)
    cr.set_source_rgba(*hexc("#ffe2a8"))
    cr.arc(1500, 760, 90, 0, 2 * math.pi)
    cr.fill()
    for i in range(5):  # drifting clouds
        x = (i * 470 + t * 40 * (1 + i % 2)) % (W + 400) - 200
        y = 180 + i * 70
        cr.set_source_rgba(1, 1, 1, 0.22)
        for dx, r in ((0, 40), (40, 55), (95, 42), (135, 30)):
            cr.arc(x + dx, y, r, 0, 2 * math.pi)
            cr.fill()
    rise = ease(seg(t, 0.0, 1.6))
    mountain(cr, 820, H + 40 + (1 - rise) * 700, 1100, 820)
    # foreground hills
    cr.move_to(0, H)
    cr.curve_to(400, H - 180, 700, H - 60, 1100, H - 150)
    cr.curve_to(1400, H - 220, 1700, H - 90, W, H - 170)
    cr.line_to(W, H)
    cr.close_path()
    cr.set_source_rgba(*hexc("#2a2360"))
    cr.fill()
    a = ease(seg(t, 1.3, 2.0))
    text(cr, "MOUNT EVEREST", 1200, 300, 64, hexc("#ffffff"), alpha=a)
    text(cr, "8,849 m tall", 1204, 360, 40, hexc("#ffe2a8"), weight=cairo.FONT_WEIGHT_NORMAL, alpha=a)


def scene_ocean(cr, t):
    # sky band
    vgrad(cr, [(0, "#1b1f5c"), (1, "#f39a6b")], 0, SURF)
    # water
    g = cairo.LinearGradient(0, SURF, 0, H)
    for p, c in ((0, "#27b6d9"), (0.18, "#0f6ea8"), (0.45, "#073a70"), (1, "#020617")):
        g.add_color_stop_rgba(p, *hexc(c))
    cr.set_source(g)
    cr.rectangle(0, SURF, W, H - SURF)
    cr.fill()
    # light rays
    for i in range(6):
        x = 150 + i * 330 + 40 * math.sin(t * 0.7 + i)
        cr.move_to(x, SURF)
        cr.line_to(x + 90, SURF)
        cr.line_to(x + 260, SURF + 420)
        cr.line_to(x + 120, SURF + 420)
        cr.close_path()
        lg = cairo.LinearGradient(0, SURF, 0, SURF + 420)
        lg.add_color_stop_rgba(0, 1, 1, 1, 0.12)
        lg.add_color_stop_rgba(1, 1, 1, 1, 0)
        cr.set_source(lg)
        cr.fill()
    # fish
    for fx, fy, fs, d in FISH:
        x = ((fx * W + d * t * 60 * fs) % (W + 200)) - 100
        y = SURF + 40 + fy * 240
        fish(cr, x, y, fs * 0.8, d, (0.75, 0.95, 1), 0.35)
    seafloor(cr)
    # the drop
    fall = ease(seg(t, 3.9, 6.4))
    bounce = math.sin(seg(t, 6.4, 7.2) * math.pi) * 10 * (1 - seg(t, 6.4, 7.2))
    base_y = -120 + fall * (TRENCH + 120) - bounce
    top = mountain(cr, 1180, base_y, 560, EV_H)
    # splash when the summit crosses the surface
    sp = seg(t, 4.9, 5.9)
    if 0 < sp < 1:
        for k in range(14):
            ang = math.pi + (k / 13) * math.pi
            r = 40 + sp * 180
            cr.set_source_rgba(0.85, 0.97, 1, 1 - sp)
            cr.arc(1180 + math.cos(ang) * r, SURF + math.sin(ang) * r * 0.5, 8 * (1 - sp) + 2, 0, 6.3)
            cr.fill()
    # surface waves
    cr.move_to(0, SURF)
    for x in range(0, W + 20, 20):
        cr.line_to(x, SURF + 6 * math.sin(x / 70 + t * 2.2))
    cr.line_to(W, 0)
    cr.line_to(0, 0)
    cr.close_path()
    vgrad_path = cairo.LinearGradient(0, 0, 0, SURF)
    vgrad_path.add_color_stop_rgba(0, *hexc("#1b1f5c"))
    vgrad_path.add_color_stop_rgba(1, *hexc("#f39a6b"))
    cr.set_source(vgrad_path)
    cr.fill()
    # the answer: water above the summit
    b = seg(t, 7.0, 8.6)
    if b > 0:
        sx = 1440
        y1 = top[1]
        cr.set_source_rgba(*hexc("#ffd166"))
        cr.set_line_width(5)
        cr.move_to(sx, y1)
        cr.line_to(sx, y1 - (y1 - SURF) * ease(b))
        cr.stroke()
        for yy in (y1, y1 - (y1 - SURF) * ease(b)):
            cr.move_to(sx - 22, yy)
            cr.line_to(sx + 22, yy)
            cr.stroke()
        cr.set_dash([10, 10])
        cr.set_line_width(2)
        cr.move_to(top[0], y1)
        cr.line_to(sx, y1)
        cr.stroke()
        cr.set_dash([])
        v = int(2000 * ease(seg(t, 7.2, 9.2)))
        text(cr, f"{v:,}{'+' if v >= 2000 else ''} m", sx + 40, (y1 + SURF) / 2 + 30, 84, hexc("#ffd166"), face="Anton",
             weight=cairo.FONT_WEIGHT_NORMAL, alpha=ease(b))
        text(cr, "of water above the summit", sx + 42, (y1 + SURF) / 2 + 80, 34,
             hexc("#ffffff"), weight=cairo.FONT_WEIGHT_NORMAL, alpha=ease(b))
    text(cr, "CHALLENGER DEEP  ·  10,935 m", 1180, TRENCH - 16, 30, hexc("#b9b0ff"), anchor="center",
         alpha=ease(seg(t, 6.0, 7.0)))


# ------------------------------------------------------------ beat 2
def astronaut(cr, x, y, s, a):
    cr.save()
    cr.translate(x, y)
    cr.scale(s, s)
    cr.set_source_rgba(1, 1, 1, a)
    cr.arc(0, -34, 13, 0, 6.3)
    cr.fill()
    cr.set_source_rgba(*hexc("#1b1f5c", a))
    cr.arc(3, -34, 7, 0, 6.3)
    cr.fill()
    cr.set_source_rgba(1, 1, 1, a)
    cr.rectangle(-12, -22, 24, 26)
    cr.fill()
    cr.rectangle(-11, 2, 9, 16)
    cr.rectangle(2, 2, 9, 16)
    cr.fill()
    cr.restore()


def sub(cr, x, y, s, a=1.0, light=0.0):
    cr.save()
    cr.translate(x, y)
    cr.scale(s, s)
    if light > 0:
        cr.move_to(70, -10)
        cr.line_to(520, -170)
        cr.line_to(520, 170)
        cr.line_to(70, 10)
        cr.close_path()
        lg = cairo.LinearGradient(70, 0, 520, 0)
        lg.add_color_stop_rgba(0, 1, 0.95, 0.7, 0.45 * light)
        lg.add_color_stop_rgba(1, 1, 0.95, 0.7, 0)
        cr.set_source(lg)
        cr.fill()
    cr.set_source_rgba(*hexc("#ffc53d", a))
    cr.move_to(-60, 0)
    cr.curve_to(-60, -40, 60, -40, 70, 0)
    cr.curve_to(60, 40, -60, 40, -60, 0)
    cr.fill()
    cr.rectangle(-15, -52, 34, 22)
    cr.fill()
    cr.set_source_rgba(*hexc("#e0a019", a))
    cr.move_to(-60, 0)
    cr.line_to(-84, -20)
    cr.line_to(-84, 20)
    cr.close_path()
    cr.fill()
    cr.set_source_rgba(*hexc("#7fe7ff", a))
    cr.arc(28, -2, 14, 0, 6.3)
    cr.fill()
    cr.set_source_rgba(*hexc("#1b3a5c", a))
    cr.arc(28, -2, 14, 0, 6.3)
    cr.set_line_width(4)
    cr.stroke()
    cr.restore()


def scene_split(cr, t):
    tb = t - B2[0]
    # left: space
    vgrad(cr, [(0, "#05061a"), (1, "#141a4a")], 0, H, 0, W / 2)
    for x, y, r, ph in STARS:
        if x < W / 2:
            cr.set_source_rgba(1, 1, 1, 0.35 + 0.35 * math.sin(t * 2 + ph))
            cr.arc(x, y, r, 0, 6.3)
            cr.fill()
    mx, my, mr = W / 4, 640, 300
    glow(cr, mx, my, mr * 1.35, (0.7, 0.75, 1), 0.25)
    rg = cairo.RadialGradient(mx - 90, my - 110, 30, mx, my, mr)
    rg.add_color_stop_rgba(0, *hexc("#e8e9f2"))
    rg.add_color_stop_rgba(1, *hexc("#8e90a8"))
    cr.set_source(rg)
    cr.arc(mx, my, mr, 0, 6.3)
    cr.fill()
    for cx, cy, r in ((-90, -40, 46), (70, 60, 60), (10, -150, 30), (120, -90, 26), (-40, 130, 34)):
        cr.set_source_rgba(*hexc("#77798f", 0.55))
        cr.arc(mx + cx, my + cy, r, 0, 6.3)
        cr.fill()
    # twelve astronauts along the moon's upper rim
    for k in range(12):
        tk = seg(tb, 0.3 + k * 0.28, 0.6 + k * 0.28)
        if tk <= 0:
            continue
        ang = math.pi * (1.12 + 0.76 * k / 11)
        x = mx + math.cos(ang) * (mr + 4)
        y = my + math.sin(ang) * (mr + 4)
        pop = 1 + 0.35 * math.sin(tk * math.pi)
        cr.save()
        cr.translate(x, y)
        cr.rotate(ang + math.pi / 2)
        astronaut(cr, 0, 0, 1.2 * pop * ease(tk), 1)
        cr.restore()
    n12 = min(12, int(12 * seg(tb, 0.3, 3.7) + 0.999))
    text(cr, f"{n12}", W / 4, 200, 150, hexc("#ffffff"), face="Anton",
         weight=cairo.FONT_WEIGHT_NORMAL, anchor="center", alpha=ease(seg(tb, 0.2, 0.6)))
    text(cr, "people have walked on the Moon", W / 4, 262, 36, hexc("#c9ccff"),
         weight=cairo.FONT_WEIGHT_NORMAL, anchor="center", alpha=ease(seg(tb, 0.4, 0.9)))
    # right: the deep
    vgrad(cr, [(0, "#04142b"), (1, "#01040b")], 0, H, W / 2, W)
    for x, y, r, a in SNOW:
        if x > W / 2:
            yy = (y + t * 25 * a) % H
            cr.set_source_rgba(0.8, 0.9, 1, 0.25 * a)
            cr.arc(x, yy, r * 0.8, 0, 6.3)
            cr.fill()
    cr.move_to(W / 2, 900)
    cr.curve_to(W * 0.65, 860, W * 0.8, 930, W, 880)
    cr.line_to(W, H)
    cr.line_to(W / 2, H)
    cr.close_path()
    cr.set_source_rgba(*hexc("#1a1530"))
    cr.fill()
    for k in range(27):
        tk = seg(tb, 3.6 + k * 0.11, 3.9 + k * 0.11)
        if tk <= 0:
            continue
        col, row = k % 9, k // 9
        x = W / 2 + 150 + col * 90
        y = 520 + row * 95
        sub(cr, x, y, 0.42 * ease(tk) * (1 + 0.3 * math.sin(tk * math.pi)))
    text(cr, "a few dozen", W * 0.75, 200, 110, hexc("#ffc53d"), face="Anton",
         weight=cairo.FONT_WEIGHT_NORMAL, anchor="center", alpha=ease(seg(tb, 3.6, 4.1)))
    text(cr, "have reached the deepest point in the ocean", W * 0.75, 262, 34, hexc("#c9e8ff"),
         weight=cairo.FONT_WEIGHT_NORMAL, anchor="center", alpha=ease(seg(tb, 3.8, 4.3)))
    # divider
    cr.set_source_rgba(1, 1, 1, 0.12)
    cr.rectangle(W / 2 - 1, 0, 2, H)
    cr.fill()
    # "better than the floor of our own planet": the Moon gets its map grid
    gm = seg(tb, 7.4, 10.0)
    if gm > 0:
        cr.save()
        cr.arc(mx, my, mr, 0, 6.3)
        cr.clip()
        cr.set_source_rgba(*hexc("#7cf0ff", 0.55))
        cr.set_line_width(2)
        span = ease(gm)
        for i in range(-6, 7):
            cr.move_to(mx - mr, my + i * 48)
            cr.line_to(mx - mr + 2 * mr * span, my + i * 48)
            cr.stroke()
            cr.move_to(mx + i * 48, my - mr)
            cr.line_to(mx + i * 48, my - mr + 2 * mr * span)
            cr.stroke()
        cr.restore()
        text(cr, "MAPPED", W / 4, H - 70, 40, hexc("#7cf0ff"), anchor="center", alpha=ease(gm))
        text(cr, "MOSTLY UNSEEN", W * 0.75, H - 70, 40, hexc("#ff8fa3"), anchor="center",
             alpha=ease(gm))


# ------------------------------------------------------------ beat 3
ZONES = [(0, "SUNLIGHT ZONE"), (200, "TWILIGHT ZONE"), (1000, "MIDNIGHT ZONE"),
         (4000, "THE ABYSS"), (6000, "THE TRENCHES")]
DEPTH_COLS = [(0, "#1fa3d6"), (200, "#0f6ea8"), (1000, "#083a6b"), (4000, "#03122a"),
              (11000, "#010409")]


def depth_at(u):
    return 10935 * (u ** 2.2)


def col_at(d):
    for (d0, c0), (d1, c1) in zip(DEPTH_COLS, DEPTH_COLS[1:]):
        if d <= d1:
            k = (d - d0) / (d1 - d0)
            a, b = hexc(c0), hexc(c1)
            return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))
    return hexc(DEPTH_COLS[-1][1])[:3]


def scene_descent(cr, t):
    tb = t - B3[0]
    u = seg(tb, 0.4, B3[1] - B3[0] + 0.2)
    d = depth_at(u)
    top, bot = col_at(max(0, d - 300)), col_at(d + 300)
    g = cairo.LinearGradient(0, 0, 0, H)
    g.add_color_stop_rgb(0, *top)
    g.add_color_stop_rgb(1, *bot)
    cr.set_source(g)
    cr.paint()
    light = clamp(1 - d / 400)
    for i in range(6):  # sun rays fade with depth
        x = 100 + i * 340 + 50 * math.sin(t * 0.6 + i)
        cr.move_to(x, 0)
        cr.line_to(x + 110, 0)
        cr.line_to(x + 330, H)
        cr.line_to(x + 160, H)
        cr.close_path()
        cr.set_source_rgba(1, 1, 1, 0.08 * light)
        cr.fill()
    speed = 120 + 900 * u
    for x, y, r, a in SNOW:  # particles stream past = we are sinking
        yy = (y - t * speed * a) % H
        cr.set_source_rgba(0.85, 0.95, 1, 0.3 * a)
        cr.arc(x, yy, r * 0.9, 0, 6.3)
        cr.fill()
    if d < 900:
        for fx, fy, fs, dd in FISH:
            x = ((fx * W + dd * t * 90 * fs) % (W + 200)) - 100
            y = (fy * H - tb * 160 * fs) % H
            fish(cr, x, y, fs * 1.3, dd, (0.95, 0.75, 0.35), 0.8 * clamp(1 - d / 900))
    dark = clamp((d - 600) / 1500)
    if dark > 0:
        for x, y, r, ph, rgb in GLOW:
            yy = (y - t * speed * 0.6) % H
            glow(cr, x, yy, r * 5, rgb, 0.55 * dark * (0.6 + 0.4 * math.sin(t * 3 + ph)))
    # bubbles from the sub
    for k in range(10):
        ph = (t * 0.9 + k / 10) % 1
        cr.set_source_rgba(0.9, 0.97, 1, 0.5 * (1 - ph))
        cr.arc(900 + 12 * math.sin(k + t * 3), 470 - ph * 380, 4 + 6 * ph, 0, 6.3)
        cr.set_line_width(2)
        cr.stroke()
    sub(cr, 960, 520 + 12 * math.sin(t * 1.6), 1.6, light=clamp((d - 300) / 1200))
    # HUD
    zone = [z for z0, z in ZONES if d >= z0][-1]
    text(cr, "DEPTH", 1560, 110, 30, hexc("#ffffff", 0.7), weight=cairo.FONT_WEIGHT_NORMAL)
    text(cr, f"{int(d):,} m", 1556, 200, 92, hexc("#ffd166"), face="Anton", weight=cairo.FONT_WEIGHT_NORMAL)
    text(cr, zone, 1560, 250, 30, hexc("#7cf0ff"))


def frame(cr, t):
    if t < B1[0] + 3.5:
        scene_everest(cr, t)
        if t > 3.1:
            cr.set_source_rgba(0, 0, 0, seg(t, 3.1, 3.5))
            cr.paint()
    elif t < B2[0] - 0.1:
        scene_ocean(cr, t)
        if t < 3.9:
            cr.set_source_rgba(0, 0, 0, 1 - seg(t, 3.5, 3.9))
            cr.paint()
    elif t < B3[0] - 0.1:
        scene_split(cr, t)
    else:
        scene_descent(cr, t)
    # quick dips between beats
    for bt in (B2[0], B3[0]):
        k = 1 - abs(t - bt + 0.05) / 0.25
        if k > 0:
            cr.set_source_rgba(0, 0, 0, k)
            cr.paint()


if __name__ == "__main__":
    render(frame, sys.argv[1] if len(sys.argv) > 1 else "A_2d_animation.mp4")
