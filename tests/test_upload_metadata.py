"""What we actually send to YouTube — title, description, hashtags, QA.

Every bug pinned here shipped silently for months, because an upload that
succeeds looks identical to an upload that succeeds WELL. Nothing in the
pipeline read its own description back.

    python -m unittest tests.test_upload_metadata -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))   # APPEND: see note below

import run_trending_daily as rtd                    # noqa: E402
from shared import video_qa                         # noqa: E402

REDDIT = {"slug": "r", "subreddit": "pettyrevenge", "title": "A Real Title",
          "script": "My neighbour kept parking in my spot. So I called.",
          "hashtags": [f"tag{i}" for i in range(15)]}
GRAPH = {"format": "graph_race", "slug": "g", "title": "A vs B: By Year",
         "y_label": "Subscribers (millions)", "years": [2019, 2024],
         "source": "Sources: company filings",
         "series": [{"name": "Netflix", "values": [1, 2]},
                    {"name": "Disney+", "values": [0, 3]}],
         "hashtags": [f"tag{i}" for i in range(15)]}
TEXT_CARD = {"format": "text_card", "slug": "t", "title": "Chips Are Shrinking",
             "text": "Bags of chips are shrinking.\n\nThe price is not.",
             "hashtags": [f"tag{i}" for i in range(15)]}


class TestHashtagCap(unittest.TestCase):
    """YouTube IGNORES EVERY HASHTAG on a video carrying more than 15 — not
    ranks them lower, discards the whole set. This channel shipped 21-22 on
    every upload for its entire life, which silently disabled its own
    hashtags. `HASHTAGS` was 1 view across 76 videos and read like 'hashtags
    don't work'."""

    def test_never_more_than_fifteen(self):
        for pkg in (REDDIT, GRAPH, TEXT_CARD):
            tags = rtd._hashtag_list(pkg)
            self.assertLessEqual(len(tags), 15, f"{pkg['slug']}: {len(tags)}")

    def test_a_package_asking_for_thirty_still_gets_fifteen(self):
        greedy = dict(REDDIT, hashtags=[f"t{i}" for i in range(30)])
        self.assertEqual(len(rtd._hashtag_list(greedy)), 15)

    def test_a_caller_cannot_raise_the_cap(self):
        self.assertLessEqual(len(rtd._hashtag_list(REDDIT, max_total=40)), 15)

    def test_the_description_carries_no_more_than_fifteen(self):
        for pkg in (REDDIT, GRAPH, TEXT_CARD):
            self.assertLessEqual(rtd._description(pkg).count("#"), 15,
                                 pkg["slug"])

    def test_topical_hashtags_come_before_the_baseline_ones(self):
        tags = rtd._hashtag_list(REDDIT)
        self.assertEqual(tags[0], "tag0")

    def test_baseline_fills_a_package_that_wrote_none(self):
        tags = rtd._hashtag_list({"slug": "x", "title": "t"})
        self.assertTrue(tags)
        self.assertIn("shorts", tags)


class TestDescriptionIsNotJustHashtags(unittest.TestCase):
    """`_description` used to be `pkg["script"]` + hashtags. text_card and
    graph_race have no `script`, so four of every six videos uploaded with a
    description that was literally "\\n\\n#tag #tag …" — a bare wall of
    hashtags with no prose at all."""

    def test_every_format_gets_real_prose(self):
        for pkg in (REDDIT, GRAPH, TEXT_CARD):
            desc = rtd._description(pkg)
            first = desc.splitlines()[0]
            self.assertTrue(first.strip(), f"{pkg['slug']}: blank first line")
            self.assertFalse(first.startswith("#"),
                             f"{pkg['slug']}: description opens with hashtags")

    def test_it_opens_with_the_title(self):
        for pkg in (REDDIT, GRAPH, TEXT_CARD):
            self.assertTrue(rtd._description(pkg).startswith(pkg["title"]),
                            pkg["slug"])

    def test_a_chart_is_described_by_what_it_shows(self):
        desc = rtd._description(GRAPH)
        for expected in ("Netflix", "Disney+", "2019", "2024",
                         "Subscribers (millions)"):
            self.assertIn(expected, desc, expected)

    def test_the_source_line_survives(self):
        self.assertIn("company filings", rtd._description(GRAPH))

    def test_a_package_with_nothing_still_produces_something_sane(self):
        desc = rtd._description({"slug": "bare", "title": "Just A Title"})
        self.assertTrue(desc.startswith("Just A Title"))
        self.assertNotIn("None", desc)

    def test_it_never_exceeds_youtubes_limit(self):
        huge = dict(REDDIT, script="word " * 4000)
        self.assertLessEqual(len(rtd._description(huge)), 5000)


class TestTechnicalQABlocksBrokenRenders(unittest.TestCase):
    """`shared/video_qa.py` existed for weeks imported by nothing, while
    CLAUDE.md said 'run it before uploads'. A black or silent render went
    straight to YouTube."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="qa-"))
        cls.have_ffmpeg = True
        try:
            cls._make("good.mp4", "testsrc=size=320x568:rate=30:duration=4",
                      "sine=frequency=440:duration=4")
            cls._make("broken.mp4",
                      "color=c=black:size=320x568:rate=30:duration=4",
                      "anullsrc=r=44100:cl=mono", extra=["-t", "4"])
        except Exception:                                # noqa: BLE001
            cls.have_ffmpeg = False

    @classmethod
    def _make(cls, name, video, audio, extra=()):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", video, "-f", "lavfi", "-i", audio, *extra,
                        "-shortest", str(cls.tmp / name)], check=True,
                       timeout=120)

    def setUp(self):
        if not self.have_ffmpeg:
            self.skipTest("ffmpeg unavailable")

    def test_a_healthy_render_is_not_blocked(self):
        self.assertIsNone(rtd._technical_qa(self.tmp / "good.mp4", {}))

    def test_a_black_and_silent_render_IS_blocked(self):
        reason = rtd._technical_qa(self.tmp / "broken.mp4", {})
        self.assertIsNotNone(reason, "a black, silent render passed QA")
        self.assertIn("technical QA", reason)

    def test_the_report_is_recorded_on_the_result(self):
        result = {}
        rtd._technical_qa(self.tmp / "good.mp4", result)
        self.assertIn("technical_qa", result)

    def test_it_fails_OPEN_on_a_file_it_cannot_analyse(self):
        """A broken QA tool must not become the outage it exists to
        prevent."""
        missing = self.tmp / "does-not-exist.mp4"
        self.assertIsNone(rtd._technical_qa(missing, {}))

    def test_it_runs_for_formats_the_vision_pass_skips(self):
        """graph_race and text_card skip the Gemini imagery QA — they must
        still get the technical pass, or two thirds of the slate is
        unchecked."""
        for pkg in (GRAPH, TEXT_CARD):
            _, block = rtd._qa_and_thumbnail(pkg, self.tmp / "broken.mp4", {})
            self.assertIsNotNone(block, f"{pkg['format']} skipped QA entirely")


class TestVideoQAIsActuallyWired(unittest.TestCase):
    def test_a_production_module_imports_it(self):
        """The regression that let it sit dark: nothing outside its own test
        ever imported it."""
        text = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        self.assertIn("from shared import video_qa", text)

    def test_qa_runs_before_the_vision_early_return(self):
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        body = src.split("def _qa_and_thumbnail", 1)[1]
        tech = body.index("_technical_qa")
        skip = body.index('("text_card", "graph_race")')
        self.assertLess(tech, skip,
                        "technical QA must run BEFORE the format early-return "
                        "or it never sees a chart or a card")


if __name__ == "__main__":
    unittest.main()
