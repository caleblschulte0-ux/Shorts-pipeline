"""The expression proof runs BEFORE the merge, not after it.

Doctor finding 808fcf2f9b8e. `auto-merge.yml` squash-merges a claude PR the
moment `sanity` and `tests` go green. The heavy expression tests are
deliberately excluded from its scripts/ loop ("covered by
expression-tests.yml"), and expression-tests.yml ran as a NEIGHBOURING
workflow that `automerge` did not need. So a PR changing
`data_learning/pro_render.py` — the production renderer the whole contract is
about — merged before any measured render had run, and the visual proof
started only once the change was already on main. A proof that runs after the
merge is a report, not a gate.

Its `pull_request:` paths were also a strict subset of its `push:` paths:
pro_render.py and `scripts/test_expressions_render.py` appeared only on push.
The changes most worth proving were exactly the ones that skipped the proof.

And `scripts/test_expressions_render.py` ran nowhere at all — skipped by name
in auto-merge as "covered by expression-tests.yml", and not invoked by
expression-tests.yml.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WF_DIR = ROOT / ".github" / "workflows"
AM = yaml.safe_load((WF_DIR / "auto-merge.yml").read_text())
EX = yaml.safe_load((WF_DIR / "expression-tests.yml").read_text())
EX_ON = EX.get(True, EX.get("on", {}))


class TheMergeWaitsForTheProof(unittest.TestCase):
    def test_automerge_needs_the_expression_suite(self):
        self.assertIn("expression", AM["jobs"]["automerge"]["needs"])

    def test_the_expression_job_really_calls_that_workflow(self):
        self.assertEqual(AM["jobs"]["expression"]["uses"],
                         "./.github/workflows/expression-tests.yml")

    def test_the_suite_is_callable(self):
        self.assertIn("workflow_call", EX_ON,
                      "the merge gate cannot call a workflow that does not "
                      "offer workflow_call")

    def test_a_failed_expression_suite_blocks_the_merge(self):
        cond = " ".join(str(AM["jobs"]["automerge"]["if"]).split())
        self.assertIn("needs.expression.result != 'failure'", cond)
        self.assertIn("needs.expression.result != 'cancelled'", cond)

    def test_always_does_not_smuggle_a_red_suite_through(self):
        """`always()` is needed because `expression` is skipped on PRs that
        touch none of its files — but it makes every other dependency's
        result stop gating implicitly, so each must be checked by hand."""
        cond = " ".join(str(AM["jobs"]["automerge"]["if"]).split())
        self.assertIn("always()", cond)
        for job in ("sanity", "tests"):
            with self.subTest(job=job):
                self.assertIn(f"needs.{job}.result == 'success'", cond)

    def test_the_gate_still_only_touches_claude_prs(self):
        cond = " ".join(str(AM["jobs"]["automerge"]["if"]).split())
        self.assertIn("startsWith(github.head_ref, 'claude/')", cond)
        self.assertIn("github.event.pull_request.draft == false", cond)


class ThePathsCoverWhatTheContractIsAbout(unittest.TestCase):
    def test_pull_request_paths_match_push_paths(self):
        self.assertEqual(EX_ON["pull_request"]["paths"],
                         EX_ON["push"]["paths"],
                         "a path that only triggers on push proves the change "
                         "after it has already merged")

    def test_the_production_renderer_is_covered_on_a_pr(self):
        self.assertIn("data_learning/pro_render.py",
                      EX_ON["pull_request"]["paths"])

    def test_every_test_the_suite_runs_is_also_a_trigger(self):
        """A test file that can change without re-running its own suite is a
        test nobody is proving."""
        runs = "\n".join(s.get("run", "") for s in EX["jobs"]["test"]["steps"])
        paths = EX_ON["pull_request"]["paths"]
        for name in ("test_expressions.py", "test_expressions_render.py",
                     "verify_expressions.py", "verify_expression_gates.py"):
            with self.subTest(script=name):
                self.assertIn(name, runs, f"{name} is invoked by nothing")
                self.assertIn(f"scripts/{name}", paths)


class NothingIsSkippedIntoOblivion(unittest.TestCase):
    """auto-merge skips two scripts by name as 'covered by
    expression-tests.yml'. That claim has to be true."""

    def test_every_script_automerge_skips_is_run_by_the_expression_suite(self):
        loop = next(s for s in AM["jobs"]["tests"]["steps"]
                    if s.get("name") == "scripts/ suite")
        runs = "\n".join(s.get("run", "") for s in EX["jobs"]["test"]["steps"])
        # the shell `case` arm, e.g. "test_a.py|test_b.py)"
        cleaned = set()
        for tok in loop["run"].split():
            if not tok.endswith(")") or ".py" not in tok:
                continue
            for name in tok.rstrip(")").split("|"):
                if name.startswith("test_") and name.endswith(".py"):
                    cleaned.add(name)
        self.assertTrue(cleaned, "could not parse the skip list")
        for name in sorted(cleaned):
            with self.subTest(script=name):
                self.assertIn(name, runs,
                              f"auto-merge skips {name} as 'covered by "
                              "expression-tests.yml' and that workflow does "
                              "not run it — it runs nowhere")


class ThePathCheckReadsOneList(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "expression_paths_touched",
            ROOT / "scripts" / "expression_paths_touched.py")
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_the_globs_come_from_the_workflow_not_a_copy(self):
        self.assertEqual(self.m.contract_globs(), EX_ON["pull_request"]["paths"])

    def test_a_renderer_change_is_touched(self):
        self.assertTrue(self.m.matches(["data_learning/pro_render.py"],
                                       self.m.contract_globs()))

    def test_an_ordinary_package_pr_is_not(self):
        self.assertEqual(
            self.m.matches(["state/trending_packages/20260909/a.json",
                            "docs/README.md"], self.m.contract_globs()), [])

    def test_it_fails_open_when_it_cannot_tell(self):
        """Running the suite unnecessarily costs 25 minutes; skipping it
        wrongly costs the gate."""
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out"
            out.write_text("")
            os.environ["GITHUB_OUTPUT"] = str(out)
            try:
                rc = self.m.main(["not-a-sha"])       # too few args
                written = out.read_text()
            finally:
                os.environ.pop("GITHUB_OUTPUT", None)
        self.assertEqual(rc, 0)
        self.assertIn("touched=true", written)


if __name__ == "__main__":
    unittest.main()
