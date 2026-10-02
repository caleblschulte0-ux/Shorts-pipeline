"""DATA IS THE CAUSE OF THE DATA'S MOTION.

Operator, 2026-10-01, watching a tank fill while Data sat on a raft on the
water:

    "this jar of water raises up bit by bit, right? And what's our guy do?
     Sits there and flails his arms like always. Why doesn't he have a thing
     of water in his hands? And he's pouring water into it. And he's the one
     that's making the water rise. ... let's say we're doing a race car thing
     ... he would be the one driving the race car."

The judge had been saying it for a fortnight, 203 `decorative_mascot`
auto-fails since 2026-09-18:

    "stands with arms out beside the draining tank doing nothing to it"
                                           amazon-still-shrinking, 2026-09-22
    "He sits on the scale's 2025 pan, but his weight is not what tips it"
                                    the-biggest-lightest-workforce, 2026-09-30
    "rides the fill edge ... in one repeated hands-on-head pose"
                                            global-ewaste-crisis, 2026-09-30

Every `scene_host` role is a REACTION to the picture. The fix is a second
vocabulary — `mascot_director.AGENT_ACTS`, keyed on what the moving part DOES
(fill, stack, turn, lift, drain ...) — whose acts put his hands on the part at
a declared anchor, and `viz_scene.AGENCY`, where every machine says which of
three things is true of him: he causes the motion, he IS the moving part, or
the data acts on him and that is the claim. There is no fourth state.

Three kinds of check, because the first two caught nothing on their own the
last time a mascot vocabulary rotted (`test_the_mascot_is_actually_directed`):
the table is complete in both directions; every agent machine really calls
`place_agent` and not a reaction role; and his anchor is MEASURED to land on
pixels that move.

Runs standalone:  python3 tests/test_data_is_the_cause.py
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "tests") not in sys.path:
    sys.path.insert(0, str(_REPO / "tests"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import mascot_director as md   # noqa: E402
from data_learning import viz_scene as vs         # noqa: E402

_VIZ = _REPO / "data_learning" / "viz_scene.py"
_ILL = _REPO / "data_learning" / "illustrated.py"
_CHARTS = _REPO / "data_learning" / "charts.py"


def _calls(src: str, name: str):
    """Every `name(...)` call in `src`, as AST nodes."""
    out = []
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == name):
            out.append(node)
    return out


def _wrists(svg: str):
    """Where his two ARMS end: the 32px-stroke limb paths' last point."""
    import re
    return [(float(x), float(y)) for x, y in re.findall(
        r'd="M[^"]*? ([-\d.]+),([-\d.]+)" fill="none" stroke="[^"]+" '
        r'stroke-width="32"', svg)]


def _kind_arg(call, pos: int, kw: str):
    for k in call.keywords:
        if k.arg == kw and isinstance(k.value, ast.Constant):
            return k.value.value
    if len(call.args) > pos and isinstance(call.args[pos], ast.Constant):
        return call.args[pos].value
    return None


class EveryMachineDeclaresWhatHeIsToIt(unittest.TestCase):
    def test_every_machine_is_in_the_table(self):
        for kind in vs._MACHINE_DRAW:
            self.assertIn(kind, vs.AGENCY, f"{kind} says nothing about him")

    def test_every_entry_is_a_machine_or_an_element_that_hosts(self):
        src = _VIZ.read_text()
        hosted = {_kind_arg(c, 3, "kind") for c in _calls(src, "scene_host")}
        hosted |= {_kind_arg(c, 5, "kind") for c in _calls(src, "place_agent")}
        hosted |= {_kind_arg(c, 5, "kind")
                   for c in _calls(_CHARTS.read_text(), "_place_agent")}
        for kind in vs.AGENCY:
            self.assertTrue(kind in vs._MACHINE_DRAW or kind in hosted,
                            f"{kind} is in AGENCY but nothing draws him there")

    def test_there_is_no_fourth_state(self):
        for kind, (rel, what) in vs.AGENCY.items():
            self.assertIn(rel, ("agent", "self", "patient"), kind)
            self.assertTrue(isinstance(what, str) and what, kind)
            if rel != "agent":
                # a reason, not a word — "patient" with no why is a loophole
                self.assertGreater(len(what.split()), 4, f"{kind}: say why")

    def test_the_exceptions_are_few(self):
        """He causes the motion in all but a handful of pictures. If this
        number grows, the handful is becoming the rule."""
        others = [k for k, (r, _w) in vs.AGENCY.items() if r != "agent"]
        self.assertLessEqual(len(others), 5, others)


class EveryVerbResolvesToAnActWithAnAnchor(unittest.TestCase):
    def test_every_agent_verb_in_the_table_is_an_act(self):
        for kind, (rel, verb) in vs.AGENCY.items():
            if rel == "agent":
                for v in verb.split("/"):        # "stack/travel": one per shape
                    self.assertIn(v, md.AGENT_ACTS, f"{kind}: {v!r}")

    def test_every_act_is_a_real_animator(self):
        for verb, (act, anchor) in md.AGENT_ACTS.items():
            self.assertIn(act, md.ANIMATORS, verb)
            self.assertEqual(len(anchor), 2, verb)

    def test_an_unknown_verb_is_refused_not_carried(self):
        self.assertIsNone(md.agent_act("levitate"))
        self.assertIsNone(md.agent_point("levitate", 0.5))
        img, a, t = vs.scene_agent("levitate", 0.5)
        self.assertIsNone(img)

    def test_the_anchor_is_where_the_hands_are(self):
        """The anchor is a HAND position during the effort zone, within a
        hand's reach — not a point in empty air the machine then pins to the
        part. Checked against the animator's own wrist coordinates."""
        import re
        # A TOOL act's anchor is the tool's BUSINESS END at the moment it
        # lands (2026-10-02: the pick on the ice) — a handle's length from
        # the hands, measured when the strike has landed, not mid-swing.
        tools = ("swing_pick", "chop", "hammer", "dig", "pump", "broom", "paddle")
        for verb, (act, (ax, ay)) in md.AGENT_ACTS.items():
            if verb in ("travel", "run", "lift"):
                continue          # wheels on the ground / feet / the rope
            phase, reach = (0.98, 230.0) if act in tools else (0.5, 100.0)
            svg = md.compose_anim({"action": act, "prop": "none",
                                   "ground": False}, phase)
            # every arm ends at its wrist: `Q... wx,wy"` in `limb()`
            wrists = _wrists(svg)
            self.assertTrue(wrists, verb)
            near = min(((wx - ax) ** 2 + (wy - ay) ** 2) ** 0.5
                       for wx, wy in wrists)
            self.assertLess(near, reach, f"{verb}: anchor {near:.0f}px from "
                                         f"the nearest hand")
            if act in tools:
                self.assertGreater(near, 40.0, f"{verb}: a tool anchor sits on "
                                               f"the tool's head, not in the hand")

    def test_the_acts_are_different_pictures(self):
        import io
        from PIL import Image, ImageChops
        seen = {}
        for verb, (act, _a) in md.AGENT_ACTS.items():
            svg = md.compose_anim({"action": act, "prop": "none",
                                   "ground": False}, 0.5)
            im = Image.open(io.BytesIO(md._rasterise(svg, 160))).convert("RGBA")
            for other, oim in seen.items():
                diff = ImageChops.difference(im, oim).getbbox()
                self.assertIsNotNone(diff, f"{verb} renders as {other}")
            seen[verb] = im

    def test_the_payoff_is_done_not_a_cheer(self):
        """An agent act must be honest over bad news: he finishes, he does
        not celebrate. No act's payoff frame is the overhead cheer."""
        import re
        for verb, (act, _a) in md.AGENT_ACTS.items():
            if verb == "run":
                continue
            svg = md.compose_anim({"action": act, "prop": "none",
                                   "ground": False}, 0.97)
            arms_up = sum(1 for _x, y in _wrists(svg) if y < 110)
            self.assertLess(arms_up, 2, f"{verb} ends in a cheer")


class AgentMachinesPutHisHandsOnThePart(unittest.TestCase):
    """AST: an agent machine calls `place_agent` with its own kind and never
    asks `scene_host` for a reaction role."""

    def test_every_agent_machine_calls_place_agent(self):
        src = _VIZ.read_text()
        placed = {_kind_arg(c, 5, "kind") for c in _calls(src, "place_agent")}
        placed |= {_kind_arg(c, 5, "kind")
                   for c in _calls(_CHARTS.read_text(), "_place_agent")}
        for kind, (rel, _v) in vs.AGENCY.items():
            if rel == "agent" and kind not in vs.AGENT_BY_OTHER_MEANS:
                self.assertIn(kind, placed, f"{kind} is an agent on paper")

    def test_no_agent_machine_asks_for_a_reaction(self):
        src = _VIZ.read_text()
        reacting = {_kind_arg(c, 3, "kind") for c in _calls(src, "scene_host")}
        for kind, (rel, _v) in vs.AGENCY.items():
            if rel == "agent" and kind not in vs.AGENT_BY_OTHER_MEANS:
                self.assertNotIn(kind, reacting,
                                 f"{kind} still poses him beside the part")

    def test_the_verb_a_machine_uses_is_the_one_it_declares(self):
        src = _VIZ.read_text()
        for c in _calls(src, "place_agent"):
            kind = _kind_arg(c, 5, "kind")
            verb = _kind_arg(c, 2, "verb")
            if kind in vs.AGENCY and verb is not None \
                    and vs.AGENCY[kind][0] == "agent":
                self.assertIn(verb, vs.AGENCY[kind][1].split("/"), kind)

    def test_the_illustrated_drawings_are_agents_too(self):
        src = _ILL.read_text()
        for fn in ("draw_tank", "draw_columns", "draw_ridge"):
            body = src[src.index(f"def {fn}("):]
            body = body[:body.index("\ndef ", 10)]
            self.assertIn('("agent", "', body, fn)

    def test_the_gauge_ring_is_pushed_not_ridden(self):
        src = _CHARTS.read_text()
        body = src[src.index("def _render_fill_vessel("):]
        body = body[:body.index("\n@_fullframe", 10)]
        self.assertNotIn('_host_pose("cheer")', body)
        self.assertIn('"sweep"', body)


def _moving_blobs(a, b, cell=24, thresh=18):
    """Coarse connected regions where frames a and b differ: a list of
    (area_cells, (x0, y0, x1, y1)) in pixels, biggest first."""
    import numpy as np
    from PIL import ImageChops
    diff = np.asarray(ImageChops.difference(a.convert("L"), b.convert("L")))
    H, W = diff.shape
    gh, gw = H // cell, W // cell
    grid = diff[:gh * cell, :gw * cell].reshape(gh, cell, gw, cell).mean(axis=(1, 3))
    on = grid > thresh
    seen = set()
    blobs = []
    for r in range(gh):
        for c in range(gw):
            if not on[r, c] or (r, c) in seen:
                continue
            stack, cells = [(r, c)], []
            seen.add((r, c))
            while stack:
                rr, cc = stack.pop()
                cells.append((rr, cc))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = rr + dr, cc + dc
                    if 0 <= nr < gh and 0 <= nc < gw and on[nr, nc] \
                            and (nr, nc) not in seen:
                        seen.add((nr, nc))
                        stack.append((nr, nc))
            rs = [x[0] for x in cells]
            cs = [x[1] for x in cells]
            blobs.append((len(cells), (min(cs) * cell, min(rs) * cell,
                                       (max(cs) + 1) * cell, (max(rs) + 1) * cell)))
    blobs.sort(reverse=True)
    return blobs


def _dist_to_box(p, box):
    x, y = p
    x0, y0, x1, y1 = box
    dx = max(x0 - x, 0, x - x1)
    dy = max(y0 - y, 0, y - y1)
    return (dx * dx + dy * dy) ** 0.5


class HisAnchorLandsOnPixelsThatMove(unittest.TestCase):
    """MEASURED. Each agent machine is rendered twice, a little apart in the
    beat, WITHOUT him; the biggest region that changed between the two
    frames is the moving part (a count-up digit is a small blob; a block
    dropping, a level rising, a needle sweeping is a big one). The anchor
    the machine handed `place_agent` must be on or next to it — or, for a
    pour, directly above it, because that is where you pour from.

    A machine that put his hands "near the picture" would pass a source
    test and fail this one, which is the point of it."""

    REACH = 130          # px from the anchor to the moving region
    AT = (0.36, 0.44)    # two reveals inside the build, where parts move

    def _render(self, kind, ins, reveal):
        from unittest import mock
        from PIL import Image, ImageDraw
        from data_learning import charts
        canvas = Image.new("RGBA", (1080, 1920), (18, 20, 28, 255))
        d = ImageDraw.Draw(canvas)
        box = (vs.RX0, vs.RTOP, vs.RX1, vs.MACHINE_BOT)
        del vs._AGENT_LOG[:]
        with mock.patch.object(vs, "scene_agent",
                               lambda *a, **k: (None, None, None)):
            vs._BEAT_PHASE = reveal
            try:
                got = vs._MACHINE_DRAW[kind](d, canvas, box, ins,
                                             charts.HIGHLIGHT, reveal, ins.unit)
            finally:
                vs._BEAT_PHASE = None
        at = [e[2] for e in vs._AGENT_LOG if e[0] == kind]
        return got, canvas, (at[-1] if at else None)

    def test_every_agent_machine(self):
        try:
            import numpy  # noqa: F401
        except ImportError:  # noqa: BLE001
            self.skipTest("numpy not installed")
        from _machine_samples import SAMPLES
        failures = []
        for kind, (rel, verb) in sorted(vs.AGENCY.items()):
            if rel != "agent" or kind not in vs._MACHINE_DRAW:
                continue
            ins = SAMPLES.get(kind)
            if ins is None:
                failures.append(f"{kind}: no sample to measure with")
                continue
            got_a, a, at_a = self._render(kind, ins, self.AT[0])
            got_b, b, _at_b = self._render(kind, ins, self.AT[1])
            if got_a is None or got_b is None:
                failures.append(f"{kind}: refused the sample")
                continue
            if at_a is None:
                failures.append(f"{kind}: never called place_agent")
                continue
            blobs = _moving_blobs(a, b)
            if not blobs:
                failures.append(f"{kind}: nothing moves between the frames")
                continue
            # the parts: every region of at least two cells (a road dash, a
            # box on a belt); single changed cells are noise
            parts = [bx for n, bx in blobs if n >= 2]
            dists = [_dist_to_box(at_a, bx) for bx in parts]
            ok = min(dists) <= self.REACH
            if not ok and verb in ("fill", "drain"):
                # what flows, flows VERTICALLY: he pours from above the level
                # and opens the tap below it — so for these the anchor is in
                # the part's x-range, not on it
                ok = any(bx[0] - 60 <= at_a[0] <= bx[2] + 60 for bx in parts)
            if not ok:
                failures.append(f"{kind} ({verb}): anchor {at_a} is "
                                f"{min(dists):.0f}px from the moving part "
                                f"{parts[0]}")
        self.assertFalse(failures, "\n".join(failures))


class HeStandsOnSomething(unittest.TestCase):
    def test_a_part_above_his_reach_gets_a_ladder(self):
        from PIL import Image, ImageDraw
        canvas = Image.new("RGBA", (1080, 1920), (18, 20, 28, 255))
        d = ImageDraw.Draw(canvas)
        before = canvas.copy()
        box, _tip = vs.place_agent(canvas, d, "fill", 0.5, None, "t",
                                   (500, 300), height=240, floor=1500)
        if box is None:
            self.skipTest("no rasteriser")
        # ink between his feet and the floor — the ladder
        from PIL import ImageChops
        strip = ImageChops.difference(
            canvas.crop((box[0], box[3] + 20, box[2], 1500)),
            before.crop((box[0], box[3] + 20, box[2], 1500))).getbbox()
        self.assertIsNotNone(strip, "no ladder under him")
        self.assertLess(box[3], 1500 - 100)

    def test_a_part_at_hand_height_needs_no_ladder(self):
        from PIL import Image, ImageDraw, ImageChops
        canvas = Image.new("RGBA", (1080, 1920), (18, 20, 28, 255))
        d = ImageDraw.Draw(canvas)
        before = canvas.copy()
        box, _tip = vs.place_agent(canvas, d, "sweep", 0.5, None, "t",
                                   (500, 1420), height=240, floor=1500)
        if box is None:
            self.skipTest("no rasteriser")
        self.assertLessEqual(abs(box[3] - 1500), 16, box)
        if box[3] + 20 < 1500:
            strip = ImageChops.difference(
                canvas.crop((0, box[3] + 20, 1080, 1500)),
                before.crop((0, box[3] + 20, 1080, 1500))).getbbox()
            self.assertIsNone(strip, "a ladder where his feet are on the floor")

    def test_the_tip_is_where_the_stream_starts(self):
        """The bucket's lip is to the right of and below the grip while he
        pours — so a stream drawn from the tip leaves the bucket, not his
        hand."""
        g, a, lip = md._pour_geom(0.5)
        self.assertGreater(a, 60.0)
        self.assertGreater(lip[0], g[0] + 30)
        self.assertGreater(lip[1], g[1] + 30)


if __name__ == "__main__":
    unittest.main()
