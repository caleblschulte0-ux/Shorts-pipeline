"""Fire, smoke, lava, houses, roads, ground, water and skies come from the realism kit, and what glows casts light.

2026-11-26. The lava short's twenty-six board rounds kept one hard defect, OFF THE LOOK, and it was always a thing a
shot had built for itself: smoke as "a row of lumpy brown clay balls", fountains as "smooth orange cones" and later "a
flat flame sprite" that "lights nothing", "popcorn" bombs, "Monopoly houses", a road that was one box. The parts of
the three shots that passed are now tools/data3d/store/fx_kit.py, and store/fx_lint.py refuses a hand-built one before
a frame renders. This holds the kit's contract (every name resolves, every emitter brings its lamp), the lint against
the code that failed and the code that passed, and the wiring.
"""
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
STORE = ROOT / "tools" / "data3d" / "store"
sys.path.insert(0, str(STORE))
sys.path.insert(0, str(STORE.parent))
import fx_kit    # noqa: E402
import fx_lint   # noqa: E402

LAVA = (STORE.parent / "stories" / "lava" / "shots.py").read_text()

# Verbatim from the lava short's FIRST board round (commit 31894d43f, 2026-11-24, every shot failed at 24-34; the
# panel: "the smoke is a row of lumpy brown clay balls", "the houses' fire is blobs", "a generic road"). Only the
# enclosing shot functions are added so the excerpt parses.
ROUND_1 = '''
def s5_fire(name, loc, size, rnd):
    """flames on a burning house: a cluster of hot tongues and a column of smoke billows over it"""
    fm = lw_fire_mat("house fire", 1.4)
    core = lw_fire_mat("house fire core", 2.0)
    tongues = []
    for k in range(7):
        x = loc[0] + rnd.uniform(-0.45, 0.45) * size; y = loc[1] + rnd.uniform(-0.3, 0.3) * size
        o = K.sph(f"{name} flame {k}", (x, y, loc[2] + 0.25 * size), 0.18 * size, core if k % 3 == 0 else fm, scale=(0.8, 0.8, 2.2), seg=12, ring=8)
        tongues.append(o)
    ash = lw_smoke_mat("fire smoke", density=2.5, col=(0.08, 0.08, 0.09))
    smoke = [lw_puff(f"{name} smoke {k}", (loc[0] + rnd.uniform(-0.4, 0.4) - 0.5 * k, loc[1] + 0.3 * k, loc[2] + 1.0 * size + 1.3 * k * size), (0.8 + 0.4 * k) * size, ash)
             for k in range(6)]
    return tongues, smoke


def place_grindavik_street():
    K.box("street asphalt", (0, 2.5, 0.004), (4.0, 20, 0.01), lw_asphalt(), bev=0)
    K.sph("far mountain", (x, 70, -4), 14.0, K.mat("far mountain", "#7D8A9C", rough=1.0), scale=(1.4, 0.5, 0.7 + 0.15 * (k % 3)), seg=24, ring=12)
    K.box("fissure glow", (0, S1_RIDGE_Y, fz - 0.1), (44, 0.6, 0.3), lw_emit("fissure line", "#FF5000", 1.4), bev=0)
    spat = [K.sph(f"fissure spatter {k}", (0, S1_RIDGE_Y, fz), rnd.uniform(0.05, 0.1), spm, seg=8, ring=6) for k in range(30)]
    ash = lw_billow_mat("eruption plume", col="#5C5A58")              # a lumpy billowing plume, not a soft smudge
    puffs = []
    for k in range(16):
        puffs.append(lw_billow(f"eruption plume {k}", (x, S1_RIDGE_Y + 3.0 + rnd.uniform(0, 3), fz + 7 + rnd.uniform(0, 6)), rnd.uniform(3.0, 4.2), ash, seed=k, scale=(1.3, 1.0, 0.9)))


def shot1():
    place_grindavik_street()


def shot5():
    tongues, smoke = s5_fire("house", (0, 0, 0), 1.35, rnd)
'''


# ---------------------------------------------------------------- the registry
def test_every_registry_name_resolves_to_a_callable_with_a_line_saying_what_it_is():
    assert len(fx_kit.REGISTRY) >= 14
    for name, e in fx_kit.REGISTRY.items():
        assert callable(e["fn"]) and e["fn"] is getattr(fx_kit, name), name
        assert e["group"] in fx_kit.GROUPS, name
        assert len(e["what"]) > 30 and "\n" not in e["what"], name


def test_the_kit_has_every_element_the_panel_failed_by_hand():
    for must in ("sky", "ground", "road", "rocks", "house", "fire", "smoke_column", "steam", "dust_puff", "lava_flow", "lava_pool",
                 "lava_fountain", "embers", "water"):
        assert must in fx_kit.REGISTRY, must
    for glows in ("fire", "house_fire", "lava_flow", "lava_pool", "lava_fountain", "embers", "glow_light"):
        assert fx_kit.REGISTRY[glows]["emits"], f"{glows} glows: it must be registered as an emitter so it is held to its lamp"


def test_the_brief_lists_every_element_and_the_readme_carries_it():
    b = fx_kit.brief(); readme = (STORE.parent / "README.md").read_text()
    for name in fx_kit.REGISTRY:
        assert f"FX.{name}:" in b, name
        assert f"`FX.{name}`" in readme, f"README.md does not list FX.{name}: paste `python store/fx_kit.py` into it"


def test_an_emitter_that_returns_no_lamp_is_refused():
    saved = dict(fx_kit.REGISTRY)
    try:
        @fx_kit.element("fire", "a test emitter that forgets its lamp, which the wrapper must refuse", emits=True)
        def dark():
            return dict(objects=[])
        with pytest.raises(RuntimeError, match="returned no light"):
            dark()

        @fx_kit.element("fire", "a test element that returns nothing a stager can use, refused too", emits=False)
        def nothing():
            return None
        with pytest.raises(TypeError):
            nothing()
    finally:
        fx_kit.REGISTRY.clear(); fx_kit.REGISTRY.update(saved)


def test_every_emitter_is_built_through_the_wrapper():
    """the function a story reaches (fx_kit.fire) IS the wrapped one: there is no way to the raw builder past the check"""
    for name, e in fx_kit.REGISTRY.items():
        assert hasattr(e["fn"], "__wrapped__"), name


# ---------------------------------------------------------------- built in Blender (skipped where bpy is not installed)
def _blender():
    bpy = pytest.importorskip("bpy")
    if not pathlib.Path(fx_kit.PH, "hdri").is_dir():
        pytest.skip("the Poly Haven assets are not unpacked in cache/polyhaven")
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.scene.frame_start = 1; bpy.context.scene.frame_end = 12
    return bpy


def test_every_emissive_element_returns_the_light_it_casts():
    bpy = _blender()
    hs = fx_kit.house("burning", burn=1.0, seed=3)
    made = {
        "sky": fx_kit.sky("day"),
        "fire": fx_kit.fire((0, 0, 0)),
        "house_fire": fx_kit.house_fire(hs),
        "glow_light": fx_kit.glow_light((0, 0, 1)),
        "lava_flow": fx_kit.lava_flow([(0, 0), (2, 0), (2, 2), (0, 2)], glow=0.0),
        "lava_pool": fx_kit.lava_pool((5, 5)),
        "embers": fx_kit.embers((8, 0, 0), n=4),
        "lava_fountain": fx_kit.lava_fountain((12, 0, 0), clots=6),
    }
    assert set(made) == {n for n, e in fx_kit.REGISTRY.items() if e["emits"]}, "a new emitter needs a line in this test"
    for name, out in made.items():
        assert out["lights"], name
        for L in out["lights"]:
            assert L.type == 'LIGHT' and L.data.energy > 0 and L.get("fx") == name, (name, L.name)
        for o in out["objects"]:
            assert o.get("fx") == name, (name, o.name)
    assert fx_lint.scene_problems(list(bpy.context.scene.objects)) == [], "the kit's own emitters are never reported as unlit"


def test_a_glowing_thing_with_no_lamp_is_measured_and_a_lamp_beside_it_clears_it():
    bpy = _blender()
    import scene_kit as K
    K.box("neon sign", (0, 0, 1), (0.6, 0.05, 0.3), K.mat("test neon", "#FF4000", emit=4.0))
    K.box("grey crate", (3, 0, 0.3), (0.6, 0.6, 0.6), K.mat("test crate", "#888888"))
    ps = fx_lint.scene_problems(list(bpy.context.scene.objects))
    assert len(ps) == 1 and "neon sign" in ps[0] and ps[0].startswith("UNLIT")
    fx_kit.point("far lamp", (0, 9, 1), 50.0)
    assert fx_lint.scene_problems(list(bpy.context.scene.objects)), "a lamp nine metres away is not its lamp"
    fx_kit.glow_light((0, -0.3, 1))
    assert fx_lint.scene_problems(list(bpy.context.scene.objects)) == []


# ---------------------------------------------------------------- the lint
def test_it_fires_on_the_lava_round_that_failed_as_clay_and_blobs():
    s1 = fx_lint.shot_problems(ROUND_1, 1); s5 = fx_lint.shot_problems(ROUND_1, 5)
    said = " ".join(s1)
    for thing, fix in (("street asphalt", "FX.road"), ("far mountain", "FX.ground"), ("fissure glow", "FX.lava_fountain"),
                       ("fissure spatter", "FX.embers"), ("eruption plume", "FX.lava_fountain")):
        assert any(thing in p and fix in p for p in s1), (thing, said)
    assert any("flame" in p and "FX.fire" in p for p in s5) and any("smoke" in p and "FX.smoke_column" in p for p in s5)
    assert any(p.startswith("UNLIT") for p in s5), "seven flame spheres and no lamp: the fire lights nothing"
    assert any(p.startswith("UNLIT") for p in s1), "a glowing fissure with no lamp"


def test_it_does_not_fire_on_the_three_lava_shots_that_passed_the_panel():
    for n in (3, 4, 5):
        assert fx_lint.shot_problems(LAVA, n) == [], f"lava shot {n} passed the panel: the lint must not block it"


def test_a_shot_built_on_the_kit_is_clean_and_a_story_that_rolls_its_own_is_told():
    kit = '''
def shot1():
    FX.sky("dawn"); g = FX.ground("gravel"); FX.road((0, -4), (0, 20))
    FX.house("home", (3, 4, 0)); f = FX.lava_fountain((0, 12, 0)); FX.embers((1, 3, 0))
    K.box("crate", (0, 0, 0.2), (0.4, 0.4, 0.4), K.mat("crate wood", "#886644"))
    return dict(light=lambda: None)
'''
    assert fx_lint.shot_problems(kit, 1) == [] and fx_lint.own_problems(kit) == []
    own = kit + '''

def my_fire(loc):
    return K.sph("blaze ball", loc, 0.4, K.mat("orange", "#FF6600", emit=3.0))
'''
    assert any(p.startswith("OWN") and "my_fire" in p for p in fx_lint.own_problems(own))
    lamp = kit.replace('K.box("crate"', 'K.box("crate", (9, 9, 9), (1, 1, 1), K.mat("sign glow", "#FFAA00", emit=3.0)); K.box("crate"')
    assert fx_lint.shot_problems(lamp, 1) == [], "the kit's emitters are lamps in the shot: UNLIT is for a shot with none"


def test_a_name_that_only_contains_the_word_is_not_the_element():
    for name in ("fire hydrant", "fire hose reel", "smoke alarm", "water tank", "house number", "road sign", "lava bomb", "sky light"):
        assert fx_lint.element_of(name) is None or name == "lava bomb", name
    for name, fx in (("lava bomb splat", "FX.embers"), ("s5 flame 3", "FX.fire"), ("clay smoke", "FX.smoke_column"),
                     ("street asphalt", "FX.road"), ("harbour water", "FX.water"), ("far mountain", "FX.ground")):
        assert fx_lint.element_of(name)[1] == fx, name


def test_the_before_list_only_shrinks():
    for story, why in fx_lint.BEFORE.items():
        assert len(why) > 30, story
        src = (STORE.parent / "stories" / story / "shots.py").read_text()
        shots = [int(k[4:]) for k in fx_lint.functions(src) if re.fullmatch(r"shot\d+", k)]
        assert fx_lint.own_problems(src) or any(fx_lint.shot_problems(src, n) for n in shots), \
            f"{story} no longer builds anything by hand: take it out of fx_lint.BEFORE so the lint binds it"
        assert not fx_lint.held(story)
    assert fx_lint.held("a story written tomorrow")


# ---------------------------------------------------------------- the wiring
def test_the_harness_runs_the_lint_before_the_build_and_measures_the_scene_after_it():
    src = (STORE / "shots.py").read_text()
    pre = src.index("fx_lint.problems(STORY, SHOT)"); built = src.index("S = SHOTS[SHOT]()"); post = src.index("fx_lint.scene_problems(")
    render = src.index("bpy.ops.render.render(")
    assert pre < built < post < render
    for at in (pre, post):
        block = src[at:at + 900]
        assert "raise SystemExit" in block and "fx_lint.held(STORY)" in block and 'os.environ.get("STAGING", "strict") == "strict"' in block
    assert "import fx_kit as FX" in src, "a story reaches the kit as FX in the harness's namespace"


def test_the_reviser_is_given_the_kit_list():
    src = (STORE / "proof_loop.py").read_text()
    assert "fx_kit.brief()" in src[src.index("def revise("):]
