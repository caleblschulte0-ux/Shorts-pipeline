"""Research intake: the feed reader and the article reader, actually wired.

Audit finding C. `funnel/feeds.py` and `funnel/article_extract.py` were both
built for the top-of-funnel research path and then imported by nothing, while
`scripts/discover_topic.py` carried its own narrower RSS parser and the
trending writer worked from a bare headline.

Two things are under test:

  1. `_parse_generic_rss` now delegates to `funnel.feeds`, and produces the
     same topics it always did for RSS — plus Atom, which it previously
     dropped on the floor silently.
  2. `_research` fills `topic.snippets` from the real article, and — the
     part that actually matters — degrades to doing nothing at all when the
     network, the site, or the parser lets it down. Research must never
     cost the day.

    python -m unittest tests.test_research_intake -v
"""
from __future__ import annotations

import contextlib
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import discover_topic as dt                              # noqa: E402
import run_trending_daily as rtd                         # noqa: E402

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Feed</title>
  <item>
    <title>Volcano erupts in Iceland - BBC News</title>
    <link>https://example.com/a</link>
    <description>&lt;p&gt;Lava reached the road overnight.&lt;/p&gt;</description>
    <pubDate>Mon, 28 Jul 2026 09:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Second story</title>
    <link>https://example.com/b</link>
    <description>short</description>
  </item>
  <item>
    <title></title><link>https://example.com/c</link>
  </item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>An Atom story</title>
    <link rel="alternate" href="https://example.com/atom1"/>
    <summary>Something genuinely happened here today.</summary>
    <published>2026-07-28T09:00:00Z</published>
  </entry>
</feed>"""


class TestTheFeedReaderIsShared(unittest.TestCase):
    def test_it_delegates(self):
        src = (ROOT / "scripts" / "discover_topic.py").read_text()
        self.assertIn("feeds.parse_feed_text", src,
                      "discover_topic kept its private RSS parser")

    def test_rss_still_parses_the_same_way(self):
        got = dt._parse_generic_rss(RSS.encode(), "bbc_world")
        self.assertEqual(len(got), 2, "titleless items are still dropped")
        self.assertEqual(got[0].query, "Volcano erupts in Iceland",
                         "the ' - BBC News' suffix strip still runs")
        self.assertEqual(got[0].urls, ["https://example.com/a"])
        self.assertEqual(got[0].sources, ["bbc_world"])

    def test_html_is_stripped_out_of_the_description(self):
        got = dt._parse_generic_rss(RSS.encode(), "bbc_world")
        blob = " ".join(got[0].headlines)
        self.assertIn("Lava reached the road", blob)
        self.assertNotIn("<p>", blob)

    def test_a_short_description_is_not_promoted_to_a_headline(self):
        got = dt._parse_generic_rss(RSS.encode(), "s")
        self.assertEqual(got[1].headlines, ["Second story"])

    def test_pubdate_still_becomes_published_at(self):
        got = dt._parse_generic_rss(RSS.encode(), "s")
        self.assertTrue(got[0].published_at)
        self.assertIn("2026-07-28", got[0].published_at)

    def test_ATOM_now_works_where_it_used_to_yield_nothing(self):
        """The old parser looked only for <item>; an Atom feed produced an
        empty list and the run just had fewer topics, silently."""
        got = dt._parse_generic_rss(ATOM.encode(), "atom_src")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].query, "An Atom story")
        self.assertEqual(got[0].urls, ["https://example.com/atom1"])

    def test_max_items_is_honoured(self):
        self.assertEqual(len(dt._parse_generic_rss(RSS.encode(), "s",
                                                   max_items=1)), 1)

    def test_garbage_xml_yields_nothing_instead_of_exploding(self):
        self.assertEqual(dt._parse_generic_rss(b"<not xml", "s"), [])

    def test_a_str_body_works_as_well_as_bytes(self):
        self.assertEqual(len(dt._parse_generic_rss(RSS, "s")), 2)


@contextlib.contextmanager
def fake_extractor(fn):
    """Swap in a stub `funnel.article_extract`.

    Patching `sys.modules` alone is NOT enough: `from funnel import
    article_extract` reads the attribute off the already-imported `funnel`
    package, so once any other test has imported the real module the stub is
    ignored. That made these tests pass alone and fail under discovery —
    patch both.
    """
    import funnel
    stub = types.ModuleType("funnel.article_extract")
    stub.extract = fn
    with mock.patch.dict(sys.modules, {"funnel.article_extract": stub}), \
            mock.patch.object(funnel, "article_extract", stub, create=True):
        yield


@contextlib.contextmanager
def no_extractor():
    """The module genuinely not importable."""
    import funnel
    had = hasattr(funnel, "article_extract")
    old = getattr(funnel, "article_extract", None)
    if had:
        delattr(funnel, "article_extract")
    try:
        with mock.patch.dict(sys.modules, {"funnel.article_extract": None}):
            yield
    finally:
        if had:
            setattr(funnel, "article_extract", old)


class Topic:
    def __init__(self, urls=None, snippets=None):
        self.urls = urls or []
        self.snippets = snippets or []
        self.query = "q"


class TestResearchFillsTheContext(unittest.TestCase):
    def test_it_pulls_the_article_text_into_snippets(self):
        body = "A real article body. " * 40
        with fake_extractor(lambda url, **k: {"text": body}):
            t = Topic(urls=["https://example.com/a"])
            rtd._research(t)
        self.assertTrue(t.snippets)
        self.assertIn("A real article body", t.snippets[0])

    def test_it_truncates_so_the_prompt_is_not_swamped(self):
        with fake_extractor(lambda url, **k: {"text": "x" * 50_000}):
            t = Topic(urls=["https://example.com/a"])
            rtd._research(t)
        self.assertLessEqual(len(t.snippets[0]), rtd.RESEARCH_CHARS)

    def test_it_caps_how_many_urls_it_fetches(self):
        calls = []

        def fake(url, **k):
            calls.append(url)
            return {"text": "y" * 500}
        with fake_extractor(fake):
            rtd._research(Topic(urls=[f"https://e/{i}" for i in range(9)]))
        self.assertLessEqual(len(calls), rtd.RESEARCH_MAX_URLS)

    def test_existing_context_is_not_overwritten(self):
        with fake_extractor(lambda url, **k: {"text": "z" * 500}):
            t = Topic(urls=["https://e/1"], snippets=["already here"])
            rtd._research(t)
        self.assertEqual(t.snippets, ["already here"])


class TestResearchNeverCostsTheDay(unittest.TestCase):
    """Every one of these used to be a reason the topic had no context.
    None of them may be a reason the video does not get made."""

    def test_a_network_error_is_swallowed(self):
        with fake_extractor(mock.Mock(side_effect=OSError("no route"))):
            t = Topic(urls=["https://e/1"])
            rtd._research(t)                       # must not raise
        self.assertEqual(t.snippets, [])

    def test_an_extractor_returning_None_is_fine(self):
        with fake_extractor(lambda url, **k: None):
            t = Topic(urls=["https://e/1"])
            rtd._research(t)
        self.assertEqual(t.snippets, [])

    def test_a_paywall_stub_is_rejected_as_too_short(self):
        with fake_extractor(lambda url, **k: {"text": "Subscribe to read."}):
            t = Topic(urls=["https://e/1"])
            rtd._research(t)
        self.assertEqual(t.snippets, [], "a nav bar is not an article")

    def test_no_urls_is_a_no_op(self):
        t = Topic(urls=[])
        rtd._research(t)
        self.assertEqual(t.snippets, [])

    def test_one_bad_url_does_not_stop_the_good_one(self):
        def fake(url, **k):
            if url.endswith("bad"):
                raise ValueError("boom")
            return {"text": "good article text. " * 30}
        with fake_extractor(fake):
            t = Topic(urls=["https://e/bad", "https://e/good"])
            rtd._research(t)
        self.assertEqual(len(t.snippets), 1)

    def test_the_module_being_absent_entirely_is_survivable(self):
        with no_extractor():
            t = Topic(urls=["https://e/1"])
            rtd._research(t)
        self.assertEqual(t.snippets, [])

    def test_the_writer_is_actually_given_the_research(self):
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        gen = src.index("script_generator.generate")
        self.assertIn("_research(topic)", src[:gen],
                      "_research must run BEFORE the script is written")


if __name__ == "__main__":
    unittest.main()
