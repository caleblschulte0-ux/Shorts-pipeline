"""Work is done WITH THE TOOL, in one arc — never a flail.

Operator, 2026-10-02: "data's movements are like tweaker ... there is one
scene where he is breaking the iceberg and he is just flailing his arms
around. Give him like a pick axe and have it feel like he is breaking the
ice." A brain scene could only ask for `strain`, which resolves to a brace
or a stagger: arms, no tool, no contact. Held here:

  * every tool act resolves to a real animator, renders, and moves through
    distinct phases (wind up, strike, hold) with no periodic term;
  * every verb in the CAUSE table maps to a tool act, and the agent anchor
    of each tool verb is where its business end lands;
  * the verifier refuses a scene whose CAUSE names work done empty-handed,
    and accepts the same scene once the tool is in his hands;
  * a scene lands one act per `beat`: the act clock restarts when the beat
    advances, and the renderer's host passes `beat` through;
  * the brain is told the tools, the beat mechanic and the rule.
"""
from __future__ import annotations

import inspect
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import mascot_director as md  # noqa: E402

try:
    import cairo  # noqa: F401
    HAVE_CAIRO = True
except Exception:  # noqa: BLE001
    HAVE_CAIRO = False

NEW_TOOLS = ("swing_pick", "chop", "hammer", "dig", "pump", "broom", "paddle")


class EveryToolActIsReal(unittest.TestCase):
    def test_every_tool_act_is_an_animator_and_every_verb_has_a_tool(self):
        for act in md.TOOL_ACTS:
            self.assertIn(act, md.ANIMATORS, act)
        for verb, act in md.VERB_TOOLS.items():
            self.assertIn(act, md.TOOL_ACTS, verb)
        self.assertNotIn("strain", md.TOOL_ACTS)

    def test_the_cause_line_names_the_tool(self):
        self.assertEqual(md.tool_for_cause("Data breaks the ice with each swing"),
                         ("break", "swing_pick"))
        self.assertEqual(md.tool_for_cause("he is chopping the trunk"), ("chop", "chop"))
        self.assertEqual(md.tool_for_cause("Data pumps a bellows at the burn line"),
                         ("pump", "pump"))
        self.assertIsNone(md.tool_for_cause("Data runs the treeline ahead of the saws that fell one tree"))
        self.assertIsNone(md.tool_for_cause("the drought cracks the ground as Data strains to hold it"))
        self.assertEqual(md.tool_for_cause("Data climbs a ladder and pours ash into the urn"),
                         ("pour", "pour"))
        self.assertIsNone(md.tool_for_cause("the scar's rim advances a ring per year and shoves Data outward"))

    def test_no_tool_act_rides_a_sine(self):
        for act in NEW_TOOLS + ("stagger_under",):
            src = inspect.getsource(md.ANIMATORS[act])
            self.assertNotIn("_s(t", src, act)
            self.assertNotIn("_gesture(", src, act)
        self.assertNotIn("_s(t", inspect.getsource(md._swing))

    def test_the_agent_anchor_is_the_business_end(self):
        """The AGENT_ACTS anchor for a tool verb is where the tool lands at
        the end of the strike, so a machine can put the pick ON the ice."""
        for verb in ("break", "chop", "smash", "dig"):
            act, anchor = md.AGENT_ACTS[verb]
            self.assertIn(act, md.TOOL_ACTS)
            got = md.agent_point(verb, 0.98)
            self.assertIsNotNone(got)
            self.assertLess(abs(got[0] - anchor[0]) + abs(got[1] - anchor[1]), 40, (verb, got, anchor))


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheToolMovesThroughOneArc(unittest.TestCase):
    def test_each_tool_act_renders_three_different_frames_and_holds(self):
        from data_learning import viz_scene as vs
        for act in NEW_TOOLS:
            ims = [vs.scene_host(act, ph) for ph in (0.1, 0.5, 0.95)]
            self.assertTrue(all(i is not None for i in ims), act)
            self.assertEqual(len({i.tobytes() for i in ims}), 3, f"{act} does not move")

    def test_the_tool_is_in_the_picture(self):
        """The strike frame is wider or taller than the bare stance: there
        is a tool in his hands, not just arms."""
        from data_learning import viz_scene as vs
        bare = vs.scene_host("hold_up", 0.5)
        for act in ("swing_pick", "chop", "broom", "paddle"):
            im = vs.scene_host(act, 0.5)
            self.assertGreater(im.width * im.height, bare.width * bare.height * 0.9, act)


ICE = '''
def scene(cr, t, u, pts, host):
    """HERO: an iceberg
    SUBSTANCE: ice
    CAUSE: Data breaks the ice, one swing per crack
    """
    rows = by_time([(str(l), float(v)) for l, v in pts])
    vgrad(cr, [(0.0, (30, 30, 60)), (1.0, (10, 10, 20))], 0, H)
    heat_shimmer(cr, t, 600, 1500, a=0.3)
    lab, val = rows[-1]
    fit_readout(cr, f"{val:.1f}", lab, 80, 520)
    host("point" if u < 0.2 else ROLE, 300 + 400 * u, 1500, 220, beat=int(u * 4))
'''


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheVerifierRefusesEmptyHandedWork(unittest.TestCase):
    PTS = [["2019", 1.05], ["2025", 4.41]]

    def _problems(self, role):
        from data_learning import scene_author as SA
        fn = SA.compile_scene(ICE.replace("ROLE", repr(role)))
        return SA.verify(fn, self.PTS)

    def test_strain_on_a_job_is_refused_and_names_the_tool(self):
        probs = self._problems("strain")
        hit = [p for p in probs if "empty hands" in p]
        self.assertTrue(hit, probs)
        self.assertIn("swing_pick", hit[0])
        self.assertIn("a pickaxe", hit[0])
        self.assertIn("beat=", hit[0])

    def test_the_pick_in_his_hands_passes(self):
        probs = self._problems("swing_pick")
        self.assertEqual([p for p in probs if "empty hands" in p], [])
        self.assertEqual(probs, [])

    def test_a_cause_with_no_work_verb_asks_for_no_tool(self):
        from data_learning import scene_author as SA
        code = ICE.replace("CAUSE: Data breaks the ice, one swing per crack",
                           "CAUSE: Data runs the treeline ahead of the saws")
        fn = SA.compile_scene(code.replace("ROLE", "'strain'"))
        self.assertEqual([p for p in SA.verify(fn, self.PTS) if "empty hands" in p], [])


class OneActPerBeat(unittest.TestCase):
    def test_the_act_clock_restarts_when_the_beat_advances(self):
        from data_learning import subject_scenes as SS
        clock = {}
        self.assertEqual(SS.act_phase(clock, ("swing_pick", 0), 0), 0.0)
        late = SS.act_phase(clock, ("swing_pick", 0), 200)
        self.assertEqual(late, 1.0)                        # played, holding
        self.assertEqual(SS.act_phase(clock, ("swing_pick", 1), 200), 0.0)   # swings again

    def test_the_renderer_passes_beat_through(self):
        from data_learning import subject_scenes as SS
        src = inspect.getsource(SS._render_frames)
        self.assertIn("beat=0", src)
        self.assertIn("(role, int(beat))", src)


class TheBrainIsToldHowToWork(unittest.TestCase):
    def test_the_prompt_carries_the_tools_the_beat_and_the_rule(self):
        from data_learning import scene_author as SA
        prompt = SA.build_prompt("t", "x", "y", [["a", 1.0]], "")
        self.assertIn("PURPOSEFUL MOVEMENT, NEVER FLAILING", prompt)
        self.assertIn("beat=0", prompt)
        for act, tool in md.TOOL_ACTS.items():
            self.assertIn(f"{act}: {tool}", prompt)
        self.assertNotIn("{roles}", prompt)

    def test_every_tool_act_is_a_role_the_verifier_accepts(self):
        from data_learning import scene_author as SA
        for act in md.TOOL_ACTS:
            self.assertIn(act, SA.ROLES)
            self.assertIn(act, SA.ACT_ROLES)

    def test_every_tool_act_has_a_pose_png_to_fall_back_on(self):
        from data_learning import charts, viz_scene as vs
        missing = [a for a in md.TOOL_ACTS
                   if charts._host_pose(vs._ROLE_PNG.get(a, a)) is None]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
