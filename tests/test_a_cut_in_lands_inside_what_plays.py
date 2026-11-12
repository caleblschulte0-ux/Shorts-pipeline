"""2026-11-12 samples: Flagg's cut ran 13.7-44.2s and the cut-in was put
at 0.8s; Dirk's ran 0.1-37.5s and got one at 40.5s. Both were dropped at
render and the clips shipped with none. The brain is shown only what
plays, and anything outside it is refused before the render."""
from __future__ import annotations

import unittest
from unittest import mock

from scripts import sports_samples as ss


def _words(n=60, step=1.0):
    return [{"w": f"w{i}", "s": i * step, "e": i * step + 0.5}
            for i in range(n)]


class ACutInLandsInsideWhatPlays(unittest.TestCase):
    def test_the_brain_sees_only_the_cut_and_outside_picks_drop(self):
        seen = {}

        def brain(user, system):
            seen["user"] = user
            return {"broll": [{"who": "Cooper Flagg", "at": 0.8,
                               "look": "a"},
                              {"who": "Cooper Flagg", "at": 20.0,
                               "look": "b"}]}

        edit = {"cut": {"start": 13.7, "end": 44.2}}
        with mock.patch.object(ss, "_brain", brain):
            ss.broll({"who": "Cooper Flagg", "post_title": "t"}, _words(),
                     60.0, edit)
        self.assertNotIn("[0.0]", seen["user"])
        self.assertIn("13.7-44.2", seen["user"])
        self.assertEqual([b["at"] for b in edit["broll"]], [20.0])

    def test_the_authors_own_pick_outside_the_cut_is_dropped(self):
        edit = {"cut": {"start": 0.1, "end": 37.5},
                "broll": [{"who": "Jalen Brunson", "at": 40.5, "look": "x"}],
                "show": [{"thing": "x", "at": 5.0}]}
        with mock.patch.object(ss, "_brain", lambda u, s: {}):
            ss.broll({"who": "Dirk", "post_title": "t"}, _words(), 60.0, edit)
        self.assertNotIn("broll", edit)
        self.assertEqual(edit["show"], [{"thing": "x", "at": 5.0}])

    def test_no_cut_means_the_whole_clip(self):
        self.assertEqual(ss._window({}, 30.0), (0.0, 30.0))


class TalkingAboutSomeoneIsAStory(unittest.TestCase):
    def test_the_picker_and_author_no_longer_default_to_a_bare_clip(self):
        from third_capture import author
        import inspect
        src = inspect.getsource(author) + ss.PICK_SYSTEM
        self.assertNotIn("When in doubt it is a clip", src)
        self.assertNotIn("When in doubt,\nit is a clip", src)
        self.assertIn("what makes us is like", src)


if __name__ == "__main__":
    unittest.main()
