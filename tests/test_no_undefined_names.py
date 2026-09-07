"""No module reaches production with a name that does not exist.

Found the hard way. A bulk edit renamed the host loader across five scene
elements and one of them lived in a function whose reveal variable is called
`reveal`, not `r`:

    host = scene_host("cheer", r)      # NameError, only when a timeline renders

Every test passed. The full suite passed. The renders I happened to run passed,
because none of them used a `timeline` scene — it would have raised the first
time a story picked one, in production, at 06:00, and taken the video with it.

This is the one defect class that unit tests systematically miss: code that is
only wrong on a path nobody exercised. A parser finds it in under a second.

Runs with pytest OR standalone:
    python3 tests/test_no_undefined_names.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# The modules a render actually goes through. Deliberately not the whole repo:
# a check nobody can keep green gets deleted, and these are the files where an
# undefined name means a lost video rather than a broken report.
RENDER_PATH = (
    "data_learning/studio_render.py",
    "data_learning/viz_scene.py",
    "data_learning/viz_director.py",
    "data_learning/charts.py",
    "data_learning/mascot_director.py",
    "data_learning/story.py",
    "scripts/story_forge.py",
    "scripts/post_stories.py",
    "scripts/showrunner_review.py",
    "scripts/build_mascot_svg.py",
)


class NoUndefinedNames(unittest.TestCase):
    def test_the_render_path_has_no_undefined_names(self):
        try:
            from pyflakes.api import check
            from pyflakes.reporter import Reporter
        except ImportError:  # noqa: BLE001
            self.skipTest("pyflakes not installed")
        import io

        bad = []
        for rel in RENDER_PATH:
            path = _REPO / rel
            if not path.exists():
                continue
            out, err = io.StringIO(), io.StringIO()
            check(path.read_text(), rel, Reporter(out, err))
            for line in out.getvalue().splitlines():
                # Only the fatal class. Unused imports and shadowed names are
                # style; an undefined name is a crash waiting for a code path.
                if "undefined name" in line or "used prior to global" in line:
                    bad.append(line)
            for line in err.getvalue().splitlines():
                if line.strip():
                    bad.append(line)
        self.assertEqual(bad, [], "\n".join(bad))

    def test_every_render_path_module_still_exists(self):
        """A silent skip because a file moved is the check quietly switching
        itself off."""
        missing = [r for r in RENDER_PATH if not (_REPO / r).exists()]
        self.assertEqual(missing, [], f"moved or renamed: {missing}")

    def test_they_all_at_least_parse(self):
        """Runs with or without pyflakes, so the file is never a no-op."""
        import ast
        for rel in RENDER_PATH:
            path = _REPO / rel
            if path.exists():
                ast.parse(path.read_text(), filename=rel)


if __name__ == "__main__":
    unittest.main(verbosity=2)
