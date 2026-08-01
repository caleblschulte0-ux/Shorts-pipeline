"""The funnel layout, enforced — so the root stops collecting modules again.

The 2026-07-30 reorg moved shared code into `funnel/`, `shared/` and
`engines/` and left 18 one-line `sys.modules` shims at the repo root so old
imports kept working. That was the right call for the migration and the wrong
thing to keep: root is the first thing a new reader sees, and "temporary"
compatibility that nothing is retiring is just permanent clutter (audit
finding H).

The shims are gone. These tests are what stops them growing back, and what
stops the next module landing at the root instead of in a package.

    python -m unittest tests.test_repo_layout -v
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

#: The only .py files that belong at the repo root. Channel renderers
#: (`make_*`) and one-shot operator scripts. Everything else goes in a
#: package.
ALLOWED_ROOT = {
    "make_explainer_stacked.py", "make_graph_race.py", "make_reddit_story.py",
    "make_text_card.py", "reddit_card.py", "seed_gameplay.py",
    "setup_youtube.py", "setup.py", "conftest.py",
}

#: The names that used to be shimmed at the root. Deleted 2026-08-01.
RETIRED_SHIMS = {
    "entity_media", "fsutil", "gameplay_scanner", "gemini_images",
    "higgsfield", "localize", "media_funnel", "media_usage", "mixkit_search",
    "og_scrape", "pexels_search", "pixabay_search", "script_generator",
    "stock_search", "themed_bottom", "topic_media", "topic_video",
    "uploaders",
}

PACKAGES = ("funnel", "shared", "engines")


def py_files():
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith((".git/", "cache/", "build/", "node_modules/")):
            continue
        yield p, rel


class TestTheRootStaysClean(unittest.TestCase):
    def test_no_unexpected_module_at_the_repo_root(self):
        found = {p.name for p in ROOT.glob("*.py")}
        extra = sorted(found - ALLOWED_ROOT)
        self.assertEqual(extra, [],
                         f"new module(s) at the repo root: {extra}. Shared "
                         f"code goes in funnel/ (media), engines/ (render) "
                         f"or shared/ (everything else) — see "
                         f"docs/PIPELINE_LAYOUT.md.")

    def test_every_retired_shim_is_really_gone(self):
        back = sorted(n for n in RETIRED_SHIMS if (ROOT / f"{n}.py").exists())
        self.assertEqual(back, [], f"retired root shim(s) reappeared: {back}")


class TestNothingImportsTheOldNames(unittest.TestCase):
    """A legacy import is now an ImportError at runtime, not a warning —
    so this test is the thing that catches it before a 4am cron does."""

    def _legacy_imports(self, path: Path) -> list[str]:
        try:
            tree = ast.parse(path.read_text(errors="ignore"))
        except SyntaxError:
            return []
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module in RETIRED_SHIMS:
                    bad.append(f"from {node.module} import ...")
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in RETIRED_SHIMS:
                        bad.append(f"import {a.name}")
        return bad

    def test_no_file_imports_a_retired_root_name(self):
        offenders = {}
        for p, rel in py_files():
            bad = self._legacy_imports(p)
            if bad:
                offenders[rel] = bad
        self.assertEqual(offenders, {},
                         "these still import the retired root names; use the "
                         "canonical package path (shared.fsutil, "
                         "funnel.media_funnel, …)")


class TestCanonicalImportsResolve(unittest.TestCase):
    def test_the_packages_import(self):
        for name in PACKAGES:
            __import__(name)

    def test_the_modules_the_shims_pointed_at_all_exist(self):
        missing = []
        for name in sorted(RETIRED_SHIMS):
            if not any((ROOT / pkg / f"{name}.py").exists()
                       for pkg in PACKAGES):
                missing.append(name)
        self.assertEqual(missing, [],
                         f"shim removed but the real module is not in a "
                         f"package: {missing}")


if __name__ == "__main__":
    unittest.main()
