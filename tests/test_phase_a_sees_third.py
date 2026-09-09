"""Phase A must recognise a registry-valid package for every channel it accepts.

Doctor finding 7f087a105388. `exchange_phase_a` exposes `third` in
`PACKAGE_DIRS` and in its `--channel` choices, maps it to
`state/third_packages`, and then filtered every file through an `is_package`
predicate that knew about `script`, `text`, `series`, `shots`, `subreddit`,
`broll_query` and `segments` — and not `source_url`, which is how the
registry detects Third's only active format.

So a canonical `{slug, source_url}` capture recipe was read successfully and
logged as a non-package. The Third branch got an empty slate while valid
packages sat on disk, and nothing about that looked wrong from the outside:
a Phase A that finds no packages exits 0.

The fixtures here are DERIVED from `config/channel_registry.json` rather than
typed out, so the detector cannot drift away from the registry again without
this failing.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import channel_registry as cr                # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "exchange_phase_a", ROOT / "scripts" / "exchange_phase_a.py")
pa = importlib.util.module_from_spec(_spec)
sys.modules["exchange_phase_a"] = pa
_spec.loader.exec_module(pa)


def _minimal(channel: str, fmt: str) -> dict:
    """The smallest object the registry says IS this format."""
    spec = cr.format_spec(channel, fmt)
    pkg: dict = {}
    for field in (spec.get("required_fields") or []):
        pkg[field] = f"{field}-value"
    rule = spec.get("detect") or {}
    if rule.get("equals") is not None:
        pkg[rule["field"]] = rule["equals"]
    elif rule.get("present"):
        pkg.setdefault(rule["field"], f"{rule['field']}-value")
    if rule.get("requires"):
        pkg.setdefault(rule["requires"], "x")
    if rule.get("absent"):
        pkg.pop(rule["absent"], None)
    return pkg


class EveryChannelPhaseAAcceptsCanLoadItsPackages(unittest.TestCase):
    def test_phase_a_offers_third_at_all(self):
        """If this ever stops being true the rest of the file is moot, and
        silently so."""
        self.assertIn("third", pa.PACKAGE_DIRS)

    def test_a_registry_minimal_package_is_recognised_for_every_channel(self):
        for channel in pa.PACKAGE_DIRS:
            for fmt in cr.active_formats(channel):
                pkg = _minimal(channel, fmt)
                with self.subTest(channel=channel, format=fmt, pkg=pkg):
                    self.assertTrue(
                        pa.is_package(pkg, channel),
                        f"{channel}/{fmt} is what the registry says a package "
                        f"looks like, and Phase A would discard it")

    def test_the_third_clip_case_specifically(self):
        """The finding's own example, spelled out — a capture recipe carries
        no script, no shots, no segments, nothing the old markers knew."""
        pkg = {"slug": "kai-vs-the-chat", "source_url":
               "https://www.twitch.tv/videos/123?t=1h02m00s"}
        self.assertTrue(pa.is_package(pkg, "third"))
        self.assertEqual(sorted(pkg), ["slug", "source_url"])


class ConfigAndReportsAreStillExcluded(unittest.TestCase):
    """The predicate's actual job. Widening it must not let junk in."""

    def test_a_report_is_not_a_package(self):
        for junk in ({"generated_at": "x", "counts": {}},
                     {"date": "20260909", "ok": True},
                     {"notes": "read me"},
                     {}):
            for channel in pa.PACKAGE_DIRS:
                with self.subTest(channel=channel, junk=junk):
                    self.assertFalse(pa.is_package(junk, channel))

    def test_a_non_dict_is_not_a_package(self):
        for junk in ([], "text", None, 7):
            self.assertFalse(pa.is_package(junk, "third"))

    def test_a_third_object_without_a_source_url_is_not_a_clip(self):
        self.assertFalse(pa.is_package({"slug": "x", "note": "y"}, "third"))

    def test_third_detection_does_not_leak_into_trending(self):
        """`source_url` means a clip on the Third channel. It is not a
        licence for any file anywhere to count as content."""
        self.assertFalse(
            pa.is_package({"slug": "x", "source_url": "http://a/b"}, "trending"))


class TheMarkerHeuristicIsUnCHANGED(unittest.TestCase):
    """The registry check is a UNION with the markers, not a replacement.
    Trending's reddit_story is detected by `subreddit`, so a package with a
    script and shots but no subreddit yet must still load."""

    def test_a_script_and_shots_still_count(self):
        self.assertTrue(pa.is_package({"slug": "s", "script": "words",
                                       "shots": [{}]}, "trending"))

    def test_every_historical_marker_still_counts(self):
        for marker in pa._PACKAGE_MARKERS:
            with self.subTest(marker=marker):
                self.assertTrue(pa.is_package({marker: "x"}, "trending"))


class ABrokenRegistryDoesNotEmptyEveryChannel(unittest.TestCase):
    def test_a_registry_error_falls_back_to_the_markers(self):
        from unittest import mock
        with mock.patch.object(cr, "classify", side_effect=RuntimeError("bad")):
            self.assertTrue(pa.is_package({"script": "w"}, "trending"))
            self.assertFalse(pa.is_package({"slug": "x",
                                            "source_url": "u"}, "third"))


if __name__ == "__main__":
    unittest.main()
