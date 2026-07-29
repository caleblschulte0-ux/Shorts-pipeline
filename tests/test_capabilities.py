"""Tests for the 2026-07-30 capability sprint: video_qa, captions, feeds,
article_extract, svg_motion. Everything runs offline — video fixtures are
synthesized with ffmpeg at test time, feed/article fixtures are inline.

    python -m unittest tests.test_capabilities -v
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FFMPEG = shutil.which("ffmpeg")
TMP = Path(tempfile.mkdtemp(prefix="cap_sprint_"))


def _mk(name: str, *args: str) -> Path | None:
    if not FFMPEG:
        return None
    out = TMP / name
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        *args, str(out)], capture_output=True, timeout=120)
    return out if r.returncode == 0 and out.exists() else None


class TestVideoQA(unittest.TestCase):
    @unittest.skipUnless(FFMPEG, "ffmpeg required")
    def test_good_video_passes(self):
        from shared import video_qa
        good = _mk("good.mp4",
                   "-f", "lavfi", "-i", "testsrc=size=320x568:rate=24:duration=5",
                   "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
                   "-af", "volume=0.5", "-shortest",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p")
        self.assertIsNotNone(good)
        rep = video_qa.qa_report(good)
        self.assertIsNotNone(rep)
        self.assertTrue(rep["analyzable"])
        self.assertTrue(rep["has_audio"])
        self.assertAlmostEqual(rep["duration"], 5.0, delta=0.3)
        ok, reasons = video_qa.passes(rep)
        self.assertTrue(ok, f"good video failed QA: {reasons}")

    @unittest.skipUnless(FFMPEG, "ffmpeg required")
    def test_black_silent_video_fails(self):
        from shared import video_qa
        bad = _mk("bad.mp4",
                  "-f", "lavfi", "-i", "color=black:size=320x568:rate=24:duration=6",
                  "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono:d=6",
                  "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p")
        self.assertIsNotNone(bad)
        rep = video_qa.qa_report(bad)
        self.assertIsNotNone(rep)
        ok, reasons = video_qa.passes(rep)
        self.assertFalse(ok)
        joined = " ".join(reasons)
        self.assertIn("black", joined)
        self.assertIn("silent", joined)

    def test_none_report_fails_closed(self):
        from shared import video_qa
        ok, reasons = video_qa.passes(None)
        self.assertFalse(ok)
        self.assertTrue(reasons)

    def test_missing_file_returns_none(self):
        from shared import video_qa
        self.assertIsNone(video_qa.qa_report("/nonexistent/nope.mp4"))


WORDS = [
    {"word": "three", "start": 0.0, "end": 0.3},
    {"word": "tax", "start": 0.35, "end": 0.6},
    {"word": "tricks", "start": 0.65, "end": 1.0},
    {"word": "they", "start": 1.05, "end": 1.25},
    {"word": "hide", "start": 1.3, "end": 1.6},
    # long pause -> new caption line
    {"word": "number", "start": 3.2, "end": 3.5},
    {"word": "one", "start": 3.55, "end": 3.9},
]


class TestCaptions(unittest.TestCase):
    def test_group_words_breaks_on_gap_and_len(self):
        from shared import captions
        lines = captions.group_words(WORDS, max_words=4, max_gap=0.6)
        self.assertEqual(len(lines), 3)  # 4-word cap splits first run; gap splits last
        self.assertEqual([w["word"] for w in lines[-1]], ["number", "one"])

    def test_build_ass_structure(self):
        from shared import captions
        ass = captions.build_ass(WORDS)
        self.assertIn("[Script Info]", ass)
        self.assertIn("PlayResX: 1080", ass)
        self.assertEqual(ass.count("Dialogue:"), 3)
        self.assertIn("\\k", ass)
        self.assertIn("THREE", ass)          # uppercase default
        self.assertNotIn("{THREE", ass)      # words escaped, tags intact

    @unittest.skipUnless(FFMPEG, "ffmpeg required")
    def test_burn_produces_video(self):
        from shared import captions
        base = _mk("capbase.mp4",
                   "-f", "lavfi", "-i", "color=blue:size=320x568:rate=24:duration=2",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p")
        self.assertIsNotNone(base)
        ass_path = captions.write_ass(captions.build_ass(WORDS), TMP / "t.ass")
        out = captions.burn(base, ass_path, TMP / "capout.mp4")
        self.assertIsNotNone(out)
        self.assertGreater(Path(out).stat().st_size, 1000)

    def test_burn_never_raises(self):
        from shared import captions
        self.assertIsNone(captions.burn("/no/in.mp4", "/no/s.ass", "/no/out.mp4"))


RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Feed</title>
<item><title>First &amp; foremost</title><link>https://x.test/a</link>
<description>Alpha &lt;b&gt;story&lt;/b&gt; summary</description>
<pubDate>Tue, 29 Jul 2026 12:00:00 GMT</pubDate></item>
<item><title>Second</title><link>https://x.test/b</link></item>
</channel></rss>"""

ATOM_FIXTURE = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>AFeed</title>
<entry><title>Atom One</title>
<link rel="alternate" href="https://y.test/1"/>
<summary>atom summary</summary><published>2026-07-29T10:00:00Z</published>
</entry></feed>"""


class TestFeeds(unittest.TestCase):
    def test_rss_parse(self):
        from funnel import feeds
        got = feeds.parse_feed_text(RSS_FIXTURE, "src")
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["title"], "First & foremost")
        self.assertEqual(got[0]["link"], "https://x.test/a")
        self.assertIn("Alpha", got[0]["summary"])
        self.assertNotIn("<b>", got[0]["summary"])
        self.assertTrue(got[0]["published"])

    def test_atom_parse(self):
        from funnel import feeds
        got = feeds.parse_feed_text(ATOM_FIXTURE, "src")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["link"], "https://y.test/1")
        self.assertEqual(got[0]["published"], "2026-07-29T10:00:00Z")

    def test_garbage_never_raises(self):
        from funnel import feeds
        self.assertEqual(feeds.parse_feed_text("not xml at all", "s"), [])
        self.assertEqual(feeds.entries("not-a-url"), [])


ARTICLE_HTML = """<html><head><title>Site - Big Tax Change</title>
<meta property="og:title" content="Big Tax Change Explained"/>
<meta property="article:published_time" content="2026-07-29"/>
</head><body>
<nav><a href="/">Home</a><a href="/news">News</a></nav>
<div id="sidebar"><p>Related: <a href="/x">Ten links here</a> and
<a href="/y">more links that are mostly anchors in a link farm</a></p></div>
<article>
<p>The federal standard deduction is rising again this year, a change that
affects nearly every household that does not itemize deductions on returns.</p>
<p>Officials said the adjustment tracks inflation data published earlier this
month, and preparers expect refunds to shift modestly for most filers now.</p>
<p>Analysts note the bracket thresholds also move, which alters withholding
tables employers use starting with the first payroll of the coming year.</p>
</article>
<footer><p>Copyright 2026 — subscribe for more content and newsletters.</p></footer>
</body></html>"""


class TestArticleExtract(unittest.TestCase):
    def test_extract_html_gets_body_not_chrome(self):
        from funnel import article_extract
        art = article_extract.extract_html(ARTICLE_HTML, "https://n.test/tax")
        self.assertIsNotNone(art)
        self.assertEqual(art["title"], "Big Tax Change Explained")
        self.assertEqual(art["published"], "2026-07-29")
        self.assertIn("standard deduction", art["text"])
        self.assertIn("withholding", art["text"])
        self.assertNotIn("Copyright", art["text"])
        self.assertNotIn("link farm", art["text"])

    def test_thin_page_returns_none(self):
        from funnel import article_extract
        self.assertIsNone(article_extract.extract_html(
            "<html><body><p>too short</p></body></html>", "u"))

    def test_never_raises(self):
        from funnel import article_extract
        self.assertIsNone(article_extract.extract("::::bad url::::"))


class TestSvgMotion(unittest.TestCase):
    def test_helpers(self):
        from engines.svg_motion import ease, interp, seg
        self.assertEqual(ease.linear(-1), 0.0)
        self.assertEqual(ease.linear(2), 1.0)
        self.assertAlmostEqual(ease.out_cubic(1.0), 1.0)
        self.assertEqual(interp(10, 20, 0.5), 15)
        self.assertEqual(seg(0.5, 0.0, 0.5), 1.0)
        self.assertEqual(seg(0.0, 0.5, 1.0), 0.0)

    def test_frame_fns_emit_svg(self):
        from engines.svg_motion import title_card, stat_pop
        for fn in (title_card("T&T", "<sub>"), stat_pop("87%", "of filers")):
            for t in (0.0, 0.5, 1.0):
                svg = fn(t)
                self.assertIn("<svg", svg)
                self.assertNotIn("<sub>", svg)   # escaped
                self.assertNotIn("T&T", svg)     # escaped

    def test_render_if_available(self):
        from engines import svg_motion
        if not svg_motion.available():
            self.skipTest("cairosvg/ffmpeg unavailable")
        out = svg_motion.maybe_svg_motion(
            svg_motion.title_card("TEST", "sprint"), TMP / "card.mp4",
            duration=1.0, fps=12, width=270, height=480)
        self.assertIsNotNone(out)
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries",
             "format=duration", "-of", "csv=p=0", str(out)],
            capture_output=True, text=True)
        self.assertAlmostEqual(float(probe.stdout.strip()), 1.0, delta=0.2)

    def test_bad_frame_fn_returns_none(self):
        from engines import svg_motion
        if not svg_motion.available():
            self.skipTest("cairosvg/ffmpeg unavailable")
        self.assertIsNone(svg_motion.maybe_svg_motion(
            lambda t: "not svg", TMP / "x.mp4", duration=0.5, fps=6))


if __name__ == "__main__":
    unittest.main(verbosity=2)
