"""LOOK AT THE KIT: one small test render of a group of store/fx_kit.py elements beside a realistic set (a real sky,
real ground, a real scanned barrel 0.5 m tall for scale), to be opened and judged by eye at phone size before a story
uses them. Nothing here is a gate; it is how a change to the kit is checked (no media goes into git).

usage: python -I fx_sheet.py GROUP OUT.jpg [SPP] [PCT] [T]      GROUP: fire | erupt | curtain | lava | built | water | sky:<preset>
"""
import math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import bpy
from mathutils import Vector
import scene_kit as K, style, fx_kit as FX
from clock import FPS, F


def scale_prop(loc):
    try: return FX.ph_model("barrel_03", loc, name="scale barrel", scale=0.55)
    except FileNotFoundError: return None


def build(group):
    sc = bpy.context.scene
    for o in list(sc.objects): bpy.data.objects.remove(o, do_unlink=True)
    sc.frame_start = 1; sc.frame_end = 90
    if group == "fire":
        FX.sky("day", sun_az=-50); g = FX.ground("gravel", area=(-7, 7, -4, 14))
        FX.rocks(6, area=(-5, 5, 3, 9), zfn=g["zfn"], seed=3)
        FX.fire((-1.3, 2.4, 0), w=1.3, h=1.5, smoke=5.0); scale_prop((-0.3, 1.5, 0))
        FX.smoke_column((0.4, 6.5, 0), w=1.2, h=6.0, seed=2.0)
        FX.steam((1.5, 3.2, 0), w=0.9, h=2.6, keys=[(0.0, 0.0), (0.6, 1.0), (2.5, 0.8)], seed=4.0)
        FX.dust_puff((0.9, 0.6, 0), w=0.8, h=1.0, t0=0.3, dur=2.0, seed=5.0)
        K.camera((0.4, -5.2, 1.5), (0.3, 3.0, 1.9), lens=30)
    elif group in ("fire1", "fire1dawn"):
        FX.sky("day" if group == "fire1" else "dawn", sun_az=-50); g = FX.ground("gravel", area=(-5, 5, -3, 9))
        FX.rocks(4, area=(-2.5, 2.5, 2.5, 5), zfn=g["zfn"], seed=3)
        FX.fire((0, 2.2, 0), w=1.3, h=1.5, smoke=3.0); scale_prop((1.1, 1.7, 0))
        K.camera((0.3, -2.6, 1.2), (0.1, 2.2, 1.3), lens=30)
    elif group in ("erupt", "curtain"):                  # an eruption behind a street, at dusk: houses give it its scale
        FX.sky(os.environ.get("SKY", "dusk"), sun_az=-60, strength=float(os.environ["SKY_STRENGTH"]) if os.environ.get("SKY_STRENGTH") else None); g = FX.ground("lava_field", area=(-30, 30, -6, 60), step=0.5)
        for k, (x, y, yaw) in enumerate(((-4.2, 7.5, 0.2), (4.0, 8.5, -0.3), (-7.5, 14.0, 0.1), (8.5, 15.0, -0.2))):
            FX.house(f"house {k}", (x, y, 0), yaw=yaw, seed=k + 2)
        if group == "erupt": FX.lava_fountain((0.5, 18.0, 0), h=12.0, w=1.6, seed=1)
        else: FX.lava_fountain((0.0, 20.0, 0), h=10.0, w=1.4, length=12.0, yaw=0.15, seed=2, clots=900)
        scale_prop((0.9, 3.0, 0))
        K.camera((0.2, -3.5, 1.5), (0.2, 18.0, 6.2), lens=24)
    elif group == "ridge":                               # lava shot 1's use: daylight, a curtain 40 m off behind a black ridge
        FX.sky("day", sun_az=-50)
        ridge = lambda x, y: 4.2 * math.exp(-((y - 30.0) / 5.0) ** 2) * (0.85 + 0.15 * math.sin(x * 0.35))
        g = FX.ground("lava_field", area=(-30, 30, -6, 60), step=0.5, zfn=ridge)
        for k, (x, y, yaw) in enumerate(((-3.4, 6.0, math.pi / 2 - 0.2), (3.4, 7.0, -math.pi / 2 + 0.2), (-3.6, 12.0, math.pi / 2), (3.6, 13.0, -math.pi / 2))):
            FX.house(f"house {k}", (x, y, 0), yaw=yaw, seed=k + 2, storeys=1)
        FX.lava_fountain((0.0, 40.0, 1.0), h=10.0, w=1.4, length=7.5, seed=2, clots=700, clot_size=2.6)
        scale_prop((0.9, 3.0, 0))
        K.camera((0.2, -3.5, 1.5), (0.2, 30.0, 6.5), lens=30)
    elif group == "lava":                                # flow, pool and bombs, close
        FX.sky(os.environ.get("SKY", "dusk"), sun_az=-60); g = FX.ground("lava_field", area=(-8, 8, -4, 22))
        FX.rocks(8, area=(-6, 6, 4, 9), zfn=g["zfn"], seed=4, tint="#4A4642")
        FX.lava_flow([(-3.4, 2.4), (-2.1, 1.5), (-0.9, 1.8), (-0.3, 2.9), (-0.7, 4.3), (-2.0, 5.2), (-3.2, 4.6), (-3.9, 3.4)])
        FX.lava_pool((1.5, 1.6), r=1.1, seed=2); scale_prop((-2.2, 0.4, 0))
        FX.embers((-0.6, 0.2, 0.05), n=46, speed=4.0, seed=3, splats=4)
        K.camera((0.2, -2.6, 1.7), (0.3, 3.0, 0.6), lens=28)
    elif group == "vehicles":                            # the four cars, three-quarter views, one driving away
        FX.sky(os.environ.get("SKY", "day"), sun_az=-55); g = FX.ground("gravel", area=(-12, 12, -5, 24), relief=0.03)
        FX.road((0.0, -5), (0.0, 24), width=3.0)
        FX.house("house", (-5.6, 9.0, 0), yaw=math.pi / 2, seed=3)
        FX.car("car a", (-0.8, 2.6, 0), yaw=0.6, kind="hatch", seed=1)
        FX.car("car b", (0.9, 6.5, 0), yaw=math.pi - 0.35, kind="suv", seed=4)
        FX.car("car c", (2.6, 3.2, 0), yaw=-0.8, kind="pickup", seed=6, lights=False)
        FX.car("van", (-2.9, 6.2, 0), yaw=0.9, kind="van", seed=0, lights=False)
        scale_prop((0.9, 0.9, 0))
        K.camera((0.4, -3.6, 1.7), (0.4, 4.2, 0.45), lens=30)
    elif group == "plant":                               # the tipper, raised and loaded, and the digger
        FX.sky(os.environ.get("SKY", "day"), sun_az=-55); g = FX.ground("gravel", area=(-12, 12, -5, 24), relief=0.03)
        FX.rocks(6, area=(-5, 5, 6, 10), seed=2)
        FX.truck("truck", (-1.9, 4.6, 0), yaw=0.75, load=0.7, tip=0.0)
        FX.digger("digger", (2.0, 4.2, 0), yaw=-1.0, slew=20)
        scale_prop((0.2, 1.4, 0))
        K.camera((0.2, -4.6, 1.6), (0.1, 4.2, 0.8), lens=30)
    elif group == "digger":                              # side on, to read the arm
        FX.sky("day", sun_az=-40); g = FX.ground("gravel", area=(-8, 8, -5, 12), relief=0.03)
        FX.digger("digger", (0.0, 3.0, 0), yaw=-math.pi / 2 - 0.25, lights=False); scale_prop((-1.6, 1.2, 0))
        K.camera((0.0, -3.2, 1.3), (0.6, 3.0, 0.9), lens=30)
    elif group == "housefire":
        FX.sky(os.environ.get("SKY", "dusk"), sun_az=-60); g = FX.ground("grass", area=(-10, 10, -5, 20), relief=0.04)
        FX.road((0.0, -5), (0.0, 20), width=2.4)
        hs = FX.house("burning", (-3.6, 5.5, 0), yaw=math.pi / 2 - 0.5, seed=5, burn=0.9, storeys=2)
        FX.house_fire(hs); FX.house("next door", (3.8, 7.0, 0), yaw=-math.pi / 2 + 0.3, seed=2); scale_prop((1.0, 1.5, 0))
        K.camera((0.6, -4.2, 1.4), (-0.8, 5.5, 2.6), lens=26)
    elif group.startswith("ground:"):                    # one kind of ground, with a house and a car on it for scale
        FX.sky(os.environ.get("SKY", "day"), sun_az=-55); g = FX.ground(group[7:], area=(-14, 14, -5, 40), relief=0.08)
        FX.house("house", (-2.8, 6.0, 0), yaw=-0.5, seed=3); FX.rocks(6, area=(-1, 6, 1, 8), zfn=g["zfn"], seed=1)
        FX.car("car", (1.6, 3.2, g["zfn"](1.6, 3.2)), yaw=0.7, seed=2, lights=False); scale_prop((0.2, 1.0, 0))
        K.camera((0.6, -4.6, 1.3), (0.2, 5.0, 1.2), lens=26)
    elif group == "built":
        FX.sky("day", sun_az=-55); g = FX.ground("grass", area=(-12, 12, -5, 24), relief=0.05)
        FX.road((0.0, -5), (0.0, 24), width=2.6)
        for k, (x, y, yaw) in enumerate(((-4.4, 3.4, math.pi / 2 - 0.25), (4.6, 5.0, -math.pi / 2), (-4.8, 9.5, math.pi / 2), (4.8, 11.5, -math.pi / 2 + 0.2), (-4.6, 16.0, math.pi / 2))):
            FX.house(f"house {k}", (x, y, 0), yaw=yaw, seed=k + 2, lit=(1,) if k == 1 else ())
        FX.rocks(8, area=(-9, 9, 0, 12), zfn=g["zfn"], seed=6, avoid=lambda x, y: abs(x) < 6.6, size=(0.2, 0.6))
        scale_prop((1.9, 1.0, 0))
        K.camera((1.2, -3.2, 1.3), (-1.2, 6.0, 1.5), lens=28)
    elif group == "water":
        FX.sky("dawn", sun_az=140); g = FX.ground("sand", area=(-10, 10, -5, 3.5), relief=0.04)
        FX.water(area=(-40, 40, 3.0, 90), z=-0.05)
        FX.rocks(9, area=(-5, 5, 1.5, 5.5), seed=2, size=(0.3, 1.1))
        FX.house("shore house", (-2.6, 1.6, 0), yaw=0.5, seed=4); scale_prop((1.2, 0.6, 0))
        K.camera((0.6, -5.0, 1.4), (0.0, 5.0, 1.0), lens=30)
    elif group.startswith("sky:"):
        FX.sky(group[4:], sun_az=float(os.environ.get("SUN_AZ", "-55"))); g = FX.ground("gravel", area=(-10, 10, -5, 24))
        FX.house("house", (-2.4, 5.0, 0), yaw=-0.5, seed=3); FX.rocks(5, area=(-1, 5, 1, 6), seed=1); scale_prop((1.0, 1.2, 0))
        K.camera((0.6, -4.6, 1.3), (-0.4, 5.0, 2.3), lens=26)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    group, out = sys.argv[1], sys.argv[2]
    spp = int(sys.argv[3]) if len(sys.argv) > 3 else 12; pct = int(sys.argv[4]) if len(sys.argv) > 4 else 45
    build(group)
    sc = bpy.context.scene
    style.render_settings(sc, spp, pct)
    sc.render.use_motion_blur = False
    sc.render.image_settings.file_format = 'JPEG'; sc.render.image_settings.quality = 88
    sc.render.threads_mode = 'FIXED'; sc.render.threads = int(os.environ.get("FX_THREADS", "1"))
    sc.frame_set(F(float(sys.argv[5]) if len(sys.argv) > 5 else 1.2))
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("SHEET", out)
