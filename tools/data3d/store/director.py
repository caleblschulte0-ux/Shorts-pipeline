"""THE DIRECTOR: a shot of a daily 3D short in twenty lines (2026-11-28).

The operator, 2026-11-28, after the lava short spent 90 hours without a video: "fix whatever is broken and make this
into a fully autonomous system that produces a new 3d video in a timely manner like at the very least 1 a day."

What was slow was never the render (about two hours on twenty runners). It was that every shot of every short was
three hundred lines of hand-written Blender: its own ground, its own houses, its own typed coordinates, found wrong
one forty-minute judge round at a time. The audit of 280 panel verdicts (memory data-3d-audit-world-acts) says which
shots pass: the WORLD acts, Data reacts, one locked camera, two or three props. This module is that grammar, with the
place and the props taken from the real world instead of modelled:

  a PLACE   s.place("suburban_garden")       one of Poly Haven's ~700 photographed environments: its HDRI lights the
                                              scene and its plate is what the lens sees, so every beat stands in a
                                              real, new place and no set is ever built or reused. The ground under him
                                              is the plate's own ground (he and the props shade it where they stand).
            s.sky("dusk"); s.ground("grass")  or a built outdoor place from the realism kit (store/fx_kit.py), for
                                              what no photograph has (a lava field, a burning street)
  the HERO  s.hero(u=0.3, height=0.42)        Data, three-quarter to the lens, on his side of the frame; the ONE
                                              locked camera is solved from where he should be on the screen
  PROPS     s.model("sofa_03", u, depth)      real scanned props (Poly Haven models, 522 of them), placed by where
                                              they are ON THE SCREEN (u across, depth from the lens), never by typed
                                              world coordinates; s.kit("fire", ...) for the realism kit's elements
  the EVENT s.fall / s.move / s.appear / s.dust / s.flash / s.shake / s.debris     what the world DOES
  ACTING    s.act([(t, "look", thing), (t, "alarmed"), (t, "step", (dx, dy)), (t, "shrug")])     what he does about it
  s.done()                                    the dict store/shots.py wants

Screen placement: u is 0 (left edge) to 1 (right edge), v is 0 (bottom) to 1 (top), depth is metres from the lens
along its axis. s.at(u, depth) is the point on the ground there; s.air(u, v, depth) is a point in the air. Sizes are
Data's world (K.U = 0.56 of ours): a model comes in at that scale, so a sofa is a sofa beside him.

Times are fractions of the beat when under 1.5 (0.3 = 30% in), seconds otherwise; the beat's length is the voice's.
Nothing here judges anything: it only makes the staging that passes the easy way to write.
"""
import math, os, random
import bpy
from mathutils import Vector, Euler, Matrix
import scene_kit as K, fx_kit as FX, compose
from clock import FPS

LENS = 24.0
TANV = 18.0 / LENS                 # half the frame's height at 1 m (scene_kit.camera: a 36 mm vertical sensor)
TANH = TANV * 9.0 / 16.0           # half its width
U = K.U
ENV_H = 1.5 * U                    # a plate is shot from about 1.5 m: this lens height makes him a grown man in it
EMOTES = ("happy", "surprised", "alarmed", "sad", "worried", "determined", "wry", "angry")
GESTURES = ("shrug", "whoa", "wave", "thumbs_up")


def _F(t):
    return int(round(t * FPS)) + 1


def _ease(u):
    u = max(0.0, min(1.0, u)); return u * u * (3 - 2 * u)


class Shot:
    def __init__(self, G, place):
        """G: the harness's globals (a story's shots.py passes globals()); place: this beat's name in script.json 'sets'"""
        self.G = G; self.DUR = G["DUR"]; self.NF = G["NF"]; self.sc = bpy.context.scene
        self.name = place; self.data = None; self.cam = None; self.conseq = []; self.grips = (); self._light = None
        self._env = None; self._shakes = []; self._acts = []; self._n = 0; self.things = {}
        self.sc.render.resolution_x, self.sc.render.resolution_y = 1080, 1920

    # ------------------------------------------------------------------------------------------------ time
    def T(self, t):
        """a time in seconds: a fraction of the beat when under 1.5"""
        return t * self.DUR if t < 1.5 else float(t)

    # ------------------------------------------------------------------------------------------------ the place
    def place(self, env, turn=0.0, light=1.5, plate=1.7, floor_shade=1.0):
        """a REAL place: the environment `env` (fetched by `env <id>` in .github/triggers/data3d_assets). turn (degrees)
        swings the whole place round him, so the lens looks at the part of it the beat is about. The ground he stands
        on is the photograph's own ground, darkened where he and the props stand on it."""
        hdr = FX.ph_path("hdri", f"{env}_2k.hdr")
        jpg = FX.ph_path("env", f"{env}.jpg")
        if not os.path.exists(jpg): jpg = FX.ph_path("hdri", f"{env}_4k.hdr") if os.path.exists(FX.ph_path("hdri", f"{env}_4k.hdr")) else hdr
        w = self.sc.world or bpy.data.worlds.new("World"); self.sc.world = w; w.use_nodes = True; nt = w.node_tree
        for n in list(nt.nodes): nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputWorld")
        tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Rotation"].default_value = (0, 0, math.radians(turn))
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        e_l = nt.nodes.new("ShaderNodeTexEnvironment"); e_l.image = bpy.data.images.load(hdr, check_existing=True)
        e_p = nt.nodes.new("ShaderNodeTexEnvironment"); e_p.image = bpy.data.images.load(jpg, check_existing=True)
        nt.links.new(mp.outputs["Vector"], e_l.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], e_p.inputs["Vector"])
        b_l = nt.nodes.new("ShaderNodeBackground"); b_l.inputs["Strength"].default_value = light
        b_p = nt.nodes.new("ShaderNodeBackground"); b_p.inputs["Strength"].default_value = plate
        nt.links.new(e_l.outputs["Color"], b_l.inputs["Color"]); nt.links.new(e_p.outputs["Color"], b_p.inputs["Color"])
        lp = nt.nodes.new("ShaderNodeLightPath"); mx = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], mx.inputs[0]); nt.links.new(b_l.outputs[0], mx.inputs[1]); nt.links.new(b_p.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs["Surface"])
        # the ground: the plate itself, seen along the lens's own ray, shaded where things stand on it
        m = bpy.data.materials.new("plate ground"); m.use_nodes = True; mt = m.node_tree
        for n in list(mt.nodes): mt.nodes.remove(n)
        mo = mt.nodes.new("ShaderNodeOutputMaterial"); geo = mt.nodes.new("ShaderNodeNewGeometry")
        neg = mt.nodes.new("ShaderNodeVectorMath"); neg.operation = 'SCALE'; neg.inputs["Scale"].default_value = -1.0
        mt.links.new(geo.outputs["Incoming"], neg.inputs[0])
        gm = mt.nodes.new("ShaderNodeMapping"); gm.inputs["Rotation"].default_value = (0, 0, math.radians(turn)); gm.vector_type = 'POINT'
        mt.links.new(neg.outputs["Vector"], gm.inputs["Vector"])
        ge = mt.nodes.new("ShaderNodeTexEnvironment"); ge.image = e_p.image; mt.links.new(gm.outputs["Vector"], ge.inputs["Vector"])
        ao = mt.nodes.new("ShaderNodeAmbientOcclusion"); ao.inputs["Distance"].default_value = 0.7; ao.samples = 16
        pw = mt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = 2.6 * floor_shade
        mt.links.new(ao.outputs["AO"], pw.inputs[0])
        mul = mt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs["Factor"].default_value = 1.0
        mt.links.new(ge.outputs["Color"], mul.inputs["A"]); mt.links.new(pw.outputs[0], mul.inputs["B"])
        em = mt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = plate; mt.links.new(mul.outputs["Result"], em.inputs["Color"])
        mt.links.new(em.outputs[0], mo.inputs["Surface"])
        bpy.ops.mesh.primitive_circle_add(vertices=64, radius=80.0, fill_type='NGON', location=(0, 0, 0))
        g = bpy.context.active_object; g.name = "plate ground"; g.data.materials.append(m)
        g.visible_shadow = False
        ld = bpy.data.lights.new("hero key", 'AREA'); ld.energy = 0.0; ld.size = 0.9           # style.follow_key wants a lamp; the place lights him
        key = bpy.data.objects.new("hero key", ld); bpy.context.collection.objects.link(key)
        self._light = lambda: key
        self._env = dict(env=env, ground=g, turn=turn, world=(b_l, b_p), mat=m)
        return self._env

    def sky(self, preset="day", sun_az=-45, **kw):
        """a built outdoor place's sky (the realism kit's real HDRI skies); follow it with s.ground(...)"""
        s = FX.sky(preset, sun_az=sun_az, **kw)
        ld = bpy.data.lights.new("hero key", 'AREA'); ld.energy = 0.0; ld.size = 0.9
        key = bpy.data.objects.new("hero key", ld); bpy.context.collection.objects.link(key)
        self._light = lambda: key
        return s

    def ground(self, kind="grass", area=(-12, 12, -6, 40), **kw):
        return FX.ground(kind, area=area, **kw)

    # ------------------------------------------------------------------------------------------------ the hero and the lens
    def hero(self, u=0.3, height=0.42, yaw=None, face_v=0.56, cam_h=None, costume=None):
        """Data at the origin, three-quarter to the lens, his face at (u, face_v) of the frame and `height` of it
        tall, on a LOCKED 24 mm lens. yaw: degrees he is turned toward frame right (+) or left (-); default: turned
        a little toward the far side of the frame, where the event is."""
        d = self.data = self.G["load_data"]()
        if yaw is None: yaw = 24 if u < 0.5 else -24
        d.place(0.0, 0.0, yaw); self.yaw = yaw
        if costume: costume(d)
        h = ENV_H if cam_h is None else cam_h
        side = -1 if u < 0.5 else 1                   # the lens stands off to the side he is on, so the far side opens up
        c0 = Vector((0.35 * side, -2.2, h)); l0 = Vector((0.0, 0.0, 0.55))
        C, L = compose.frame_data(d, c0, l0, LENS, face_at=(u, face_v), height=height, t=0.0, fps=FPS)
        C.z = max(0.12, C.z)
        self.cam = K.camera(tuple(C), tuple(L), lens=LENS, fstop=11.0)
        self._basis()
        return d

    def _basis(self):
        bpy.context.view_layer.update(); M = self.cam.matrix_world
        self.C = M.translation.copy(); q = M.to_quaternion()
        self.fw = (q @ Vector((0, 0, -1))).normalized(); self.rt = (q @ Vector((1, 0, 0))).normalized(); self.up = (q @ Vector((0, 1, 0))).normalized()

    def at(self, u, depth, z=0.0):
        """the point at height z whose picture is at `u` across the frame, `depth` metres from the lens"""
        fh = Vector((self.fw.x, self.fw.y, 0)).normalized()
        base = self.C + fh * depth; base.z = z
        d = (base - self.C).dot(self.fw)
        return base + self.rt * ((u - 0.5) * 2 * TANH * d)

    def air(self, u, v, depth):
        """the point in the air at (u, v) of the frame, `depth` metres along the lens's axis"""
        return self.C + (self.fw + self.rt * ((u - 0.5) * 2 * TANH) + self.up * ((v - 0.5) * 2 * TANV)) * depth

    def spot(self, u, v, z=0.0):
        """the point of the GROUND (height z) whose picture is at (u, v) of the frame: how a thing is stood in a
        photographed place. Read (u, v) off the scout sheet (daily/scout.py): a spot on the open floor, in front of the
        photograph's own walls and furniture (v under about 0.4; the floor ends where the wall starts)"""
        d = self.fw + self.rt * ((u - 0.5) * 2 * TANH) + self.up * ((v - 0.5) * 2 * TANV)
        if d.z >= -1e-4: raise SystemExit(f"director: ({u}, {v}) is above the horizon, there is no ground there")
        return self.C + d * ((z - self.C.z) / d.z)

    def see(self, p):
        """(u, v, depth) of a world point"""
        r = Vector(p) - self.C; d = r.dot(self.fw)
        return (0.5 + r.dot(self.rt) / (2 * TANH * d), 0.5 + r.dot(self.up) / (2 * TANV * d), d)

    # ------------------------------------------------------------------------------------------------ props
    def model(self, aid, u=0.7, depth=3.0, yaw=0.0, scale=1.0, z=0.0, name=None, at=None, only=None, v=None):
        """a real scanned prop (Poly Haven model `aid`), standing on the ground at (u, depth). yaw in degrees; scale 1
        is its real size in Data's world."""
        p = Vector(at) if at is not None else self.spot(u, v, z) if v is not None else self.at(u, depth, z)
        self._n += 1
        o = FX.ph_model(aid, loc=tuple(p), rot=(0, 0, math.radians(yaw)), scale=U * scale, name=name or f"{aid} {self._n}", only=only)
        self.things[o.name] = o
        return o

    def kit(self, element, u=None, depth=None, z=0.0, **kw):
        """an element of the realism kit (fire, smoke_column, steam, dust_puff, house, car, truck, lava_pool, embers
        ...) at (u, depth): its first argument (base / loc / origin / centre) is put there"""
        fn = getattr(FX, element)
        if u is not None:
            p = self.at(u, depth, z)
            import inspect
            first = [a for a in inspect.signature(fn).parameters if a in ("base", "loc", "origin", "centre")]
            if first: kw[first[0]] = (p.x, p.y) if first[0] == "centre" else tuple(p)
        return fn(**kw)

    def parts(self, o):
        o = o["root"] if isinstance(o, dict) and "root" in o else o
        if isinstance(o, dict): return [x for x in o.get("objects", []) if hasattr(x, "type")]
        return [x for x in [o] + list(o.children_recursive) if x.type in ('MESH', 'FONT', 'CURVE')]

    # ------------------------------------------------------------------------------------------------ what the world does
    def move(self, o, keys, ease=True):
        """keys: [(t, location, rotation_euler_degrees or None)]; keyed every frame between them (eased)"""
        ks = [(self.T(t), Vector(loc), None if rot is None else Vector([math.radians(a) for a in rot])) for t, loc, rot in keys]
        r0 = Vector(o.rotation_euler)
        for (ta, la, ra), (tb, lb, rb) in zip(ks, ks[1:]):
            for f in range(_F(ta), _F(tb) + 1):
                u = ((f - 1) / FPS - ta) / max(1e-6, tb - ta); e = _ease(u) if ease else max(0.0, min(1.0, u))
                o.location = la.lerp(lb, e); o.keyframe_insert("location", frame=f)
                if ra is not None or rb is not None:
                    a = ra if ra is not None else r0; b = rb if rb is not None else a
                    o.rotation_euler = Euler(a.lerp(b, e)); o.keyframe_insert("rotation_euler", frame=f)
        return o

    def fall(self, o, start, end, t0, t1, spin=(0, 0, 0), bounce=0.0):
        """o falls from `start` to `end` between t0 and t1 under gravity's curve (it speeds up; it does not ease in to
        land), turning by `spin` degrees on the way; bounce: how high it hops once after it lands (metres)"""
        t0, t1 = self.T(t0), self.T(t1); a, b = Vector(start), Vector(end); r0 = Vector(o.rotation_euler)
        sp = Vector([math.radians(x) for x in spin])
        o.location = a; o.keyframe_insert("location", frame=1)
        for f in range(_F(t0), _F(t1) + 1):
            u = max(0.0, min(1.0, ((f - 1) / FPS - t0) / max(1e-6, t1 - t0)))
            o.location = a.lerp(b, u * u); o.keyframe_insert("location", frame=f)
            o.rotation_euler = Euler(r0 + sp * u); o.keyframe_insert("rotation_euler", frame=f)
        if bounce:
            tb = 0.12 + 0.45 * math.sqrt(bounce)
            for f in range(_F(t1), _F(t1 + tb) + 1):
                u = ((f - 1) / FPS - t1) / tb; o.location = b + Vector((0, 0, bounce * 4 * u * (1 - u))); o.keyframe_insert("location", frame=f)
        return t1

    def appear(self, o, t, show=True):
        """o (and its parts) is in the picture only from t (show=False: only until t)"""
        f = _F(self.T(t))
        for x in ([o] + list(o.children_recursive)) if hasattr(o, "children_recursive") else self.parts(o):
            x.hide_render = show; x.keyframe_insert("hide_render", frame=max(1, f - 1))
            x.hide_render = not show; x.keyframe_insert("hide_render", frame=f)

    def dust(self, p, t, w=1.0, h=1.2, dur=1.8, col=(0.72, 0.68, 0.62), dens=1.5, seed=0.0):
        """a puff of dust at p from t (plaster, soil, ash by its colour)"""
        d = FX.dust_puff(tuple(p), w=w, h=h, t0=self.T(t), dur=dur, col=col, dens=dens, seed=seed)
        for o in d["objects"]: o.visible_shadow = False; o.visible_diffuse = False      # its box must not shade the photographed ground
        return d

    def flash(self, p, t, power=400.0, col=(1.0, 0.85, 0.6), dur=0.35, r=0.3, name="flash"):
        """a burst of light at p at t that dies away over dur (an impact, a spark, a bolt)"""
        t = self.T(t); ld = bpy.data.lights.new(name, 'POINT'); ld.color = col; ld.shadow_soft_size = r; ld.energy = 0.0
        o = bpy.data.objects.new(name, ld); o.location = tuple(p); bpy.context.collection.objects.link(o)
        for f in range(1, self.NF + 1):
            x = (f - 1) / FPS - t; ld.energy = power * math.exp(-4.0 * x / dur) if x >= 0 else 0.0; ld.keyframe_insert("energy", frame=f)
        return o

    def glow(self, p, power=30.0, col=(1.0, 0.5, 0.15), keys=None, r=0.25, name="glow"):
        """a lamp at p (what a glowing thing casts); keys [(t, 0..1)] brings it up and down"""
        ld = bpy.data.lights.new(name, 'POINT'); ld.color = col; ld.shadow_soft_size = r; ld.energy = power
        o = bpy.data.objects.new(name, ld); o.location = tuple(p); bpy.context.collection.objects.link(o)
        if keys:
            ks = [(self.T(t), v) for t, v in keys]
            for f in range(1, self.NF + 1):
                x = (f - 1) / FPS; v = ks[0][1] if x <= ks[0][0] else ks[-1][1]
                for (ta, va), (tb, vb) in zip(ks, ks[1:]):
                    if ta <= x <= tb: v = va + (vb - va) * _ease((x - ta) / max(1e-6, tb - ta))
                ld.energy = power * v; ld.keyframe_insert("energy", frame=f)
        return o

    def shake(self, t, amp=0.03, dur=0.5):
        """the lens jolts at t (an impact felt): it is still LOCKED, it only shudders and settles"""
        self._shakes.append((self.T(t), amp, dur))

    def debris(self, p, n, t, mat, speed=2.2, size=(0.02, 0.07), seed=0, spread=1.0, up=1.0, ground_z=0.0, life=None):
        """n broken pieces thrown from p at t on real arcs, tumbling, coming to rest on the ground. mat: a material
        (FX.ph_mat("plastered_wall") for plaster, a roof tile's, a plank's). Returns the pieces."""
        t = self.T(t); rnd = random.Random(seed); out = []; g = 9.81 * U
        for k in range(n):
            s = rnd.uniform(*size); o = FX.block(f"debris {self._n} {k}", tuple(p), s, mat, rnd, squash=rnd.uniform(0.25, 0.8))
            a = rnd.uniform(0, 2 * math.pi); v = Vector((math.cos(a) * spread, math.sin(a) * spread, rnd.uniform(0.3, 1.0) * up)) * speed * rnd.uniform(0.4, 1.0)
            spin = Vector((rnd.uniform(-9, 9), rnd.uniform(-9, 9), rnd.uniform(-9, 9))); r0 = Vector((rnd.uniform(0, 6), rnd.uniform(0, 6), rnd.uniform(0, 6)))
            p0 = Vector(p); rest_t = None; rest_p = None
            o.hide_render = True; o.keyframe_insert("hide_render", frame=max(1, _F(t) - 1)); o.hide_render = False; o.keyframe_insert("hide_render", frame=_F(t))
            for f in range(_F(t), self.NF + 1):
                x = (f - 1) / FPS - t
                if rest_t is None:
                    q = p0 + v * x + Vector((0, 0, -0.5 * g * x * x))
                    if q.z <= ground_z + s * 0.3 and x > 0.05: rest_t = x; q.z = ground_z + s * 0.3; rest_p = q.copy()
                else: q = rest_p
                o.location = q; o.keyframe_insert("location", frame=f)
                xx = x if rest_t is None else rest_t
                o.rotation_euler = Euler(r0 + spin * xx); o.keyframe_insert("rotation_euler", frame=f)
            out.append(o)
        self._n += 1
        return out

    # ------------------------------------------------------------------------------------------------ what he does about it
    def act(self, beats):
        """his performance, in order: [(t, what, arg)]
          "look", target      his head and eyes go to a thing, a point, or "lens"
          an emotion          happy surprised alarmed sad worried determined wry angry: the whole body plays it
          a gesture           shrug whoa wave thumbs_up
          "step", (dx, dy)    he walks that far (metres; +x frame right, +y away from the lens) over about a second
          "walk", point       he walks to a point (s.at(u, depth))
          "turn", degrees     he turns on the spot to that yaw
          "face", name        only his face changes (neutral happy pleased surprised worried alarmed sad wry ...)
          "talk", seconds     he says something"""
        d = self.data; last_t = 0.0
        for b in sorted(beats, key=lambda b: self.T(b[0])):
            t = self.T(b[0]); what = b[1]; arg = b[2] if len(b) > 2 else None; hold = b[3] if len(b) > 3 else None
            if what == "look":
                self.sc.frame_set(_F(t)); bpy.context.view_layer.update()       # where the thing IS at that moment
                p = self.C if isinstance(arg, str) and arg == "lens" else self._point(arg)
                d.look_at(Vector(p), t, max_yaw=55, max_pitch=45)
            elif what in EMOTES:
                d.perform(what, t, hold=hold if hold is not None else 0.9)
            elif what in GESTURES:
                d.act(what, t, dur=0.3, hold=hold if hold is not None else 0.7)
            elif what == "step":
                p0 = d._obj_loc(t)[0]; tgt = (p0.x + arg[0], p0.y + arg[1]); yaw_keep = d._obj_loc(t)[1]
                t1 = t + (hold if hold is not None else max(0.7, 1.6 * math.hypot(*arg)))
                d.walk_to(tgt, t, t1); d.turn_to(math.degrees(yaw_keep), t1, t1 + 0.35)
            elif what == "walk":
                p = self._point(arg); t1 = t + (hold if hold is not None else 1.4)
                d.walk_to((p[0], p[1]), t, t1)
            elif what == "turn":
                d.turn_to(arg, t, t + (hold if hold is not None else 0.5))
            elif what == "face":
                d.expression(arg, t, t + (hold if hold is not None else 1.5))
            elif what == "talk":
                d.talk(t, t + float(arg or 1.2))
            else:
                raise SystemExit(f"director: no act {what!r} (look, step, walk, turn, face, talk, {', '.join(EMOTES + GESTURES)})")
            last_t = max(last_t, t)
        self._acts = beats

    def _point(self, x):
        if isinstance(x, dict): x = x.get("root") or x.get("objects", [None])[0]
        if hasattr(x, "matrix_world"):
            ps = [x.matrix_world.translation] if x.type == 'EMPTY' and not x.children else None
            if ps is None:
                import compose as _c
                cs = [Vector(c) for c in _c.corners(self.parts(x))] if self.parts(x) else []
                cs = cs or [o.matrix_world.translation.copy() for o in self.parts(x)] or [x.matrix_world.translation.copy()]
                return sum(cs, Vector()) / len(cs)
            return ps[0]
        return Vector(x)

    # ------------------------------------------------------------------------------------------------ hand it over
    def happens(self, what, objs, t0, t1=None, moves=None, whole=False):
        """declare the beat's EVENT for the measured checks: what happens (words), to which things, from t0 to t1"""
        ps = []
        for o in (objs if isinstance(objs, (list, tuple)) else [objs]): ps += self.parts(o)
        opt = {"whole": whole, "hero": False}
        if moves: opt["moves"] = True if moves is True else sum((self.parts(o) for o in moves), [])
        self.conseq.append((what, ps, self.T(t0), self.T(t1) if t1 is not None else self.DUR, opt))

    def done(self):
        d = self.data
        d.alive(0.0, self.DUR + 0.3)
        d.finish()
        if self._shakes:                                    # the locked lens shudders at an impact and settles
            base = self.cam.location.copy()
            for f in range(1, self.NF + 1):
                x = (f - 1) / FPS; off = Vector()
                for t, amp, dur in self._shakes:
                    if x >= t:
                        k = math.exp(-5.0 * (x - t) / dur)
                        off += Vector((amp * math.sin(2 * math.pi * 13 * (x - t)), 0, amp * 0.8 * math.sin(2 * math.pi * 17 * (x - t) + 1.0))) * k
                self.cam.location = base + off; self.cam.keyframe_insert("location", frame=f)
        self.cam.data.dof.focus_distance = (d.pos() + Vector((0, 0, 0.5)) - self.C).length
        return dict(lanes=[], kiosks=[], place=self.name, light=self._light, data=d, rest=1, grips=self.grips, cutaway=None,
                    boxes=[], conseq=self.conseq, no_blur=False)
