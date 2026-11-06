"""Turnaround and walk test sheets for the rigged Data (tools/data3d/character.py).

    <vbpy> -I tools/data3d/char_check.py [--out DIR] [--spp 16]

Writes DIR/turn.jpg (front, 3/4, side, back, face close-up) and DIR/walk.jpg (every 10th frame of a 4 s side-view
walk, with the measured foot slide and knee/elbow angles printed), and prints every measurable number. VIEW BOTH
AT FULL SIZE before trusting the rig.
"""
import bpy, sys, os, math, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from mathutils import Vector

ap = argparse.ArgumentParser(); ap.add_argument('--out', default=os.environ.get('CHAR_OUT', '/tmp/char')); ap.add_argument('--spp', type=int, default=16)
ap.add_argument('--only', default='turn,walk,face,acts')
args = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
os.makedirs(args.out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
import character
from PIL import Image

sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = args.spp; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 480, 720; sc.render.image_settings.file_format = 'PNG'
sc.render.fps = 24
sc.view_settings.view_transform = 'Filmic' if 'Filmic' in [i.identifier for i in sc.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Standard'

# ---- stage
bpy.ops.mesh.primitive_plane_add(size=20); floor = bpy.context.object; floor.name = 'Floor'
fm = bpy.data.materials.new('Floor'); fm.use_nodes = True; fm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.42, 0.40, 0.37, 1)
fm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9; floor.data.materials.append(fm)
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.58, 0.62, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
def light(name, kind, loc, energy, size=1.0, rot=None):
    L = bpy.data.lights.new(name, kind); L.energy = energy
    if kind == 'AREA': L.size = size
    o = bpy.data.objects.new(name, L); bpy.context.collection.objects.link(o); o.location = loc
    if rot: o.rotation_euler = rot
    return o
light('Key', 'AREA', (1.6, -2.0, 2.4), 400, 1.5, (math.radians(45), 0, math.radians(38)))
light('Fill', 'AREA', (-2.2, -1.6, 1.4), 120, 2.5, (math.radians(65), 0, math.radians(-55)))
light('Rim', 'AREA', (-0.5, 2.2, 2.0), 150, 1.0, (math.radians(-50), 0, math.radians(190)))
cam_d = bpy.data.cameras.new('Cam'); cam_d.lens = 50; cam = bpy.data.objects.new('Cam', cam_d); bpy.context.collection.objects.link(cam); sc.camera = cam
def aim(loc, at):
    cam.location = loc; d = Vector(at) - Vector(loc); cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

data = character.load(sc)
print(f'built: U={data.U:.4f} m Fo={data.Fo:.4f} m, {len(data.parts)} parts, height 0.95 m')

def shot(path):
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)

def sheet(paths, out, cols=None):
    ims = [Image.open(p) for p in paths]; cols = cols or len(ims); rows = math.ceil(len(ims) / cols)
    W, H = ims[0].size; S = Image.new('RGB', (W * cols, H * rows), (30, 30, 30))
    for i, im in enumerate(ims): S.paste(im.convert('RGB'), ((i % cols) * W, (i // cols) * H))
    S.save(out, quality=88); print('sheet', out, S.size)

if 'turn' in args.only:
    data.place(0, 0, 0); data._plant_feet_here(0.0); data.release(0.0); data.expression('neutral', 0.0); data.finish(); sc.frame_set(1)
    paths = []
    c = Vector((0, 0, 0.48)); R = 2.7
    for name, ang in (('front', 180), ('three_quarter', 135), ('side', 90), ('back', 0)):
        a = math.radians(ang); aim((R * math.sin(a), R * math.cos(a), 0.62), c)
        p = os.path.join(args.out, f'turn_{name}.png'); shot(p); paths.append(p)
    cam_d.lens = 85; aim((0.0, -0.95, 0.75), (0, 0, 0.705)); p = os.path.join(args.out, 'turn_face.png'); shot(p); paths.append(p); cam_d.lens = 50
    sheet(paths, os.path.join(args.out, 'turn.jpg'))
    # profile check: any eye-white pixels outside the lens from the side? measured as eye-ball extent vs frame extent
    sc.frame_set(1)
    for s in 'LR':
        ball = bpy.data.objects[f'Eye ball.{s}']; ys = [(ball.matrix_world @ Vector(v)).y for v in ball.bound_box]
        head = bpy.data.objects['Head']; hy = min((head.matrix_world @ Vector(v)).y for v in head.bound_box)
        print(f'eye {s}: front of eyeball y={min(ys):.4f} m, front of head y={hy:.4f} m (eye proud of head by {(hy - min(ys)) * 1000:.1f} mm)')

if 'walk' in args.only:
    for o in list(bpy.data.actions): bpy.data.actions.remove(o)
    data.place(-0.9, 0, 90); data._plant_feet_here(0.0); data.expression('neutral', 0.0)
    data.walk_to((0.9, 0), 0.0, 4.0); n = data.finish()
    print('walk: frames', n, 'target foot slide mm (max, mean):', data.foot_slide(), 'hip drop m: %.3f' % data.walk_drop)
    # the ACTUAL shoe position per frame, not the target: measured from the evaluated scene
    import collections; shoe = {s: bpy.data.objects['Shoe' if s == 'L' else 'Shoe.001'] for s in 'LR'}
    last = {}; slides = []; planted = {(f, s) for f, s, st, _ in data.walk_slide if st}
    for f in range(1, n + 1):
        sc.frame_set(f)
        for s in 'LR':
            p = shoe[s].matrix_world.translation.copy(); stance = (f, s) in planted
            if s in last and last[s][1] and stance: slides.append(((p - last[s][0]).length * 1000, f, s))
            last[s] = (p, stance)
    slides.sort(reverse=True); print('walk: measured planted-shoe movement mm: max %.2f mean %.2f (worst at frame %d %s)' % (slides[0][0], sum(x[0] for x in slides) / len(slides), slides[0][1], slides[0][2]))
    knees = []
    for f in range(1, n + 1):
        sc.frame_set(f); M = data.arm.matrix_world
        for s in 'LR':
            L, Sh = data.pb[f'leg.{s}'], data.pb[f'shin.{s}']
            u = (M @ L.tail - M @ L.head).normalized(); v = (M @ Sh.tail - M @ Sh.head).normalized()
            knees.append(math.degrees(math.acos(max(-1.0, min(1.0, u.dot(v))))))
    print('walk: knee bend deg max %.1f mean %.1f' % (max(knees), sum(knees) / len(knees)))
    print('walk: elbow bend (max, mean):', character.arm_bend(data, 1, n, 1))
    cam_d.lens = 50; paths = []
    for f in range(1, n + 1, 10):
        sc.frame_set(f); x = data.arm.matrix_world.translation.x; aim((x, -2.6, 0.62), (x, 0, 0.48))   # the camera tracks him
        p = os.path.join(args.out, f'walk_{f:03d}.png'); shot(p); paths.append(p)
    sheet(paths, os.path.join(args.out, 'walk.jpg'), cols=5)

if 'face' in args.only:
    for o in list(bpy.data.actions): bpy.data.actions.remove(o)
    data.place(0, 0, 0); data._plant_feet_here(0.0); data.release(0.0)
    data.expression('neutral', 0.0); data.expression('happy', 0.5, 1.0); data.expression('surprised', 1.5, 2.0)
    data.blink(2.6); data.look_at(Vector((1.2, -1.0, 0.9)), 3.0); data.look_at(Vector((-1.2, -1.0, 0.3)), 3.5)
    data.say([(4.0, 0.0), (4.15, 0.6), (4.3, 0.1), (4.45, 0.7), (4.6, 0.0)]); data.gaze(5.0, 18, 8); data.gaze(5.5, -18, -6)
    n = data.finish(); paths = []
    cam_d.lens = 85
    for name, t in (('neutral', 0.0), ('happy', 0.75), ('surprised', 1.75), ('blink', 2.6), ('look_r', 3.0), ('look_l', 3.5), ('say', 4.15), ('gaze_r', 5.0), ('gaze_l', 5.5), ('profile_blink', 2.6)):
        sc.frame_set(character.F(t))
        if name == 'profile_blink': aim((-0.95, 0.0, 0.75), (0, 0, 0.705))
        else: aim((0.0, -0.95, 0.75), (0, 0, 0.705))
        p = os.path.join(args.out, f'face_{name}.png'); shot(p); paths.append(p)
    sheet(paths, os.path.join(args.out, 'face.jpg'), cols=5); cam_d.lens = 50
    sc.frame_set(character.F(2.6))
    for s in 'LR':
        lid = bpy.data.objects[f'Lid upper.{s}']; ys = [(lid.matrix_world @ Vector(v)).y for v in lid.bound_box]
        ball = bpy.data.objects[f'Eye ball.{s}']; by = min((ball.matrix_world @ Vector(v)).y for v in ball.bound_box)
        pu = bpy.data.objects[f'Pupil.{s}']; py = min((pu.matrix_world @ Vector(v)).y for v in pu.bound_box)
        print(f'blink {s}: lid front y={min(ys):.4f} m, eyeball front y={by:.4f} m, pupil front y={py:.4f} m (lid proud of eye by {(by - min(ys)) * 1000:.1f} mm, of pupil by {(py - min(ys)) * 1000:.1f} mm)')

if 'acts' in args.only:
    for o in list(bpy.data.actions): bpy.data.actions.remove(o)
    data.place(0, 0, 0); data._plant_feet_here(0.0); data.release(0.0); data.expression('neutral', 0.0)
    t = data.act('shrug', 0.5, dur=0.3, hold=0.6); t = data.act('wave', t + 0.3, dur=0.3, hold=0.9); t = data.act('thumbs_up', t + 0.3, dur=0.3, hold=0.6)
    data.release(t + 0.4)
    # a straight-arm hold: the hand on a point at full reach, measured every frame
    sh = data.arm.matrix_world @ data.J['R']['sh']; far = sh + Vector((0.0, -1.0, 0.0)) * (data.U + data.Fo) * 1.3
    data._arm_ik('R', far, t + 1.0, 0.5); data._arm_ik('R', far, t + 2.0, 0.5)
    n = data.finish()
    print('acts: frames', n, 'straight hold elbow (max, mean) over its frames:', character.arm_bend(data, character.F(t + 1.0), character.F(t + 2.0), 1))
    paths = []
    for name, tt in (('shrug', 1.1), ('wave', 2.3), ('wave2', 2.6), ('thumbs', 3.9), ('rest', t + 0.4), ('reach', t + 1.5)):
        sc.frame_set(character.F(tt)); aim((0.5, -2.3, 0.75), (0, 0, 0.55)); p = os.path.join(args.out, f'act_{name}.png'); shot(p); paths.append(p)
    sc.frame_set(character.F(t + 1.5)); aim((2.4, 0.0, 0.62), (0, 0, 0.55)); p = os.path.join(args.out, 'act_reach_side.png'); shot(p); paths.append(p)
    sheet(paths, os.path.join(args.out, 'acts.jpg'), cols=7)
