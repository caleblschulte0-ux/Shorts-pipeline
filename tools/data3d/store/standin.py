"""A STAND-IN for Data while tools/data3d/character.py is being rebuilt: the same API, a capsule body with a deforming
armature (elbows, knees), so the staging, the straight-arm cart push and the lighting can be developed and MEASURED.
Rest facing -Y, up Z, metres. Replace by `from character import load` when it lands; the store glue only uses this API."""
import bpy, bmesh, math
from mathutils import Vector, Matrix

import os as _o, sys as _s; _s.path.insert(0, _o.path.dirname(_o.path.dirname(_o.path.abspath(__file__)))); from clock import FPS   # the one clock (tools/data3d/clock.py)
F = lambda t: int(round(t * FPS)) + 1


def _mat(name, hexc, rough=0.5):
    import scene_kit as K
    return K.mat(name, hexc, rough=rough)


def _capsule(name, a, b, r, m, parent_bone, arm, seg=20):
    a = Vector(a); b = Vector(b); d = b - a; h = d.length
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    for v in bm.verts: v.co.z += h / 2
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=10, radius=r)
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=10, radius=r)
    verts = list(bm.verts)
    n = len(verts); half = (n - seg * 2 - 2)  # rough: last two spheres
    # move the two spheres: the last 2*(seg*9+2) verts
    ns = seg * 9 + 2
    for v in verts[-2 * ns:-ns]: v.co.z += 0
    for v in verts[-ns:]: v.co.z += h
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o); me.materials.append(m)
    for p in me.polygons: p.use_smooth = True
    o.location = a; o.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    # bake world transform so the armature modifier works in world/armature space
    mw = o.matrix_world.copy(); o.matrix_world = Matrix.Identity(4)
    for v in me.vertices: v.co = mw @ v.co
    vg = o.vertex_groups.new(name=parent_bone); vg.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
    md = o.modifiers.new("arm", "ARMATURE"); md.object = arm
    o.parent = arm
    return o


class Data:
    height = 0.95

    def __init__(self, sc):
        self.sc = sc; self._end = 0.0
        teal = _mat("Data / teal", "#2FA68C", 0.5); coat = _mat("Coat / warm ivory", "#F4F1EA", 0.8)
        frames = _mat("Frames / charcoal", "#16181C", 0.3); eyes = _mat("Eyes / ivory", "#F8F8F4", 0.1); pup = _mat("Pupils / deep charcoal", "#0A0B0D", 0.2)
        # armature
        ad = bpy.data.armatures.new("DataRig"); arm = bpy.data.objects.new("Data", ad); bpy.context.collection.objects.link(arm)
        bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
        def bone(name, head, tail, parent=None):
            b = ad.edit_bones.new(name); b.head = head; b.tail = tail
            if parent: b.parent = ad.edit_bones[parent]
            return b
        SH = 0.50; HIP = 0.28; SX = 0.075
        bone("root", (0, 0, 0), (0, 0, 0.1))
        bone("spine", (0, 0, HIP), (0, 0, 0.42), "root"); bone("chest", (0, 0, 0.42), (0, 0, 0.56), "spine")
        bone("neck", (0, 0, 0.56), (0, 0, 0.6), "chest"); bone("head", (0, 0, 0.6), (0, 0, 0.9), "neck")
        self.U, self.Fo, self.H = 0.103, 0.105, 0.08
        for s, sg in (("L", -1), ("R", 1)):
            bone(f"clav.{s}", (0, 0, SH), (sg * SX, 0, SH), "chest")
            bone(f"arm.{s}", (sg * SX, 0, SH), (sg * SX, 0, SH - self.U), f"clav.{s}")
            bone(f"fore.{s}", (sg * SX, 0, SH - self.U), (sg * SX, 0, SH - self.U - self.Fo), f"arm.{s}")
            bone(f"hand.{s}", (sg * SX, 0, SH - self.U - self.Fo), (sg * SX, 0, SH - self.U - self.Fo - self.H), f"fore.{s}")
            bone(f"leg.{s}", (sg * 0.04, 0, HIP), (sg * 0.04, 0, 0.14), "root"); bone(f"shin.{s}", (sg * 0.04, 0, 0.14), (sg * 0.04, 0, 0.02), f"leg.{s}")
            bone(f"foot.{s}", (sg * 0.04, 0, 0.02), (sg * 0.04, -0.08, 0.02), f"shin.{s}")
        bpy.ops.object.mode_set(mode='OBJECT')
        self.arm = arm; self.pb = arm.pose.bones
        # body meshes, each weighted to one bone
        _capsule("Coat / continuous tapered body", (0, 0, HIP - 0.02), (0, 0, SH + 0.04), 0.085, coat, "spine", arm)
        _capsule("DA_Neck", (0, 0, 0.54), (0, 0, 0.62), 0.03, teal, "neck", arm)
        head = _capsule("DA_Head", (0, 0, 0.70), (0, 0, 0.78), 0.165, teal, "head", arm)
        for sg, s in ((-1, "L"), (1, "R")):
            _capsule(f"Sleeve.{s}", (sg * SX, 0, SH), (sg * SX, 0, SH - self.U), 0.034, coat, f"arm.{s}", arm)
            _capsule(f"Fore.{s}", (sg * SX, 0, SH - self.U), (sg * SX, 0, SH - self.U - self.Fo), 0.03, coat, f"fore.{s}", arm)
            _capsule(f"Mitten.{s}", (sg * SX, 0, SH - self.U - self.Fo), (sg * SX, 0, SH - self.U - self.Fo - self.H + 0.02), 0.04, teal, f"hand.{s}", arm)
            _capsule(f"Leg.{s}", (sg * 0.04, 0, HIP), (sg * 0.04, 0, 0.14), 0.032, teal, f"leg.{s}", arm)
            _capsule(f"Shin.{s}", (sg * 0.04, 0, 0.14), (sg * 0.04, 0, 0.03), 0.03, teal, f"shin.{s}", arm)
            _capsule(f"Shoe.{s}", (sg * 0.04, 0.02, 0.025), (sg * 0.04, -0.09, 0.025), 0.03, teal, f"foot.{s}", arm)
            # eyes: spheres sunk into the head, lens frames
            e = _capsule(f"Eye.{s}", (sg * 0.06, -0.13, 0.78), (sg * 0.06, -0.135, 0.78), 0.035, eyes, "head", arm)
            _capsule(f"Pupil.{s}", (sg * 0.06, -0.158, 0.78), (sg * 0.06, -0.16, 0.78), 0.012, pup, "head", arm)
            _capsule(f"Lens.{s}", (sg * 0.06, -0.165, 0.78), (sg * 0.06, -0.168, 0.78), 0.045, frames, "head", arm)
        for pb in self.pb: pb.rotation_mode = 'XYZ'
        self._yaw = 0.0

    # ---------------------------------------------------------------- placement
    def place(self, x, y, rot_deg=0.0):
        self.arm.location = (x, y, 0); self.arm.rotation_euler = (0, 0, math.radians(rot_deg)); self._yaw = math.radians(rot_deg)
        bpy.context.view_layer.update()
    def pos(self): return Vector(self.arm.location)
    def forward(self, yaw=None):
        yaw = self.arm.rotation_euler.z if yaw is None else yaw
        return Vector((math.sin(yaw), -math.cos(yaw), 0))      # rest facing -Y
    def _obj_loc(self, t):
        self.sc.frame_set(F(t)); return Vector(self.arm.location), self.arm.rotation_euler.z
    def _kobj(self, t, loc=None, rot=None):
        if loc is not None: self.arm.location = (loc[0], loc[1], 0); self.arm.keyframe_insert('location', frame=F(t))
        if rot is not None: self.arm.rotation_euler = (0, 0, rot); self.arm.keyframe_insert('rotation_euler', frame=F(t))
        self._end = max(self._end, t)
    def _k(self, bone, t, rot=None, loc=None):
        pb = self.pb[bone]
        if rot is not None: pb.rotation_euler = tuple(math.radians(v) for v in rot); pb.keyframe_insert('rotation_euler', frame=F(t))
        if loc is not None: pb.location = loc; pb.keyframe_insert('location', frame=F(t))
        self._end = max(self._end, t)

    # ---------------------------------------------------------------- walking (procedural; legs swing, knees bend, a bob)
    def walk_to(self, target, t0, t1, face=None):
        p0, _ = self._obj_loc(t0); tgt = Vector((target[0], target[1], 0)); d = tgt - p0; dist = d.length
        yaw = math.atan2(d.x, -d.y) if dist > 1e-4 else self.arm.rotation_euler.z
        self._kobj(t0, loc=p0, rot=yaw)
        stride = 0.42; steps = max(1.0, dist / stride); period = (t1 - t0) / steps
        for f in range(F(t0), F(t1) + 1):
            t = (f - 1) / FPS; u = (t - t0) / max(1e-6, t1 - t0)
            p = p0 + d * u; ph = 2 * math.pi * (t - t0) / max(1e-6, period)
            self.arm.location = (p.x, p.y, 0.012 * abs(math.sin(ph))); self.arm.keyframe_insert('location', frame=f)
            self.arm.rotation_euler = (0, 0, yaw); self.arm.keyframe_insert('rotation_euler', frame=f)
            for s, sg in (("L", 1), ("R", -1)):
                sw = 28 * math.sin(ph) * sg
                self._k(f"leg.{s}", t, rot=(sw, 0, 0))
                self._k(f"shin.{s}", t, rot=(-max(0.0, 40 * math.sin(ph + 0.9) * sg) - 4, 0, 0))
                self._k(f"foot.{s}", t, rot=(max(0.0, -sw * 0.5), 0, 0))
            self._k("spine", t, rot=(4 + 1.5 * math.sin(2 * ph), 0, 0))
        self._kobj(t1, loc=tgt, rot=yaw)
        for s in "LR":
            self._k(f"leg.{s}", t1 + 0.3, rot=(0, 0, 0)); self._k(f"shin.{s}", t1 + 0.3, rot=(0, 0, 0)); self._k(f"foot.{s}", t1 + 0.3, rot=(0, 0, 0))
        self._k("spine", t1 + 0.3, rot=(0, 0, 0))
        return t1
    def turn_to(self, rot_deg, t0, t1):
        _, y0 = self._obj_loc(t0); self._kobj(t0, rot=y0); self._kobj(t1, rot=math.radians(rot_deg)); return t1
    def look_at(self, point, t, max_yaw=40):
        self.sc.frame_set(F(t)); M = self.arm.matrix_world; hp = M @ self.pb["head"].head
        d = Vector(point) - hp; fw = self.forward(); side = Vector((fw.y, -fw.x, 0))
        yaw = math.degrees(math.atan2(d.dot(side), d.dot(fw))); yaw = max(-max_yaw, min(max_yaw, yaw))
        pitch = math.degrees(math.atan2(d.z, Vector((d.x, d.y, 0)).length)); pitch = max(-25, min(25, pitch))
        self._k("head", t, rot=(-pitch * 0.6, 0, -yaw)); return t
    def expression(self, name, t0, t1=None, blend=0.22): return t0
    def blink(self, t): return t
    def breathe(self, t0, t1): return t1
    def act(self, name, t0, dur=0.4, hold=0.4, **kw):
        if name == 'shrug':
            for s in "LR":
                self._k(f"arm.{s}", t0, rot=(0, 0, 0)); self._k(f"arm.{s}", t0 + dur, rot=(-20, 0, 0)); self._k(f"fore.{s}", t0 + dur, rot=(-70, 0, 0))
                self._k(f"arm.{s}", t0 + dur + hold, rot=(-20, 0, 0)); self._k(f"arm.{s}", t0 + dur + hold + dur, rot=(0, 0, 0)); self._k(f"fore.{s}", t0 + dur + hold + dur, rot=(0, 0, 0))
            self._k("clav.L", t0 + dur, rot=(0, 0, 8)); self._k("clav.L", t0 + dur + hold + dur, rot=(0, 0, 0))
        return t0 + dur + hold + dur
    def release(self, t):
        for s in "LR":
            self._k(f"arm.{s}", t, rot=(0, 0, 0)); self._k(f"fore.{s}", t, rot=(-6, 0, 0)); self._k(f"hand.{s}", t, rot=(0, 0, 0))
    def rest_bones(self, t0, t1): self.release(t1)

    # ---------------------------------------------------------------- two-bone IK (the lost version's maths, kept)
    def _arm_ik(self, s, target, t, elbow_out):
        self.sc.frame_set(F(t))
        A, Fo = self.pb[f'arm.{s}'], self.pb[f'fore.{s}']
        A.rotation_euler = (0, 0, 0); Fo.rotation_euler = (0, 0, 0); bpy.context.view_layer.update()
        M = self.arm.matrix_world
        sh = M @ A.head; tgt = Vector(target)
        U = self.U * self.arm.scale.x; Fl = self.Fo * self.arm.scale.x
        d = tgt - sh; D = d.length; reach = U + Fl
        if D > reach * 0.995: tgt = sh + d.normalized() * reach * 0.995; D = reach * 0.995
        cosA = (U * U + D * D - Fl * Fl) / (2 * U * D)
        ang = math.acos(max(-1, min(1, cosA)))
        if D >= reach * 0.99: ang = 0.0                      # at full reach the arm is STRAIGHT
        fw = self.forward(); side = Vector((-1 if s == 'L' else 1, 0, 0)); side = M.to_3x3() @ side; side.normalize()
        n = d.cross(fw + side * elbow_out)
        if n.length < 1e-6: n = Vector((0, 0, 1))
        n.normalize()
        upper_dir = Matrix.Rotation(ang, 4, n) @ d.normalized()
        elbow = sh + upper_dir * U
        fore_dir = (tgt - elbow).normalized()
        R3w = M.to_3x3().normalized()
        def aim(pb, head, dirn):
            y = dirn.normalized(); x = y.cross(Vector((0, 0, 1)))
            if x.length < 1e-4: x = y.cross(Vector((0, 1, 0)))
            x.normalize(); z = x.cross(y)
            Rw = Matrix((x, y, z)).transposed(); Ra = R3w.inverted() @ Rw
            Ma = Ra.to_4x4(); Ma.translation = M.inverted() @ head
            pb.matrix = Ma; bpy.context.view_layer.update()
        aim(A, sh, upper_dir); aim(Fo, elbow, fore_dir)
        for pb in (A, Fo):
            pb.rotation_mode = 'XYZ'; pb.keyframe_insert('rotation_euler', frame=F(t))
        self._end = max(self._end, t)
    def hold(self, pL, pR, t0, t1=None, elbow_out=0.6):
        self._arm_ik('L', Vector(pL), t0, elbow_out); self._arm_ik('R', Vector(pR), t0, elbow_out)
        if t1: self._arm_ik('L', Vector(pL), t1, elbow_out); self._arm_ik('R', Vector(pR), t1, elbow_out)
    def _foot_bottom(self): return 0.0
    def finish(self):
        n = F(self._end); self.sc.frame_end = max(self.sc.frame_end, n)
        return n


def load(sc):
    return Data(sc)
