"""People: the round-headed doodle characters.

Everyone is drawn the way the channels the operator pointed at draw them: a
big white round head with a dark marker outline, dot eyes, a small mouth,
messy hair, a simple outfit with a shadow side, and thick ink stick limbs
ending in small mitten hands and oval feet. The head is white for everyone —
it is a cartoon convention, not a skin tone, and it keeps every era and place
drawable by one rig.

A person is (who, era, seed) for LOOK, (pose, action, facing, mood) for what
they are DOING, and a time `t` in seconds. Actions are loops of real work —
stirring, knapping, eating, warming hands — so a scene moves because somebody
is doing something (never an idle bob: see ink.py on vibration).

Every name a script may use is a key of POSES / ACTIONS / WHO / MOODS / ITEMS;
`validate_cast` refuses anything else. A name looked up with a silent default
is a capability that does not exist (CLAUDE.md), so nothing here has one.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

from . import ink
from .ink import INK, rgb, shade

HEAD = rgb("#fbf8f1")
R0 = 46.0                                   # head radius of an adult at scale 1

WHO = {
    # size, hair default, beard?, long hair?
    "man": dict(size=1.0, beard=0.5, long=False, grey=False),
    "woman": dict(size=0.96, beard=0.0, long=True, grey=False),
    "child": dict(size=0.72, beard=0.0, long=False, grey=False),
    "girl": dict(size=0.72, beard=0.0, long=True, grey=False),
    "elder": dict(size=0.95, beard=0.9, long=False, grey=True),
    "old_woman": dict(size=0.92, beard=0.0, long=True, grey=True),
}

HAIR = [rgb("#6b4526"), rgb("#5a3d2a"), rgb("#8a5a2b"), rgb("#4a3a33"), rgb("#9c6b3a")]
GREY_HAIR = [rgb("#c9c4bd"), rgb("#aaa49c")]
EGYPT_HAIR = [rgb("#2e2a2c"), rgb("#3a3234")]

# era -> outfit palette and pattern
OUTFIT = {
    "stone_age": dict(cloth=[rgb("#b87a45"), rgb("#a86c3c"), rgb("#c48c55")],
                      texture="fur", strap=True),
    "medieval": dict(cloth=[rgb("#5d7a9e"), rgb("#7b8f55"), rgb("#9a5d45"),
                            rgb("#8c7a5a"), rgb("#6d6591"), rgb("#a3844e")],
                     texture=None, strap=False),
    # the Mediterranean world of Rome and Greece: undyed tunics, a few in
    # terracotta, olive and sea blue, a rope belt, no hood
    "ancient": dict(cloth=[rgb("#e9e1cf"), rgb("#e0d3b4"), rgb("#c47a55"), rgb("#8b9a60"),
                           rgb("#6f8fa8"), rgb("#d9c9a0")],
                    texture=None, strap=False),
    # the 19th century: dark wool coats and long dresses, a flat cap or a bonnet
    "victorian": dict(cloth=[rgb("#3f4650"), rgb("#5a4a3f"), rgb("#4e5a4a"), rgb("#6e3f3f"),
                             rgb("#3a3f5c"), rgb("#7a6a55")],
                      texture=None, strap=False),
    # the Nile valley: white linen, a kilt or a straight dress, black hair, a collar of colour
    "egypt": dict(cloth=[rgb("#f2ecdc"), rgb("#ece3cc"), rgb("#f5efe0"), rgb("#e6dcc0")],
                  texture=None, strap=False),
    # 1500-1750: wool coats and doublets in deep colours, a tricorn or a coif
    "early_modern": dict(cloth=[rgb("#5a3a2a"), rgb("#2f4a6a"), rgb("#6b2f2f"), rgb("#3f5a3a"),
                                rgb("#8a6a3a"), rgb("#4a3a5a")],
                         texture=None, strap=False),
}

POSES = ("stand", "sit", "sit_on", "crouch", "lie", "walk")
MOODS = ("calm", "happy", "sleepy", "worried", "surprised", "content", "focused")
ITEMS = ("none", "spear", "stick", "torch", "bowl", "fish", "stone", "axe",
         "bundle", "basket", "rod", "bread", "cup", "hoe", "lantern", "needle")

# action -> poses it can be done in (validation), and the item it implies
ACTIONS = {
    "idle": dict(poses=POSES, item=None),
    "warm_hands": dict(poses=("stand", "sit", "sit_on", "crouch"), item=None),
    "stir": dict(poses=("stand", "sit", "sit_on", "crouch"), item="stick"),
    "eat": dict(poses=("stand", "sit", "sit_on", "crouch"), item="bread"),
    "drink": dict(poses=("stand", "sit", "sit_on", "crouch"), item="cup"),
    "carry": dict(poses=("stand", "walk"), item="bundle"),
    "point": dict(poses=("stand", "sit", "sit_on", "walk"), item=None),
    "talk": dict(poses=("stand", "sit", "sit_on", "crouch"), item=None),
    "wave": dict(poses=("stand", "sit", "sit_on", "walk"), item=None),
    "knap": dict(poses=("sit", "sit_on", "crouch"), item="stone"),
    "gather": dict(poses=("crouch", "stand"), item=None),
    "hold": dict(poses=POSES[:4] + ("walk",), item=None),
    "sleep": dict(poses=("lie",), item=None),
    "yawn": dict(poses=("stand", "sit", "sit_on"), item=None),
    "sew": dict(poses=("sit", "sit_on"), item="needle"),
    "chop": dict(poses=("stand",), item="axe"),
    "fish": dict(poses=("stand", "sit", "sit_on"), item="rod"),
    "hoe": dict(poses=("stand",), item="hoe"),
    "hug_self": dict(poses=("stand", "sit", "sit_on", "crouch"), item=None),
    "look_up": dict(poses=("stand", "sit", "sit_on", "lie"), item=None),
    "play": dict(poses=("stand", "crouch"), item="stick"),
    "feed_fire": dict(poses=("sit", "sit_on", "crouch"), item="stick"),
}


def _person_rng(seed):
    return random.Random(seed * 7919 + 13)


@lru_cache(maxsize=4096)
def look(who: str, era: str, seed: int) -> dict:
    """The fixed appearance of one person — the same on every frame."""
    w = WHO[who]
    r = _person_rng(seed)
    o = OUTFIT[era]
    hair = r.choice(GREY_HAIR if w["grey"] else (EGYPT_HAIR if era == "egypt" else HAIR))
    cloth = r.choice(o["cloth"])
    lk = dict(size=w["size"], hair=hair, cloth=cloth, texture=o["texture"],
              strap=o["strap"], long=w["long"],
              beard=r.random() < w["beard"], era=era, who=who,
              hood=(era == "medieval" and r.random() < 0.35 and not w["long"]),
              scarf=(era == "medieval" and w["long"] and r.random() < 0.6),
              cap=(era == "victorian" and not w["long"] and r.random() < 0.7),
              bonnet=(era == "victorian" and w["long"] and r.random() < 0.6),
              tricorn=(era == "early_modern" and not w["long"] and r.random() < 0.65),
              coif=(era == "early_modern" and w["long"] and r.random() < 0.6),
              spikes=r.randint(6, 9), seed=seed)
    return lk


# ------------------------------------------------------------------ skeleton
def _ik(sx, sy, tx, ty, l1, l2, bend):
    """Two-bone IK: elbow position for a shoulder->hand chain. `bend` +1/-1."""
    dx, dy = tx - sx, ty - sy
    d = max(1e-6, math.hypot(dx, dy))
    d_c = min(d, l1 + l2 - 1e-3)
    a = math.atan2(dy, dx)
    cos_b = (l1 * l1 + d_c * d_c - l2 * l2) / (2 * l1 * d_c)
    b = math.acos(max(-1.0, min(1.0, cos_b)))
    ex = sx + l1 * math.cos(a + bend * b)
    ey = sy + l1 * math.sin(a + bend * b)
    if d > l1 + l2:
        tx, ty = sx + (l1 + l2) * dx / d, sy + (l1 + l2) * dy / d
    return (ex, ey), (tx, ty)


def skeleton(pose: str, R: float, t: float, phase: float = 0.0) -> dict:
    """Joint positions in LOCAL coords: feet on the ground at y=0, facing +x.
    Returns hips, neck, head centre, and leg chains (hip, knee, foot) x2."""
    leg, torso = 2.0 * R, 1.75 * R
    if pose in ("stand",):
        hip = (0.0, -leg)
        legs = [((-0.28 * R, -leg), (-0.30 * R, -leg * 0.5), (-0.34 * R, 0.0)),
                ((0.28 * R, -leg), (0.30 * R, -leg * 0.5), (0.36 * R, 0.0))]
        lean = 0.0
    elif pose == "walk":
        hip = (0.0, -leg)
        c = t * 2 * math.pi / 1.1 + phase
        legs = []
        for k, s in ((0, 1), (1, -1)):
            sw = math.sin(c) * s
            foot = (0.62 * R * sw, -max(0.0, math.cos(c) * s) * 0.18 * R)
            knee = (0.22 * R * sw + 0.18 * R, -leg * 0.52)
            legs.append(((0.0, -leg), knee, foot))
        lean = 0.06
    elif pose == "sit":
        hip = (0.0, -0.32 * R)
        legs = [((-0.1 * R, -0.32 * R), (0.95 * R, -1.05 * R), (1.55 * R, 0.0)),
                ((0.15 * R, -0.32 * R), (1.15 * R, -0.95 * R), (1.8 * R, 0.0))]
        lean = -0.02
    elif pose == "sit_on":
        seat = 1.05 * R
        hip = (0.0, -seat)
        legs = [((-0.1 * R, -seat), (0.95 * R, -seat), (0.95 * R, 0.0)),
                ((0.15 * R, -seat), (1.15 * R, -seat + 0.05 * R), (1.2 * R, 0.0))]
        lean = 0.0
    elif pose == "crouch":
        hip = (-0.3 * R, -0.95 * R)
        legs = [((-0.3 * R, -0.95 * R), (0.55 * R, -1.45 * R), (0.35 * R, 0.0)),
                ((-0.2 * R, -0.95 * R), (0.75 * R, -1.25 * R), (0.7 * R, 0.0))]
        lean = 0.22
    else:
        raise KeyError(f"pose {pose!r} has no skeleton")
    neck = (hip[0] + math.sin(lean) * torso, hip[1] - math.cos(lean) * torso)
    head = (neck[0] + math.sin(lean) * 0.9 * R, neck[1] - math.cos(lean) * 0.95 * R)
    return dict(hip=hip, neck=neck, head=head, legs=legs, lean=lean)


def head_of(sk: dict, R: float, action: str) -> tuple[float, float]:
    """Where the head is drawn for an action: tipped back and up when the
    figure looks up, so the whole silhouette says it, not just the eyes."""
    hx, hy = sk["head"]
    if action == "look_up":
        return hx + 0.3 * R, hy - 0.2 * R
    return hx, hy


# what is carried at the side whatever the free hand is doing
LOW_HELD = ("lantern", "torch")


def hand_targets(action: str, sk: dict, R: float, t: float, ph: float):
    """(front_hand, back_hand) targets in local coords for an action at t."""
    nx, ny = sk["neck"]
    hx, hy = sk["hip"]
    chest = (nx + 0.9 * R, ny + 0.9 * R)
    rest_f = (nx + 0.42 * R, hy - 0.05 * R)
    rest_b = (nx - 0.42 * R, hy - 0.05 * R)
    c = 2 * math.pi * t
    if action in ("idle", "hold"):
        return rest_f, rest_b
    if action == "warm_hands":
        k = math.sin(c / 1.3 + ph) * 0.18 * R
        return ((nx + 1.35 * R + k, ny + 0.95 * R), (nx + 1.2 * R - k, ny + 1.05 * R))
    if action == "stir":
        a = c / 2.2 + ph
        return ((nx + 1.45 * R + math.cos(a) * 0.35 * R, ny + 1.25 * R + math.sin(a) * 0.12 * R),
                rest_b)
    if action in ("eat", "drink"):
        k = (math.sin(c / 3.0 + ph) + 1) / 2          # 0 at lap, 1 at mouth
        k = k ** 2
        # beside the chin, not over the mouth: a bowl at the mouth "covers
        # the man's face" (the ninth film's storyboard)
        mouth = (sk["head"][0] + 1.0 * R, sk["head"][1] + 0.8 * R)
        lap = (nx + 1.0 * R, ny + 1.4 * R)
        return ((lap[0] + (mouth[0] - lap[0]) * k, lap[1] + (mouth[1] - lap[1]) * k),
                (nx + 0.8 * R, ny + 1.5 * R))
    if action == "carry":
        # in both arms, in front, at the waist
        return ((nx + 0.95 * R, ny + 1.35 * R), (nx + 0.7 * R, ny + 1.5 * R))
    if action == "point":
        # short of a straight arm, so the elbow bends
        k = math.sin(c / 4.0 + ph) * 0.08 * R
        return ((nx + 1.55 * R, ny + 0.2 * R + k), rest_b)
    if action == "play":
        # a stick swung between chest and knee, both hands in it — swung
        # high it rose out of the head "like an antenna" (the ninth film)
        k = math.sin(c / 1.1 + ph)
        return ((nx + 1.1 * R + k * 0.4 * R, ny + 1.0 * R - k * 0.45 * R),
                (nx + 0.8 * R + k * 0.35 * R, ny + 1.2 * R - k * 0.35 * R))
    if action == "feed_fire":
        # a branch pushed low toward the flames and drawn back
        k = (math.sin(c / 2.6 + ph) + 1) / 2
        return ((nx + 1.1 * R + k * 0.7 * R, ny + 1.35 * R + k * 0.25 * R), rest_b)
    if action == "talk":
        # a hand raised and turned as the teller speaks — big enough to read
        # from across the room
        k = (math.sin(c / 1.8 + ph) + 1) / 2
        return ((nx + 1.15 * R + k * 0.25 * R, ny + 0.95 * R - k * 0.95 * R), rest_b)
    if action == "wave":
        k = math.sin(c / 0.9 + ph)
        return ((nx + 0.7 * R + k * 0.35 * R, ny - 1.25 * R), rest_b)
    if action == "knap":
        # the hammerstone rises to shoulder height and comes down on the core
        # in the lap — a swing big enough to read (the ninth film: "the woman
        # knapping flint is never shown")
        k = abs(math.sin(c / 1.6 + ph))
        return ((nx + 1.15 * R, ny + 0.15 * R + k * 1.2 * R), (nx + 1.0 * R, ny + 1.55 * R))
    if action == "gather":
        k = (math.sin(c / 3.2 + ph) + 1) / 2
        return ((nx + 1.3 * R, sk["hip"][1] + (0.9 - 0.3 * k) * R), rest_b)
    if action == "yawn":
        k = max(0.0, math.sin(c / 5.0 + ph))
        up = (nx + 0.3 * R, ny - 1.3 * R * k + 0.9 * R * (1 - k))
        return (up, (nx - 0.3 * R, ny - 1.3 * R * k + 0.9 * R * (1 - k)))
    if action == "sew":
        k = (math.sin(c / 1.5 + ph) + 1) / 2
        return ((nx + 0.9 * R + k * 0.6 * R, ny + 1.25 * R - k * 0.35 * R),
                (nx + 0.85 * R, ny + 1.4 * R))
    if action == "chop":
        # the hands well forward: at 1.0 R the axe head passed through the
        # face at the top of the swing (the medieval storyboard: "axe handle
        # and head cross the man's face"); tests hold the gap
        k = abs(math.sin(c / 2.4 + ph))
        y = ny - 0.9 * R + k * 2.4 * R
        return ((nx + 1.35 * R, y), (nx + 1.1 * R, y + 0.1 * R))
    if action == "hoe":
        k = abs(math.sin(c / 2.8 + ph))
        y = ny + 0.2 * R + k * 0.9 * R
        return ((nx + 1.55 * R, y), (nx + 1.15 * R, y - 0.4 * R))
    if action == "fish":
        k = math.sin(c / 4.5 + ph) * 0.1 * R
        return ((nx + 1.25 * R, ny + 0.7 * R + k), (nx + 1.0 * R, ny + 0.85 * R + k))
    if action == "hug_self":
        # arms crossed on the chest, each hand at the other shoulder
        return ((nx - 0.05 * R, ny + 0.55 * R), (nx + 0.5 * R, ny + 0.6 * R))
    if action == "look_up":
        # hands down. Every raised arm was tried — straight up crossed the
        # face, behind vanished, at the brow read as a hand at the cheek,
        # stretched past the crown read as "an antenna" (the ninth film) —
        # so the head tipped well back and the open mouth say it, and a
        # figure lying on its back says it best (see _draw_lying)
        return rest_f, rest_b
    raise KeyError(f"action {action!r} has no hands")


# ------------------------------------------------------------------ drawing
def _breath(cr, cx, cy, R, t, seed):
    """A puff of breath every few seconds in frost or snow — the sixth
    film's judge could see no cold in the cold chapter. It leaves the
    mouth, drifts up and forward, and fades."""
    period = 3.4 + (seed % 5) * 0.3
    u = ((t + seed * 0.7) % period) / period
    if u > 0.55:
        return
    k = u / 0.55
    mx, my = cx + 0.3 * R, cy + 0.4 * R
    for i in range(3):
        px = mx + (0.35 + 0.9 * k + i * 0.22) * R
        py = my - (0.15 + 0.7 * k) * R + i * 0.08 * R
        rr = (0.12 + 0.3 * k) * R * (1 - i * 0.2)
        ink.dot(cr, px, py, rr, (0.96, 0.97, 1.0, 0.55 * (1 - k)))


def _face_up(cr, cx, cy, R, t, seed, lw):
    """A face turned straight up, seen from the side: two eyes at the crown,
    one above the other, and a small open mouth forward of them."""
    r = random.Random(seed)
    blink = (t + r.random() * 5) % 4.5 < 0.14
    ex, ey = cx + 0.15 * R, cy - 0.55 * R
    for dy in (-0.3 * R, 0.3 * R):
        if blink:
            ink.line(cr, [(ex - 0.08 * R, ey + dy - 0.12 * R), (ex + 0.06 * R, ey + dy),
                          (ex - 0.08 * R, ey + dy + 0.12 * R)], lw=lw * 0.8, amp=0)
        else:
            ink.dot(cr, ex, ey + dy, 0.085 * R)
    cr.arc(cx + 0.55 * R, cy - 0.65 * R, 0.07 * R, 0, 2 * math.pi)
    ink.stroke(cr, lw * 0.7)


def _face(cr, cx, cy, R, mood, t, seed, looking_up=False):
    r = random.Random(seed)
    blink_every = 3.8 + r.random() * 2.5
    blink = (t + r.random() * 5) % blink_every < 0.14
    ex = 0.30 * R
    ox = 0.18 * R + (0.18 * R if looking_up else 0)   # face turned toward +x
    ey = cy - 0.02 * R - (0.45 * R if looking_up else 0)   # the face tips up to the sky
    lw = max(2.5, R * 0.075)
    if mood == "sleepy" or blink:
        for sx in (-1, 1):
            x = cx + ox + sx * ex
            ink.line(cr, [(x - 0.13 * R, ey), (x, ey + 0.06 * R), (x + 0.13 * R, ey)],
                     lw=lw * 0.8, amp=0)
    elif mood == "happy":
        for sx in (-1, 1):
            x = cx + ox + sx * ex
            ink.line(cr, [(x - 0.12 * R, ey + 0.04 * R), (x, ey - 0.07 * R),
                          (x + 0.12 * R, ey + 0.04 * R)], lw=lw * 0.8, amp=0)
    else:
        er = 0.085 * R if mood != "surprised" else 0.11 * R
        for sx in (-1, 1):
            ink.dot(cr, cx + ox + sx * ex, ey, er)
        if mood == "worried":
            for sx in (-1, 1):
                x = cx + ox + sx * ex
                ink.line(cr, [(x - 0.14 * R, ey - 0.2 * R - sx * 0.05 * R),
                              (x + 0.14 * R, ey - 0.2 * R + sx * 0.05 * R)], lw=lw * 0.7, amp=0)
        if mood == "focused":
            for sx in (-1, 1):
                x = cx + ox + sx * ex
                ink.line(cr, [(x - 0.14 * R, ey - 0.2 * R + sx * 0.04 * R),
                              (x + 0.14 * R, ey - 0.2 * R - sx * 0.04 * R)], lw=lw * 0.7, amp=0)
    my = cy + 0.38 * R - (0.45 * R if looking_up else 0)
    mx = cx + ox
    if looking_up and mood not in ("happy", "content"):
        # an open mouth, as at a sky full of stars
        cr.arc(mx, my + 0.02 * R, 0.07 * R, 0, 2 * math.pi)
        ink.stroke(cr, lw * 0.7)
    elif mood in ("happy", "content"):
        w = 0.24 * R if mood == "happy" else 0.17 * R
        ink.line(cr, [(mx - w, my - 0.04 * R), (mx, my + 0.08 * R), (mx + w, my - 0.04 * R)],
                 lw=lw * 0.8, amp=0)
    elif mood == "surprised":
        cr.arc(mx, my + 0.02 * R, 0.08 * R, 0, 2 * math.pi)
        ink.stroke(cr, lw * 0.7)
    elif mood == "worried":
        ink.line(cr, [(mx - 0.14 * R, my + 0.05 * R), (mx, my - 0.03 * R), (mx + 0.14 * R, my + 0.05 * R)],
                 lw=lw * 0.8, amp=0)
    else:
        ink.line(cr, [(mx - 0.11 * R, my), (mx + 0.11 * R, my + 0.01 * R)], lw=lw * 0.75, amp=0)


def _hair_pts(cx, cy, R, lk, back: bool):
    r = random.Random(lk["seed"] * 31 + (7 if back else 0))
    pts = []
    if back and lk["long"]:
        # long hair falling behind the head to the shoulders
        for a in range(0, 181, 12):
            ang = math.radians(180 + a)
            rr = 1.08 * R + r.uniform(0, 0.08 * R)
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang) * 1.02))
        pts += [(cx + 1.12 * R, cy + 0.5 * R), (cx + 1.0 * R, cy + 1.25 * R),
                (cx + 0.55 * R, cy + 1.05 * R), (cx - 0.7 * R, cy + 1.05 * R),
                (cx - 1.1 * R, cy + 1.3 * R), (cx - 1.15 * R, cy + 0.4 * R)]
        return pts
    if back:
        return None
    # a messy mop: over the crown from ear to ear, then a jagged fringe back
    shaggy = lk["era"] == "stone_age"
    tuft = (0.22 if shaggy else 0.07) * R
    n = 13
    for i in range(n + 1):
        a = math.radians(168 + (372 - 168) * i / n)
        rr = 1.07 * R + (r.uniform(0.2, 1.0) * tuft if i % 2 else r.uniform(0, 0.3) * tuft)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    # right side down past the ear, then the fringe (teeth pointing down)
    pts.append((cx + 1.02 * R, cy + 0.12 * R))
    pts.append((cx + 0.86 * R, cy - 0.1 * R))
    k = 6
    for i in range(k + 1):
        x = cx + 0.78 * R - 1.72 * R * i / k
        y = cy - (0.32 if i % 2 else 0.5) * R + (r.uniform(-0.05, 0.08) * R if shaggy else 0)
        if not shaggy:
            y = cy - 0.42 * R
        pts.append((x, y))
    pts.append((cx - 1.02 * R, cy + 0.15 * R))
    return pts


def _item(cr, name, hx, hy, R, t, lw, facing_up=False):
    """Something held in the front hand, drawn in hand-local coords."""
    if name in ("none", None):
        return
    if name == "spear":
        # held out in front and leaning away from the body, so the tip
        # clears the head whatever the pose (a seated watcher's hand sits
        # right under his chin; straight up put the point through his face)
        # the butt rests on the ground (local y=0 is where the feet are)
        bx, by = hx + 0.3 * R, 0.0
        tx, ty = hx + 1.5 * R, hy - 2.6 * R
        ink.line(cr, [(bx, by), (tx, ty)], lw=lw * 0.9, ink=rgb("#6b4a2e"), amp=0)
        dx, dy = tx - bx, ty - by
        n = math.hypot(dx, dy)
        ux, uy = dx / n, dy / n
        px, py = -uy, ux
        ink.fill_stroke(cr, [(tx + ux * 0.5 * R, ty + uy * 0.5 * R),
                             (tx + px * 0.16 * R, ty + py * 0.16 * R),
                             (tx - px * 0.16 * R, ty - py * 0.16 * R)], rgb("#8d8d86"), lw=lw * 0.7, amp=0)
    elif name == "stick":
        # a staff: from a little above the hand down toward the ground, so
        # it never rises past the head (local y=0 is the ground)
        ink.line(cr, [(hx - 0.1 * R, hy - 0.45 * R), (hx + 0.3 * R, max(hy + 1.6 * R, min(0.0, hy + 3.0 * R)))],
                 lw=lw * 0.8, ink=rgb("#6b4a2e"), amp=0)
    elif name == "torch":
        # held out in front and leaning away, like the spear: the flame
        # sits forward of the face and above it (the storyboard judge:
        # "burning stick's flame drawn across the man's beard/face")
        ink.line(cr, [(hx - 0.2 * R, hy + 0.5 * R), (hx + 0.9 * R, hy - 1.7 * R)], lw=lw, ink=rgb("#6b4a2e"),
                 amp=0)
        from .props import flame
        flame(cr, hx + 0.9 * R, hy - 1.7 * R, 0.55 * R, t, seed=int(hx))
    elif name == "lantern":
        ink.line(cr, [(hx, hy), (hx, hy + 0.35 * R)], lw=lw * 0.6, amp=0)
        ink.fill_stroke(cr, ink.ellipse_pts(hx, hy + 0.65 * R, 0.28 * R, 0.34 * R, 14),
                        rgb("#f3c25a"), lw=lw * 0.7, amp=0)
        from .props import flame
        flame(cr, hx, hy + 0.7 * R, 0.2 * R, t, seed=int(hx), glow_r=2.4)
    elif name in ("bowl", "cup"):
        w = 0.42 * R if name == "bowl" else 0.24 * R
        ink.fill_stroke(cr, [(hx - w, hy - 0.1 * R), (hx + w, hy - 0.1 * R),
                             (hx + w * 0.7, hy + 0.25 * R), (hx - w * 0.7, hy + 0.25 * R)],
                        rgb("#a0673e"), lw=lw * 0.7, amp=0)
    elif name == "fish":
        ink.fill_stroke(cr, ink.ellipse_pts(hx + 0.3 * R, hy, 0.45 * R, 0.16 * R, 16),
                        rgb("#8fa7b3"), lw=lw * 0.7, amp=0.5, seed=3)
    elif name == "stone":
        ink.fill_stroke(cr, ink.blob_pts(hx + 0.1 * R, hy - 0.05 * R, 0.2 * R, 0.14 * R, 5),
                        rgb("#8e8a84"), lw=lw * 0.7, amp=0)
    elif name == "bread":
        ink.fill_stroke(cr, ink.ellipse_pts(hx + 0.1 * R, hy - 0.05 * R, 0.26 * R, 0.16 * R, 16),
                        rgb("#d5a25c"), lw=lw * 0.7, amp=0)
    elif name == "axe":
        ink.line(cr, [(hx - 0.2 * R, hy + 0.5 * R), (hx + 0.35 * R, hy - 1.1 * R)], lw=lw * 0.9,
                 ink=rgb("#6b4a2e"), amp=0)
        ink.fill_stroke(cr, [(hx + 0.25 * R, hy - 1.15 * R), (hx + 0.75 * R, hy - 1.25 * R),
                             (hx + 0.7 * R, hy - 0.8 * R), (hx + 0.35 * R, hy - 0.85 * R)],
                        rgb("#9a9a94"), lw=lw * 0.7, amp=0)
    elif name == "hoe":
        # the top of the handle stays in front of the face, never across it
        ink.line(cr, [(hx - 0.4 * R, hy - 1.4 * R), (hx + 0.9 * R, hy + 1.7 * R)], lw=lw * 0.9,
                 ink=rgb("#6b4a2e"), amp=0)
        ink.fill_stroke(cr, [(hx + 0.8 * R, hy + 1.6 * R), (hx + 1.25 * R, hy + 1.45 * R),
                             (hx + 1.2 * R, hy + 1.75 * R)], rgb("#8e8e88"), lw=lw * 0.6, amp=0)
    elif name == "rod":
        tip = (hx + 2.6 * R, hy - 1.8 * R)
        ink.line(cr, [(hx - 0.3 * R, hy + 0.3 * R), tip], lw=lw * 0.6, ink=rgb("#6b4a2e"), amp=0)
        sway = math.sin(t * 1.1) * 0.12 * R
        ink.line(cr, [tip, (tip[0] + 0.3 * R + sway, tip[1] + 2.8 * R)], lw=1.6, amp=0)
    elif name == "bundle":
        for k in range(4):
            ink.line(cr, [(hx - 0.9 * R, hy - 0.1 * R + k * 0.12 * R),
                          (hx + 0.7 * R, hy - 0.25 * R + k * 0.12 * R)], lw=lw * 0.9,
                     ink=rgb("#6d4b2d"), amp=0.5, seed=k)
        ink.line(cr, [(hx - 0.2 * R, hy - 0.35 * R), (hx - 0.15 * R, hy + 0.35 * R)], lw=lw * 0.5,
                 ink=rgb("#c7a36a"), amp=0)
    elif name == "basket":
        ink.fill_stroke(cr, [(hx - 0.45 * R, hy + 0.05 * R), (hx + 0.45 * R, hy + 0.05 * R),
                             (hx + 0.35 * R, hy + 0.65 * R), (hx - 0.35 * R, hy + 0.65 * R)],
                        rgb("#b88a4d"), lw=lw * 0.7, amp=0, texture="hatch", tex_alpha=0.25)
    elif name == "needle":
        ink.line(cr, [(hx, hy), (hx + 0.2 * R, hy - 0.25 * R)], lw=1.6, amp=0)
    else:
        raise KeyError(f"item {name!r} is not drawable")


def draw(cr, *, who: str, era: str, seed: int, pose: str, action: str,
         x: float, ground_y: float, scale: float, t: float, facing: str = "right",
         mood: str = "calm", item: str | None = None, dim: float = 0.0, cold: bool = False):
    """Draw one person with feet at (x, ground_y)."""
    lk = look(who, era, seed)
    R = R0 * scale * lk["size"]
    ph = (seed % 97) * 0.37
    cr.save()
    cr.translate(x, ground_y)
    if facing == "left":
        cr.scale(-1, 1)
    lw = max(2.4, R * 0.1)
    held = item if item is not None else (ACTIONS[action]["item"] or "none")

    if pose == "lie":
        _draw_lying(cr, lk, R, t, lw, mood if action != "sleep" else "sleepy", seed,
                    looking_up=(action == "look_up"))
        cr.restore()
        return

    sk = skeleton(pose, R, t, ph)
    sk["head"] = head_of(sk, R, action)
    front, back = hand_targets(action, sk, R, t, ph)
    nx, ny = sk["neck"]
    if held in LOW_HELD and front[1] < ny + 0.5 * R:
        # a light is carried low: a gesture that lifts the hand goes to the
        # other hand (the Elizabethan film's judge: "the lantern drawn over
        # the man's face" — a watchman waving with the lantern in that hand)
        front, back = (nx + 0.42 * R, sk["hip"][1] - 0.05 * R), front
    sh_f = (nx + 0.22 * R, ny + 0.28 * R)
    sh_b = (nx - 0.22 * R, ny + 0.28 * R)
    ua, la = 0.95 * R, 0.9 * R
    ua_b, la_b = ua, la

    if pose == "sit_on":
        _seat(cr, lk, sk["hip"], R, lw)
    # back arm + back leg (behind the body)
    e, h = _ik(*sh_b, *back, ua_b, la_b, 1)
    ink.line(cr, [sh_b, e, h], lw=lw, amp=0)
    hip, knee, foot = sk["legs"][0]
    ink.line(cr, [hip, knee, foot], lw=lw, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(foot[0] + 0.12 * R, foot[1] - 0.07 * R, 0.24 * R, 0.12 * R, 12),
                    ink.INK, lw=0, amp=0)
    # long hair behind the body
    hcx, hcy = sk["head"]
    bh = _hair_pts(hcx, hcy, R, lk, back=True)
    if bh:
        ink.fill_stroke(cr, bh, lk["hair"], lw=lw * 0.8, amp=1.2, seed=seed)

    # front leg
    hip, knee, foot = sk["legs"][1]
    ink.line(cr, [hip, knee, foot], lw=lw, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(foot[0] + 0.12 * R, foot[1] - 0.07 * R, 0.24 * R, 0.12 * R, 12),
                    ink.INK, lw=0, amp=0)

    # body / outfit
    hx0, hy0 = sk["hip"]
    lean = sk["lean"]
    top_w, bot_w = 0.52 * R, 0.78 * R
    hem = 0.55 * R if pose in ("stand", "walk") else 0.25 * R
    if lk["era"] == "medieval" and lk["long"]:
        hem = 1.5 * R if pose in ("stand", "walk") else 0.35 * R
    if lk["era"] == "ancient":
        # a tunic to the knee on everyone; to the ankle on the long-haired
        hem = (1.5 * R if lk["long"] else 1.1 * R) if pose in ("stand", "walk") else 0.35 * R
    if lk["era"] == "victorian":
        # a long dress, or a coat to the knee
        hem = (1.6 * R if lk["long"] else 1.0 * R) if pose in ("stand", "walk") else 0.35 * R
    if lk["era"] == "egypt":
        # a straight dress to the ankle, or a kilt to the knee
        hem = (1.55 * R if lk["long"] else 0.95 * R) if pose in ("stand", "walk") else 0.35 * R
    if lk["era"] == "early_modern":
        # a long gown, or a coat to the knee over breeches
        hem = (1.6 * R if lk["long"] else 1.0 * R) if pose in ("stand", "walk") else 0.35 * R
    body = [(nx - 0.3 * R, ny + 0.06 * R), (nx + 0.3 * R, ny + 0.06 * R),
            (nx + top_w, ny + 0.3 * R), (hx0 + bot_w, hy0 + hem),
            (hx0, hy0 + hem + 0.06 * R), (hx0 - bot_w, hy0 + hem), (nx - top_w, ny + 0.3 * R)]
    ink.fill_stroke(cr, body, lk["cloth"], lw=lw * 0.85, amp=1.6, seed=seed + 1,
                    shadow=shade(lk["cloth"]), shadow_dir=(-1, 0.3),
                    texture=lk["texture"], tex_alpha=0.55)
    if lk["strap"]:
        ink.line(cr, [(nx - 0.45 * R, ny + 0.2 * R), (nx + 0.3 * R, ny + 0.95 * R)],
                 lw=lw * 0.55, ink=shade(lk["cloth"], 0.6), amp=0)
    if lk["era"] == "egypt":
        # a broad collar of colour at the neck
        ink.fill_stroke(cr, [(nx - 0.42 * R, ny + 0.12 * R), (nx + 0.42 * R, ny + 0.12 * R),
                             (nx + 0.5 * R, ny + 0.42 * R), (nx - 0.5 * R, ny + 0.42 * R)],
                        rgb("#2f8f8f") if seed % 2 else rgb("#c99a2e"), lw=lw * 0.6, amp=0.6, seed=seed + 8)
    if lk["era"] in ("medieval", "ancient", "victorian", "early_modern"):
        by = hy0 - 0.15 * R
        ink.line(cr, [(hx0 - bot_w * 0.85, by), (hx0 + bot_w * 0.85, by)], lw=lw * 0.7,
                 ink=rgb("#4b3524") if lk["era"] in ("medieval", "victorian", "early_modern") else rgb("#9c7d4a"),
                 amp=0)

    # head (with hood/scarf) + hair + face
    if lk["hood"] or lk["scarf"]:
        hood_c = shade(lk["cloth"], 0.9)
        ink.fill_stroke(cr, ink.ellipse_pts(hcx - 0.05 * R, hcy - 0.05 * R, 1.22 * R, 1.25 * R, 26),
                        hood_c, lw=lw * 0.85, amp=1.2, seed=seed + 5)
    ink.fill_stroke(cr, ink.ellipse_pts(hcx, hcy, R, 1.03 * R, 30), HEAD, lw=lw * 0.95, amp=1.1,
                    seed=seed + 2, shadow=rgb("#e9e2d4"), shadow_dir=(-1, 0.4))
    if not (lk["hood"] or lk["scarf"]):
        fh = _hair_pts(hcx, hcy, R, lk, back=False)
        ink.fill_stroke(cr, fh, lk["hair"], lw=lw * 0.8, amp=0.8, seed=seed + 3)
    if lk.get("cap"):
        capc = shade(lk["cloth"], 0.85)
        ink.fill_stroke(cr, [(hcx - 1.0 * R, hcy - 0.45 * R), (hcx - 0.85 * R, hcy - 0.95 * R),
                             (hcx + 0.6 * R, hcy - 1.05 * R), (hcx + 1.0 * R, hcy - 0.5 * R),
                             (hcx + 1.35 * R, hcy - 0.42 * R), (hcx + 1.3 * R, hcy - 0.3 * R)], capc,
                        lw=lw * 0.8, amp=1.0, seed=seed + 6, shadow=shade(capc), shadow_dir=(0, 1))
    if lk.get("tricorn"):
        hc = rgb("#2a2422")
        ink.fill_stroke(cr, [(hcx - 1.3 * R, hcy - 0.5 * R), (hcx - 0.7 * R, hcy - 1.35 * R),
                             (hcx + 0.75 * R, hcy - 1.35 * R), (hcx + 1.3 * R, hcy - 0.5 * R),
                             (hcx + 0.8 * R, hcy - 0.75 * R), (hcx - 0.8 * R, hcy - 0.75 * R)], hc,
                        lw=lw * 0.8, amp=1.0, seed=seed + 6, shadow=shade(hc), shadow_dir=(0, 1))
    if lk.get("coif"):
        cc = rgb("#efe8d8")
        ink.fill_stroke(cr, [(hcx - 1.05 * R, hcy + 0.2 * R), (hcx - 1.05 * R, hcy - 0.6 * R),
                             (hcx - 0.5 * R, hcy - 1.2 * R), (hcx + 0.5 * R, hcy - 1.2 * R),
                             (hcx + 1.05 * R, hcy - 0.6 * R), (hcx + 1.05 * R, hcy + 0.2 * R),
                             (hcx + 0.75 * R, hcy - 0.45 * R), (hcx - 0.75 * R, hcy - 0.45 * R)], cc,
                        lw=lw * 0.8, amp=1.0, seed=seed + 6, shadow=shade(cc), shadow_dir=(0, 1))
    if lk.get("bonnet"):
        bc = shade(lk["cloth"], 0.95)
        ink.fill_stroke(cr, [(hcx - 1.05 * R, hcy + 0.1 * R), (hcx - 1.1 * R, hcy - 0.7 * R),
                             (hcx - 0.5 * R, hcy - 1.25 * R), (hcx + 0.55 * R, hcy - 1.2 * R),
                             (hcx + 1.05 * R, hcy - 0.7 * R), (hcx + 1.15 * R, hcy - 0.2 * R),
                             (hcx + 0.7 * R, hcy - 0.55 * R), (hcx - 0.55 * R, hcy - 0.6 * R)], bc,
                        lw=lw * 0.8, amp=1.0, seed=seed + 6, shadow=shade(bc), shadow_dir=(0, 1))
    if lk["beard"]:
        # under the chin, not across the mouth, and a shade lighter than the
        # hair — the fourth film's judge read a beard as "a black wedge
        # across the face"
        # a fringe along the jaw, below the mouth: the filled wedge under the
        # chin was read by two storyboard rounds as "a brown prop drawn
        # across the seated man's face"
        bpts = [(hcx - 0.2 * R, hcy + 0.9 * R), (hcx + 0.45 * R, hcy + 0.82 * R), (hcx + 0.95 * R, hcy + 0.62 * R),
                (hcx + 0.8 * R, hcy + 0.95 * R), (hcx + 0.35 * R, hcy + 1.18 * R), (hcx - 0.15 * R, hcy + 1.1 * R)]
        ink.fill_stroke(cr, bpts, ink.mix(lk["hair"], HEAD, 0.3), lw=lw * 0.7, amp=1.5, seed=seed + 4)
    _face(cr, hcx, hcy, R, mood, t, seed, looking_up=(action == "look_up"))
    if cold and action != "sleep":
        _breath(cr, hcx, hcy, R, t, seed)

    # the work itself, where the action has something to show: a hide
    # across the lap for sewing, a core and its flakes for knapping. The
    # first film's judge: "the story's activities are never shown".
    if action == "sew":
        hide = rgb("#c9a06c")
        kx, ky = sk["legs"][1][1]          # draped over the knees
        ink.fill_stroke(cr, ink.blob_pts(kx, ky - 0.1 * R, 1.05 * R, 0.5 * R, seed + 7, 0.08, 16),
                        hide, lw=lw * 0.7, amp=1.2, seed=seed + 7, shadow=shade(hide), shadow_dir=(0, 1),
                        texture="grain", tex_alpha=0.25)
        for k in range(3):
            sx = kx - 0.5 * R + k * 0.35 * R
            ink.line(cr, [(sx, ky - 0.22 * R), (sx + 0.12 * R, ky - 0.08 * R)], lw=1.4, amp=0)
    elif action == "knap":
        core = rgb("#7d7a74")
        ink.fill_stroke(cr, ink.blob_pts(nx + 1.0 * R, ny + 1.55 * R, 0.5 * R, 0.36 * R, seed + 8, 0.12, 8),
                        core, lw=lw * 0.7, amp=0.8, seed=seed + 8, shadow=shade(core), shadow_dir=(1, 1))
        for k in range(5):
            fx = 1.3 * R + k * 0.28 * R + (seed % 5) * 0.03 * R
            ink.fill_stroke(cr, [(fx, -0.02 * R), (fx + 0.16 * R, -0.03 * R), (fx + 0.07 * R, -0.16 * R)],
                            rgb("#8e8a84"), lw=1.6, amp=0)
        # a flake in the air on each strike, falling
        kk = abs(math.sin(2 * math.pi * t / 1.6 + ph))
        if kk < 0.35:
            u = kk / 0.35
            fx, fy = nx + 1.45 * R + u * 0.5 * R, ny + 1.3 * R + u * 0.9 * R
            ink.fill_stroke(cr, [(fx, fy), (fx + 0.18 * R, fy - 0.04 * R), (fx + 0.08 * R, fy - 0.2 * R)],
                            rgb("#a8a49c"), lw=1.6, amp=0)

    if action == "play":
        # the game: a pebble tossed up off the stick and caught, so a viewer
        # who did not hear the words sees a game and not two children with
        # sticks (the ninth film: "the stick-and-stone game is never shown")
        u = (t / 1.1 + ph / (2 * math.pi)) % 1.0
        px = nx + 1.3 * R + u * 0.3 * R
        py = ny + 0.9 * R - math.sin(math.pi * u) * 2.2 * R
        ink.fill_stroke(cr, ink.ellipse_pts(px, py, 0.24 * R, 0.2 * R, 8), rgb("#d8d2c8"), lw=lw * 0.7, amp=0)
    # front arm + held item
    bend = -1 if action in ("wave", "yawn") else 1
    e, h = _ik(*sh_f, *front, ua, la, bend)
    if held != "none":
        _item(cr, held, h[0], h[1], R, t, lw)
    ink.line(cr, [sh_f, e, h], lw=lw, amp=0)
    ink.fill_stroke(cr, ink.ellipse_pts(h[0], h[1], 0.17 * R, 0.16 * R, 12), HEAD, lw=lw * 0.6, amp=0)
    if action in ("warm_hands", "carry", "yawn", "sew", "chop", "hoe", "fish", "hug_self", "knap", "eat",
                  "drink", "play"):
        e2, h2 = _ik(*sh_b, *back, ua, la, bend)
        ink.fill_stroke(cr, ink.ellipse_pts(h2[0], h2[1], 0.16 * R, 0.15 * R, 12), HEAD,
                        lw=lw * 0.6, amp=0)
    cr.restore()


def _seat(cr, lk, hip, R, lw):
    """What a person sitting 'on' something sits on: a stool indoors in the
    middle ages, a log in the stone age."""
    hx, hy = hip
    if lk["era"] == "medieval":
        top = hy + 0.12 * R
        ink.fill_stroke(cr, [(hx - 0.8 * R, top), (hx + 0.8 * R, top), (hx + 0.8 * R, top + 0.22 * R),
                             (hx - 0.8 * R, top + 0.22 * R)], rgb("#7a5233"), lw=lw * 0.8, amp=0.5, seed=3)
        for dx in (-0.6, 0.6):
            ink.line(cr, [(hx + dx * R, top + 0.22 * R), (hx + dx * R * 1.1, 0)], lw=lw * 1.1,
                     ink=rgb("#5a3b24"), amp=0)
    else:
        c = rgb("#7a5233")
        ink.fill_stroke(cr, [(hx - 1.0 * R, 0), (hx - 1.0 * R, hy + 0.1 * R), (hx + 0.9 * R, hy + 0.1 * R),
                             (hx + 0.9 * R, 0)], c, lw=lw * 0.8, amp=1.0, seed=5, shadow=shade(c),
                        shadow_dir=(0, 1))
        ink.fill_stroke(cr, ink.ellipse_pts(hx + 0.9 * R, (hy + 0.1 * R) / 2, 0.18 * R, -(hy + 0.1 * R) / 2, 16),
                        rgb("#c9a06c"), lw=lw * 0.7, amp=0)


def _draw_lying(cr, lk, R, t, lw, mood, seed, looking_up=False):
    """Asleep on the ground under a fur/blanket, head to the left — or, when
    looking up, on the back with the face to the sky and an arm raised at
    it (the seventh film's judge asked for exactly this for a sky chapter)."""
    head = (-2.1 * R, -0.95 * R)
    hair = _hair_pts(head[0], head[1], R, lk, back=False)
    blanket = rgb("#8a5a35") if lk["era"] == "stone_age" else lk["cloth"]
    ink.fill_stroke(cr, [(-1.35 * R, -0.95 * R), (-0.6 * R, -1.55 * R), (0.5 * R, -1.7 * R),
                         (1.5 * R, -1.35 * R), (2.35 * R, -1.1 * R), (2.7 * R, -0.45 * R),
                         (2.6 * R, 0.0), (-1.5 * R, 0.0)], blanket, lw=lw * 0.85, amp=2.2,
                    seed=seed + 9, shadow=shade(blanket), shadow_dir=(0, 1),
                    texture="fur" if lk["era"] == "stone_age" else None, tex_alpha=0.5)
    ink.fill_stroke(cr, ink.ellipse_pts(head[0], head[1], R, 1.03 * R, 30), HEAD, lw=lw * 0.95,
                    amp=1.1, seed=seed + 2)
    ink.fill_stroke(cr, hair, lk["hair"], lw=lw * 0.8, amp=0.8, seed=seed + 3)
    if looking_up:
        # face to the sky: eyes and an open mouth at the top of the head.
        # No raised arm: the Egypt film's judge read it as "a figure lying
        # flat with a stick jutting from its head", like every raised arm
        # before it (see hand_targets' look_up)
        _face_up(cr, head[0], head[1], R, t, seed, lw)
        return
    _face(cr, head[0], head[1], R, "sleepy", t, seed)
    # Zzz: letters drifting up and fading, a slow loop
    cr.select_font_face("Anton", 0, 0)
    for k in range(3):
        u = ((t / 3.6) + k / 3.0) % 1.0
        cr.set_font_size(R * (0.35 + 0.25 * u))
        cr.move_to(head[0] + 0.9 * R + u * 0.8 * R, head[1] - 1.1 * R - u * 1.3 * R)
        cr.set_source_rgba(ink.INK[0], ink.INK[1], ink.INK[2], 0.75 * math.sin(math.pi * u))
        cr.show_text("z")
