"""A CI PUSH RACE MUST NOT DELETE WHAT MAIN JUST LEARNED.

2026-09-21, 17:33 UTC: PR #407 merged four hand-authored tier-1 mechanics
into `data_learning/viz_mechanics.json`. 17:47: the explainer run that had
checked out main at 16:58 lost the push race, and `ci_commit_state.sh`
restored ITS copy of the library over fresh main — sixty entries, zero
exemplars — and reported success. Posted logs never had this problem
because they are unioned; now the library (by `sig`) and the story config
(by `slug`) are too, through `scripts/merge_state_json.py`.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import merge_state_json as M                    # noqa: E402


def _m(sig, **kw):
    return {"sig": sig, "mechanic": sig, "code": "c", **kw}


class TheLibraryIsUnioned(unittest.TestCase):
    def test_the_seeded_teachers_survive_a_stale_run(self):
        theirs = [_m("a"), _m("t1", exemplar=True, starred=True, grade={"bespoke": 3})]
        ours = [_m("a"), _m("new-from-run", moves=True)]
        got = M.merge_mechanics(theirs, ours)
        self.assertEqual({e["sig"] for e in got}, {"a", "t1", "new-from-run"})
        t1 = next(e for e in got if e["sig"] == "t1")
        self.assertTrue(t1["exemplar"]); self.assertEqual(t1["grade"]["bespoke"], 3)

    def test_a_grade_on_either_side_is_kept_and_the_newer_wins(self):
        theirs = [_m("x", grade={"bespoke": 1, "ts": "2026-09-20T00:00:00Z"})]
        ours = [_m("x", grade={"bespoke": 3, "ts": "2026-09-21T00:00:00Z"}, moves=True)]
        got = M.merge_mechanics(theirs, ours)
        self.assertEqual(got[0]["grade"]["bespoke"], 3)
        self.assertIs(got[0]["moves"], True)
        got2 = M.merge_mechanics(ours, theirs)
        self.assertEqual(got2[0]["grade"]["bespoke"], 3, "the older grade won")

    def test_legacy_entries_without_a_sig_survive_and_get_one(self):
        """The first live merge dropped 24 of them: 64 -> 40."""
        legacy = {"mechanic": "old-one", "code": "c1", "concept": "x", "starred": True}
        theirs = [dict(legacy), _m("t1", exemplar=True)]
        ours = [dict(legacy), _m("run")]
        got = M.merge_mechanics(theirs, ours)
        self.assertEqual(len(got), 3)
        old = next(e for e in got if e["mechanic"] == "old-one")
        import hashlib
        self.assertEqual(old["sig"], hashlib.sha1(b"old-onec1").hexdigest()[:12])

    def test_the_real_2026_09_21_race_loses_nothing(self):
        """The two exact library versions the runner merged, if git has them."""
        import subprocess
        try:
            a = json.loads(subprocess.check_output(
                ["git", "-C", str(ROOT), "show", "4ace6373:data_learning/viz_mechanics.json"],
                stderr=subprocess.DEVNULL))
            b = json.loads(subprocess.check_output(
                ["git", "-C", str(ROOT), "show", "164f801a:data_learning/viz_mechanics.json"],
                stderr=subprocess.DEVNULL))
        except Exception:  # noqa: BLE001 — a shallow checkout
            self.skipTest("those commits are not in this checkout")
        got = M.merge_mechanics(a, b)
        self.assertGreaterEqual(len(got), len(a))
        self.assertEqual(sum(1 for e in got if e.get("exemplar")), 4)

    def test_starred_is_never_lost_and_the_cap_holds(self):
        theirs = [_m(f"s{i}", starred=(i < 5)) for i in range(130)]
        ours = [_m("brand-new")]
        got = M.merge_mechanics(theirs, ours)
        self.assertLessEqual(len(got), M.LIB_CAP)
        self.assertEqual(sum(1 for e in got if e.get("starred")), 5)
        self.assertIn("brand-new", {e["sig"] for e in got})


class TheStoriesAreUnioned(unittest.TestCase):
    def test_mains_new_story_and_the_runs_rendered_scene_both_survive(self):
        theirs = {"stories": [{"slug": "old", "segments": [{"key": "a"}]},
                              {"slug": "routine-added-this", "segments": []}]}
        ours = {"stories": [{"slug": "old", "segments": [
            {"key": "a", "scene": {"mechanic": "m", "code": "x", "rendered_as": "seg0"}}]}]}
        got = M.merge_stories(theirs, ours)
        self.assertEqual([s["slug"] for s in got["stories"]], ["old", "routine-added-this"])
        self.assertEqual(got["stories"][0]["segments"][0]["scene"]["code"], "x")

    def test_a_graded_scene_on_main_is_not_erased_by_an_older_copy(self):
        theirs = {"stories": [{"slug": "s", "segments": [
            {"key": "a", "scene": {"code": "x", "grade": {"bespoke": 3}}}]}]}
        ours = {"stories": [{"slug": "s", "segments": [{"key": "a"}]}]}
        got = M.merge_stories(theirs, ours)
        self.assertEqual(got["stories"][0]["segments"][0]["scene"]["grade"]["bespoke"], 3)


class TheScriptFailsClosedAndTheShellRoutesIt(unittest.TestCase):
    def test_unparseable_input_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "t.json"; t.write_text("{not json")
            o = Path(td) / "o.json"; o.write_text("[]")
            rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "merge_state_json.py"),
                                 str(t), str(o), str(Path(td) / "viz_mechanics.json")],
                                capture_output=True).returncode
            self.assertEqual(rc, 1)

    def test_the_cli_round_trips_a_library(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "t.json"; t.write_text(json.dumps([_m("t1", exemplar=True)]))
            o = Path(td) / "o.json"; o.write_text(json.dumps([_m("run")]))
            out = Path(td) / "viz_mechanics.json"
            subprocess.run([sys.executable, str(ROOT / "scripts" / "merge_state_json.py"),
                            str(t), str(o), str(out)], check=True, capture_output=True)
            self.assertEqual({e["sig"] for e in json.loads(out.read_text())}, {"t1", "run"})

    def test_ci_commit_state_routes_both_files_to_the_merger(self):
        sh = (ROOT / "scripts" / "ci_commit_state.sh").read_text()
        self.assertIn("-name 'viz_mechanics.json'", sh)
        self.assertIn("-name 'niche.config.json'", sh)
        self.assertIn("merge_state_json.py", sh)
        # and still refuses to push when the merge fails
        i = sh.index("python3 scripts/merge_state_json.py")
        self.assertIn(".merge_failed", sh[i:i + 400])


def _git(cwd, *args, **kw):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True, **kw).stdout


class AMidRunPushRaceKeepsTheRunsOtherArtifacts(unittest.TestCase):
    """2026-09-22 09:36 UTC: post_stories pushed the posted log the moment a
    video was live (one path), main had moved three times since checkout,
    the push failed, and the race handler backed up THAT path, reset --hard,
    and destroyed seven appended verdicts and a repair plan. This stages the
    same race against a real bare remote and requires everything to survive:
    the posted log unioned and pushed; the ledger a union of both sides,
    still uncommitted for the caller's own persist; the plan's edit intact."""

    def _seed(self, td: Path):
        bare = td / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
        seed = td / "seed"
        subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True)
        _git(seed, "config", "user.email", "t@t"); _git(seed, "config", "user.name", "t")
        (seed / "scripts").mkdir()
        for name in ("ci_commit_state.sh", "merge_posted_log.py", "merge_state_json.py"):
            (seed / "scripts" / name).write_text((ROOT / "scripts" / name).read_text())
        (seed / "state" / "scene_plans").mkdir(parents=True)
        (seed / "state" / "explainer_posted_log.json").write_text(json.dumps({"posted": {}}))
        (seed / "state" / "showrunner_verdicts.jsonl").write_text('{"slug": "A"}\n')
        (seed / "state" / "scene_plans" / "p.json").write_text('{"v": 1}')
        _git(seed, "add", "."); _git(seed, "commit", "-qm", "seed")
        _git(seed, "remote", "add", "origin", str(bare)); _git(seed, "push", "-q", "origin", "main")
        return bare

    def test_the_verdicts_and_the_plan_survive_the_race(self):
        with tempfile.TemporaryDirectory() as tds:
            td = Path(tds)
            bare = self._seed(td)
            run = td / "run"; other = td / "other"
            for d in (run, other):
                subprocess.run(["git", "clone", "-q", str(bare), str(d)], check=True)
                _git(d, "config", "user.email", "t@t"); _git(d, "config", "user.name", "t")
            # main moves: another workflow lands a verdict of its own
            with (other / "state" / "showrunner_verdicts.jsonl").open("a") as fh:
                fh.write('{"slug": "B-from-main"}\n')
            _git(other, "commit", "-qam", "other run"); _git(other, "push", "-q", "origin", "main")
            # the stale run: two verdicts appended, a plan repaired, a video posted
            with (run / "state" / "showrunner_verdicts.jsonl").open("a") as fh:
                fh.write('{"slug": "C"}\n{"slug": "D"}\n')
            (run / "state" / "scene_plans" / "p.json").write_text('{"v": 2}')
            (run / "state" / "explainer_posted_log.json").write_text(
                json.dumps({"posted": {"y": {"at": "2026-09-22T11:50:00Z"}}}))
            r = subprocess.run(["bash", "scripts/ci_commit_state.sh", "posted y",
                                "state/explainer_posted_log.json"],
                               cwd=run, capture_output=True, text=True,
                               env={**__import__("os").environ, "CI_COMMIT_BRANCH": "main"})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("union-merging", r.stdout)
            # the posted log reached the remote
            remote_log = json.loads(_git(run, "show", "origin/main:state/explainer_posted_log.json"))
            self.assertIn("y", remote_log["posted"])
            # the ledger is a UNION of both sides and is still the run's to commit
            led = (run / "state" / "showrunner_verdicts.jsonl").read_text().splitlines()
            self.assertEqual(led, ['{"slug": "A"}', '{"slug": "B-from-main"}',
                                   '{"slug": "C"}', '{"slug": "D"}'])
            self.assertEqual(json.loads((run / "state" / "scene_plans" / "p.json").read_text()), {"v": 2})
            status = _git(run, "status", "--porcelain")
            self.assertIn("state/showrunner_verdicts.jsonl", status)
            self.assertIn("state/scene_plans/p.json", status)
            self.assertNotIn("posted_log", status, "the given path was committed")

    def test_the_line_union_never_drops_or_reorders(self):
        got = M.merge_jsonl('{"a":1}\n{"b":2}\n', '{"a":1}\n{"c":3}\n\n')
        self.assertEqual(got, '{"a":1}\n{"b":2}\n{"c":3}\n')
        self.assertEqual(M.merge_jsonl("", ""), "")


if __name__ == "__main__":
    unittest.main()
