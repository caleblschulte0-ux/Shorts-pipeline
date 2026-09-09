"""Every data_learning test module must actually EXECUTE something.

`data_learning/tests/*` are free `test_*` functions, not unittest cases, so
the required suite (`unittest discover -s tests`) collects nothing from them.
They earn their keep only by being invoked by name from a workflow. Two of
them — `test_viz_director` and `test_viz_scene` — had no runner and were
named in no workflow, so for months they were a guardrail on paper: importing
either module and exiting 0 was the entire "test run" (doctor finding
`abfb291b5f65`).

This file is the required suite's hold on that arrangement. It does not
re-run those tests (several need ffmpeg, playwright and a network); it
asserts the three things whose absence made them silent:

  1. the module defines at least one `test_*` function,
  2. it has a `__main__` runner that goes through `_runner.run`, and
  3. some workflow really invokes it.

Plus the property that made a missing runner survive: a collect-and-run loop
that prints PASS over an empty list. `_runner.run` fails on zero.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "data_learning" / "tests"
WORKFLOWS = ROOT / ".github" / "workflows"


def _modules() -> list[Path]:
    return sorted(p for p in SUITE.glob("test_*.py"))


def _workflow_text() -> str:
    return "\n".join(p.read_text(errors="ignore")
                     for p in sorted(WORKFLOWS.glob("*.yml")))


class DataLearningTestsAreReallyRun(unittest.TestCase):
    def test_there_are_modules_to_check(self):
        # A glob that silently matches nothing is the same bug one level up.
        self.assertGreaterEqual(len(_modules()), 6)

    def test_every_module_defines_tests(self):
        for path in _modules():
            with self.subTest(module=path.name):
                tree = ast.parse(path.read_text())
                fns = [n for n in tree.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and n.name.startswith("test_")]
                classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
                           and any(isinstance(b, ast.Attribute)
                                   and b.attr == "TestCase"
                                   for b in n.bases)]
                script = [n for n in tree.body
                          if isinstance(n, ast.FunctionDef)
                          and n.name in ("main", "_main")]
                self.assertTrue(
                    fns or classes or script,
                    f"{path.name} defines no test_* function, no TestCase and "
                    "no main() — it would 'pass' by doing nothing")

    def test_every_free_function_module_has_a_runner(self):
        for path in _modules():
            src = path.read_text()
            tree = ast.parse(src)
            free = [n for n in tree.body
                    if isinstance(n, ast.FunctionDef)
                    and n.name.startswith("test_")]
            if not free:
                continue        # a real unittest module; discovery covers it
            with self.subTest(module=path.name):
                self.assertIn(
                    '__name__ == "__main__"', src,
                    f"{path.name} has {len(free)} free test functions and no "
                    "runner — nothing executes them")
                self.assertIn(
                    "_runner import run", src,
                    f"{path.name} must run through data_learning.tests._runner "
                    "so a zero-test collection fails instead of printing PASS")

    def test_every_module_is_invoked_by_a_workflow(self):
        wf = _workflow_text()
        for path in _modules():
            with self.subTest(module=path.name):
                # assertTrue, not assertIn: assertIn would print every
                # workflow file in the repo as the haystack.
                self.assertTrue(
                    f"data_learning/tests/{path.name}" in wf,
                    f"{path.name} is invoked by no workflow — it runs nowhere")

    def test_the_shared_runner_fails_on_zero_tests(self):
        import contextlib
        import io
        import sys
        sys.path.insert(0, str(ROOT))
        from data_learning.tests import _runner
        buf = io.StringIO()          # the runner prints; keep the suite quiet
        ctx = contextlib.redirect_stdout(buf)
        with ctx:
            self.assertEqual(_runner.run({}, "empty"), 1)
            self.assertEqual(_runner.run({"test_ok": lambda: None}, "one"), 0)

        def _boom():
            raise AssertionError("no")
        with ctx:
            self.assertEqual(_runner.run({"test_bad": _boom}, "bad"), 1)

        def _typo():
            raise TypeError("wrong shape")
        # A non-assertion error is a failure too — it used to abort the
        # module and take every test after it with it.
        with ctx:
            self.assertEqual(_runner.run({"test_typo": _typo}, "typo"), 1)


if __name__ == "__main__":
    unittest.main()
