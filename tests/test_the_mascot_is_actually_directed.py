"""HE WAS NOT BEING DIRECTED BADLY. HE WAS NOT BEING DIRECTED AT ALL.

`decorative_mascot` is an auto-fail, so it takes the story with it, and it was
the largest block class on this channel by a distance: **147 of 228 recorded
verdicts**. The judge described the defect exactly, over and over, for a month:

    "Data holds the same arms-out standing pose while parked on a bar in
     hook@0.8, seg1:mid, seg2:mid, seg3:mid and seg4:end — he relocates but
     never performs a setup->action->payoff tied to the wolf counts"
                                      colorado-wolves-return, 2026-09-07
    "In every scene Data only stands: parked by a bar in hook@0.8, standing on
     the balance pan in seg1:mid, standing inside the yellow capsule in
     seg2:start and seg3:start"       f1-pit-stop-vanishing-act, 2026-09-09
    "he just stands at the right pole holding a clipboard and slides a few
     pixels"                          buybacks-beat-dividends, 2026-09-09

Two `dict.get` defaults, on two vocabularies nobody was checking.

`compose_anim` resolves an action with `ANIMATORS.get(action, _a_carry)`. Of
the six names the scene kit used — `point` (18 machines), `strain` (9),
`cheer` (8), `think` (3), `shock` (1), `climb` (1) — only `cheer` and `climb`
were animators at all. **31 of 41 call sites rendered a pixel-identical carry
pose**, whose entire motion is a 4px sway. Verified by rendering them and
comparing arrays, which is what this file still does.

And the prop: every machine asks for `"prop": "none"`, which was not a key in
`PROPS`, so `PROPS.get(name, price_tag)` handed Data a blank yellow PRICE TAG
in every beat. That is the "clipboard" in the verdict above.

The fix is a ROLE vocabulary that resolves to real animators and rotates
inside the role per story, so five machine beats are five performances. The
guard is the general form of the bug: **every name a machine passes must
resolve, and a silent fallback may not stand in for one that does not.**

Runs standalone:  python3 tests/test_the_mascot_is_actually_directed.py
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import mascot_director as md   # noqa: E402
from data_learning import viz_scene as vs         # noqa: E402

_VIZ = _REPO / "data_learning" / "viz_scene.py"


def _scene_host_act_literals():
    """Every literal act name any machine passes to `scene_host`.

    Read from the AST rather than by regex because several call sites pass a
    conditional — `scene_host("cheer" if cleared else "strain", ...)` — and
    BOTH arms have to resolve.
    """
    tree = ast.parse(_VIZ.read_text())
    names = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "scene_host" and node.args):
            continue
        for sub in ast.walk(node.args[0]):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                names.add(sub.value)
    return names


class EveryNameAMachinePassesMustRESOLVE(unittest.TestCase):
    """The general form. A vocabulary with a silent default is a vocabulary
    nobody is checking, and both halves of this bug were exactly that."""

    def test_every_act_a_machine_asks_for_reaches_a_real_animator(self):
        names = _scene_host_act_literals()
        self.assertGreaterEqual(len(names), 6, "the AST scan found nothing")
        bad = {n: vs.scene_act(n) for n in names
               if vs.scene_act(n) not in md.ANIMATORS}
        self.assertEqual(bad, {}, f"acts that fall back to a carry pose: {bad}")

    def test_every_pose_in_every_role_is_a_real_animator(self):
        bad = {r: [a for a in pool if a not in md.ANIMATORS]
               for r, pool in vs.SCENE_ROLES.items()}
        self.assertEqual({k: v for k, v in bad.items() if v}, {})

    def test_the_scene_kit_asks_for_no_prop_and_gets_no_prop(self):
        self.assertIn("none", md.PROPS)
        self.assertEqual(md.PROPS["none"](100, 100), "")

    def test_every_prop_the_scene_kit_names_exists(self):
        import inspect
        src = inspect.getsource(vs.scene_host)
        for tok in ('"prop": "', "'prop': '"):
            i = src.find(tok)
            if i < 0:
                continue
            name = src[i + len(tok):src.index(tok[-1], i + len(tok))]
            self.assertIn(name, md.PROPS, f"prop {name!r} is not a prop")


class THIRTYONECallSitesRenderedTheSameSprite(unittest.TestCase):
    """The regression oracle, measured rather than argued: the four broken
    roles were pixel-identical to the carry pose and to each other."""

    PHASE = 0.55

    def _arr(self, act):
        import numpy as np
        img = vs.scene_host(act, self.PHASE)
        self.assertIsNotNone(img, act)
        return np.asarray(img.convert("RGBA"), dtype="int16")

    def test_no_role_renders_the_carry_pose(self):
        import numpy as np
        carry = self._arr("carry")
        same = []
        for role in vs.SCENE_ROLES:
            a = self._arr(role)
            if a.shape == carry.shape and bool(np.array_equal(a, carry)):
                same.append(role)
        self.assertEqual(same, [], f"roles still rendering a carry pose: {same}")

    def test_the_six_roles_are_six_different_pictures(self):
        import numpy as np
        seen = {}
        for role in vs.SCENE_ROLES:
            a = self._arr(role)
            key = (a.shape, hash(a.tobytes()))
            self.assertNotIn(key, seen,
                             f"{role} renders the same frame as {seen.get(key)}")
            seen[key] = role

    def test_he_MOVES_across_the_beat(self):
        """A pose that is identical at the start, middle and end of a beat is
        a sticker whatever it depicts — and that is half of what the cadence
        gate measures too."""
        import numpy as np
        still = []
        for role in vs.SCENE_ROLES:
            frames = [self._arr_at(role, p) for p in (0.15, 0.5, 0.9)]
            if all(f.shape == frames[0].shape for f in frames) and \
                    all(np.array_equal(f, frames[0]) for f in frames[1:]):
                still.append(role)
        self.assertEqual(still, [], f"roles frozen across the beat: {still}")

    def _arr_at(self, act, phase):
        import numpy as np
        img = vs.scene_host(act, phase)
        return np.asarray(img.convert("RGBA"), dtype="int16")


class FiveBeatsAreFivePERFORMANCES(unittest.TestCase):
    """"He relocates but never performs" was also literally true across beats:
    18 machines asked for `point`, so one video's five machine beats were the
    same sprite five times."""

    def test_a_role_spreads_across_its_pool_over_a_slate_of_machines(self):
        from tests._machine_samples import SAMPLES
        for role, pool in vs.SCENE_ROLES.items():
            if len(pool) < 2:
                continue
            picked = {vs.scene_act(role, ins, kind)
                      for kind, ins in SAMPLES.items()}
            self.assertGreater(
                len(picked), 1,
                f"role {role!r} always picks the same act: {picked}")

    def test_the_pick_is_DETERMINISTIC(self):
        """A re-render must be identical, or a diff of two runs means
        nothing and the cache below is a lie."""
        from tests._machine_samples import SAMPLES
        ins = next(iter(SAMPLES.values()))
        for role in vs.SCENE_ROLES:
            first = vs.scene_act(role, ins, "burden")
            for _ in range(4):
                self.assertEqual(vs.scene_act(role, ins, "burden"), first)

    def test_no_insight_still_gives_a_real_performance(self):
        """The fallback must be a pose, never the silent carry."""
        for role, pool in vs.SCENE_ROLES.items():
            self.assertEqual(vs.scene_act(role), pool[0])
            self.assertIn(vs.scene_act(role), md.ANIMATORS)

    def test_a_raw_animator_name_still_passes_through(self):
        """`draw_burden` names `hoist_stack` directly and `draw_hurdle` picks
        cheer-or-strain from whether the number cleared the bar. Roles and
        animator names must not collide."""
        self.assertEqual(vs.scene_act("hoist_stack"), "hoist_stack")
        self.assertEqual(set(vs.SCENE_ROLES) & set(md.ANIMATORS),
                         {"cheer", "climb"},
                         "a role name shadows a different animator")


class WhereThereIsNoCAIROThereIsStillAMascot(unittest.TestCase):
    """`compose_anim` rasterises through cairosvg. Where libcairo2 is not
    installed it raises and the kit falls back to the eight committed pose
    PNGs — cheer, duck, idle, laugh, point, ride, shock, think — which is
    where the ROLE names came from in the first place.

    So the fallback has to be keyed on the ROLE, not on the animator it
    resolves to: `compose_anim` wants `point_at`, `_host_pose` wants `point`,
    and asking the PNG set for `point_at` finds no file and returns None —
    which is indistinguishable from a machine that deliberately draws no host.

    `strain` and `climb` never had a file at all, so wherever cairosvg cannot
    run, ten machines drew NO MASCOT and nothing said so. It surfaced when the
    in-box void gate passed locally and failed in CI on exactly the five
    machines that lean on the host to fill their lower band.

    The `tests` job installs cairosvg and libcairo2 now, so CI measures the
    render that actually ships. This holds the fallback anyway — a render
    environment losing its mascot silently is the failure worth keeping shut.
    """

    ROLES = ("point", "strain", "think", "shock", "cheer", "climb")

    def test_every_role_has_a_pose_png_to_fall_back_on(self):
        from data_learning import charts
        missing = [r for r in self.ROLES
                   if charts._host_pose(vs._ROLE_PNG.get(r, r)) is None]
        self.assertEqual(missing, [], f"roles with no mascot at all: {missing}")

    def test_the_fallback_is_keyed_on_the_ROLE_not_the_animator(self):
        import inspect
        src = inspect.getsource(vs.scene_host)
        self.assertIn("_host_pose(_ROLE_PNG.get(role", src)

    def test_the_ci_test_job_installs_the_rasteriser(self):
        """Otherwise every visual test in CI measures a render that does not
        ship, and the two disagree in a way nobody can reproduce locally."""
        wf = (_REPO / ".github" / "workflows" / "auto-merge.yml").read_text()
        job = wf[wf.index("\n  tests:"):]
        self.assertIn("cairosvg", job)
        self.assertIn("libcairo2", job)


class NoMachineLostItsHost(unittest.TestCase):
    """Wiring 41 call sites by script is exactly how a machine ends up with no
    mascot at all."""

    def test_every_machine_that_had_a_host_still_draws_one(self):
        import numpy as np
        from PIL import Image, ImageDraw
        from data_learning import charts
        from tests._machine_samples import SAMPLES
        box = (vs.RX0, vs.RTOP, vs.RX1, vs.MACHINE_BOT)
        drew = []
        for kind, ins in SAMPLES.items():
            if kind not in vs._MACHINE_DRAW:
                continue
            safe = vs.drawable_insight(ins)
            if safe is None:
                continue
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            got = vs._guarded(kind, vs._MACHINE_DRAW[kind], d, img, box, safe,
                              charts.HIGHLIGHT, 0.95, safe.unit)
            if got is not None:
                drew.append(kind)
        self.assertGreaterEqual(len(drew), 30, "machines stopped drawing")

    def test_no_machine_raises_after_the_rewiring(self):
        from PIL import Image, ImageDraw
        from data_learning import charts
        from tests._machine_samples import SAMPLES
        box = (vs.RX0, vs.RTOP, vs.RX1, vs.MACHINE_BOT)
        saved = set(vs._MACHINE_FAILED)
        vs._MACHINE_FAILED.clear()
        try:
            for kind, ins in SAMPLES.items():
                if kind not in vs._MACHINE_DRAW:
                    continue
                safe = vs.drawable_insight(ins)
                if safe is None:
                    continue
                img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
                vs._guarded(kind, vs._MACHINE_DRAW[kind], ImageDraw.Draw(img),
                            img, box, safe, charts.HIGHLIGHT, 0.95, safe.unit)
            self.assertEqual(sorted(vs._MACHINE_FAILED), [])
        finally:
            vs._MACHINE_FAILED.clear()
            vs._MACHINE_FAILED.update(saved)


if __name__ == "__main__":
    unittest.main()
