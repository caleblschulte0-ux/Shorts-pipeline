"""Props for the card rewards short (2026-11-18): a big gold rewards card, coins, a card reader, price tags on sticks,
a piggy bank, a chute, a tin shack and a model mansion, a brass lever. Units as scene_kit: metres at Data's scale.

Every prop is built in its own root's frame and then placed (saffron_kit._place), so a shot only says where it goes.
Colours are named once here; the coins share the checkout short's gold (a full metal read as brown sludge in store
light, 11-12 CI judge)."""
import math
import random

import bpy
from mathutils import Vector

import scene_kit as K
from saffron_kit import _place, _mat


def gold():
    return bpy.data.materials.get("coins") or K.mat("coins", "#F4CC52", rough=0.22, metal=0.65, emit=0.12)


def coin_proto(name="card coin proto", r=0.016, h=0.004):
    return K.cyl(name, (0, 0, -5), r, h, gold(), v=24, bev=0.0012)


def coins(n, name="coin", r=0.02, h=0.005):
    """n loose coins parked out of sight (props.pour moves them)"""
    proto = coin_proto(name + " proto", r, h)
    out = []
    for i in range(n):
        o = proto.copy(); bpy.context.collection.objects.link(o); o.name = f"{name} {i}"; out.append(o)
    return out


def card(name, loc, w=0.17, h=0.107, yaw=0.0, upright=False, parent=None):
    """a big gold rewards card: rounded slab, a chip, an embossed number line, REWARDS across it. Lying flat by
    default (face up, +Z); upright=True stands it on its long edge facing -Y (the camera)."""
    root = K.empty(name, (0, 0, 0))
    face = _mat("rewards card gold", "#E3B23C", rough=0.28, metal=0.55)
    K.box(name + " slab", (0, 0, 0.002), (w, h, 0.004), face, bev=0.0035, parent=root)
    K.box(name + " stripe", (0, h * 0.18, 0.0042), (w * 0.999, h * 0.12, 0.0006), _mat("card stripe", "#B8861F", rough=0.35, metal=0.6), bev=0, parent=root)
    K.box(name + " chip", (-w * 0.3, -h * 0.02, 0.0045), (w * 0.15, h * 0.2, 0.001), _mat("card chip", "#CFC7B0", rough=0.25, metal=0.9), bev=0.0006, parent=root)
    ink = _mat("card ink", "#3B2A0C", rough=0.5)
    K.text(name + " rewards", "REWARDS", (w * 0.12, h * 0.33, 0.0046), h * 0.15, (0, 0, 0), ink, extrude=0.0004, parent=root)
    K.text(name + " number", "4000 1234 5678 9010", (0, -h * 0.25, 0.0046), h * 0.1, (0, 0, 0), ink, extrude=0.0005, parent=root)
    if upright:
        inner = root; root = K.empty(name + " stand root", (0, 0, 0)); inner.parent = root
        inner.location = (0, 0, h / 2 + 0.006); inner.rotation_euler = (math.pi / 2, 0, 0)
    _place(root, loc, yaw, parent)
    return root


def card_stand(name, loc, w=0.12):
    """a little black acrylic stand the upright card sits in"""
    m = _mat("card stand", "#1C1B1E", rough=0.3)
    K.box(name, (loc[0], loc[1], loc[2] + 0.004), (w, 0.04, 0.008), m, bev=0.002)
    K.box(name + " lip", (loc[0], loc[1] - 0.012, loc[2] + 0.012), (w, 0.006, 0.016), m, bev=0.001)


def dish(name, loc, r=0.06):
    """a shallow tray the coins land in"""
    return K.cyl(name, (loc[0], loc[1], loc[2] + 0.004), r, 0.008, _mat("coin dish", "#2E3136", rough=0.35, metal=0.5), v=48, bev=0.003)


def reader(name, loc, yaw=0.0):
    """a countertop card reader: a dark wedge with a screen and a key that lights green. Returns (root, lamp material,
    key top local point)"""
    root = K.empty(name, (0, 0, 0))
    body = _mat("reader body", "#24272B", rough=0.35)
    K.box(name + " base", (0, 0, 0.012), (0.07, 0.09, 0.024), body, bev=0.006, parent=root)
    hd = K.box(name + " head", (0, 0.012, 0.034), (0.066, 0.06, 0.016), body, bev=0.005, parent=root)
    hd.rotation_euler = (math.radians(-18), 0, 0)
    lamp = bpy.data.materials.new(name + " lamp"); lamp.use_nodes = True
    b = lamp.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.05, 0.07, 0.06, 1); b.inputs["Emission Color"].default_value = (0.1, 1.0, 0.3, 1)
    b.inputs["Emission Strength"].default_value = 0.0
    K.box(name + " screen", (0, 0.016, 0.044), (0.05, 0.034, 0.002), lamp, bev=0.0005, parent=root).rotation_euler = (math.radians(-18), 0, 0)
    _place(root, loc, yaw, None)
    return root, lamp, Vector((0, -0.015, 0.04))


def key_emission(m, keys, F):
    b = m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for t, v in keys:
        b.default_value = v; b.keyframe_insert("default_value", frame=max(1, F(t)))


def key_color(m, keys, F):
    b = m.node_tree.nodes["Principled BSDF"].inputs["Base Color"]
    for t, hexc in keys:
        b.default_value = (*K.lin(hexc), 1); b.keyframe_insert("default_value", frame=max(1, F(t)))


def product_box(name, loc, size, hexc, label="", yaw=0.0):
    root = K.empty(name, (0, 0, 0))
    K.box(name + " body", (0, 0, size[2] / 2), size, _mat(name + " card", hexc, rough=0.6), bev=0.004, parent=root)
    K.box(name + " band", (0, -size[1] / 2 - 0.0005, size[2] * 0.6), (size[0] * 0.999, 0.001, size[2] * 0.3), _mat("box band", "#F4F0E6", rough=0.6), bev=0, parent=root)
    if label:
        K.text(name + " label", label, (0, -size[1] / 2 - 0.0016, size[2] * 0.6), size[2] * 0.14, (math.pi / 2, 0, 0), _mat("box ink", "#1C1B1E", rough=0.5), extrude=0.0003, parent=root)
    _place(root, loc, yaw, None)
    return root


def price_tag(name, loc, stick=0.1):
    """a price tag on a thin stick stuck in a product: a white card with a big "$" facing the camera. Returns (rise
    root to key location.z, tag material for colour keys)"""
    rise = K.empty(name, (0, 0, 0))
    K.cyl(name + " stick", (0, 0, stick / 2), 0.0025, stick, _mat("tag stick", "#E9E4D8", rough=0.5), v=8, bev=0, parent=rise)
    m = bpy.data.materials.new(name + " card"); m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*K.lin("#F7F4EC"), 1)
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
    K.box(name + " card", (0, 0, stick + 0.022), (0.055, 0.004, 0.044), m, bev=0.003, parent=rise)
    K.text(name + " dollar", "$", (0, -0.0028, stick + 0.022), 0.034, (math.pi / 2, 0, 0), _mat("tag ink", "#1C1B1E", rough=0.5), extrude=0.0006, parent=rise)
    rise.location = loc
    return rise, m


def piggy(name, loc, s=1.0, yaw=0.0):
    """a pink piggy bank facing +X: a round body, a snout, ears, four stubby legs and a coin slot on its back. Its
    root sits UNDER ITS FRONT FEET, so rotating root.rotation_euler.y (negative) tips it forward onto its snout.
    Returns (root, snout tip local point)."""
    root = K.empty(name, (0, 0, 0))
    pink = _mat("piggy pink", "#F2A0B4", rough=0.3)
    L = 0.11 * s; R = 0.06 * s
    body = K.sph(name + " body", (-L / 2, 0, R + 0.018 * s), 1.0, pink, scale=(L * 0.62, R, R))
    K.cyl(name + " snout", (-L / 2 + L * 0.62, 0, R + 0.02 * s), 0.024 * s, 0.026 * s, pink, rot=(0, math.pi / 2, 0), bev=0.004)
    dark = _mat("piggy nostril", "#9C4A5E", rough=0.5)
    for sy in (-1, 1):
        K.cyl(name + " nostril", (-L / 2 + L * 0.62 + 0.0135 * s, sy * 0.008 * s, R + 0.02 * s), 0.004 * s, 0.002, dark, rot=(0, math.pi / 2, 0), bev=0)
        K.sph(name + " ear", (-L / 2 + L * 0.35, sy * R * 0.55, 2 * R + 0.01 * s), 0.018 * s, pink, scale=(0.6, 1.0, 1.2))
        K.sph(name + " eye", (-L / 2 + L * 0.5, sy * R * 0.55, R * 1.45 + 0.018 * s), 0.0055 * s, _mat("piggy eye", "#1C1B1E", rough=0.3))
        for sx in (-1, 1):
            K.cyl(name + " leg", (-L / 2 + sx * L * 0.35, sy * R * 0.5, 0.012 * s), 0.014 * s, 0.024 * s, pink, bev=0.003)
    K.box(name + " slot", (-L / 2, 0, 2 * R + 0.018 * s), (0.03 * s, 0.006 * s, 0.003), dark, bev=0.0006)
    for o in list(bpy.data.objects):
        if o.name.startswith(name + " ") and o.parent is None: o.parent = root
    # the root is under the front feet: shift every child back so the pivot is at the front legs
    for c in root.children: c.location.x -= -L / 2 + L * 0.35 + 0.014 * s
    _place(root, loc, yaw, None)
    return root, Vector((L * 0.62 - L * 0.35 - 0.014 * s + 0.013 * s, 0, R + 0.02 * s))


def chute(name, a, b, w=0.06):
    """a bent-tin chute from a to b (world points on its floor): a floor and two low sides"""
    a, b = Vector(a), Vector(b); d = b - a
    m = _mat("chute tin", "#A9AEB3", rough=0.35, metal=0.8)
    root = K.empty(name, tuple((a + b) / 2))
    root.rotation_euler = (0, -math.atan2(d.z, math.hypot(d.x, d.y)), math.atan2(d.y, d.x))
    L = d.length
    K.box(name + " floor", (0, 0, -0.002), (L, w, 0.004), m, bev=0.001, parent=root)
    for sy in (-1, 1):
        K.box(name + " side", (0, sy * w / 2, 0.008), (L, 0.003, 0.02), m, bev=0.0008, parent=root)
    return root


def shack(name, loc, s=1.0):
    """a tiny tin shack: grey corrugated walls, a slanted rust roof, a dark door"""
    root = K.empty(name, (0, 0, 0))
    W, D, H = 0.07 * s, 0.06 * s, 0.05 * s
    K.box(name + " walls", (0, 0, H / 2), (W, D, H), _mat("shack tin", "#8D9196", rough=0.5, metal=0.5), bev=0.002, parent=root)
    r = K.box(name + " roof", (0, 0, H + 0.006 * s), (W * 1.15, D * 1.15, 0.006 * s), _mat("shack rust", "#8A4B2A", rough=0.7), bev=0.001, parent=root)
    r.rotation_euler = (0, math.radians(10), 0)
    K.box(name + " door", (W * 0.15, -D / 2 - 0.0005, H * 0.36), (W * 0.26, 0.001, H * 0.62), _mat("shack door", "#2B2420", rough=0.7), bev=0, parent=root)
    _place(root, loc, 0.0, None)
    return root


def mansion(name, loc, s=1.0):
    """a big white model mansion: two wings and a taller centre with columns, a grey roof, dark windows, a gold door"""
    root = K.empty(name, (0, 0, 0))
    wall = _mat("mansion white", "#F2EEE6", rough=0.45); roof = _mat("mansion roof", "#4C5157", rough=0.5)
    win = _mat("mansion window", "#2A3440", rough=0.15); trim = _mat("mansion gold", "#D2A84A", rough=0.3, metal=0.8)
    W, D, H = 0.2 * s, 0.07 * s, 0.07 * s
    K.box(name + " wings", (0, 0, H / 2), (W, D, H), wall, bev=0.002, parent=root)
    K.box(name + " centre", (0, -0.004 * s, H * 0.7), (W * 0.34, D * 1.05, H * 1.4), wall, bev=0.002, parent=root)
    K.box(name + " wing roof", (0, 0, H + 0.004 * s), (W * 1.04, D * 1.08, 0.008 * s), roof, bev=0.002, parent=root)
    p = K.box(name + " pediment", (0, -D * 0.53, H * 1.4 + 0.01 * s), (W * 0.36, 0.004, 0.02 * s), wall, bev=0.001, parent=root)
    K.box(name + " centre roof", (0, -0.004 * s, H * 1.4 + 0.004 * s), (W * 0.37, D * 1.12, 0.008 * s), roof, bev=0.002, parent=root)
    for k in range(4):
        K.cyl(f"{name} column {k}", (-W * 0.13 + W * 0.0867 * k, -D * 0.6, H * 0.65), 0.004 * s, H * 1.3, wall, v=12, bev=0, parent=root)
    for sx in (-1, 1):
        for k in range(2):
            for z in (0.3, 0.7):
                K.box(f"{name} window {sx}{k}{z}", (sx * (W * 0.27 + W * 0.1 * k), -D / 2 - 0.0005, H * z), (0.012 * s, 0.001, 0.016 * s), win, bev=0, parent=root)
    K.box(name + " door", (0, -D * 0.55 - 0.0005, H * 0.2), (0.018 * s, 0.001, H * 0.4), trim, bev=0, parent=root)
    _place(root, loc, 0.0, None)
    return root


def lever(name, base, length=0.09):
    """a brass lever on a little housing: returns (pivot to key rotation_euler.y, knob local point on the pivot)"""
    brass = _mat("lever brass", "#C9A04A", rough=0.3, metal=0.9)
    K.box(name + " housing", (base[0], base[1], base[2] + 0.012), (0.05, 0.04, 0.024), _mat("lever housing", "#2E3136", rough=0.4, metal=0.4), bev=0.004)
    piv = K.empty(name + " pivot", (base[0], base[1], base[2] + 0.024))
    K.cyl(name + " arm", (0, 0, length / 2), 0.004, length, brass, v=12, bev=0, parent=piv)
    K.sph(name + " knob", (0, 0, length), 0.016, _mat("lever knob", "#B8241C", rough=0.35), parent=piv)
    return piv, Vector((0, 0, length))
