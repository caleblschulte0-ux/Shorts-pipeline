"""Data, the rigged 3D character (rebuild of 2026-11-06, after the scratchpad was wiped).

Geometry is ChatGPT/Codex's approved model, built verbatim by base_build.py (NEVER redesign him). This module only
replaces what has to be animated: each one-capsule sleeve becomes upper arm + forearm with an ELBOW, each leg
thigh + shin with a KNEE, the eye pads become sunk eye SPHERES with lids, pupils and glints that move, the smile curve
becomes a lip tube with shape keys (rest flat line, smile, open, oh), and a deforming armature drives it all.

Units: the model is in rig units (0.2 m per unit); the armature object is scaled 0.2 so the world is in metres and
Data is 0.95 m tall. Rest facing is -Y. clock.FPS (30) fps; every time is seconds; frame F(t) = round(t*FPS) + 1.

    from character import load
    data = load(bpy.context.scene)
    data.place(x, y, rot_deg=90)           # faces +X
    data.walk_to((x1, y1), t0, t1)         # procedural walk: planted feet (measured), knees, bob
    data._arm_ik('L', world_point, t, elbow_out)   # 2-bone IK; at >= 99% reach the arm is EXACTLY straight
    data.look_at(point, t, max_yaw=40); data.expression('surprised', t0, t1); data.blink(t); data.breathe(t0, t1)
    data.act('shrug'|'wave'|'thumbs_up', t0, dur=0.3, hold=0.5); data.release(t)
    n = data.finish()
    arm_bend(data, f0, f1) -> (max_deg, mean_deg) elbow angle over frames (0 = straight)
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix, Euler, Quaternion

from clock import FPS   # the one clock (clock.py)
SCALE = 0.2
SOFT_Z = -0.0006   # metres the body settles when standing: a 0.198 m leg bends ~9 deg at the knee (-0.003 had him in a 20 deg squat all the time)
LEG_USE = 0.993     # the most of a leg the body ever stands on: 0.985 kept every planted knee bent 20-26 deg (a squat); 0.993 is ~13 deg, under the IK straight_at 0.995
HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE_FIX = os.environ.get('PROFILE_FIX', '1') == '1'
EYE_CAP_DEG = 50     # the eyeball is a cap this many degrees off its front; its rim sits ~3 cm inside the head


def F(t):
    return int(round(t * FPS)) + 1


def ease(u):
    u = max(0.0, min(1.0, u)); return u * u * (3 - 2 * u)


# ------------------------------------------------------------------------------------------------ geometry helpers
def head_surface_y(x, z, cx=0.0, cz=3.525, rx=0.929, ry=0.69, rz=0.86):
    """y of the head ellipsoid's front surface at (x, z) in rig units (the base head after every shift)."""
    v = 1 - ((x - cx) / rx) ** 2 - ((z - cz) / rz) ** 2
    return -ry * math.sqrt(max(0.01, v))


def _capsule(name, a, b, r, mat, segs=40):
    a, b = Vector(a), Vector(b)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=24, location=(a + b) / 2)
    o = bpy.context.object; o.name = name
    o.scale = (r, r, (b - a).length / 2 + r)
    o.rotation_euler = (b - a).to_track_quat('Z', 'Y').to_euler()
    o.data.materials.append(mat)
    for p in o.data.polygons: p.use_smooth = True
    return o


def _sphere(name, loc, r, mat, scale=None, segs=40):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=24, location=loc)
    o = bpy.context.object; o.name = name; o.scale = scale or (r, r, r)
    o.data.materials.append(mat)
    for p in o.data.polygons: p.use_smooth = True
    return o


def _cap(name, centre, r, mat, keep, segs=48):
    """a spherical shell piece: the verts of a sphere of radius r (local, centred at origin) for which keep(n) holds"""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=32, location=centre)
    o = bpy.context.object; o.name = name; o.scale = (r, r, r)
    bm = bmesh.new(); bm.from_mesh(o.data)
    for v in bm.verts: v.co = Vector((v.co.x, -v.co.z, v.co.y))        # poles on Y: a y-cut is a ring, a z-cut a meridian
    kill = [v for v in bm.verts if not keep(v.co.normalized())]
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    bm.to_mesh(o.data); bm.free(); o.data.update()
    o.data.materials.append(mat)
    for p in o.data.polygons: p.use_smooth = True
    return o


def _tube(path, r=0.016, m=10, normal=Vector((0, -1, 0))):
    """verts/faces of a closed tube along a closed path (list of Vectors)"""
    n = len(path); verts = []; faces = []
    for i, p in enumerate(path):
        tn = (path[(i + 1) % n] - path[i - 1]).normalized()
        nx = normal - normal.dot(tn) * tn
        if nx.length < 1e-4: nx = Vector((0, 0, 1)) - tn.z * tn
        nx.normalize(); bn = tn.cross(nx)
        for k in range(m):
            a = 2 * math.pi * k / m
            verts.append(p + r * (math.cos(a) * nx + math.sin(a) * bn))
    for i in range(n):
        for k in range(m):
            faces.append((i * m + k, i * m + (k + 1) % m, ((i + 1) % n) * m + (k + 1) % m, ((i + 1) % n) * m + k))
    return verts, faces


def _mouth_paths(n=24):
    """closed paths of 2n points on the head surface: rest (thin closed lips), smile, open, oh"""
    def on_head(x, z, off=0.03):
        return Vector((x, head_surface_y(x, z) - off, z))
    def two_rows(fz, x0, x1, gap):
        top = [on_head(x0 + (x1 - x0) * i / (n - 1), fz(x0 + (x1 - x0) * i / (n - 1)) + gap) for i in range(n)]
        bot = [on_head(x1 + (x0 - x1) * i / (n - 1), fz(x1 + (x0 - x1) * i / (n - 1)) - gap) for i in range(n)]
        return top + bot
    def ellipse(cx, cz, rx, rz):
        pts = []
        for i in range(2 * n):
            a = math.pi - 2 * math.pi * i / (2 * n)          # start at the left corner, over the top, back under
            pts.append(on_head(cx + rx * math.cos(a), cz + rz * math.sin(a)))
        return pts
    # REST is a still, closed smile: a thin line with the corners turned up (operator, 2026-11-06: from the side the flat
    # dark slab read as a moustache). 'smile' is the bigger version; talking keys still move freely over it.
    rest = two_rows(lambda x: 3.085 + 0.07 * (x / 0.30) ** 2, -0.30, 0.30, 0.005)
    smile = two_rows(lambda x: 3.065 + 0.16 * (x / 0.37) ** 2, -0.37, 0.37, 0.009)
    opn = ellipse(0.0, 3.10, 0.27, 0.17)
    oh = ellipse(0.0, 3.08, 0.13, 0.13)
    # FROWN: the same thin closed line with its corners turned DOWN (2026-11-12, the second 3D short: every face he had
    # was some amount of smile, so "worried" over a rotting banana still read as pleased). Closed, never a hole.
    frown = two_rows(lambda x: 3.10 - 0.055 * (x / 0.26) ** 2, -0.26, 0.26, 0.005)
    return {'rest': rest, 'smile': smile, 'open': opn, 'oh': oh, 'frown': frown}


# ------------------------------------------------------------------------------------------------ the character
class Data:
    EXPRESSIONS = {
        # 2026-11-13 (caaleb: "we need to do a lot of work on how he express"): rendered side by side the seven faces
        # were nearly one face. Each now has its own BROW SHAPE (worry lifts the inner ends, mad drops them) and its
        # own EYES (squint is the lower lid rising: the eye smile), so it reads at phone size from the brows alone.
        'neutral': dict(smile=0.0, open=0.0, oh=0.0, brow=0.0, lid=0.0),
        'happy': dict(smile=1.0, open=0.0, oh=0.0, brow=0.08, lid=0.0, squint=0.55),
        'surprised': dict(smile=0.0, open=0.0, oh=0.9, brow=0.32, lid=0.0, frown=0.3, worry=0.25),
        'worried': dict(smile=0.0, open=0.0, oh=0.0, brow=0.1, lid=0.15, frown=1.0, worry=1.0),
        'alarmed': dict(smile=0.0, open=0.0, oh=0.0, brow=0.34, lid=0.0, frown=0.7, worry=0.55),  # brows high, eyes wide, the mouth turned down: shock without the mouth hole
        'talk': dict(smile=0.2, open=0.5, oh=0.0, brow=0.04, lid=0.0),
        'wry': dict(smile=0.45, open=0.0, oh=0.0, brow=0.13, lid=0.15, worry=0.35, squint=0.2),   # "what can you do": brows up, a half smile
        'determined': dict(smile=0.15, open=0.0, oh=0.0, brow=0.12, lid=0.2, mad=0.75, squint=0.35),
        'sad': dict(smile=0.0, open=0.0, oh=0.0, brow=0.0, lid=0.35, frown=0.8, worry=0.9),
    }

    def __init__(self, sc):
        self.sc = sc; self._end = 0.0; self._ik_last = {}
        self._build()
        # the RESTING face is keyed on frame one. Unkeyed, every shape key and the mouth cavity sat at full value, and the
        # first expression() keyed that "current" state as its start: a shot whose first expression came late opened on
        # a wide dark mouth hole (11-12 judge, shot 3: "a large dark open-mouth slab ... the first thing seen").
        self._face(0.0, **self.EXPRESSIONS['neutral'])

    # ---------------------------------------------------------------- build
    def _build(self):
        src = open(os.path.join(HERE, 'base_build.py')).read().split('\n')
        keep = [l for i, l in enumerate(src, 1) if i not in (8, 9, 10, 11) and i < 197]
        ns = {'__name__': 'base_build'}
        before = set(bpy.data.objects)
        exec('\n'.join(keep), ns)
        parts = [o for o in ns['parts']]
        root = bpy.data.objects.get('DATA_ROOT')
        for o in parts: o.parent = None
        if root: bpy.data.objects.remove(root)
        mats = {m.name: m for m in bpy.data.materials}
        self.M = lambda n: mats[n]
        teal, ivory, black, eye, pupil = mats['Data / teal'], mats['Coat / warm ivory'], mats['Frames / charcoal'], mats['Eyes / ivory'], mats['Pupils / deep charcoal']
        P = {}
        for o in parts: P.setdefault(o.name.split('.')[0], []).append(o)
        # ---- limbs: the one-capsule sleeve and leg become two capsules with a joint
        for o in P['Sleeve'] + P['Leg']: bpy.data.objects.remove(o)
        self.J = {}            # joints in rig units
        for s, sg in (('L', -1), ('R', 1)):
            sh = Vector((sg * 0.37, 0.0, 2.42)); el = Vector((sg * 0.52, -0.01, 1.95)); wr = el + (el - sh) * 0.95   # collinear at rest: 0 deg
            hip = Vector((sg * 0.261, 0.007, 1.25)); kn = Vector((sg * 0.261, 0.007, 0.72)); an = Vector((sg * 0.261, 0.007, 0.26))
            self.J[s] = dict(sh=sh, el=el, wr=wr, hip=hip, kn=kn, an=an)
            P.setdefault('Upper arm', []).append(_capsule(f'Upper arm.{s}', sh, el, 0.214, ivory))
            P.setdefault('Forearm', []).append(_capsule(f'Forearm.{s}', el, wr, 0.205, ivory))
            P.setdefault('Thigh', []).append(_capsule(f'Thigh.{s}', hip, kn, 0.162, teal))
            P.setdefault('Shin', []).append(_capsule(f'Shin.{s}', kn, an, 0.150, teal))
        # ---- face: eye spheres sunk into the head, lids, pupils and glints on the sphere, the lip tube, a cavity
        for o in P['Eye white'] + P['Pupil'] + P['Eye glint'] + P['Eye glint small'] + P['Smile']: bpy.data.objects.remove(o)
        self.R_EYE = 0.30; self.EYE = {}
        for s, sg in (('L', -1), ('R', 1)):
            ex, ez = sg * 0.411, 3.73
            ys = head_surface_y(ex, ez); protrude = 0.07
            c = Vector((ex, ys - protrude + self.R_EYE, ez))
            self.EYE[s] = c
            ball = _cap(f'Eye ball.{s}', c, self.R_EYE, eye, lambda n: -n.y > math.cos(math.radians(EYE_CAP_DEG)))   # only the front dome: a whole sphere showed its white outside the lens in three-quarter view
            gaze = bpy.data.objects.new(f'Gaze.{s}', None); bpy.context.collection.objects.link(gaze); gaze.location = c
            bpy.context.view_layer.update()
            pup = _cap(f'Pupil.{s}', c, self.R_EYE + 0.005, pupil, lambda n: -n.y > math.cos(math.radians(31)))   # a cap ON the sphere: under a closed lid everywhere
            g1 = _sphere(f'Eye glint.{s}', c + (self.R_EYE + 0.004) * Vector((-0.17, -0.97, 0.18)).normalized(), 0.04, eye, (0.045, 0.012, 0.043))
            g2 = _sphere(f'Eye glint small.{s}', c + (self.R_EYE + 0.004) * Vector((0.17, -0.97, -0.12)).normalized(), 0.02, eye, (0.02, 0.009, 0.019))
            for o in (pup, g1, g2): o.parent = gaze; o.matrix_parent_inverse = gaze.matrix_world.inverted()
            gaze.rotation_euler = (0, 0, math.radians(-4 * sg))        # a slight convergence, like the base model's gaze
            up = _cap(f'Lid upper.{s}', c, self.R_EYE + 0.025, teal, lambda n: -n.y > math.cos(math.radians(88)) and n.z > -0.001)
            lo = _cap(f'Lid lower.{s}', c, self.R_EYE + 0.025, teal, lambda n: -n.y > math.cos(math.radians(88)) and n.z < 0.001)
            pu = bpy.data.objects.new(f'Lid pivot upper.{s}', None); pl = bpy.data.objects.new(f'Lid pivot lower.{s}', None)
            for e in (pu, pl): bpy.context.collection.objects.link(e); e.location = c
            bpy.context.view_layer.update()
            up.parent = pu; up.matrix_parent_inverse = pu.matrix_world.inverted()
            lo.parent = pl; lo.matrix_parent_inverse = pl.matrix_world.inverted()
            pu.rotation_euler = (math.radians(-100), 0, 0); pl.rotation_euler = (math.radians(100), 0, 0)
            self.EYE[s + 'gaze'] = gaze; self.EYE[s + 'up'] = pu; self.EYE[s + 'lo'] = pl
            P.setdefault('face', []).extend([ball, gaze, pu, pl])
        paths = _mouth_paths()
        LIP_R = 0.009                                        # a thin line, not a slab
        verts, faces = _tube(paths['rest'], r=LIP_R)
        me = bpy.data.meshes.new('Lips'); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
        # the lip is a slightly darker tint of his own skin, never dark brown: nothing in profile reads as facial hair
        lip_m = bpy.data.materials.new('Mouth / lip'); lip_m.use_nodes = True
        lb = lip_m.node_tree.nodes['Principled BSDF']; tb = teal.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value
        lb.inputs['Base Color'].default_value = (tb[0] * 0.55, tb[1] * 0.6, tb[2] * 0.6, 1); lb.inputs['Roughness'].default_value = 0.5
        lips = bpy.data.objects.new('Lips', me); bpy.context.collection.objects.link(lips); lips.data.materials.append(lip_m)
        for p in me.polygons: p.use_smooth = True
        lips.shape_key_add(name='Basis')
        for key in ('smile', 'open', 'oh', 'frown'):
            v2, _ = _tube(paths[key], r=LIP_R); sk = lips.shape_key_add(name=key)
            for i, v in enumerate(v2): sk.data[i].co = v
        cav_m = bpy.data.materials.new('Mouth / cavity'); cav_m.use_nodes = True
        b = cav_m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = (0.02, 0.005, 0.006, 1); b.inputs['Roughness'].default_value = 0.6
        cav = _sphere('Mouth cavity', (0, head_surface_y(0, 3.10) - 0.018, 3.10), 1.0, cav_m, (0.001, 0.001, 0.001))
        self.lips = lips; self.cavity = cav
        P.setdefault('face', []).extend([lips, cav])
        # ---- profile fix: ears swept back, temples on the head
        if PROFILE_FIX:
            for o in P['Ear']: o.rotation_euler.x = math.radians(-30)
        # ---- the armature
        arm_data = bpy.data.armatures.new('DataRig'); arm = bpy.data.objects.new('Data', arm_data)
        bpy.context.collection.objects.link(arm); bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        eb = arm_data.edit_bones
        def bone(name, head, tail, parent=None):
            b = eb.new(name); b.head = Vector(head); b.tail = Vector(tail); b.use_connect = False
            if parent: b.parent = eb[parent]
            return b
        bone('root', (0, 0, 1.25), (0, 0, 1.55))
        bone('spine', (0, 0, 1.55), (0, 0, 2.05), 'root'); bone('chest', (0, 0, 2.05), (0, 0, 2.55), 'spine')
        bone('neck', (0, 0, 2.55), (0, 0, 2.75), 'chest'); bone('head', (0, 0, 2.75), (0, 0, 3.6), 'neck')
        for s in 'LR':
            J = self.J[s]
            bone(f'clav.{s}', (J['sh'].x * 0.3, 0, 2.45), J['sh'], 'chest')
            bone(f'arm.{s}', J['sh'], J['el'], f'clav.{s}'); bone(f'fore.{s}', J['el'], J['wr'], f'arm.{s}')
            bone(f'hand.{s}', J['wr'], J['wr'] + Vector((0.08 * (1 if s == 'R' else -1), -0.04, -0.34)), f'fore.{s}')
            bone(f'leg.{s}', J['hip'], J['kn'], 'root'); bone(f'shin.{s}', J['kn'], J['an'], f'leg.{s}')
            bone(f'foot.{s}', J['an'], J['an'] + Vector((0, -0.36, -0.18)), f'shin.{s}')
        bpy.ops.object.mode_set(mode='OBJECT')
        self.arm = arm; self.pb = arm.pose.bones
        for pb in self.pb: pb.rotation_mode = 'XYZ'
        arm.scale = (SCALE, SCALE, SCALE)
        self.U = (self.J['L']['el'] - self.J['L']['sh']).length * SCALE
        self.Fo = (self.J['L']['wr'] - self.J['L']['el']).length * SCALE
        self.LEG = ((self.J['L']['kn'] - self.J['L']['hip']).length, (self.J['L']['an'] - self.J['L']['kn']).length)   # rig units
        self.height = 0.95
        # ---- attach: rigid parts to bones, the coat deforms over root/spine/chest
        def rigid(o, bname):
            b = arm_data.bones[bname]
            o.parent = arm; o.parent_type = 'BONE'; o.parent_bone = bname
            o.matrix_parent_inverse = (b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()
        head_parts = ['Head', 'Ear', 'Glasses frame', 'Glasses bridge', 'Temple', 'Brow', 'Nose', 'face']
        for key in head_parts:
            for o in P.get(key, []): rigid(o, 'head')
        for o in P['Neck']: rigid(o, 'neck')
        for key in ('Shirt opening', 'Tie knot', 'Tie blade', 'Lapel', 'Pocket', 'Pen', 'Coat button', 'Coat center seam'):
            for o in P.get(key, []): rigid(o, 'chest')
        for o in P['Upper arm']: rigid(o, 'arm.' + o.name[-1])
        for o in P['Forearm']: rigid(o, 'fore.' + o.name[-1])
        for o in P['Thigh']: rigid(o, 'leg.' + o.name[-1])
        for o in P['Shin']: rigid(o, 'shin.' + o.name[-1])
        for o in P['Mitten'] + P['Thumb']:
            rigid(o, 'hand.' + ('L' if o.matrix_world.translation.x < 0 else 'R'))
        for o in P['Shoe']:
            rigid(o, 'foot.' + ('L' if o.matrix_world.translation.x < 0 else 'R'))
        coat = P['Coat / continuous tapered body'][0]
        coat.parent = arm; coat.matrix_parent_inverse = Matrix.Identity(4)
        for name in ('root', 'spine', 'chest'): coat.vertex_groups.new(name=name)
        for v in coat.data.vertices:
            z = v.co.z * coat.scale.z + coat.location.z
            w = {'root': 0.0, 'spine': 0.0, 'chest': 0.0}
            if z < 1.45: w['root'] = 1.0
            elif z < 1.75: u = (z - 1.45) / 0.3; w['root'] = 1 - u; w['spine'] = u
            elif z < 2.0: w['spine'] = 1.0
            elif z < 2.3: u = (z - 2.0) / 0.3; w['spine'] = 1 - u; w['chest'] = u
            else: w['chest'] = 1.0
            for name, ww in w.items():
                if ww > 0: coat.vertex_groups[name].add([v.index], ww, 'REPLACE')
        md = coat.modifiers.new('Rig', 'ARMATURE'); md.object = arm
        while coat.modifiers[0] != md: bpy.ops.object.modifier_move_up({'object': coat}, modifier=md.name) if False else coat.modifiers.move(len(coat.modifiers) - 1, 0)
        self.parts = [o for o in bpy.data.objects if o not in before and o != arm]
        self.brows = P['Brow']
        self._brow_shapes()
        self.sc.frame_set(1)
        self._rest = {pb.name: pb.bone.matrix_local.copy() for pb in self.pb}

    # ---------------------------------------------------------------- basics
    def place(self, x, y, rot_deg=0.0):
        self.arm.location = (x, y, 0); self.arm.rotation_euler = (0, 0, math.radians(rot_deg)); bpy.context.view_layer.update()

    def pos(self):
        return Vector(self.arm.location)

    def forward(self, yaw=None):
        yaw = self.arm.rotation_euler.z if yaw is None else yaw
        return Vector((math.sin(yaw), -math.cos(yaw), 0))

    def _obj_loc(self, t):
        self.sc.frame_set(F(t)); return Vector(self.arm.location), self.arm.rotation_euler.z

    def _kobj(self, t, loc=None, rot=None):
        if loc is not None: self.arm.location = (loc[0], loc[1], loc[2] if len(loc) > 2 else self.arm.location.z); self.arm.keyframe_insert('location', frame=F(t))
        if rot is not None: self.arm.rotation_euler.z = rot; self.arm.keyframe_insert('rotation_euler', frame=F(t))
        self._end = max(self._end, t)

    def _k(self, bone, t, rot=None):
        pb = self.pb[bone]
        if rot is not None:
            pb.rotation_euler = tuple(math.radians(v) for v in rot); pb.keyframe_insert('rotation_euler', frame=F(t))
        self._end = max(self._end, t)

    def _set_bone(self, pb, head_world, R_world, t):
        """pose a bone so its head sits at head_world with world rotation R_world (3x3, bone Y = direction); key it"""
        M = self.arm.matrix_world
        Ra = M.to_3x3().normalized().inverted() @ R_world
        Ma = Ra.to_4x4(); Ma.translation = M.inverted() @ head_world
        pb.matrix = Ma; bpy.context.view_layer.update()
        pb.keyframe_insert('rotation_euler', frame=F(t))

    @staticmethod
    def _frame(dirn, up_hint=Vector((0, 0, 1))):
        y = dirn.normalized(); x = y.cross(up_hint)
        if x.length < 1e-4: x = y.cross(Vector((0, 1, 0)))
        x.normalize(); z = x.cross(y)
        return Matrix((x, y, z)).transposed()

    def _two_bone(self, A, B, target, pole, t, La, Lb, straight_at=0.99):
        """2-bone IK on pose bones A (upper) and B (lower) toward a world target; pole = world direction the joint
        bends toward. At >= straight_at of full reach the chain is EXACTLY straight."""
        self.sc.frame_set(F(t))
        A.rotation_euler = (0, 0, 0); B.rotation_euler = (0, 0, 0); bpy.context.view_layer.update()
        M = self.arm.matrix_world
        head = M @ A.head; tgt = Vector(target)
        d = tgt - head; D = d.length; reach = La + Lb
        if D >= reach * straight_at: tgt = head + d.normalized() * reach * 0.999; D = reach * 0.999; ang = 0.0; clamped = D < d.length - 1e-4
        else:
            cosA = (La * La + D * D - Lb * Lb) / (2 * La * D); ang = math.acos(max(-1, min(1, cosA))); clamped = False
        n = d.cross(pole)
        f_ = F(t); last = self._ik_last.get(A.name)
        near = last is not None and abs(f_ - last[0]) <= 2
        if n.length < 0.15 * d.length * pole.length and near:   # the bend plane is degenerate (target in line with the pole):
            n = last[1].copy()                                   # keep last frame's, never let the elbow flip sides
        if n.length < 1e-6: n = Vector((1, 0, 0))
        n.normalize()
        if near and n.dot(last[1]) < 0 and d.cross(pole).length < 0.35 * d.length * pole.length:
            n = -n                                               # a sign flip near the degenerate pose: hold the side
        upper = Matrix.Rotation(ang, 4, n) @ d.normalized()
        joint = head + upper * La; lower = (tgt - joint).normalized()
        # THE ELBOW IS A HINGE: both bones take the bend plane's normal as their x, so the forearm only ever turns ABOUT
        # the elbow and never spins about its own length (measured 2026-11-13: the forearm rolled ~300 deg as he let go
        # of the lever, the mitten spinning, because each bone took its roll from world up on its own)
        xh = upper.cross(Vector((0, 0, 1)))
        sgn = last[2] if near and len(last) > 2 else (1.0 if xh.length < 1e-4 or n.dot(xh) >= 0 else -1.0)
        x = n * sgn
        RA = Matrix((x, upper.normalized(), x.cross(upper.normalized()))).transposed()
        RB = Matrix((x, lower, x.cross(lower))).transposed()
        self._ik_last[A.name] = (f_, n.copy(), sgn)
        self._set_bone(A, head, RA, t); self._set_bone(B, joint, RB, t)
        return clamped

    def _frame_cont(self, key, dirn, f_):
        """_frame with a CONTINUOUS roll (caaleb 2026-11-13, "why does data tweak out"): _frame takes the roll from
        world up, which is undefined for an arm that hangs or reaches straight up, so a lever pull down to his side
        spun the forearm up to 50 deg in one frame. Near vertical, the roll follows the previous frame's instead."""
        y = dirn.normalized(); xh = y.cross(Vector((0, 0, 1)))
        prev = self._ik_last.get('roll ' + key)
        if prev is not None and abs(f_ - prev[0]) <= 2:
            xc = prev[1] - y * prev[1].dot(y)
            if xc.length > 1e-4:
                xc.normalize()
                w = min(1.0, max(0.0, (xh.length - 0.35) / 0.4))          # 0 when within ~20 deg of vertical
                xh = xh.normalized() if xh.length > 1e-4 else xc
                if xh.dot(xc) < 0 and w < 1.0: xh = -xh
                x = (xc * (1 - w) + xh * w)
                x = x.normalized() if x.length > 1e-4 else xc
            else:
                x = xh.normalized() if xh.length > 1e-4 else y.cross(Vector((0, 1, 0))).normalized()
        else:
            x = xh.normalized() if xh.length > 1e-4 else y.cross(Vector((0, 1, 0))).normalized()
        self._ik_last['roll ' + key] = (f_, x.copy())
        z = x.cross(y)
        return Matrix((x, y, z)).transposed()

    def _arm_ik(self, s, target, t, elbow_out=0.5):
        A, Fo = self.pb[f'arm.{s}'], self.pb[f'fore.{s}']
        fw = self.forward(); side = Vector((-1 if s == 'L' else 1, 0, 0)); side = (self.arm.matrix_world.to_3x3() @ side).normalized()
        pole = (fw + side * elbow_out)
        if pole.length < 1e-4: pole = fw
        over = self._two_bone(A, Fo, target, -pole, t, self.U, self.Fo)
        if over: print(f'hold: {s} hand out of reach, clamped')
        self._k(f'hand.{s}', t, rot=(0, 0, 0))

    def _leg_ik(self, s, target, t, pitch=0.0):
        """pitch: degrees, toe UP positive, about the body's right axis (heel strike / toe-off roll)"""
        L, Sh = self.pb[f'leg.{s}'], self.pb[f'shin.{s}']
        knee_dir = self.forward()                               # the knee bends FORWARD: _two_bone bends toward `pole` (the arm passes -pole so the ELBOW goes back; the leg had copied that and walked on bird knees, measured knee_fwd < 0 every frame)
        over = self._two_bone(L, Sh, target, knee_dir, t, self.LEG[0] * SCALE, self.LEG[1] * SCALE, straight_at=0.995)
        # the foot stays LEVEL in the world whatever the shin does (else the shoe pivots about the ankle: a slide)
        fb = self.pb[f'foot.{s}']; M = self.arm.matrix_world
        R0 = M.to_3x3().normalized() @ self._rest[f'foot.{s}'].to_3x3()
        if pitch:
            yaw = self.arm.rotation_euler.z; right = Vector((math.cos(yaw), math.sin(yaw), 0))
            R0 = Matrix.Rotation(math.radians(-pitch), 3, right) @ R0
        self._set_bone(fb, M @ Sh.tail, R0, t)
        return over

    # the shoe, in metres from the ankle: heel contact behind, ball of the foot ahead, both on the sole
    HEEL = (-0.033, -0.052); BALL = (0.090, -0.052)   # the ends of the flat sole: the shoe is rigid, so it rolls on its edges

    def _foot_ankle(self, ground_pt_ankle, fw, pitch):
        """ankle position for a foot rolled `pitch` degrees about its heel (toe up, pitch>0) or its ball (heel up,
        pitch<0), given where the ankle would sit if the foot were flat. Returns the rolled ankle."""
        if abs(pitch) < 1e-6: return ground_pt_ankle
        piv = self.HEEL if pitch > 0 else self.BALL
        P = ground_pt_ankle + fw * piv[0] + Vector((0, 0, piv[1]))
        axis = Vector((fw.y, -fw.x, 0)).normalized()           # right of travel: +angle about it lifts the toe
        R = Matrix.Rotation(math.radians(pitch), 3, axis)
        return P + R @ (ground_pt_ankle - P)

    def hold(self, pL, pR, t0, t1=None, elbow_out=0.6):
        self._arm_ik('L', Vector(pL), t0, elbow_out); self._arm_ik('R', Vector(pR), t0, elbow_out)
        if t1 is not None:
            self._arm_ik('L', Vector(pL), t1, elbow_out); self._arm_ik('R', Vector(pR), t1, elbow_out)

    RELAXED = {'arm.L': (-4, 0, 5), 'arm.R': (-4, 0, -5), 'fore.L': (-22, 0, 0), 'fore.R': (-22, 0, 0), 'hand.L': (0, 0, 0), 'hand.R': (0, 0, 0)}

    def _pose_now(self, bone, t):
        self.sc.frame_set(F(t)); return tuple(math.degrees(v) for v in self.pb[bone].rotation_euler)

    def release(self, t, dur=0.45):
        """let go: the arms hold where they are at t, then fall to a RELAXED hang (elbows soft, never dead straight)
        over `dur` with a little overshoot, instead of snapping to the rest pose in three frames"""
        bones = list(self.RELAXED)
        now = {b: self._pose_now(b, t) for b in bones}
        for b in bones: self._k(b, t, rot=now[b])
        for b in bones:
            r = self.RELAXED[b]
            over = tuple(v * 1.18 for v in r) if b.startswith('fore') else r
            self._k(b, t + dur * 0.7, rot=over); self._k(b, t + dur, rot=r)

    def idle(self, t0, t1, seed=3):
        """standing life: breath in the chest, a slow weight shift in the hips, a little sway in the relaxed arms"""
        import random
        rnd = random.Random(seed); ph = rnd.random() * 6.28
        for f in range(F(t0), F(t1) + 1, 3):
            t = (f - 1) / FPS; u = t - t0; w = min(1.0, u / 0.4)
            br = math.sin(2 * math.pi * u / 3.0 + ph)
            self._k('chest', t, rot=(-1.4 * br * w, 0, 0)); self._k('spine', t, rot=(0.6 * br * w, 0, 1.2 * math.sin(2 * math.pi * u / 4.6 + ph) * w))
            self._k('neck', t, rot=(0.8 * br * w, 0, 0))

    # ---------------------------------------------------------------- head and face
    def look_at(self, target, t, max_yaw=40, max_pitch=22, blend=0.3):
        hb = self.pb['head']
        if not self._has_keys(self.arm, 'pose.bones["head"].rotation_euler'):      # the first look: hold the rest pose until it starts
            self.sc.frame_set(F(max(0.0, t - blend))); hb.rotation_euler = (0, 0, 0); hb.keyframe_insert('rotation_euler', frame=F(max(0.0, t - blend)))
        self.sc.frame_set(F(t)); M = self.arm.matrix_world; head = M @ hb.head
        d = Vector(target) - head - Vector((0, 0, 0.12))
        # in the ARMATURE's own frame (rest face is -Y): the body's yaw is already in M, so it must not be added again.
        # (it was: every look_at after a turn twisted the head by the body's yaw, so at 180 he faced away with his head screwed round)
        dl = M.to_3x3().normalized().inverted() @ d
        yaw = math.degrees(math.atan2(dl.y, dl.x) + math.pi / 2)
        yaw = (yaw + 180) % 360 - 180; yaw = max(-max_yaw, min(max_yaw, yaw))
        pitch = math.degrees(math.atan2(dl.z, Vector((dl.x, dl.y, 0)).length)); pitch = max(-max_pitch, min(max_pitch, pitch))
        # bone Y is up; yaw about the armature's Z, pitch tilts the top of the head toward the target
        Rl = Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(-pitch * 0.6), 3, 'X') @ self._rest['head'].to_3x3()
        self._set_bone(hb, head, M.to_3x3().normalized() @ Rl, t)

    def _has_keys(self, obj, data_path):
        ad = obj.animation_data
        if not ad or not ad.action: return False
        return any(fc.data_path == data_path for fc in _fcurves(ad.action))

    def _key_val(self, obj, path, t, value, index=-1):
        if index >= 0: getattr(obj, path)[index] = value
        else: setattr(obj, path, value)
        obj.keyframe_insert(path, frame=F(t), index=index)

    OH_MAX = 0.0    # caaleb 11-04 and 11-12 ("data's mouth looked weird"): never an open 'o' / mouth hole, in ANY shot.
                    # Shock is the brows, the eyes and the body. Held here, where every expression is keyed, so no shot can ask for one.

    def _brow_shapes(self):
        """Two shape keys on each brow (caaleb 2026-11-13: "we need to do a lot of work on how he express"): a brow that
        only slides up and down cannot act. 'worry' lifts the INNER end (sad, pleading, worried), 'mad' drops it
        (determined, angry, focused). The outer end stays put, so it is a tilt, and the brow stays on the head."""
        self.sc.frame_set(1); bpy.context.view_layer.update()
        for b in self.brows:
            if b.type != 'CURVE' or b.data.shape_keys: continue
            M = b.matrix_world; Mi = M.inverted().to_3x3()
            pts = [p for sp in b.data.splines for p in sp.points]
            wx = [(M @ Vector(p.co[:3])).x for p in pts]
            head_x = (self.arm.matrix_world @ self.pb['head'].head).x
            inner = min(range(len(pts)), key=lambda i: abs(wx[i] - head_x))
            outer = max(range(len(pts)), key=lambda i: abs(wx[i] - head_x))
            span = abs(wx[outer] - wx[inner]) or 1.0
            up = (Mi @ Vector((0, 0, 1)))
            b.shape_key_add(name='Basis')
            for name, sgn in (('worry', 1.0), ('mad', -1.0)):
                k = b.shape_key_add(name=name)
                for i, p in enumerate(pts):
                    w = max(0.0, 1.0 - abs(wx[i] - wx[inner]) / span) ** 1.3
                    k.data[i].co = Vector(p.co[:3]) + up * (sgn * 0.42 * span * w)
                k.slider_min, k.slider_max = 0.0, 1.0

    def _brow_key(self, name):
        sk = self.brows[0].data.shape_keys
        return sk.key_blocks[name].value if sk and name in sk.key_blocks else 0.0

    def _face(self, t, smile=0.0, open=0.0, oh=0.0, brow=0.0, lid=0.0, frown=0.0, worry=0.0, mad=0.0, squint=0.0):
        oh = min(oh, self.OH_MAX)
        kb = self.lips.data.shape_keys.key_blocks
        for name, v in (('smile', smile), ('open', open), ('oh', oh), ('frown', frown)):
            kb[name].value = v; kb[name].keyframe_insert('value', frame=F(t))
        sc = Vector((0.26, 0.06, 0.16)) * open + Vector((0.12, 0.06, 0.12)) * oh
        self.cavity.scale = tuple(max(0.001, v) for v in sc); self.cavity.keyframe_insert('scale', frame=F(t))
        for b in self.brows:                                   # the brow rides UP the head surface, so it goes back as it rises
            b.location.z = 0.305 + brow * 0.5; b.location.y = brow * 0.45; b.keyframe_insert('location', frame=F(t))
        for s in 'LR':
            self.EYE[s + 'up'].rotation_euler.x = math.radians(-100 + 100 * lid); self.EYE[s + 'up'].keyframe_insert('rotation_euler', frame=F(t), index=0)
            self.EYE[s + 'lo'].rotation_euler.x = math.radians(100 - 100 * min(0.95, lid * 0.6 + squint * 0.8)); self.EYE[s + 'lo'].keyframe_insert('rotation_euler', frame=F(t), index=0)
        for b in self.brows:
            sk = b.data.shape_keys
            if not sk: continue
            for name, v in (('worry', worry), ('mad', mad)):
                sk.key_blocks[name].value = v; sk.key_blocks[name].keyframe_insert('value', frame=F(t))
        self._squint = squint
        self._end = max(self._end, t)

    def expression(self, name, t0, t1=None, blend=0.22, cross='other'):
        e = self.EXPRESSIONS[name]
        self.sc.frame_set(F(max(0, t0 - blend)))
        cur = self._face_state()
        self._face(t0 - blend, **cur); self._face(t0, **e)
        if t1 is not None:
            self._face(t1, **e); self._face(t1 + blend, **self.EXPRESSIONS['neutral'])

    def _face_state(self):
        kb = self.lips.data.shape_keys.key_blocks
        lid = (math.degrees(self.EYE['Lup'].rotation_euler.x) + 100) / 100
        lo = (100 - math.degrees(self.EYE['Llo'].rotation_euler.x)) / 100      # = lid*0.6 + squint*0.8
        return dict(smile=kb['smile'].value, open=kb['open'].value, oh=kb['oh'].value, frown=kb['frown'].value, brow=(self.brows[0].location.z - 0.305) * 2,
                    lid=lid, worry=self._brow_key('worry'), mad=self._brow_key('mad'), squint=max(0.0, (lo - lid * 0.6) / 0.8))

    def say(self, keys, key='open'):
        for t, v in keys: self._face(t, **{key: v})

    def blink(self, t, dur=0.2):
        for s in 'LR':
            up, lo = self.EYE[s + 'up'], self.EYE[s + 'lo']
            self.sc.frame_set(F(t - dur / 2)); u0, l0 = up.rotation_euler.x, lo.rotation_euler.x         # the lids as they were
            for tt, (uu, ll) in ((t - dur / 2, (u0, l0)), (t, (math.radians(25), math.radians(-10))), (t + dur / 2, (u0, l0))):   # the lids overlap at the centre: shut
                up.rotation_euler.x = uu; lo.rotation_euler.x = ll
                up.keyframe_insert('rotation_euler', frame=F(tt), index=0); lo.keyframe_insert('rotation_euler', frame=F(tt), index=0)
        self._end = max(self._end, t + dur)

    def gaze(self, t, dx, dz, blend=0.15):
        """the pupils turn dx degrees (positive = his right) and dz up, on their spheres"""
        for s in 'LR':
            g = self.EYE[s + 'gaze']
            if not self._has_keys(g, 'rotation_euler'): g.keyframe_insert('rotation_euler', frame=F(max(0.0, t - blend)))   # hold the rest gaze until now
            g.rotation_euler = (math.radians(-dz), 0, math.radians(dx)); g.keyframe_insert('rotation_euler', frame=F(t))   # +X turns the -Y pupil DOWN, so up is -dz (it was +dz: 'look down' rolled his eyes up out of his glasses)
        self._end = max(self._end, t)

    def breathe(self, t0, t1, amp=1.5, period=3.2):
        f0, f1 = F(t0), F(t1)
        for f in range(f0, f1 + 1, 3):
            t = (f - 1) / FPS; a = amp * math.sin(2 * math.pi * (t - t0) / period)
            self._k('chest', t, rot=(-a * 0.6, 0, 0)); self._k('spine', t, rot=(a * 0.3, 0, 0))

    # ---------------------------------------------------------------- locomotion
    def turn_to(self, rot_deg, t0, t1, lift=0.022):
        """turn on the spot by STEPPING: each foot holds its spot, lifts, and is put down under the new facing (the
        farther foot first, the other overlapping it), the body easing round and dipping a little as it shifts"""
        p, y0 = self._obj_loc(t0); y1 = math.radians(rot_deg)
        while y1 - y0 > math.pi: y1 -= 2 * math.pi
        while y1 - y0 < -math.pi: y1 += 2 * math.pi
        z0 = p.z
        self.sc.frame_set(F(t0)); M = self.arm.matrix_world
        start = {s: M @ self.pb[f'shin.{s}'].tail for s in 'LR'}
        def under(yaw, s):
            c, sn = math.cos(yaw), math.sin(yaw); j = self.J[s]['an'] * SCALE
            return Vector((p.x + c * j.x - sn * j.y, p.y + sn * j.x + c * j.y, j.z))
        end = {s: under(y1, s) for s in 'LR'}
        first = max('LR', key=lambda s: (start[s] - end[s]).length)
        win = {first: (0.0, 0.6), ('R' if first == 'L' else 'L'): (0.4, 1.0)}
        legL = sum(self.LEG) * SCALE; hipz = self.J['L']['hip'].z * SCALE
        for f in range(F(t0), F(t1) + 1):
            t = (f - 1) / FPS; u = (t - t0) / max(1e-6, t1 - t0)
            yaw = y0 + (y1 - y0) * ease(u)
            feet = {}
            for s in 'LR':
                a, b = win[s]; v = min(1.0, max(0.0, (u - a) / (b - a)))
                pos = start[s].lerp(end[s], ease(v)); pos.z = start[s].z + (end[s].z - start[s].z) * v + lift * math.sin(math.pi * v)
                feet[s] = pos
            loc = Vector((p.x, p.y, z0 + (SOFT_Z - z0) * ease(u) - 0.006 * math.sin(math.pi * u)))
            c, sn = math.cos(yaw), math.sin(yaw)
            for s in 'LR':
                h = self.J[s]['hip'] * SCALE; hip = Vector((p.x + c * h.x - sn * h.y, p.y + sn * h.x + c * h.y, loc.z + hipz))
                horiz = (Vector((feet[s].x, feet[s].y, 0)) - Vector((hip.x, hip.y, 0))).length
                need = feet[s].z + math.sqrt(max(0.0, (LEG_USE * legL) ** 2 - horiz ** 2)) - hipz
                if need < loc.z: loc.z = need
            self.arm.location = loc; self.arm.rotation_euler.z = yaw
            self.arm.keyframe_insert('location', frame=f); self.arm.keyframe_insert('rotation_euler', frame=f)
            self._end = max(self._end, t)
            bpy.context.view_layer.update()
            for s in 'LR': self._leg_ik(s, feet[s], t)

    def _plant_feet_here(self, t, lift=(0.0, 0.0)):
        """both feet under the body at the current pose (standing)"""
        self.sc.frame_set(F(t)); M = self.arm.matrix_world
        for s, lf in (('L', lift[0]), ('R', lift[1])):
            an = M @ self.J[s]['an']; an.z = self.J[s]['an'].z * SCALE + lf
            self._leg_ik(s, an, t)

    def walk_to(self, target, t0, t1, step=None, bob=0.005, lift=0.015, lean=5.0, stance=0.6, ramp=0.35, pushing=False):
        """procedural walk for a short-legged character: SHORT QUICK steps (no lunge, no crouch), a 60% stance with
        heel strike and toe-off roll, the hip high at mid-stance, the pelvis turning with the leg and the shoulders
        held square against it (square when pushing), a lean into the travel, and an eased start and stop."""
        p0, yaw0 = self._obj_loc(t0)
        tgt = Vector((target[0], target[1], 0)); d = tgt - p0; dist = d.length
        if dist < 1e-4: return t1
        dirn = d.normalized(); yaw = math.atan2(dirn.x, -dirn.y)
        self._kobj(t0, loc=p0, rot=yaw0)
        legL = sum(self.LEG) * SCALE
        L = step if step else 0.75 * legL                   # metres per step: 0.62 leg length with a 3 cm lift read as a high-knee scurry; 0.75 with 1.5 cm is a walk
        T = t1 - t0; ra = min(ramp, T / 3)
        vmax = dist / (T - ra)                              # trapezoid speed: ramps of `ra` at both ends
        def s_of(t):
            u = t - t0
            if u <= 0: return 0.0
            if u < ra: return vmax * u * u / (2 * ra)
            if u < T - ra: return vmax * (ra / 2 + (u - ra))
            if u < T: w = T - u; return dist - vmax * w * w / (2 * ra)
            return dist
        right = Vector((math.cos(yaw), math.sin(yaw), 0)); hipz = self.J['L']['hip'].z * SCALE
        anz = self.J['L']['an'].z * SCALE
        self.walk_slide = []; self.walk_drop = 0.0
        # the gait starts at L's mid-stance with R passing it (feet side by side at rest) and ends in double support:
        # dist = (k + 0.5) steps, so the last foot lands as the body stops
        k = max(1, round(dist / L - 0.5)); L = dist / (k + 0.5)
        def planted(o, jj):
            return p0 + dirn * ((2 * jj - o) * L)
        for f in range(F(t0), F(t1) + 1):
            t = (f - 1) / FPS; sdist = s_of(t); ph = sdist / L + stance
            yaw_now = yaw0 + (yaw - yaw0) * ease((t - t0) / 0.2) if t - t0 < 0.2 else yaw
            loc = p0 + dirn * sdist
            moving = 0.0 if sdist >= dist - 1e-4 or sdist <= 1e-4 else min(1.0, (t - t0) / ra, max(0.0, (t1 - t) / ra))
            started = min(1.0, sdist / (0.25 * L))
            loc.z = -bob * moving * (1 - abs(math.sin(math.pi * (ph - (stance - 0.5)))))
            feet = {}; sway = 0.0
            for s, o in (('L', 0.0), ('R', 1.0)):
                php = ph + o; j = math.floor(php / 2); psi = php / 2 - j
                lat = right * self.J[s]['hip'].x * SCALE
                if psi < stance:
                    base = planted(o, j) + lat; fz = 0.0; u = psi / stance
                    # heel strike settles flat by 15% of stance; heel peels off from 70%
                    pitch = 12 * (1 - ease(u / 0.15)) if u < 0.15 else (-16 * ease((u - 0.7) / 0.3) if u > 0.7 else 0.0)
                    if psi < 0.5: sway += (1 if s == 'R' else -1)
                else:
                    u = (psi - stance) / (1 - stance); a, b = planted(o, j) + lat, planted(o, j + 1) + lat
                    travel = (b - a).length > 1e-3
                    base = a.lerp(b, ease(u)); fz = lift * started * math.sin(math.pi * u) * (1 if travel else 0)
                    pitch = (-16 * (1 - ease(u / 0.5)) + 12 * ease((u - 0.5) / 0.5)) if travel else 0.0
                pitch *= moving if moving > 0 else 0.0
                ankle = self._foot_ankle(Vector((base.x, base.y, anz + fz)), dirn, pitch)
                feet[s] = (ankle, psi < stance, base, pitch)
            # the hip drops only as much as a reaching leg truly needs (short steps: rarely)
            for s in 'LR':
                lat = right * self.J[s]['hip'].x * SCALE
                hip = loc + lat + Vector((0, 0, hipz)); ank = feet[s][0]
                horiz = (Vector((ank.x, ank.y, 0)) - Vector((hip.x, hip.y, 0))).length
                need = ank.z + math.sqrt(max(0.0, (LEG_USE * legL) ** 2 - horiz ** 2)) - hipz
                if need < loc.z: self.walk_drop = max(self.walk_drop, loc.z - need); loc.z = need
            cyc = math.cos(math.pi * ph)                    # +1 at the left heel strike: the left leg is forward
            self.arm.location = loc; self.arm.rotation_euler.z = yaw_now
            self.arm.keyframe_insert('location', frame=f); self.arm.keyframe_insert('rotation_euler', frame=f)
            # pelvis turns with the forward leg and rolls toward the swing side; spine and chest undo the turn so the
            # shoulders stay square (they hold the cart); the lean rises with the speed
            pel = 6.0 * cyc * moving; roll = 2.5 * math.sin(math.pi * ph) * moving
            lean_now = lean * moving
            self._k('root', t, rot=(0, pel, roll))
            sq = 1.0 if pushing else 0.7
            self._k('spine', t, rot=(lean_now * 0.6, -pel * 0.5 * sq, -roll * 0.6))
            self._k('chest', t, rot=(lean_now * 0.4, -pel * 0.5 * sq, -roll * 0.4))
            bpy.context.view_layer.update()
            for s in 'LR':
                ankle, st, base, pitch = feet[s]
                self._leg_ik(s, ankle, t, pitch)
                self.walk_slide.append((f, s, st, tuple(base)))
            # arms swing opposite the legs (a grip keys them afterwards when pushing); the head lags the bob
            a = 16 * cyc * moving
            self._k('arm.L', t, rot=(a, 0, 0)); self._k('arm.R', t, rot=(-a, 0, 0))   # +X swings an arm BACK: the arm opposite the forward leg leads
            self._k('fore.L', t, rot=(-14, 0, 0)); self._k('fore.R', t, rot=(-14, 0, 0))
            self._k('neck', t, rot=(-lean_now * 0.7 + 1.6 * moving * math.cos(2 * math.pi * (ph - (stance - 0.5))), 0, 0))
        self._end = max(self._end, t1)
        return t1

    def foot_slide(self):
        """max and mean planted-foot movement per frame in mm (stance frames only), from the last walk_to"""
        import collections
        last = {}; mv = []
        for f, s, stance, foot in self.walk_slide:
            if stance and s in last and last[s][0] == f - 1 and last[s][2]: mv.append((Vector(foot) - Vector(last[s][1])).length * 1000)
            last[s] = (f, foot, stance)
        return (round(max(mv), 2), round(sum(mv) / len(mv), 2)) if mv else (0, 0)

    # ---------------------------------------------------------------- acts
    def act(self, name, t0, dur=0.3, hold=0.5, side='R'):
        M = self.arm.matrix_world; fw = self.forward(); right = Vector((math.cos(self.arm.rotation_euler.z), math.sin(self.arm.rotation_euler.z), 0))
        sh = {s: M @ self.J[s]['sh'] for s in 'LR'}
        t1, t2 = t0 + dur, t0 + dur + hold; t3 = t2 + dur
        if name in ('shrug', 'whoa'):
            # caaleb 2026-11-12, of a shrug that held the hands up by the shoulders: "inverted ... a normal person
            # would ... their arms would be bent downwards at a 45-ish degree angle ... hands pointed outwards".
            # FK SOLVED to directions (tools/data3d/pose_dirs in the commit): upper arm down and a little out, forearm
            # out to the side, a little forward, 45 degrees BELOW horizontal; palms up for a shrug, open toward the
            # lens for a whoa. FK, not IK: IK Euler triples like (66, -103, -52) flail on the way back to the hang.
            for s, sg in (('L', -1), ('R', 1)):
                # 11-12 judge: the first shrug (forearms out sideways) read at phone size as "arms held straight out,
                # palms down, a T-pose spread". A shrug tucks the elbows and brings the forearms FORWARD and out.
                if name == 'shrug': arm = (-4, 0, -sg * 20); fore = (-18, 0, -sg * 48); hand = (-10, sg * -95, 0)
                else:               arm = (-16, 0, -sg * 18); fore = (-20, 0, -sg * 40); hand = (-15, sg * -20, -sg * 25)
                for bn in (f'arm.{s}', f'fore.{s}', f'hand.{s}'): self._k(bn, t0, rot=self._pose_now(bn, t0))   # from the pose he is IN
                self._k(f'arm.{s}', t1, rot=arm); self._k(f'fore.{s}', t1, rot=fore); self._k(f'hand.{s}', t1, rot=hand)
                self._k(f'arm.{s}', t2, rot=(arm[0] - 2, 0, arm[2] * 1.15)); self._k(f'fore.{s}', t2, rot=(fore[0] - 3, 0, fore[2] * 1.1)); self._k(f'hand.{s}', t2, rot=hand)
                for bn in (f'arm.{s}', f'fore.{s}', f'hand.{s}'): self._k(bn, t3, rot=self.RELAXED[bn])
                lift = -30 if name == 'shrug' else -6
                self._k(f'clav.{s}', t0, rot=(0, 0, 0)); self._k(f'clav.{s}', t1, rot=(0, 0, sg * lift)); self._k(f'clav.{s}', t2, rot=(0, 0, sg * lift)); self._k(f'clav.{s}', t3, rot=(0, 0, 0))
            self.expression('wry' if name == 'shrug' else 'surprised', t0, t2)
            if name == 'shrug':      # the head goes with it: tipped to one side and a little down
                self._k('neck', t0, rot=self._pose_now('neck', t0)); self._k('neck', t1, rot=(6, 9, 0)); self._k('neck', t2, rot=(6, 9, 0)); self._k('neck', t3, rot=(0, 0, 0))
        elif name == 'wave':
            s = side; sg = 1 if s == 'R' else -1
            # 11-12 judge: a wave at shoulder height "doesn't read". The hand goes up BESIDE THE HEAD, palm to the lens,
            # the elbow still bent, and it swings wide enough to see on a phone.
            up = sh[s] + right * sg * 0.15 + fw * 0.05 + Vector((0, 0, 0.25))
            self._arm_ik(s, sh[s] + right * sg * 0.04 + Vector((0, 0, -0.17)), t0, 0.3)
            self._arm_ik(s, up, t1, 1.2)
            n = max(2, int(hold / 0.3)); self._k(f'hand.{s}', t1, rot=(0, 0, 0))
            for i in range(n):
                tt = t1 + (i + 0.5) * hold / n
                self._arm_ik(s, up + right * sg * (0.05 if i % 2 else -0.05), tt, 1.2); self._k(f'hand.{s}', tt, rot=(0, 0, sg * (40 if i % 2 else -40)))
            self._arm_ik(s, up, t2, 1.2); self._k(f'hand.{s}', t2, rot=(0, 0, 0))
            self._arm_ik(s, sh[s] + right * sg * 0.04 + Vector((0, 0, -0.17)), t3, 0.3)
            self.expression('happy', t0, t2)
        elif name == 'thumbs_up':
            s = side; sg = 1 if s == 'R' else -1
            p = sh[s] + fw * 0.17 + right * sg * 0.02 + Vector((0, 0, -0.02))
            self._arm_ik(s, sh[s] + right * sg * 0.04 + Vector((0, 0, -0.17)), t0, 0.3); self._k(f'hand.{s}', t0, rot=(0, 0, 0))
            self._arm_ik(s, p, t1, 0.4); self._k(f'hand.{s}', t1, rot=(-85, 0, sg * 15))     # the fist turns so the thumb points UP
            self._arm_ik(s, p, t2, 0.4); self._k(f'hand.{s}', t2, rot=(-85, 0, sg * 15))
            self._arm_ik(s, sh[s] + right * sg * 0.04 + Vector((0, 0, -0.17)), t3, 0.3); self._k(f'hand.{s}', t3, rot=(0, 0, 0))
            self.expression('happy', t0, t2)
        else:
            raise KeyError(name)
        self._end = max(self._end, t3)
        return t3

    # ---------------------------------------------------------------- end
    def finish(self):
        n = F(self._end)
        self.sc.frame_start, self.sc.frame_end = 1, max(2, n)
        owners = [self.arm, self.lips, self.cavity, self.lips.data.shape_keys] + list(self.brows) + [self.EYE[k] for k in self.EYE if k[-2:] in ('up', 'lo') or k.endswith('gaze')]
        for o in owners:
            ad = getattr(o, 'animation_data', None)
            if ad and ad.action:
                for fc in _fcurves(ad.action):
                    for kp in fc.keyframe_points: kp.interpolation = 'BEZIER'; kp.easing = 'AUTO'
        if SMOOTH: self.smooth(n)
        self.sc.frame_set(1)
        return n

    def smooth(self, n):
        """THE TWITCH FILTER (caaleb 2026-11-13, of the banana short: "why does data tweak out"). Measured with
        store/twitch.py: arms whipping 26-30 deg in ONE frame (900 deg/s) where a grip key met a sparse pose key, the
        torso stopping dead from 5.6 deg/frame to 0, and the smile dropping 0.6 -> 0.2 between two frames. Every body
        channel and face control is baked per frame and low-passed (a Gaussian, wider on the torso and head than on
        the hands, angle jumps unwrapped first), so every move eases in and out the way a person's does. Blinks (the
        lids) keep their speed. The staging, anatomy and clipping checks run after this, on what is rendered."""
        if n < 4: return
        body = self.arm.animation_data.action if self.arm.animation_data else None
        jobs = []
        if body:
            for fc in _fcurves(body):
                dp = fc.data_path
                if not dp.startswith('pose.bones['): continue
                bone = dp.split('"')[1]
                sig = SMOOTH_TORSO if bone.startswith(('head', 'neck', 'spine', 'chest', 'hips', 'root', 'clav')) else SMOOTH_LIMB
                jobs.append((fc, sig, 'rotation' in dp))
        sk = self.lips.data.shape_keys
        if sk.animation_data and sk.animation_data.action:
            jobs += [(fc, SMOOTH_FACE, False) for fc in _fcurves(sk.animation_data.action)]
        for b in self.brows:
            k = b.data.shape_keys if b.type == 'CURVE' else None
            if k and k.animation_data and k.animation_data.action:
                jobs += [(fc, SMOOTH_FACE, False) for fc in _fcurves(k.animation_data.action)]
        for o in [self.cavity] + list(self.brows):
            if o.animation_data and o.animation_data.action:
                jobs += [(fc, SMOOTH_FACE, False) for fc in _fcurves(o.animation_data.action)]
        bones = {}
        for fc, sig, is_angle in jobs:
            if is_angle and fc.data_path.endswith('rotation_euler'):
                bones.setdefault(fc.data_path.split('"')[1], (sig, {}))[1][fc.array_index] = fc
        for bname, (sig, fcs) in bones.items():           # rotations are smoothed as ROTATIONS (quaternions), so a
            if len(fcs) < 3 or all(len(fc.keyframe_points) < 2 for fc in fcs.values()): continue   # turn is never averaged channel by channel through a flip
            # between two keys the bone turns the SHORT way (a slerp, eased): Euler channels interpolated one by one
            # tumble the arm the long way round when an IK key (pb.matrix decomposed) meets a hand-written pose key,
            # which is the 77-112 deg/frame whip measured as he let go of the rail lever
            ts = sorted({round(kp.co.x) for fc in fcs.values() for kp in fc.keyframe_points})
            kq = []
            for tk in ts:
                q = Euler([fcs[i].evaluate(tk) for i in range(3)], 'XYZ').to_quaternion()
                if kq and q.dot(kq[-1]) < 0: q.negate()
                kq.append(q)
            qs = []
            for f in range(1, n + 1):
                if f <= ts[0]: q = kq[0].copy()
                elif f >= ts[-1]: q = kq[-1].copy()
                else:
                    j = max(i for i in range(len(ts)) if ts[i] <= f)
                    u = (f - ts[j]) / max(1, ts[j + 1] - ts[j]); q = kq[j].slerp(kq[j + 1], ease(u))
                if qs and q.dot(qs[-1]) < 0: q.negate()
                qs.append(q)
            comps = [_gauss([q[i] for q in qs], sig) for i in range(4)]
            prev = None; outs = [[], [], []]
            for k in range(n):
                q = Quaternion((comps[0][k], comps[1][k], comps[2][k], comps[3][k])).normalized()
                e = q.to_euler('XYZ', prev) if prev is not None else q.to_euler('XYZ'); prev = e
                for i in range(3): outs[i].append(e[i])
            for i in range(3):
                fc = fcs[i]; fc.keyframe_points.clear(); fc.keyframe_points.add(n)
                for k in range(n):
                    kp = fc.keyframe_points[k]; kp.co = (k + 1, outs[i][k]); kp.interpolation = 'LINEAR'
                fc.update()
        done = {id(fc) for _, fcs in bones.values() for fc in fcs.values() if len(fcs) >= 3}
        for fc, sig, is_angle in jobs:
            if id(fc) in done or len(fc.keyframe_points) < 2: continue
            v = [fc.evaluate(f) for f in range(1, n + 1)]
            if is_angle:                                     # unwrap: a 359 -> 1 degree step is 2 degrees, not 358
                for i in range(1, len(v)):
                    while v[i] - v[i - 1] > math.pi: v[i] -= 2 * math.pi
                    while v[i] - v[i - 1] < -math.pi: v[i] += 2 * math.pi
            out = _gauss(v, sig)
            fc.keyframe_points.clear()
            fc.keyframe_points.add(len(out))
            for i, val in enumerate(out):
                kp = fc.keyframe_points[i]; kp.co = (i + 1, val); kp.interpolation = 'LINEAR'
            fc.update()


SMOOTH = os.environ.get("TWITCH_FILTER", "1") == "1"
SMOOTH_TORSO, SMOOTH_LIMB, SMOOTH_FACE = 2.5, 1.5, 2.0       # Gaussian sigma, in frames at 30 fps


def _gauss(v, sig):
    """a Gaussian low-pass of a per-frame series, the ends held (a shot starts and ends on its own pose)"""
    r = max(1, int(3 * sig)); w = [math.exp(-0.5 * (k / sig) ** 2) for k in range(-r, r + 1)]
    n = len(v); out = []
    for i in range(n):
        acc = tw = 0.0
        for k, wk in zip(range(-r, r + 1), w):
            j = min(n - 1, max(0, i + k)); acc += wk * v[j]; tw += wk
        out.append(acc / tw)
    return out


def _fcurves(action):
    """every fcurve of an action, legacy or slotted (Blender 5)"""
    if hasattr(action, 'fcurves'): return list(action.fcurves)
    out = []
    for layer in action.layers:
        for strip in layer.strips:
            for cb in strip.channelbags: out.extend(cb.fcurves)
    return out


def load(sc):
    return Data(sc)


def arm_bend(data, f0, f1, step=4):
    """MEASURED: the angle between upper arm and forearm, both arms, over frames (0 = straight)"""
    worst = 0.0; tot = 0.0; n = 0
    for f in range(f0, f1 + 1, step):
        data.sc.frame_set(f); M = data.arm.matrix_world
        for s in 'LR':
            A, Fo = data.pb[f'arm.{s}'], data.pb[f'fore.{s}']
            u = (M @ A.tail - M @ A.head).normalized(); v = (M @ Fo.tail - M @ Fo.head).normalized()
            a = math.degrees(math.acos(max(-1.0, min(1.0, u.dot(v))))); worst = max(worst, a); tot += a; n += 1
    return round(worst, 1), round(tot / max(1, n), 1)
