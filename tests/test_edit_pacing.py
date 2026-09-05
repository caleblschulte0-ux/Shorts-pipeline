"""The EDIT is monotonic: every cut brings a new subject, and nothing returns.

Three edits have been tried on this channel and the operator refused each in
turn. The rulings, verbatim, because the next session will otherwise re-derive
one of them:

  1. one chart per beat, held 8-20s — "we sit on a fucking one chart as it
     slowly moves for twenty seconds. Like, that's boring."
  2. the same chart re-framed tighter — "the jump cut zoom ins are not it ...
     there is like 4 'things' and then movement, that's not good enough".
  3. two depictions ALTERNATING across the beat — "we'll open on a fucking
     graph, and then we'll cut to a different graph, and then we'll cut back to
     the original graph ... it just does not roll cohesively."

What replaced them: "Once we show a graph and explain it and it does its thing,
it's gone. We move on to the next one."

So the invariants are (a) a beat's depictions are a forward-only sequence with
no repeats, (b) spans tile the beat exactly, and (c) each visual gets long
enough to be read — the other half of the ruling is "we're cutting so much for
no reason", so pacing is bounded from BELOW as well as above.

Runs with pytest OR standalone:
    python3 tests/test_edit_pacing.py
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

from data_learning import studio_render as srd  # noqa: E402
from data_learning import viz_director as vd  # noqa: E402

_SRC = (_REPO / "data_learning" / "studio_render.py").read_text()

# The renderer with every comment line stripped. The prose has to stay free to
# SAY "zoompan" — the comment explaining why the Ken Burns push was removed is
# the thing stopping the next session from adding it back — while the code is
# held to not contain one.
_CODE = "\n".join(l for l in _SRC.splitlines()
                  if not l.lstrip().startswith("#"))

# Beat lengths this channel actually produces, from short to pathological.
_BEATS = (4.0, 6.0, 8.0, 10.5, 14.0, 20.0, 26.0)
_MIN_SPAN = 3.0      # below this the cut is churn, not an edit
_MAX_SPAN = 13.0     # above this it is a hold, not a shot


class _Pt:
    def __init__(self, label, value):
        self.label, self.value = label, value


class _Ins:
    def __init__(self, kind, items):
        self.kind, self.items = kind, items


def _years():
    return _Ins("scene", [_Pt(str(y), y - 2000) for y in range(2019, 2027)])


def _ranking():
    return _Ins("geo_city", [_Pt(n, v) for n, v in
                             (("San Jose", 11.3), ("Los Angeles", 9.7),
                              ("Miami", 8.2), ("Seattle", 6.8))])


class Spans(unittest.TestCase):
    def test_spans_tile_the_beat_exactly(self):
        """Consecutive and gapless. Every visual is built for its own span and
        laid at its own t0, so a gap is a hole in the picture and an overlap is
        two charts on screen at once."""
        for dur in _BEATS:
            for n in (1, 2, 3):
                spans = srd._visual_spans(10.0, 10.0 + dur, n)
                self.assertEqual(len(spans), n)
                self.assertAlmostEqual(spans[0][0], 10.0, places=6)
                self.assertAlmostEqual(spans[-1][1], 10.0 + dur, places=6)
                for a, b in zip(spans, spans[1:]):
                    self.assertAlmostEqual(a[1], b[0], places=6,
                                           msg=f"gap/overlap at {dur}s x{n}")

    def test_a_visual_is_never_a_flash_and_never_a_hold(self):
        for dur in _BEATS:
            kinds = srd._depiction_sequence(_years(), set(), dur)
            for t0, t1 in srd._visual_spans(0.0, dur, len(kinds)):
                self.assertLessEqual(t1 - t0, _MAX_SPAN, f"hold at {dur}s")
                if len(kinds) > 1:
                    self.assertGreaterEqual(t1 - t0, _MIN_SPAN,
                                            f"churn at {dur}s")

    def test_a_short_beat_stays_on_one_visual(self):
        """'we're cutting so much for no reason' — a 4s sentence is one thing,
        not two."""
        self.assertEqual(len(srd._depiction_sequence(_years(), set(), 4.0)), 1)


class Monotonic(unittest.TestCase):
    def test_a_beat_never_shows_the_same_depiction_twice(self):
        """THE PING-PONG. The refused edit was A-B-A-B inside one beat; a
        repeat anywhere in the sequence is that defect returning."""
        for ins in (_years(), _ranking()):
            for dur in _BEATS:
                seq = srd._depiction_sequence(ins, set(), dur)
                self.assertEqual(len(seq), len(set(seq)),
                                 f"{seq} revisits a depiction")

    def test_the_beats_own_chart_opens_and_is_not_repeated(self):
        seq = srd._depiction_sequence(_years(), set(), 20.0)
        self.assertEqual(seq[0], "scene")
        self.assertNotIn("scene", seq[1:])

    def test_longer_beats_earn_more_things(self):
        short = srd._depiction_sequence(_years(), set(), 6.0)
        long = srd._depiction_sequence(_years(), set(), 20.0)
        self.assertGreater(len(long), len(short))

    def test_every_depiction_is_contact_verified(self):
        """STRICT_CONTACT: the host physically attaches to whatever is on
        screen, and he now re-stages on each depiction as it comes up — so a
        kind the coupling does not support would leave him in mid-air."""
        for ins in (_years(), _ranking()):
            for kind in srd._depiction_sequence(ins, set(), 20.0)[1:]:
                self.assertIn(kind, vd._CONTACT_OK, f"{kind!r} unsupported")

    def test_it_prefers_kinds_no_other_beat_has_shown(self):
        seq = srd._depiction_sequence(_years(), {"trend"}, 20.0)
        self.assertNotIn("trend", seq[1:])


class HonestRedraws(unittest.TestCase):
    """More visuals must never be bought with a misleading chart. Widening the
    candidate pool is the obvious lever for "we need 7-8 things", so the limit
    is a test rather than a comment."""

    def test_a_time_series_is_never_drawn_as_a_share_of_a_whole(self):
        """`share`/`waffle_grid` assert the items sum to something. Years do
        not sum, so drawing them that way states something false."""
        for c in srd._alt_candidates_for(_years()):
            self.assertNotIn(c, ("share", "waffle_grid"))

    def test_a_ranking_is_never_drawn_as_a_trend(self):
        """A line asserts an ordered progression; Miami does not come after
        Seattle in any sequence."""
        self.assertNotIn("trend", srd._alt_candidates_for(_ranking()))

    def test_non_geographic_data_never_becomes_a_map(self):
        for ins in (_years(), _ranking()):
            for c in srd._alt_candidates_for(ins):
                self.assertNotIn(c, ("geo_us", "geo_world", "geo_city"))

    def test_the_pool_is_deep_enough_for_a_whole_video(self):
        """8 visuals across 3 beats needs more than 3 candidates per shape —
        with a shallow pool later beats fall back to repeating an earlier
        beat's chart, which is the variety problem in a new place."""
        for shape in ("series", "ranking", "other"):
            self.assertGreaterEqual(len(srd._SHAPE_CANDIDATES[shape]), 5)

    def test_every_candidate_is_contact_verified(self):
        for cands in srd._SHAPE_CANDIDATES.values():
            for c in cands:
                self.assertIn(c, vd._CONTACT_OK)


class TheZoomIsGone(unittest.TestCase):
    """Deleted, not parked. A dead helper gets re-wired by whoever finds it,
    and this one is the literal thing the operator has now refused twice."""

    def test_no_punch_crop_helper_exists(self):
        self.assertFalse(hasattr(srd, "_punch_crop"))

    def test_the_render_graph_contains_no_zoom_or_punch_crop(self):
        for bad in ("zoompan", "_punch_crop", "_shot_plan"):
            self.assertNotIn(bad, _CODE, f"{bad} is back in the renderer")

    def test_the_only_crop_left_is_aspect_fill(self):
        """`crop=W:H` after a scale-to-cover is letterbox removal, not a
        framing choice. A crop with computed offsets is a punch-in."""
        import re as _re
        for m in _re.findall(r"crop=[^\"',\s]+", _CODE):
            self.assertRegex(
                m, r"^crop=\{?[A-Za-z_0-9]*\}?:\{?[A-Za-z_0-9]*\}?$",
                f"{m} looks like a punch-in, not an aspect fill")


class FfmpegShape(unittest.TestCase):
    def test_each_visual_is_consumed_exactly_once(self):
        """ffmpeg consumes a filter output label exactly once. The alternating
        edit needed split= to fan one source across several shots and got it
        wrong first (exit 234, no render at all). One-overlay-per-span makes
        the whole class unrepresentable — so there must be no split= left."""
        blk = _SRC[_SRC.index("ONE OVERLAY PER SPAN"):]
        blk = blk[:blk.index("# Mascots")]
        self.assertNotIn("split=", blk)
        self.assertEqual(blk.count("overlay=x="), 1,
                         "one overlay statement, emitted per span")

    def test_each_build_is_laid_at_its_own_span_start(self):
        """THE FREEZE. Laying every depiction from the BEAT's start is what
        made a short build run out and tpad clone its last frame for 3.0s —
        73 duplicate frames against a ceiling of 45."""
        blk = _SRC[_SRC.index("ONE OVERLAY PER SPAN"):]
        blk = blk[:blk.index("# Mascots")]
        self.assertIn("setpts=PTS-STARTPTS+{t0:.2f}/TB", blk)
        blk2 = _SRC[_SRC.index("THE BEAT'S VISUALS"):]
        blk2 = blk2[:blk2.index("SCENE-ADDRESSABLE")]
        self.assertIn("(t1 - t0) * 30", blk2,
                      "a build must be framed for its OWN span")


if __name__ == "__main__":
    unittest.main(verbosity=2)
