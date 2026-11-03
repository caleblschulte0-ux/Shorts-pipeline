"""Standalone Data reference prototype. Blender 4+: blender -b -t 4 --python build.py -- /tmp/data-preview
No production imports or publishing side effects. Front is -Y, up is Z.
"""
import bpy, math, sys
from pathlib import Path
from mathutils import Vector

OUT = Path(sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else '/tmp/data-preview')
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def material(name, color, rough=.58):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    bs=m.node_tree.nodes['Principled BSDF']; bs.inputs['Base Color'].default_value=(*color,1); bs.inputs['Roughness'].default_value=rough
    return m
teal=material('Data / teal',(.055,.36,.285)); white=material('Coat / warm ivory',(.53,.55,.53)); black=material('Frames / charcoal',(.008,.011,.014),.42)
eye=material('Eyes / ivory',(.72,.74,.71),.32); red=material('Tie / vermilion',(.74,.065,.025)); blue=material('Pen / blue',(.02,.34,.65)); floor=material('Stage',(.065,.073,.09),.85)
pupil_ink=material('Pupils / deep charcoal',(.003,.004,.006),.28)
skin=teal.node_tree.nodes['Principled BSDF']
skin.inputs['Roughness'].default_value=.62
skin.inputs['Specular IOR Level'].default_value=.22
skin.inputs['Subsurface Weight'].default_value=.15
skin.inputs['Subsurface Radius'].default_value=(.8,.6,.45)
skin.inputs['Subsurface Scale'].default_value=.12
eye.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.5
eye.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value=.12
pupil_ink.node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value=.12
parts=[]
def finish(o,name,mat):
    o.name=name; o.data.materials.append(mat)
    if o.type=='MESH':
        for p in o.data.polygons: p.use_smooth=True
    parts.append(o); return o

def ell(name,loc,scale,mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48,ring_count=32,location=loc)
    o=bpy.context.object; o.scale=scale; return finish(o,name,mat)

def box(name,loc,scale,mat,bevel=.08):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    b=o.modifiers.new('Soft edges','BEVEL'); b.width=bevel; b.segments=5
    return finish(o,name,mat)

def line(name,pts,r,mat,closed=False):
    c=bpy.data.curves.new(name,'CURVE'); c.dimensions='3D'; c.resolution_u=24; c.bevel_depth=r; c.bevel_resolution=5
    s=c.splines.new('POLY'); s.points.add(len(pts)-1)
    for p,co in zip(s.points,pts): p.co=(*co,1)
    s.use_cyclic_u=closed; o=bpy.data.objects.new(name,c); bpy.context.collection.objects.link(o); return finish(o,name,mat)

def capsule(name,a,b,r,mat):
    o=ell(name,(Vector(a)+Vector(b))/2,(r,r,(Vector(b)-Vector(a)).length/2+r),mat)
    o.rotation_euler=(Vector(b)-Vector(a)).to_track_quat('Z','Y').to_euler(); return o

def panel(name,pts,mat,thick=.04):
    mesh=bpy.data.meshes.new(name); mesh.from_pydata(pts,[],[list(range(len(pts)))]); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); finish(o,name,mat)
    s=o.modifiers.new('Fabric thickness','SOLIDIFY'); s.thickness=thick
    b=o.modifiers.new('Soft seam','BEVEL'); b.width=.025; b.segments=3
    return o

# The head owns the silhouette; limbs are slightly lanky, not stick thin.
head=ell('Head',(0,0,3.26),(.91,.69,.86),teal)
for v in head.data.vertices:
    v.co.x*=1+.035*math.exp(-((v.co.z+.28)/.32)**2)
for x in (-.36,.36):
    ear=ell('Ear.L' if x<0 else 'Ear.R',(x,.015,4.09),(.155,.15,.39),teal); ear.rotation_euler.y=-.12 if x<0 else .12
ell('Neck',(0,0,2.33),(.19,.19,.10),teal)
for x in (-.25,.25):
    capsule('Leg', (x,0,.27),(x,.015,1.08),.155,teal)
    # A single continuous shoe last: shaped heel, instep and low rounded toe.
    shoe_verts=[]; shoe_faces=[]; steps=48
    sections=[(.20,.025,.16,.025),(.17,.14,.18,.155),(.09,.18,.21,.20),(-.04,.215,.19,.18),(-.22,.235,.15,.13),(-.36,.21,.14,.12),(-.44,.135,.14,.095),(-.48,.018,.14,.025)]
    for yy,rx,zc,rz in sections:
        for k in range(steps):
            a=2*math.pi*k/steps
            shoe_verts.append((rx*math.copysign(abs(math.cos(a))**.8,math.cos(a)),yy,max(.008,zc+rz*math.sin(a))))
    for j in range(len(sections)-1):
        for k in range(steps): shoe_faces.append((j*steps+k,j*steps+(k+1)%steps,(j+1)*steps+(k+1)%steps,(j+1)*steps+k))
    shoe_faces+=[tuple(reversed(range(steps))),tuple((len(sections)-1)*steps+k for k in range(steps))]
    sm=bpy.data.meshes.new('Shoe last');sm.from_pydata(shoe_verts,[],shoe_faces);sm.update()
    shoe=bpy.data.objects.new('Shoe',sm);bpy.context.collection.objects.link(shoe);shoe.location.x=x
    finish(shoe,'Shoe',teal); sub=shoe.modifiers.new('Soft shoe silhouette','SUBSURF');sub.levels=2
# Coat: continuous tapered shell with a flattened front, not stacked spheres.
verts=[]; n=64
for z,rx,ry in [( .83,.51,.31),(.88,.52,.32),(1.1,.50,.32),(1.8,.43,.29),(2.17,.34,.25),(2.30,.25,.20)]:
    for i in range(n):
        a=2*math.pi*i/n; verts.append((rx*math.cos(a),ry*math.sin(a),z))
faces=[]
for j in range(5):
    for i in range(n): faces.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
faces.append(tuple(reversed(range(n)))); faces.append(tuple(5*n+i for i in range(n)))
mesh=bpy.data.meshes.new('Coat shell'); mesh.from_pydata(verts,[],faces); mesh.update()
o=bpy.data.objects.new('Coat / continuous tapered body',mesh); bpy.context.collection.objects.link(o); finish(o,o.name,white)
sub=o.modifiers.new('Tailored smooth surface','SUBSURF'); sub.levels=2
for side in (-1,1):
    capsule('Sleeve', (side*.34,0,2.08),(side*.66,-.015,1.37),.205,white)
    ell('Mitten',(side*.69,-.04,1.19),(.195,.195,.23),teal)
    ell('Thumb',(side*.57,-.19,1.21),(.095,.09,.12),teal)
# Shirt opening, tie and folded lapels live on the front surface.
panel('Shirt opening',[(-.23,-.261,2.24),(.23,-.261,2.24),(0,-.345,1.52)],eye)
ell('Tie knot',(0,-.316,2.15),(.09,.045,.10),red)
panel('Tie blade',[(-.048,-.34,2.08),(.048,-.34,2.08),(.095,-.36,1.74),(0,-.37,1.55),(-.095,-.36,1.74)],red)
for s in (-1,1):
    panel('Lapel',[(s*.15,-.30,2.27),(s*.32,-.27,2.10),(s*.24,-.32,1.99),(s*.30,-.32,1.91),(s*.035,-.365,1.55)],white)
line('Coat center seam',[(0,-.333,.87),(0,-.337,1.51)],.012,white)
box('Pocket',(.29,-.315,1.39),(.23,.07,.30),white,.035)
box('Pen',(.30,-.365,1.62),(.045,.045,.25),blue,.018)
for z in (1.35,1.10): ell('Coat button',(.055,-.345,z),(.032,.015,.032),eye)
# White eye pads and genuine open rounded-square frames.
for x in (-.39,.39):
    wh=ell('Eye white',(x,-.635,3.40),(.325,.115,.325),eye)
    # A convex squircle rather than a beveled thin cube: avoids square, staring eyes.
    for v in wh.data.vertices:
        v.co.x=math.copysign(abs(v.co.x)**.72,v.co.x)
        v.co.z=math.copysign(abs(v.co.z)**.72,v.co.z)
    pts=[]
    for cx,cz,start in [(.17,.17,0),(-.17,.17,90),(-.17,-.17,180),(.17,-.17,270)]:
        for i in range(13):
            a=math.radians(start+i*90/12); pts.append((x+cx+.16*math.cos(a),-.735,3.40+cz+.16*math.sin(a)))
    line('Glasses frame',pts,.053,black,True)
    gaze=.055 if x<0 else .005
    ell('Pupil',(x+gaze,-.76,3.42),(.157,.025,.162),pupil_ink)
    ell('Eye glint',(x+gaze-.045,-.787,3.485),(.043,.011,.043),eye)
    ell('Eye glint small',(x+gaze+.045,-.787,3.38),(.019,.009,.019),eye)
    line('Temple',[(x+(-.34 if x<0 else .34),-.73,3.42),(x+(-.43 if x<0 else .43),-.33,3.42),(x+(-.43 if x<0 else .43),.17,3.35)],.041,black)
    brow=[]
    for i in range(25):
        v=-.19+i*.38/24; z=3.84+.065*math.sin((v+.19)/.38*math.pi); xx=x+v
        y=-.69*math.sqrt(max(.01,1-(xx/.91)**2-((z-3.26)/.86)**2))-.035
        brow.append((xx,y,z))
    brow_ob=line('Brow',brow,.047,black)
    # Taper and cap the brow so it reads as a soft expression, not a metal bar.
    for j,pt in enumerate(brow_ob.data.splines[0].points): pt.radius=.60+.40*math.sin(math.pi*j/24)**.5
    brow_ob.data.use_fill_caps=True
line('Glasses bridge',[(-.06,-.735,3.43),(.06,-.735,3.43)],.045,black)
ell('Nose',(0,-.755,3.10),(.055,.075,.073),teal)
smile=[]
for i in range(41):
    x=-.37+i*.74/40; z=2.80+.16*(x/.37)**2
    y=-.69*math.sqrt(1-(x/.91)**2-((z-3.26)/.86)**2)-.025
    smile.append((x,y,z))
mouth=line('Smile',smile,.020,black)
mouth.data.use_fill_caps=True
for j,pt in enumerate(mouth.data.splines[0].points): pt.radius=.55+.45*math.sin(math.pi*j/40)**.5
# Match the reference's broad glasses and face spacing.
for ob in parts:
    if ob.name.startswith(('Eye','Pupil','Glasses','Brow','Temple')):
        ob.location.x*=1.055
        ob.scale.x*=1.055
# Tuck the neck into the collar and soften the overall head silhouette.
for ob in parts:
    if ob.name.startswith(('Head','Ear','Eye','Pupil','Glasses','Brow','Temple','Nose','Smile')):
        ob.location.z-=.08
# Broaden the coat and stance while retaining the reference's lanky silhouette.
for ob in parts:
    if ob.name.startswith(('Coat', 'Sleeve', 'Mitten', 'Thumb', 'Leg', 'Shoe', 'Pocket', 'Pen', 'Lapel', 'Shirt', 'Tie')):
        ob.location.x *= 1.10
        ob.scale.x *= 1.10
# Restore the reference's longer coat: stretch the upper body above the hem,
# then raise the whole head assembly to meet the new shoulder height.
for ob in parts:
    if ob.name.startswith(('Head','Ear','Eye','Pupil','Glasses','Brow','Temple','Nose','Smile')):
        ob.location.z+=.17
    elif not ob.name.startswith(('Leg','Shoe')):
        ob.location.z=.83+(ob.location.z-.83)*1.10
        ob.scale.z*=1.10
# Group all components under a root for re-use and posing in Claude's scene.
bpy.ops.object.empty_add(); root=bpy.context.object; root.name='DATA_ROOT'
for o in parts: o.parent=root
bpy.ops.mesh.primitive_plane_add(size=200); bpy.context.object.data.materials.append(floor)
world=bpy.data.worlds.new('Studio'); world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.10,.12,.16,1); world.node_tree.nodes['Background'].inputs[1].default_value=.35; bpy.context.scene.world=world
for name,loc,power,size in [('Key',(-3,-5,6),650,5),('Fill',(4,-4,4),190,5),('Rim',(1,3,6),150,4)]:
    bpy.ops.object.light_add(type='AREA',location=loc); o=bpy.context.object; o.name=name; o.data.energy=power; o.data.shape='DISK'; o.data.size=size; o.rotation_euler=(Vector((0,0,2.2))-o.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(); cam=bpy.context.object; bpy.context.scene.camera=cam; cam.data.type='ORTHO'; cam.data.ortho_scale=5.25
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=384; sc.cycles.use_adaptive_sampling=True; sc.cycles.adaptive_threshold=.018; sc.cycles.use_denoising=False; sc.render.resolution_x=800; sc.render.resolution_y=900; sc.render.resolution_percentage=100; sc.render.image_settings.file_format='PNG'
sc.view_settings.view_transform='Standard'; sc.view_settings.look='None'
for name,loc in [('front',(0,-9,2.65)),('three_quarter',(5,-9,2.9))]:
    cam.location=loc; cam.rotation_euler=(Vector((0,0,2.23))-cam.location).to_track_quat('-Z','Y').to_euler()
    sc.render.filepath=str(OUT/(name+'.png')); bpy.ops.render.render(write_still=True)
cam.location=(5,-9,2.9); cam.rotation_euler=(Vector((0,0,2.23))-cam.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'data_reference.blend'),compress=True)
print('DATA_REFERENCE_DONE',OUT)
