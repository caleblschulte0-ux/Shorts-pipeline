"""FRAME-FIRST PLACEMENT (caaleb, 2026-11-23: "our code is shit if it's cutting this off and putting them in the wrong
spot"). Shots used to type world coordinates for every prop and then aim a camera somewhere else, so what the viewer
saw was whatever the two happened to agree on: a sign cut by the frame edge, Data's hands off the side, the beat's
prop a sliver at the bottom. Here a shot says WHERE ON THE SCREEN a thing goes and the solver finds where it goes in
the world.

The screen is 0..1 across and 0..1 up of the 1080x1920 frame (x right, y up, as world_to_camera_view gives it).

  place(obj, cam, box=(x0, y0, x1, y1), frame=f, depth=d | on_ground=True, scale_ok=False)
      moves (and, if allowed, uniformly scales) obj so its projected bounding box sits inside box; `key=True` keys
      it on that frame, so a moving thing is placed per keyframe (`place_keys`).
  solve_camera(points_at, cam_loc, look, lens, face_at=(x, y), height=h)
      for Data: the camera is solved, never him, because his hands are already on the set; it trucks and dollies the
      lens so his face lands at face_at and he stands h of the frame tall. Returns (cam_loc, look).
  frame_data(data, cam_loc, look, lens, face_at, height, t)
      solve_camera on his rig at time t.
  fits(objs, cam, box, frames) / check(...)
      the report: COMPOSE lines naming every declared box a thing leaves, which store/shots.py runs on a shot's
      `boxes` [(label, objs, box)] and fails strict.

The core (Pinhole, project, fit, solve_camera) is plain math with no bpy, so tests/test_data3d_compose.py runs it
anywhere; the bpy layer below it only reads corners and writes locations."""
import math

RES = (1080, 1920)
SENSOR_H = 36.0          # scene_kit.camera: sensor_fit VERTICAL, 36 mm
TOL = 0.004              # of the frame: a box edge may be missed by this much


# ------------------------------------------------------------------ the math, no bpy

def _v(a): return (float(a[0]), float(a[1]), float(a[2]))
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _norm(a):
    n = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


class Pinhole:
    """scene_kit.camera's lens: aimed from loc at look with world Z up, `lens` mm on a 36 mm vertical sensor"""
    def __init__(self, loc, look, lens, res=RES):
        self.loc = _v(loc); self.look = _v(look); self.lens = float(lens)
        self.fw = _norm(_sub(self.look, self.loc))
        self.right = _norm(_cross(self.fw, (0.0, 0.0, 1.0)))
        self.up = _cross(self.right, self.fw)
        self.th = (SENSOR_H / 2) / self.lens                  # tan of half the vertical angle
        self.tw = self.th * res[0] / res[1]

    def project(self, p):
        """(x, y, depth): x, y in 0..1 of the frame, depth along the lens axis (<= 0 is behind the lens)"""
        d = _sub(_v(p), self.loc); z = _dot(d, self.fw)
        if z <= 1e-6: return (0.5, 0.5, z)
        return (0.5 + _dot(d, self.right) / (2 * z * self.tw), 0.5 + _dot(d, self.up) / (2 * z * self.th), z)

    def moved(self, by):
        return Pinhole(_add(self.loc, by), _add(self.look, by), self.lens)


def bbox(project, pts):
    """the screen box (x0, y0, x1, y1) of world points, and whether all are in front of the lens"""
    q = [project(p) for p in pts]
    front = all(z > 0 for _x, _y, z in q)
    xs = [x for x, _y, _z in q]; ys = [y for _x, y, _z in q]
    return (min(xs), min(ys), max(xs), max(ys)), front


def inside(b, box, tol=TOL):
    return b[0] >= box[0] - tol and b[1] >= box[1] - tol and b[2] <= box[2] + tol and b[3] <= box[3] + tol


def _target(b, box, on_ground):
    """the screen error to close: the box centre to the target centre, or (on the ground) its foot to the box foot"""
    cx, tx = (b[0] + b[2]) / 2, (box[0] + box[2]) / 2
    if on_ground:
        return (tx - cx, box[1] - b[1])
    return (tx - cx, (box[1] + box[3]) / 2 - (b[1] + b[3]) / 2)


def fit(project, pts, box, axes, on_ground=False, scale_ok=False, pivot=None, iters=40, keep=False):
    """solve a world offset (along the two `axes`) and a uniform scale about `pivot` so the points' screen box sits in
    `box`. Newton on a numeric Jacobian. keep: a thing already inside its box stays where it is. Returns dict(offset,
    scale, box, ok, why)."""
    pts = [_v(p) for p in pts]
    pv = _v(pivot) if pivot is not None else _mul(tuple(map(sum, zip(*pts))), 1.0 / len(pts))
    off = (0.0, 0.0, 0.0); s = 1.0
    def moved(o, sc):
        return [_add(_add(pv, _mul(_sub(p, pv), sc)), o) for p in pts]
    bw, bh = box[2] - box[0], box[3] - box[1]
    b0, f0 = bbox(project, pts)
    if keep and f0 and inside(b0, box):
        return dict(offset=(0.0, 0.0, 0.0), scale=1.0, box=b0, ok=True, why="")
    for _ in range(iters):
        b, front = bbox(project, moved(off, s))
        if scale_ok:
            w, h = b[2] - b[0], b[3] - b[1]
            k = min(bw / w if w > 1e-6 else 9, bh / h if h > 1e-6 else 9)
            if k < 1.0: s *= k * 0.985; continue
        e = _target(b, box, on_ground)
        if abs(e[0]) < 1e-4 and abs(e[1]) < 1e-4: break
        J = []
        for a in axes:                       # d(error)/d(step along each axis)
            h_ = 1e-3
            b2, _f = bbox(project, moved(_add(off, _mul(a, h_)), s))
            e2 = _target(b2, box, on_ground)
            J.append(((e[0] - e2[0]) / h_, (e[1] - e2[1]) / h_))
        (a11, a21), (a12, a22) = J
        det = a11 * a22 - a12 * a21
        if abs(det) < 1e-9: break
        u = (e[0] * a22 - a12 * e[1]) / det; v = (a11 * e[1] - a21 * e[0]) / det
        step = max(abs(u), abs(v)); lim = 2.0
        if step > lim: u, v = u * lim / step, v * lim / step
        off = _add(off, _add(_mul(axes[0], u), _mul(axes[1], v)))
    b, front = bbox(project, moved(off, s))
    ok = front and inside(b, box)
    why = "" if ok else ("behind the lens" if not front else
                         f"it is {b[2] - b[0]:.2f} x {b[3] - b[1]:.2f} of the frame for a {bw:.2f} x {bh:.2f} box"
                         if (b[2] - b[0]) > bw + TOL or (b[3] - b[1]) > bh + TOL else "the solve did not converge")
    return dict(offset=off, scale=s, box=b, ok=ok, why=why)


def screen_axes(cam, on_ground):
    """the two world directions a thing is slid along: the lens's right and up, or (on the ground) right and away"""
    if on_ground:
        r = _norm((cam.right[0], cam.right[1], 0.0)); f = _norm((cam.fw[0], cam.fw[1], 0.0))
        return (r, f)
    return (cam.right, cam.up)


def solve_camera(head, crown, foot, cam_loc, look, lens, face_at=(0.5, 0.6), height=0.4, iters=30):
    """truck and dolly the lens (look moves with it) so `head` lands at face_at and crown-to-foot spans `height` of
    the frame. Returns (cam_loc, look, report)."""
    cam = Pinhole(cam_loc, look, lens)
    for _ in range(iters):
        hx, hy, hz = cam.project(head)
        top = cam.project(crown)[1]; bot = cam.project(foot)[1]
        h = top - bot
        if hz <= 0: break
        k = h / height if height else 1.0
        dolly = hz * (1 - k)                             # move along the lens axis: height goes as 1/depth
        ex, ey = face_at[0] - hx, face_at[1] - hy
        truck = _add(_mul(cam.right, -ex * 2 * hz * cam.tw), _mul(cam.up, -ey * 2 * hz * cam.th))
        step = _add(_mul(cam.fw, dolly * 0.7), _mul(truck, 0.7))
        cam = cam.moved(step)
        if abs(ex) < 1e-4 and abs(ey) < 1e-4 and abs(1 - k) < 1e-3: break
    hx, hy, _ = cam.project(head); h = cam.project(crown)[1] - cam.project(foot)[1]
    ok = abs(hx - face_at[0]) < 0.01 and abs(hy - face_at[1]) < 0.01 and abs(h - height) < 0.01
    return cam.loc, cam.look, dict(ok=ok, face=(hx, hy), height=h)


# ------------------------------------------------------------------ the bpy layer

def _bpy():
    import bpy
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    return bpy, Vector, world_to_camera_view


def tree(obj):
    """obj and everything parented under it that is drawn"""
    out = [obj] + list(obj.children_recursive)
    return [o for o in out if o.type in ("MESH", "FONT", "CURVE")]


def corners(objs):
    bpy, Vector, _w = _bpy()
    pts = []
    for o in objs:
        if o.hide_render: continue
        if max(abs(v) for v in o.matrix_world.to_scale()) < 0.01: continue    # keyed off (scale 1e-3, float32)
        pts += [tuple(o.matrix_world @ Vector(c)) for c in o.bound_box]
    return pts


def lens_of(cam):
    """the solver's Pinhole for a scene camera, as it stands on the current frame"""
    m = cam.matrix_world
    loc = tuple(m.translation); fw = tuple(-m.col[2][i] for i in range(3))
    return Pinhole(loc, _add(loc, fw), cam.data.lens)


def place(obj, cam, box, frame=None, depth=None, on_ground=False, ground_z=0.0, scale_ok=False, key=False, label=None, keep=True):
    """move (and scale) obj (or a list of objects, moved together) so its drawn tree's screen box sits in `box`. depth: first slide it along the lens ray to
    that depth. on_ground: slide it on the floor (right / away), its foot kept on ground_z. Returns the fit dict and
    prints a COMPOSE line when it cannot fit."""
    bpy, Vector, _w = _bpy()
    sc = bpy.context.scene
    roots = list(obj) if isinstance(obj, (list, tuple)) else [obj]       # a group (a sign's board, its words, its strings) moves as one
    if frame is not None: sc.frame_set(frame)
    bpy.context.view_layer.update()
    pin = lens_of(cam)
    draw = lambda: [o for r_ in roots for o in tree(r_)]
    def shift(by):
        for r_ in roots: r_.location = Vector(r_.location) + Vector(by)
        bpy.context.view_layer.update()
    if depth is not None:
        here = _v(roots[0].matrix_world.translation); d = pin.project(here)[2]
        shift(_mul(pin.fw, depth - d))
    pts = corners(draw())
    if not pts: return dict(ok=False, why="nothing drawn", offset=(0, 0, 0), scale=1.0, box=None)
    piv = _v(roots[0].matrix_world.translation)
    if on_ground:
        zmin = min(p[2] for p in pts)
        shift((0.0, 0.0, ground_z - zmin)); pts = corners(draw())
        piv = (piv[0], piv[1], ground_z)
    r = fit(pin.project, pts, box, screen_axes(pin, on_ground), on_ground=on_ground, scale_ok=scale_ok and len(roots) == 1, pivot=piv, keep=keep)
    shift(r["offset"])
    if r["scale"] != 1.0: roots[0].scale = Vector(roots[0].scale) * r["scale"]
    if key:
        for r_ in roots:
            r_.keyframe_insert("location", frame=frame or sc.frame_current)
            if scale_ok: r_.keyframe_insert("scale", frame=frame or sc.frame_current)
    bpy.context.view_layer.update()
    if not r["ok"]:
        print(f"COMPOSE {label or roots[0].name}: cannot fit {tuple(round(v, 3) for v in box)}: {r['why']} -> FAIL", flush=True)
    return r


def place_keys(obj, cam, box_at, frames, **kw):
    """a moving thing placed per keyframe: box_at(frame) -> its box on that frame"""
    return [place(obj, cam, box_at(f), frame=f, key=True, **kw) for f in frames]


def data_points(data):
    """his face centre, his crown and his feet, in the world, on the current frame"""
    m = data.arm.matrix_world; pb = data.pb
    head, top = m @ pb["head"].head, m @ pb["head"].tail
    face = tuple(head.lerp(top, 0.5)); crown = tuple(top)            # head to feet as staging.check measures it
    foot = tuple(m.translation)
    return face, crown, foot


def frame_data(data, cam_loc, look, lens, face_at=(0.5, 0.58), height=0.38, t=0.0, fps=30):
    """solve the camera (never him: his hands are already on the set) so his face sits at face_at and he stands
    `height` of the frame tall at time t. Returns (cam_loc, look) as mathutils Vectors."""
    bpy, Vector, _w = _bpy()
    bpy.context.scene.frame_set(int(round(t * fps)) + 1); bpy.context.view_layer.update()
    face, crown, foot = data_points(data)
    loc, lk, rep = solve_camera(face, crown, foot, tuple(cam_loc), tuple(look), lens, face_at, height)
    if not rep["ok"]:
        print(f"COMPOSE Data: cannot put his face at {face_at} at {height:.2f} of the frame: got {rep} -> FAIL", flush=True)
    return Vector(loc), Vector(lk)


def check(cam, nf, boxes, name="shot", step=2, seen=0.9):
    """the report: every declared (label, objs, box[, t0, t1]) inside its box on `seen` of its frames"""
    bpy, Vector, w2c = _bpy()
    sc = bpy.context.scene; ok_all = True
    for it in boxes:
        label, objs, box = it[:3]
        t0, t1 = (it[3], it[4]) if len(it) > 4 else (0.0, (nf - 1) / 30)
        objs = objs() if callable(objs) else objs
        n = good = 0; worst = None
        for f in range(int(round(t0 * 30)) + 1, min(nf, int(round(t1 * 30)) + 1) + 1, step):
            sc.frame_set(f); bpy.context.view_layer.update()
            pts = corners(objs)
            if not pts: continue
            q = [w2c(sc, cam, Vector(p)) for p in pts]
            if any(v.z <= 0 for v in q): n += 1; continue
            b = (min(v.x for v in q), min(v.y for v in q), max(v.x for v in q), max(v.y for v in q))
            n += 1
            if inside(b, box, 0.01): good += 1
            elif worst is None: worst = (f, tuple(round(v, 3) for v in b))
        frac = good / max(1, n); ok = frac >= seen; ok_all &= ok
        print(f"COMPOSE {name}: {label} inside {tuple(box)} on {frac:.0%} of its frames (min {seen:.0%})"
              + ("" if ok else f"; first miss f{worst[0]} at {worst[1]}" if worst else "") + f" -> {'OK' if ok else 'FAIL'}", flush=True)
    return ok_all


def drop_cut(roots, cam, nf, step=4, label="set dressing"):
    """background dressing (a show table's jars, a shelf of tins) that the frame edge cuts is taken out of the shot, never
    left half in: a cut label is a defect (staging.edges). Returns the names dropped. Never use it on the beat's prop:
    that is placed (place) and held (boxes)."""
    bpy, Vector, w2c = _bpy()
    sc = bpy.context.scene; out = []
    for r in roots:
        objs = tree(r)
        for f in range(1, nf + 1, step):
            sc.frame_set(f); bpy.context.view_layer.update()
            pts = corners(objs)
            if not pts: break
            q = [w2c(sc, cam, Vector(p)) for p in pts]
            if any(v.z <= 0 for v in q): continue
            b = (min(v.x for v in q), min(v.y for v in q), max(v.x for v in q), max(v.y for v in q))
            seen = b[2] > 0 and b[0] < 1 and b[3] > 0 and b[1] < 1
            if seen and not (b[0] >= 0 and b[2] <= 1 and b[1] >= 0 and b[3] <= 1):
                for o in [r] + list(r.children_recursive): o.hide_render = True; o.hide_viewport = True
                out.append(r.name); break
    print(f"COMPOSE {label}: dropped {len(out)} of {len(roots)} cut by the frame edge" + (f": {', '.join(out[:6])}" if out else ""), flush=True)
    return out
