"""FIFTEEN OF TWENTY-FIVE DEPICTIONS HAD NO SHAPE, AND NOTHING SAID SO.

`performance_for` picks the mascot's act by filtering the seventeen verified
performances down to those that support the CLAIM'S SHAPE — a trend, a
two-value comparison, a part-to-whole, a ranking. It gets that shape from
`_SHAPE_OF_KIND`, keyed on the depiction:

    shape = _SHAPE_OF_KIND.get(kind, "ranking")

`viz_director` calls it for every insight with whatever kind it assigned, and
**fifteen of the twenty-five kinds it can emit were not in the table** —
including every SCENE kind, which is what this channel actually renders. All
fifteen silently answered "ranking".

The cost is not nothing: a two-value balance was choosing its act from the
eleven performances that support a ranking, and the eight that support
`two_value` — balance_beam, catch_fall, compare_scales, compressed,
drag_line, pull_down_win, stretched — were never candidates for it at all.

This is the third `dict.get(name, default)` on an unchecked vocabulary found
in two days. The other two cost `decorative_mascot` 147 of this channel's 228
verdicts and the FATAL `junk_imagery` 63 more. CLAUDE.md now states the rule:
a name looked up with a silent default is a capability that does not exist,
and when you add a name to one of these tables you add the test that says it
RESOLVES, in the same change. This is that test.

`ANY` is not a fallback, it is an answer. `scene` and `mechanic` do not HAVE
a shape — the picture is chosen from the data, not from the word "scene" —
and filtering those by a guessed shape throws away most of the catalogue for
no reason. They skip the filter and the claim decides, which is the rule the
rest of `mascot_director` already runs on.

Runs standalone:  python3 tests/test_every_kind_has_a_shape.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import mascot_director as md   # noqa: E402
from data_learning import viz_director as vd      # noqa: E402

SHAPES = {"trend", "two_value", "part_to_whole", "ranking"}


class TheTwoTABLESAgree(unittest.TestCase):
    def test_every_kind_the_director_can_emit_has_a_shape(self):
        missing = sorted(k for k in vd.KINDS if k not in md._SHAPE_OF_KIND)
        self.assertEqual(missing, [],
                         f"kinds that silently become 'ranking': {missing}")

    def test_every_shape_is_a_real_shape_or_ANY(self):
        bad = {k: v for k, v in md._SHAPE_OF_KIND.items()
               if v not in SHAPES and v != md.ANY}
        self.assertEqual(bad, {}, f"unknown shapes: {bad}")

    def test_every_shape_that_is_not_ANY_has_performances(self):
        """A shape no verified performance supports filters to nothing, and
        `performance_for` then falls back to shoved_bar for every beat."""
        for shape in {v for v in md._SHAPE_OF_KIND.values()} - {md.ANY}:
            acts = [n for n, m in md.VERIFIED_PERFORMANCES.items()
                    if shape in m.get("supported_shapes", ())]
            self.assertTrue(acts, f"no performance supports {shape!r}")

    def test_the_chart_only_kinds_are_still_there(self):
        """`charts.py` passes names the director does not use — dropping them
        would recreate the bug from the other side."""
        for k in ("rank", "stack", "bars"):
            self.assertIn(k, md._SHAPE_OF_KIND, k)


class ANYIsAnAnswerNotAFallback(unittest.TestCase):
    def test_scene_and_mechanic_take_ANY(self):
        for k in ("scene", "mechanic"):
            self.assertEqual(md._SHAPE_OF_KIND[k], md.ANY, k)

    def test_ANY_does_not_filter_the_catalogue(self):
        """Every act stays a candidate; the claim's relationships rank them."""
        import inspect
        src = inspect.getsource(md.performance_for)
        self.assertIn("shape != ANY and shape not in", src)

    def test_an_ANY_kind_can_reach_a_performance_a_ranking_cannot(self):
        ranking_only = {n for n, m in md.VERIFIED_PERFORMANCES.items()
                        if "ranking" in m.get("supported_shapes", ())}
        everything = set(md.VERIFIED_PERFORMANCES)
        self.assertTrue(everything - ranking_only,
                        "there is nothing a ranking cannot already reach")


class EveryACTIONNameResolvesToARealPose(unittest.TestCase):
    """The same rule for the other table in this file. `DATA_ACTION` maps a
    chart kind to the act Data performs on it, and `compose_anim` resolves it
    with `ANIMATORS.get(action, _a_carry)` — so a name that is not in the
    vocabulary is silently the generic carry pose.

    `DATA_ACTION["scene"] = "point"` for a month. The vocabulary is
    `point_at`. That entry was WRITTEN to escape the one-pose default — its
    comment says so — and it resolved to the same generic carry pose that
    default produced. `tests/test_edit_pacing.py` asserted only that it was
    not `push_bar`, which it was not.
    """

    def _vocab(self):
        return set(md.ANIMATORS) | set(md.ACTIONS) | {"pose"}

    def test_every_data_action_is_a_real_pose(self):
        bad = {k: v for k, v in md.DATA_ACTION.items()
               if v not in self._vocab()}
        self.assertEqual(bad, {}, f"kinds mapped to a non-existent act: {bad}")

    def test_scene_reaches_an_animator(self):
        act = md.data_action_spec("scene")["action"]
        self.assertIn(act, md.ANIMATORS)

    def test_the_payoff_act_is_real_too(self):
        self.assertIn(md.data_action_spec("scene", "payoff")["action"],
                      self._vocab())

    def test_the_unknown_kind_default_is_a_real_pose(self):
        self.assertIn(md.data_action_spec("no-such-kind")["action"],
                      self._vocab())

    def test_every_rule_in_choose_names_a_real_pose_and_prop(self):
        """`choose()` is the other producer; both its columns are vocabularies
        resolved with a silent default further down."""
        bad_act = sorted({a for _p, (_prop, a, _e) in md._RULES
                          if a not in self._vocab()})
        bad_prop = sorted({prop for _p, (prop, _a, _e) in md._RULES
                           if prop not in md.PROPS})
        self.assertEqual(bad_act, [], f"rules naming no pose: {bad_act}")
        self.assertEqual(bad_prop, [], f"rules naming no prop: {bad_prop}")

    def test_the_renderers_last_resort_is_a_real_pose(self):
        """`studio_render._act` ends with a bare string when nothing else
        answered. It said `"point"` too."""
        import re
        src = (_REPO / "data_learning" / "studio_render.py").read_text()
        i = src.index("def _act(seg, phase=")
        block = src[i:i + 2200]
        lits = re.findall(r'return "([a-z_]+)"', block)
        bad = [x for x in lits if x not in self._vocab()]
        self.assertEqual(bad, [], f"_act can return a non-existent act: {bad}")


class TheSelectorStillWorksForEveryKind(unittest.TestCase):
    def test_every_kind_selects_a_real_verified_performance(self):
        bad = {}
        for kind in sorted(set(vd.KINDS) | set(md._SHAPE_OF_KIND)):
            spec = md.performance_for(kind, "rent climbed past wages", "Rent",
                                      require_contact=True)
            if spec["action"] not in md.VERIFIED_PERFORMANCES:
                bad[kind] = spec["action"]
        self.assertEqual(bad, {}, f"kinds selecting an unknown act: {bad}")

    def test_a_two_value_kind_can_now_reach_a_two_value_act(self):
        """The concrete cost of the old default: `balance_scene` is a
        two-value claim and could only draw from the ranking eleven."""
        two_value = {n for n, m in md.VERIFIED_PERFORMANCES.items()
                     if "two_value" in m.get("supported_shapes", ())}
        seen = {md.performance_for("balance_scene", claim, "A", seed=s)["action"]
                for s in range(6)
                for claim in ("rent outran wages", "it fell by half",
                              "one is double the other")}
        self.assertTrue(seen & two_value,
                        f"balance_scene never reaches a two_value act: {seen}")

    def test_selection_is_still_deterministic(self):
        first = md.performance_for("scene", "it climbed", "A", seed=3)
        for _ in range(4):
            self.assertEqual(
                md.performance_for("scene", "it climbed", "A", seed=3), first)


if __name__ == "__main__":
    unittest.main()
