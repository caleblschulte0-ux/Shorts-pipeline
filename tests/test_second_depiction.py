"""Every beat shows its number TWO ways, and both spans cover the beat.

A video had four things in it: three chart cards and a host. The first attempt
at "more" cut each card into tighter framings, which is one subject with
movement on it — the operator's verdict was exact: "the jump cut zoom ins are
not it ... there is like 4 things and then movement, that's not good enough, we
need 7-8 things".

So a beat now renders its figure twice, in two different contact-verified
depictions, and cuts between them. Three beats become six visuals; with the
hook image and the closing card that is eight, and each one is the data.

Two things are pinned here because each already broke once:

  * the ALTERNATE KIND has to come from the DATA's shape, not a lookup of the
    current kind. The first version keyed off `kind` alone and produced nothing
    on a real video, because the kinds that actually ship are `scene` (an
    authored element-kit depiction) and `geo_city` (the metro map) — neither is
    a chart name and neither was in the table.
  * the ALT BUILD must span the whole beat. Rendering it at half length looked
    like a saving (it only occupies about half the shots) but both depictions
    are laid on the timeline from the beat's START, so the short one ran out
    and ffmpeg's tpad cloned its last frame: a 3.0s frozen stretch beginning
    exactly on a shot boundary, 73 duplicate frames against a ceiling of 45.
    The gate would have blocked every video that shipped in.

Runs with pytest OR standalone:
    python3 tests/test_second_depiction.py
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import studio_render as sr  # noqa: E402
from data_learning import viz_director as vd  # noqa: E402

_SRC = (_REPO / "data_learning" / "studio_render.py").read_text()


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


class SecondDepiction(unittest.TestCase):
    def test_the_kinds_that_actually_ship_get_an_alternate(self):
        """`scene` and `geo_city` are what this channel renders. If these come
        back None the feature is silently off, which is exactly how the first
        version shipped as a no-op."""
        self.assertIsNotNone(sr._alt_depiction_kind("scene", set(), _years()))
        self.assertIsNotNone(
            sr._alt_depiction_kind("geo_city", set(), _ranking()))

    def test_the_alternate_is_chosen_from_the_data_shape(self):
        """A run of years wants a line; a handful of named things wants a
        race. Shape is the durable question, not the name of the current
        depiction."""
        self.assertIn("trend", sr._alt_candidates_for(_years()))
        self.assertIn("pictorial_race", sr._alt_candidates_for(_ranking()))

    def test_the_alternate_is_always_a_different_kind(self):
        for kind, ins in (("scene", _years()), ("geo_city", _ranking()),
                          ("trend", _years()), ("pictorial_race", _ranking())):
            alt = sr._alt_depiction_kind(kind, set(), ins)
            self.assertNotEqual(alt, kind, f"{kind} alternates to itself")

    def test_the_alternate_is_contact_verified(self):
        """STRICT_CONTACT: the host must be able to physically attach to
        whatever is on screen, so a second depiction cannot introduce a kind
        the mascot coupling does not support."""
        for kind, ins in (("scene", _years()), ("geo_city", _ranking())):
            alt = sr._alt_depiction_kind(kind, set(), ins)
            self.assertIn(alt, vd._CONTACT_OK,
                          f"{alt!r} is not a contact-verified depiction")

    def test_it_avoids_kinds_the_video_already_uses(self):
        """Two beats showing the same alternate is a near-repeat, not a second
        thing."""
        used = {"scene", "trend"}
        self.assertNotEqual(sr._alt_depiction_kind("scene", used, _years()),
                            "trend")

    def test_the_alt_build_spans_the_whole_beat(self):
        """THE FREEZE. Both depictions start at the beat's start, so a
        short alt runs out and tpad clones — 73 duplicate frames, gate block."""
        blk = _SRC[_SRC.index("THE SECOND DEPICTION of this same number"):]
        blk = blk[:blk.index("finally:")]
        self.assertIn("frames=nfr", blk,
                      "the alt build no longer spans the beat — it will freeze")
        self.assertNotRegex(
            blk, r"frames=max\(\d+,\s*nfr\s*//",
            "a fractional alt build is the frozen-stretch bug")

    def test_shots_never_reuse_an_ffmpeg_label(self):
        """ffmpeg consumes a filter output label exactly once; reusing [g0]
        for three shots made it refuse the whole graph (exit 234) and the
        render produced nothing at all."""
        blk = _SRC[_SRC.index("# Shot 0 establishes on the chart"):]
        blk = blk[:blk.index("prev = f\"b{i}_{k}\"")]
        self.assertIn("split=", blk,
                      "shots must fan out with split, not reuse one label")


if __name__ == "__main__":
    unittest.main(verbosity=2)
