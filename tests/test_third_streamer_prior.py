"""The streamer prior must reward streamers whose clips actually get watched.

`_learned_prior()` decides which streamers get Third's slots. Until
2026-09-22 it judged a clip with >=50 views on RETENTION (AVP over the
channel mean — ratios around 0.6-1.4) and every other clip on
VIEWS-PER-HOUR over the channel median. That median was 0.03, because nearly
every Short gets ~no traffic, so a flop at 0.08 vph scored a 2.7x "win"
against it while a real hit scored ~1.3x on retention. A streamer whose
clips all flopped was judged only on the inflating scale.

Measured on the channel's own analytics that day:

    kaicenat  1.40 (max boost)   median 5 views
    buddha    1.40 (max boost)   median 8 views
    jynxzi    1.25               median 41, top video 1,355, #1 search term

It had no tests, which is how the inversion survived.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load():
    spec = importlib.util.spec_from_file_location(
        "run_third_prior", ROOT / "scripts" / "run_third.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _vid(streamer, views, *, age=100.0, avp=None, usable=None):
    usable = (views >= 50) if usable is None else usable
    return {"streamer": streamer, "is_public": True, "age_hours": age,
            "views": views, "engaged_views": views,
            "views_per_hour": views / age,
            "usable_for_retention": usable,
            "average_view_percentage": avp if avp is not None else 60.0,
            "actual_structure": "clip"}


def _prior(videos):
    m = _load()
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "latest.json"
        f.write_text(json.dumps({"videos": videos}))
        with mock.patch.object(m, "ANALYTICS_LATEST", f):
            m._PRIOR_CACHE = None
            return m._learned_prior()


# A channel shaped like the real one: most Shorts get almost nothing.
BACKGROUND = [_vid(f"filler{i % 6}", v) for i, v in
              enumerate([0, 0, 1, 1, 1, 2, 2, 3, 3, 4, 5, 6] * 2)]


class HitsBeatFlops(unittest.TestCase):
    def test_a_streamer_of_hits_outranks_a_streamer_of_flops(self):
        """The exact inversion: B's clips all flop a little less badly than
        the channel median, A's are genuine hits with ordinary retention."""
        hits = [_vid("hitter", v, avp=70.0) for v in (1355, 300, 226, 200, 90)]
        flops = [_vid("flopper", v) for v in (8, 7, 9, 6, 8)]
        p = _prior(BACKGROUND + hits + flops)
        self.assertGreater(p.get("hitter", 1.0), p.get("flopper", 1.0),
                           f"flops outranked hits: {p}")

    def test_a_streamer_below_the_channel_median_is_not_boosted(self):
        """The prior is RELATIVE — it says 'beat our own median', not 'beat
        some absolute number'. So the invariant is about the median: a
        streamer whose clips all sit below it must not gain slots. (A first
        draft of this test asserted an absolute 'never broke 10 views' bar
        against a background whose median was below 10 — the prior was right
        to call that streamer above average, and the test was wrong.)"""
        background = [_vid(f"filler{i % 6}", v) for i, v in
                      enumerate([12, 15, 18, 20, 22, 25, 30, 35] * 3)]
        flops = [_vid("flopper", v) for v in (8, 7, 9, 6, 8, 5, 9)]
        hits = [_vid("hitter", v, avp=70.0) for v in (1355, 300, 226, 200)]
        p = _prior(background + hits + flops)
        self.assertLess(p.get("flopper", 1.0), 1.0,
                        f"a streamer entirely below the channel median was "
                        f"boosted: {p}")

    def test_retention_still_counts_where_it_is_measurable(self):
        """Kept from the original design: among comparable reach, the
        streamer whose viewers stay should rank higher."""
        stay = [_vid("stayer", v, avp=110.0) for v in (120, 110, 100, 90)]
        leave = [_vid("leaver", v, avp=30.0) for v in (120, 110, 100, 90)]
        p = _prior(BACKGROUND + stay + leave)
        self.assertGreater(p.get("stayer", 1.0), p.get("leaver", 1.0))


class TheOriginalGuardrailsHold(unittest.TestCase):
    def test_the_band_is_still_gentle(self):
        hits = [_vid("hitter", 5000, avp=150.0) for _ in range(20)]
        flops = [_vid("flopper", 0, usable=False) for _ in range(20)]
        p = _prior(BACKGROUND + hits + flops)
        for s, mult in p.items():
            with self.subTest(streamer=s):
                self.assertGreaterEqual(mult, 0.70)
                self.assertLessEqual(mult, 1.40)

    def test_two_clips_are_not_evidence_about_a_streamer(self):
        p = _prior(BACKGROUND + [_vid("rare", 5000, avp=150.0)] * 2)
        self.assertNotIn("rare", p)

    def test_no_snapshot_means_neutral(self):
        m = _load()
        with mock.patch.object(m, "ANALYTICS_LATEST",
                               Path("/nonexistent/latest.json")):
            m._PRIOR_CACHE = None
            self.assertEqual(m._learned_prior(), {})

    def test_young_videos_and_stories_are_excluded(self):
        young = [_vid("fresh", 5000, age=5.0) for _ in range(5)]
        story = [dict(_vid("storyteller", 5000), actual_structure="story")
                 for _ in range(5)]
        p = _prior(BACKGROUND + young + story)
        self.assertNotIn("fresh", p)
        self.assertNotIn("storyteller", p)


class OnTheChannelsOwnNumbers(unittest.TestCase):
    """The committed snapshot, measured — not a fixture shaped to pass."""

    @classmethod
    def setUpClass(cls):
        snap = ROOT / "state" / "analytics_third" / "latest.json"
        if not snap.exists():
            raise unittest.SkipTest("no committed analytics snapshot")
        m = _load()
        m._PRIOR_CACHE = None
        cls.p = m._learned_prior()
        cls.videos = json.loads(snap.read_text()).get("videos", [])

    def test_the_prior_agrees_with_median_views_on_direction(self):
        """For every pair of qualifying streamers whose median views differ
        at least 3x, the prior must not rank the lower one higher."""
        import statistics as st
        med = {}
        for s in self.p:
            vs = [v["views"] for v in self.videos
                  if str(v.get("streamer", "")).lower() == s
                  and (v.get("age_hours") or 0) >= 24]
            if vs:
                med[s] = st.median(vs)
        bad = [(a, b) for a in med for b in med
               if med[a] >= 3 * max(1, med[b]) and self.p[a] < self.p[b]]
        self.assertEqual(bad, [], f"prior inverted against views: {bad} "
                                  f"(prior={self.p}, median views={med})")


if __name__ == "__main__":
    unittest.main()
