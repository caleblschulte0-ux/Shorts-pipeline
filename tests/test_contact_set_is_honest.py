"""`_CONTACT_OK` must name kinds that REALLY bake a coupled host.

2026-08-24: `timeline` sat in viz_director._CONTACT_OK — the set whose own
comment promises "renderer BAKES a mechanically-coupled host" — while
`timeline` is a FULL-FRAME renderer (`charts._render_timeline`) that authors
its own sequence and never calls `_bake_host`. Under STRICT_CONTACT the
benchmark suite picks only from this set, so the promise is load-bearing:
the moment the variety pass reached for `timeline`, grocery-squeeze rendered
a beat with 0/10 grip frames and the structural gate refused the render.

The claim had been false for as long as it existed and stayed invisible
because `pictorial_race` always won the slot first. That is the engine-
registry lesson in a second file: a capability list nobody checks drifts
into a lie, and the lie surfaces as a mystery failure somewhere else.

Checked BOTH directions, like tests/test_engine_registry_honesty.py:
  * every member of _CONTACT_OK really bakes (directly, or by a routing
    that happens before any drawing);
  * no kind that plainly bakes is missing from it.

    python -m unittest tests.test_contact_set_is_honest -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data_learning import charts as C            # noqa: E402
from data_learning import viz_director as vd     # noqa: E402

SRC = (ROOT / "data_learning" / "charts.py").read_text()

# Kinds `_compose_story` rewrites to another kind BEFORE drawing — the routed
# target is what actually renders, so its bake is the one that counts.
ROUTES = {"waffle_grid": "stack", "share": "stack",
          "pictograph": "pictorial_race"}

# The card compositor for each remaining kind.
COMPOSITORS = {
    "trend": "_story_trend", "pictorial_race": "_story_pictorial_race",
    "rank": "_story_bars", "bars": "_story_bars",
    "comparison": "_story_versus", "stack": "_story_stack",
    "bubbles": "_story_bubbles", "geo_us": "_story_geo",
    "geo_world": "_story_geo",
}


def _fn_body(name: str) -> str:
    if f"def {name}(" not in SRC:
        return ""
    return SRC.split(f"def {name}(", 1)[1].split("\ndef ", 1)[0]


class TestEveryContactKindReallyBakes(unittest.TestCase):

    def test_no_member_is_a_bakeless_fullframe_renderer(self):
        """The exact 08-24 defect: a full-frame renderer in the set whose
        body has no `_bake_host`. Full-frame kinds author their own
        sequence — `render_series` never reaches the card path for them."""
        for kind in sorted(vd._CONTACT_OK):
            fn = C.FULLFRAME_RENDERERS.get(kind)
            if fn is None:
                continue
            self.assertIn("_bake_host", _fn_body(fn.__name__),
                          f"{kind} is a full-frame renderer ({fn.__name__}) "
                          "that never bakes a host, but _CONTACT_OK promises "
                          "a mechanically-coupled mascot")

    def test_every_member_bakes_or_routes_to_one_that_does(self):
        for kind in sorted(vd._CONTACT_OK):
            target = ROUTES.get(kind, kind)
            comp = COMPOSITORS.get(target)
            self.assertIsNotNone(
                comp, f"{kind} has no known compositor — if a new kind joined "
                      "_CONTACT_OK, map it here and prove it bakes")
            self.assertIn("_bake_host", _fn_body(comp),
                          f"{kind} -> {comp} does not bake a host")

    def test_timeline_specifically_stays_out(self):
        """Pinned by name: it is the one that was wrong, and its renderer is
        still bakeless, so re-adding it re-opens the same hole."""
        self.assertNotIn("timeline", vd._CONTACT_OK)
        self.assertNotIn("_bake_host", _fn_body("_render_timeline"))

    def test_the_fallback_mapping_is_not_a_routing(self):
        """The old comment justified timeline's membership with
        "timeline -> trend". That mapping is charts.FALLBACK, which is the
        degrade path taken only when the full-frame renderer RETURNS NONE —
        a successful timeline render never touches trend."""
        self.assertEqual(C.FALLBACK.get("timeline"), "trend")
        body = _fn_body("render_story_build")
        self.assertIn("FALLBACK.get(insight.kind", body)
        self.assertIn("if res is not None:", body)

    def test_nothing_that_bakes_is_silently_excluded(self):
        """The other direction: a card kind whose compositor bakes belongs in
        the set, or the benchmark suite quietly stops exercising it."""
        for kind, comp in COMPOSITORS.items():
            if "_bake_host" in _fn_body(comp):
                self.assertIn(kind, vd._CONTACT_OK,
                              f"{kind} bakes a host but is excluded from "
                              "_CONTACT_OK — strict runs will never pick it")


if __name__ == "__main__":
    unittest.main()
