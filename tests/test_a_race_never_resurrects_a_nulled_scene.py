"""A PUSH RACE WRITES BACK ONLY WHAT THE RUN CHANGED.

2026-10-28. PR #706 nulled the giant-phone `hook_scene` on
nyc-noise-complaints-per-day at 14:26 UTC. The explainer posting run that
had checked out before it lost its push race at 18:47, and the story merger
took OUR story for the slug, the whole of it: the scene came back. The
19:18 forge, checked out before 18:47, did the same in the other direction
and reverted five retold stories and two drawn beats; the 23:48 posting run
then put the phone back again and threw away the forge's re-drawn
homeschool-surge beat. Main's unit suite went red on every PR.

A two-way "ours wins" cannot tell an edit from a stale copy. Given the base
the run last synced with, `merge_state_json` merges the story config
three-way, field by field, and `ci_commit_state.sh` hands it that base.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import merge_state_json as M                    # noqa: E402

PHONE = "def draw(cr, t):\n    giant_phone(cr)\n"


def _story(slug="nyc", **kw):
    s = {"slug": slug, "hook": "h", "closing": "c", "hook_scene": None,
         "segments": [{"say": "s0", "illustrated_scene": None},
                      {"say": "s1", "illustrated_scene": None}]}
    s.update(kw)
    return s


def _cfg(*stories):
    return {"niche": "n", "stories": [json.loads(json.dumps(s)) for s in stories]}


class TheMergeIsThreeWay(unittest.TestCase):
    def test_a_scene_main_nulled_stays_null(self):
        base = _cfg(_story(hook_scene=PHONE))
        theirs = _cfg(_story(hook_scene=None))                 # #706
        ours = _cfg(_story(hook_scene=PHONE, hook="sharper"))  # the stale run
        got = M.merge_for("data_learning/niche.config.json", theirs, ours, base)
        st = got["stories"][0]
        self.assertIsNone(st["hook_scene"], "the race put the nulled scene back")
        self.assertEqual(st["hook"], "sharper", "the run's own edit was lost")

    def test_without_a_base_the_old_rule_resurrects_it(self):
        """What the old code did, so the test above means something."""
        theirs = _cfg(_story(hook_scene=None))
        ours = _cfg(_story(hook_scene=PHONE, hook="sharper"))
        got = M.merge_for("data_learning/niche.config.json", theirs, ours)
        self.assertEqual(got["stories"][0]["hook_scene"], PHONE)

    def test_each_side_keeps_its_own_beat(self):
        base = _cfg(_story())
        t = _story(); t["segments"][1]["illustrated_scene"] = "redrawn-on-main"
        o = _story(); o["segments"][0]["illustrated_scene"] = "drawn-in-run"
        got = M.merge_stories3(_cfg(t), _cfg(o), base)["stories"][0]
        self.assertEqual(got["segments"][0]["illustrated_scene"], "drawn-in-run")
        self.assertEqual(got["segments"][1]["illustrated_scene"], "redrawn-on-main")

    def test_a_story_the_run_never_touched_is_mains(self):
        base = _cfg(_story(), _story("other", hook="old"))
        theirs = _cfg(_story(), _story("other", hook="retold"))
        ours = _cfg(_story(hook="mine"), _story("other", hook="old"))
        got = {s["slug"]: s for s in M.merge_stories3(theirs, ours, base)["stories"]}
        self.assertEqual(got["other"]["hook"], "retold")
        self.assertEqual(got["nyc"]["hook"], "mine")

    def test_a_real_conflict_still_goes_to_the_run(self):
        base = _cfg(_story(hook="a"))
        got = M.merge_stories3(_cfg(_story(hook="b")), _cfg(_story(hook="c")), base)
        self.assertEqual(got["stories"][0]["hook"], "c")

    def test_a_scene_for_words_main_rewrote_is_not_kept(self):
        base = _cfg(_story())
        t = _story(); t["segments"][0]["say"] = "rewritten"
        o = _story(); o["segments"][0]["illustrated_scene"] = "drawn-for-s0"
        got = M.merge_stories3(_cfg(t), _cfg(o), base)["stories"][0]
        self.assertEqual(got["segments"][0]["say"], "rewritten")
        self.assertIsNone(got["segments"][0]["illustrated_scene"])

    def test_new_stories_on_both_sides_survive(self):
        base = _cfg(_story())
        got = M.merge_stories3(_cfg(_story(), _story("forged")),
                               _cfg(_story(), _story("authored")), base)
        self.assertEqual([s["slug"] for s in got["stories"]], ["nyc", "forged", "authored"])

    def test_the_real_2026_10_28_race(self):
        """Replay the day's three persists three-way. Each run's own copy is
        what it pushed (ours won every slug, so the commit IS its copy), and
        its base is the main it checked out: 14:13 for the 18:47 run, #706
        for the 19:18 forge, 18:47 for the 23:48 run."""
        def show(rev):
            return json.loads(subprocess.check_output(
                ["git", "-C", str(ROOT), "show", f"{rev}:data_learning/niche.config.json"],
                stderr=subprocess.DEVNULL))
        try:
            v = {r: show(r) for r in ("e298bfaf4", "ed0a35d40", "27225c89d",
                                      "f121e98ff", "c588395c1")}
        except Exception:  # noqa: BLE001 — a shallow checkout
            self.skipTest("those commits are not in this checkout")
        main = M.merge_stories3(v["ed0a35d40"], v["27225c89d"], v["e298bfaf4"])
        main = M.merge_stories3(main, v["f121e98ff"], v["ed0a35d40"])
        main = M.merge_stories3(main, v["c588395c1"], v["27225c89d"])
        got = {s["slug"]: s for s in main["stories"]}
        self.assertIsNone(got["nyc-noise-complaints-per-day"]["hook_scene"])
        hs = got["homeschool-surge"]["segments"][1]["illustrated_scene"]
        self.assertIn("# scene standard: 2026-10-28.1", hs, "the forge's re-drawn beat was lost")
        run = {s["slug"]: s for s in v["c588395c1"]["stories"]}
        for slug in ("deepfake-video-explosion", "earthquake-detection-illusion"):
            self.assertEqual(got[slug]["hook"], run[slug]["hook"], f"{slug}: the retell was lost")
        self.assertEqual(got["earthquake-detection-illusion"]["segments"][0]["illustrated_scene"],
                         run["earthquake-detection-illusion"]["segments"][0]["illustrated_scene"])


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True).stdout


class ThePersistHandsTheMergerItsBase(unittest.TestCase):
    """The same race against a real bare remote, through the shell script."""

    def test_a_stale_run_does_not_put_back_what_main_nulled(self):
        with tempfile.TemporaryDirectory() as tds:
            td = Path(tds)
            bare = td / "remote.git"
            subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
            seed = td / "seed"
            subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True)
            (seed / "scripts").mkdir()
            for name in ("ci_commit_state.sh", "merge_posted_log.py", "merge_state_json.py"):
                (seed / "scripts" / name).write_text((ROOT / "scripts" / name).read_text())
            cfgp = Path("data_learning") / "niche.config.json"
            (seed / "data_learning").mkdir()
            (seed / cfgp).write_text(json.dumps(_cfg(_story(hook_scene=PHONE)), indent=1))
            for d in (seed,):
                _git(d, "config", "user.email", "t@t"); _git(d, "config", "user.name", "t")
            _git(seed, "add", "."); _git(seed, "commit", "-qm", "seed")
            _git(seed, "remote", "add", "origin", str(bare)); _git(seed, "push", "-q", "origin", "main")
            run, fix = td / "run", td / "fix"
            for d in (run, fix):
                subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{bare}", str(d)],
                               check=True)
                _git(d, "config", "user.email", "t@t"); _git(d, "config", "user.name", "t")
            # main nulls the scene (#706)
            (fix / cfgp).write_text(json.dumps(_cfg(_story(hook_scene=None)), indent=1))
            _git(fix, "commit", "-qam", "null the phone"); _git(fix, "push", "-q", "origin", "main")
            # the stale run sharpens the hook and persists
            (run / cfgp).write_text(json.dumps(_cfg(_story(hook_scene=PHONE, hook="sharper")), indent=1))
            r = subprocess.run(["bash", "scripts/ci_commit_state.sh", "explainer",
                                str(cfgp)], cwd=run, capture_output=True, text=True,
                               env={**os.environ, "CI_COMMIT_BRANCH": "main"})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("union-merging", r.stdout)
            _git(run, "fetch", "-q", "origin", "main")
            st = json.loads(_git(run, "show", f"origin/main:{cfgp}"))["stories"][0]
            self.assertIsNone(st["hook_scene"], "the persist resurrected a nulled scene")
            self.assertEqual(st["hook"], "sharper", "the run's own edit did not land")


if __name__ == "__main__":
    unittest.main()
