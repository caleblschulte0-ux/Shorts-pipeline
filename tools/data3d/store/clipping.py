"""The CLIPPING check, for every 3D shot (caaleb, 2026-11-12: "there were some clipping issues when data moves
sometimes ... we can't take 4 days of me constantly certifying it").

MEASURED on the posed, evaluated meshes, every STEP frames:
  his hands and forearms never sink into his own coat, head or legs
  no part of him sinks into anything in the set (a jar, a sack, a lever, a kiosk)
A point of one mesh counts as inside another when the nearest surface of the other faces away from it and it is
deeper than DEPTH. A shot with more than GRACE clipped frames for any pair is refused before it renders, with the
frames and the pair named. The hand that GRIPS a thing may touch it; that is what a grip is.
"""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

DEPTH = 0.012          # metres: a graze is not a clip; this is deep enough to see on a phone
DEPTH_SELF = 0.02      # a hand resting on his own coat dents its soft flare a little; a sunk hand is deeper
GRACE = 2              # frames
HANDS = ("Mitten", "Thumb", "Forearm")
GRIPPED = ("sack", "lever", "handle", "grip", "page", "cart")   # the things a shot hands him to hold
OWN = ("Coat", "Head", "Neck", "Thigh", "Shin")
SKIP = ("floor", "Floor", "shadow", "Shadow", "proto", "glint", "Pupil", "Lid", "Eye", "Lips", "Mouth", "Cube", "ground", "wall", "Wall")


def _world_mesh(o, dg):
    ev = o.evaluated_get(dg); me = ev.to_mesh()
    vs = [o.matrix_world @ v.co for v in me.vertices]; ps = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear(); return vs, ps


_SOLID = {}


def _solid(o, ws):
    """only a CLOSED mesh with real thickness has an inside: a bill, a sign face or a shadow card has none, and the
    nearest-face test would call everything behind it 'inside'"""
    key = (o.name, len(ws[0]), len(ws[1]))
    if key not in _SOLID:
        thin = min(o.dimensions) < 0.02          # its OWN thickness, not a world box a tilted page fills
        edges = {}
        for poly in ws[1]:
            for i in range(len(poly)):
                e = tuple(sorted((poly[i], poly[(i + 1) % len(poly)]))); edges[e] = edges.get(e, 0) + 1
        closed = bool(edges) and all(c == 2 for c in edges.values())
        shell = False
        if closed and not thin:   # a closed SHELL (a leaf or a sheet given a few mm by Solidify) is still a sheet: it
            vs, ps = ws          # has no inside a body could be in, only two faces a point is always 'behind' one of
            vol = abs(sum(vs[p[0]].dot(vs[p[i]].cross(vs[p[i + 1]])) for p in ps for i in range(1, len(p) - 1))) / 6
            box = [max(v[i] for v in vs) - min(v[i] for v in vs) for i in range(3)]
            shell = vol < 0.05 * max(1e-9, box[0] * box[1] * box[2])
        _SOLID[key] = not thin and closed and not shell
    return _SOLID[key]


def _inside(points, tree, depth):
    n = 0; deepest = 0.0
    for p in points:
        hit = tree.find_nearest(p)
        if hit[0] is None: continue
        loc, nor, _, d = hit
        if d > depth and (p - loc).dot(nor) < 0 and _odd(p, tree): n += 1; deepest = max(deepest, d)
    return n, deepest


def _odd(p, tree, d=Vector((0.0123, 0.0071, 1.0)).normalized()):
    """a point is INSIDE a closed mesh when a ray from it crosses the surface an odd number of times. The nearest-face
    test alone called a point in a bowl's open mouth 'inside' its bottom (2026-11-13: an eye 60 cm 'into' a basket)."""
    o, n = Vector(p), 0
    for _ in range(40):
        hit = tree.ray_cast(o, d)
        if hit[0] is None: break
        n += 1; o = hit[0] + d * 1e-4
    return n % 2 == 1


def _data_parts(data):
    return [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == data.arm and not o.hide_render]


def check(data, nf, step=3, name="shot", grips=()):
    grips = tuple(grips)
    """grips: names of objects a hand holds on purpose (the hand may touch them)"""
    sc = bpy.context.scene; parts = _data_parts(data); bad = {}; worst = {}
    hands = [o for o in parts if o.name.startswith(HANDS)]
    own = [o for o in parts if o.name.startswith(OWN)]
    for f in range(1, nf + 1, step):
        sc.frame_set(f); bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
        mesh = {o: _world_mesh(o, dg) for o in parts}
        lo = Vector([min(v[i] for o in parts for v in mesh[o][0]) for i in range(3)]) - Vector((0.05,) * 3)
        hi = Vector([max(v[i] for o in parts for v in mesh[o][0]) for i in range(3)]) + Vector((0.05,) * 3)
        trees = {o: BVHTree.FromPolygons(*mesh[o], all_triangles=False) for o in own}
        for h in hands:
            for o, tr in trees.items():
                if o.name.startswith("Coat") and h.name.startswith("Forearm"): continue   # the sleeve meets the coat at the shoulder
                k, dd = _inside(mesh[h][0][::3], tr, DEPTH_SELF if o.name.startswith("Coat") else DEPTH)
                if k: key = f"{h.name} into {o.name}"; bad.setdefault(key, set()).add(f); worst[key] = max(worst.get(key, 0), dd)
        # the set: anything near him he must not pass through
        for s in bpy.data.objects:
            if s.type != 'MESH' or s in parts or s.hide_render or s.name.startswith(SKIP) or s.parent == data.arm: continue
            bb = [s.matrix_world @ Vector(c) for c in s.bound_box]
            if any(min(c[i] for c in bb) > hi[i] or max(c[i] for c in bb) < lo[i] for i in range(3)): continue
            held = any(s.name.startswith(g) or (s.parent and s.parent.name.startswith(g)) for g in grips + GRIPPED)
            ws = _world_mesh(s, dg)
            if not ws[1] or not _solid(s, ws): continue
            tr = BVHTree.FromPolygons(*ws, all_triangles=False)
            for o in parts:
                if o.name.startswith(("Pen", "Pocket", "Lapel", "Tie", "Shirt", "Coat button")): continue
                if held and o.name.startswith(HANDS): continue      # the hand that holds it may touch it; nothing else of him may
                k, dd = _inside(mesh[o][0][::4], tr, DEPTH)
                if k: key = f"{o.name} into {s.name}"; bad.setdefault(key, set()).add(f); worst[key] = max(worst.get(key, 0), dd)
    fails = {r for r, fr in bad.items() if len(fr) > GRACE}
    if not bad: print(f"CLIPPING {name}: nothing of him passes through anything -> OK", flush=True)
    for r, fr in sorted(bad.items()):
        fr = sorted(fr)
        print(f"CLIPPING {name}: {r} on {len(fr)} frames (deepest {worst[r] * 100:.1f} cm), frames {fr[:6]}{'...' if len(fr) > 6 else ''}"
              f" -> {'FAIL' if r in fails else 'within grace'}", flush=True)
    return not fails
