"""Third's fallback slate must be sized from the registry, never a template.

Doctor finding, signature 5ac409690185, ruled `doing` 2026-08-15:
`state/third_packages/default_clip.json`
carried its own `count` field (4) while `config/channel_registry.json` set
`target_count("third")` to 6. `run_third.main` read the template's count
with no registry lookup at all, so a flawless fallback day topped out at
4/6 — one quality rejection produced the 3/6 shape the 2026-08-13 alarm
actually recorded. The registry is supposed to be the ONLY place channel
policy lives (CLAUDE.md); a template field that silently wins is a second
source of truth.

    python -m unittest tests.test_third_fallback_count -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))   # APPEND: see note below

from shared import channel_registry  # noqa: E402
import run_third  # noqa: E402

# A minimal fallback template shaped like the real default_clip.json, but
# with a `count` deliberately different from the live registry's
# target_count("third") so the test proves the template loses.
_FIXTURE_TEMPLATE = {
    "count": 999,
    "story_count": 1,
    "channel": "third",
    "title": "{clip_title}",
    "capture": {"kind": "twitch_clip", "sources": {"twitch": ["kaicenat"]},
                "core": ["kaicenat"], "range": "24hr", "top": 8,
                "min_views": 1500, "min_pool": 8, "min_banger": 0.5,
                "min_banger_content": 0.7, "max_per_streamer": 2,
                "content_hard_floor": 0.35},
    "hashtags": ["shorts"],
}


class ThirdFallbackSlateSizeTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._orig_package_dir = run_third.PACKAGE_DIR
        self._tmpdir_ctx = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir_ctx.cleanup)
        tmp_path = Path(self._tmpdir_ctx.name)
        run_third.PACKAGE_DIR = tmp_path
        (tmp_path / "default_clip.json").write_text(
            json.dumps(_FIXTURE_TEMPLATE))

    def tearDown(self):
        run_third.PACKAGE_DIR = self._orig_package_dir

    def test_slate_size_comes_from_the_live_registry_not_the_template(self):
        registry_target = channel_registry.target_count("third")
        self.assertGreater(registry_target, 0)
        self.assertNotEqual(
            _FIXTURE_TEMPLATE["count"], registry_target,
            "fixture must disagree with the registry or this test cannot "
            "distinguish the fix from the bug")

        packages = run_third._synthesize_fallback_packages("20260819")

        self.assertEqual(len(packages), registry_target)
        slugs = [pkg["slug"] for pkg, _ in packages]
        self.assertEqual(len(slugs), len(set(slugs)),
                         "synthesized slugs must be unique")
        self.assertEqual(
            slugs, [f"clip-20260819-{i}" for i in range(1, registry_target + 1)])

    def test_synthesis_is_deterministic_for_the_same_date(self):
        first = run_third._synthesize_fallback_packages("20260819")
        second = run_third._synthesize_fallback_packages("20260819")
        self.assertEqual([p["story_mode"] for p, _ in first],
                         [p["story_mode"] for p, _ in second])

    def test_no_template_synthesizes_nothing(self):
        (run_third.PACKAGE_DIR / "default_clip.json").unlink()
        self.assertEqual(run_third._synthesize_fallback_packages("20260819"),
                         [])

    def test_unresolvable_registry_refuses_to_guess_a_count(self):
        with mock.patch.object(
                channel_registry, "target_count",
                side_effect=channel_registry.RegistryError("boom")):
            with self.assertRaises(channel_registry.RegistryError):
                run_third._synthesize_fallback_packages("20260819")


class ThirdBrainProcessContractTest(unittest.TestCase):
    """Doctor finding 3445b0aecae4, ruled `doing`: `_call_claude` only
    treated a nonzero CLI exit as failure when the output matched the
    usage-limit regex — any OTHER failed process that had emitted a JSON
    object before dying (partial reply, stale buffer) was parsed and
    returned as a successful brain answer, so ranking / scene judgment ran
    on garbage while health accounting recorded an `ok`. The contract now:
    rc=0 before any stdout is trusted; the usage-limit breaker keeps its
    regex path; every other nonzero exit raises a bounded diagnostic that
    the callers already catch and count via `_brain_note(False)`.

        python -m unittest tests.test_third_fallback_count -v
    """

    def setUp(self):
        from third_capture import author
        self.author = author
        # snapshot the module-level breaker + health counters so these
        # tests cannot leak an armed limit into another test's run
        self._limit = dict(author._LIMIT_HIT)
        self._brain = dict(author._BRAIN)
        author._LIMIT_HIT.update(at="", detail="")
        env = mock.patch.dict(os.environ,
                              {"CLAUDE_CODE_OAUTH_TOKEN": "test-token"})
        env.start()
        self.addCleanup(env.stop)
        # _call_claude imports shutil/subprocess inside the function, so the
        # patches go on the modules themselves, not on author.*
        which = mock.patch("shutil.which", return_value="/usr/bin/claude")
        which.start()
        self.addCleanup(which.stop)

    def tearDown(self):
        self.author._LIMIT_HIT.clear()
        self.author._LIMIT_HIT.update(self._limit)
        self.author._BRAIN.clear()
        self.author._BRAIN.update(self._brain)

    def _completed(self, rc, stdout="", stderr=""):
        import subprocess
        return subprocess.CompletedProcess(
            args=["claude"], returncode=rc, stdout=stdout, stderr=stderr)

    def test_nonzero_exit_with_valid_json_is_a_failure_not_an_answer(self):
        """The exact shape from the finding's evidence: rc=1, a complete
        JSON object on stdout, a transport error on stderr."""
        with mock.patch("subprocess.run", return_value=self._completed(
                1, stdout='{"title": "partial"}',
                stderr="fatal transport error")):
            with self.assertRaises(RuntimeError) as ctx:
                self.author._call_claude("hi")
        msg = str(ctx.exception)
        self.assertIn("rc=1", msg)
        self.assertIn("fatal transport error", msg,
                      "the diagnostic must carry the CLI's own message")
        self.assertFalse(self.author.brain_limited()["at"],
                         "a plain failure must not arm the usage-limit "
                         "breaker")

    def test_nonzero_exit_with_limit_text_takes_the_breaker_path(self):
        with mock.patch("subprocess.run", return_value=self._completed(
                1, stderr="You have hit your usage limit — resets at 5pm")):
            self.assertIsNone(self.author._call_claude("hi"))
        self.assertTrue(self.author.brain_limited()["at"],
                        "a limit-shaped failure must arm the breaker, "
                        "not raise")

    def test_zero_exit_with_valid_json_is_accepted(self):
        with mock.patch("subprocess.run", return_value=self._completed(
                0, stdout='{"title": "good"}')):
            self.assertEqual(self.author._call_claude("hi"),
                             {"title": "good"})

    def test_the_caller_counts_the_failure_not_a_success(self):
        """The health accounting is why this matters: `rank_clips` must
        record a failed brain task (and fall back), never an `ok` built
        from a dead process's stdout."""
        before = dict(self.author._BRAIN)
        with mock.patch("subprocess.run", return_value=self._completed(
                1, stdout='{"scores": [{"i": 0, "banger": 0.9}]}',
                stderr="fatal transport error")), \
                mock.patch.object(self.author, "_call_groq",
                                  return_value=None):
            out = self.author.rank_clips([{"channel": "x", "views": 1,
                                           "vph": 1.0, "title": "t",
                                           "url": "u"}])
        self.assertEqual(out, {}, "a failed process produced a ranking")
        self.assertEqual(self.author._BRAIN["ok"], before["ok"],
                         "a failed call was counted as a healthy brain")
        self.assertEqual(self.author._BRAIN["fail"], before["fail"] + 1)


if __name__ == "__main__":
    unittest.main()
