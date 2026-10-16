"""A story that cuts to another streamer's stream SAYS whose stream it is.

Searches 31-46 (2026-10-13..16): the near-misses were stories told across
two streams, and the critic's commonest note was the switch, "Pokelawls
is never introduced before the cut to his stream" (Jerma's bike fire,
capped at 79 three searches running). The edit now labels it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import story  # noqa: E402

SOURCES = {"a": {"channel": "jerma985"}, "b": {"channel": "pokelawls"},
           "c": {"channel": "Jerma985"}}


def _beats(*ids, overlays=None):
    overlays = overlays or {}
    return [{"source_id": s, "context_overlay": overlays.get(i, "")}
            for i, s in enumerate(ids)]


class WhoseStream(unittest.TestCase):
    def test_a_switch_is_labelled(self):
        b = _beats("a", "b")
        self.assertEqual(story.beat_overlay(b, 1, SOURCES),
                         "On Pokelawls' stream")
        self.assertEqual(story.beat_overlay(_beats("b", "a"), 1, SOURCES),
                         "On Jerma985's stream")

    def test_the_label_fits_the_overlay_rule(self):
        t = story.beat_overlay(_beats("a", "b"), 1, SOURCES)
        self.assertTrue(2 <= len(t.split()) <= 6)

    def test_same_channel_and_opening_say_nothing_new(self):
        self.assertEqual(story.beat_overlay(_beats("a", "c"), 1, SOURCES), "")
        self.assertEqual(story.beat_overlay(_beats("a", "b"), 0, SOURCES), "")

    def test_an_overlay_that_names_the_channel_is_kept(self):
        b = _beats("a", "b", overlays={1: "Pokelawls watches his bike"})
        self.assertEqual(story.beat_overlay(b, 1, SOURCES),
                         "Pokelawls watches his bike")

    def test_the_plan_and_the_render_both_use_it(self):
        src = (ROOT / "third_capture" / "story.py").read_text()
        self.assertEqual(src.count("beat_overlay(beats, idx, sources)"), 2)
        self.assertNotIn('beat.get("context_overlay", ""),', src)

    def test_the_plan_ledger_shows_the_label(self):
        edl = {"hook_overlay": "Jerma fuels a bike",
               "beats": [{"source_id": "a", "start": 0, "end": 6},
                         {"source_id": "b", "start": 0, "end": 6}]}
        srcs = {k: dict(v, words=[], duration_s=10) for k, v in
                SOURCES.items()}
        led = story.plan_ledger(edl, srcs)
        texts = [c["text"] for c in led.get("on_screen") or []]
        self.assertIn("On Pokelawls' stream", texts)


if __name__ == "__main__":
    unittest.main()
