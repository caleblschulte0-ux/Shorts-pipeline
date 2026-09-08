"""The credential heartbeat, and the one distinction it exists to make.

Operator, 2026-09-08: *"I can't be refreshing the Gemini key all the time."*

They should not have to. The reason it feels that way is that nothing in the
pipeline could tell them WHICH key was failing or WHY — every preflight checks
whether a credential is set, and a revoked key is a non-empty string. So a
dead key and a spent quota look identical from the outside, and the only
defence is to rotate everything on a schedule.

These hold the two things that make the answer trustworthy: a 429 must never
be reported as a key to replace, and the alarm must fire on the DAY a key
dies rather than every day after.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# LOADED BY PATH, never by putting `scripts/` on sys.path. That shortcut makes
# `scripts/test_exchange.py` shadow `tests/test_exchange.py` and unittest
# discovery dies with "module incorrectly imported" for the whole suite —
# which is a very confusing way to break every other test in the repo.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "credential_check",
    Path(__file__).resolve().parent.parent / "scripts" / "credential_check.py")
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)


class ADeadKeyIsNotASpentQuota(unittest.TestCase):
    """The whole point. A 401 sends somebody to mint a new key; a 429 means
    the key is fine and the window is spent, and rotating it changes nothing.
    Reporting both as "broken" is what teaches an operator to rotate on a
    schedule to stay ahead of a problem they do not have."""

    def test_a_refusal_is_DEAD(self):
        for code in (401, 403):
            self.assertEqual(cc.classify(code)[0], cc.DEAD, code)

    def test_a_rate_limit_is_LIMITED_and_asks_for_nothing(self):
        status, detail = cc.classify(429)
        self.assertEqual(status, cc.LIMITED)
        self.assertIn("rate limited", detail)
        self.assertIn("the key is fine", cc._ACTION[cc.LIMITED])

    def test_an_answer_is_OK(self):
        self.assertEqual(cc.classify(200)[0], cc.OK)

    def test_a_400_is_only_dead_when_the_service_SAYS_the_key_is(self):
        """Google returns 400 API_KEY_INVALID rather than 401, so a blanket
        "400 means fine" misses a genuinely dead Gemini key. A 400 that says
        nothing about the key is not evidence about the key."""
        self.assertEqual(
            cc.classify(400, '{"error":{"status":"API_KEY_INVALID"}}')[0],
            cc.DEAD)
        self.assertEqual(cc.classify(400, "malformed page range")[0],
                         cc.UNREACHABLE)

    def test_the_service_being_down_says_NOTHING_about_the_key(self):
        """A 500 reported as a dead key is a wasted afternoon and a rotated
        credential that was never the problem."""
        for code in (500, 502, 503):
            self.assertEqual(cc.classify(code)[0], cc.UNREACHABLE, code)
        self.assertIn("not a key problem", cc._ACTION[cc.UNREACHABLE])


class ItAlarmsOnTheDayTheKeyDies(unittest.TestCase):
    """`daily.yml` already learned this once, in its own words: "alerting on
    it daily is how people learn to ignore the channel". A standing alarm for
    a key you already know about buries the one that says something new."""

    def _report(self, **status):
        return {"credentials": [{"name": k, "env": "X", "status": v,
                                 "detail": ""} for k, v in status.items()]}

    def test_a_key_that_just_died_is_reported(self):
        self.assertEqual(
            cc.changed_to_dead(self._report(gemini=cc.DEAD),
                               self._report(gemini=cc.OK)),
            ["gemini"])

    def test_a_key_that_was_ALREADY_dead_is_not_reported_again(self):
        self.assertEqual(
            cc.changed_to_dead(self._report(gemini=cc.DEAD),
                               self._report(gemini=cc.DEAD)),
            [])

    def test_the_first_ever_run_still_reports(self):
        """No previous record is not evidence that the key was fine."""
        self.assertEqual(cc.changed_to_dead(self._report(groq=cc.DEAD), None),
                         ["groq"])

    def test_a_spent_quota_never_raises_the_alarm(self):
        self.assertEqual(
            cc.changed_to_dead(self._report(gemini=cc.LIMITED),
                               self._report(gemini=cc.OK)),
            [])


class ItReportsAndNeverACTS(unittest.TestCase):
    """It is allowed to say a key is dead. It is not allowed to disable a
    channel, edit a secret, or change what any workflow does — a checker that
    can switch things off is a new way for the day to go dark quietly."""

    def test_it_writes_only_its_own_record(self):
        src = Path(cc.__file__).read_text()
        for forbidden in ("posted_log", "channel_registry", "subprocess.run(['git'",
                          'subprocess.run(["git"'):
            self.assertNotIn(forbidden, src)

    def test_the_only_subprocess_it_runs_is_the_claude_cli(self):
        src = Path(cc.__file__).read_text()
        self.assertEqual(src.count("subprocess.run("), 1)
        self.assertIn('subprocess.run(["claude"', src)


class ItFindsEveryChannelsToken(unittest.TestCase):
    """Discovered from the environment, not listed. A hardcoded list drifts
    the day a channel is added, and the token nobody is watching is then the
    new one — while a dead YouTube token does not degrade a day, it ENDS it:
    the video renders, passes every gate, and has nowhere to go."""

    def test_every_youtube_token_in_the_environment_is_probed(self):
        env = {"YOUTUBE_TOKEN_JSON": "{}",
               "YOUTUBE_TOKEN_JSON_EXPLAINER": "{}",
               "YOUTUBE_TOKEN_JSON_BRANDNEW": "{}",
               "YOUTUBE_TOKEN_JSON_EMPTY": "   ",
               "SOMETHING_ELSE": "x"}
        self.assertEqual(cc.youtube_envs(env),
                         ["YOUTUBE_TOKEN_JSON", "YOUTUBE_TOKEN_JSON_BRANDNEW",
                          "YOUTUBE_TOKEN_JSON_EXPLAINER"])

    def test_a_malformed_token_secret_is_dead_not_a_crash(self):
        self.assertEqual(cc.probe_youtube("not json")[0], cc.DEAD)
        self.assertEqual(
            cc.probe_youtube(json.dumps({"refresh_token": "r"}))[0], cc.DEAD)


class ItNeverProbesWhatItWasNotGiven(unittest.TestCase):
    def test_offline_mode_calls_nothing(self):
        def _boom(_):
            raise AssertionError("offline mode made a network call")
        real, cc.PROBES = cc.PROBES, (("groq", "GROQ_API_KEY", _boom),)
        try:
            rows = cc.check(offline=True,
                            environ={"GROQ_API_KEY": "x"})["credentials"]
        finally:
            cc.PROBES = real
        self.assertEqual(rows[0]["status"], "set")

    def test_an_unset_credential_is_never_called(self):
        def _boom(_):
            raise AssertionError("probed a credential that is not set")
        real, cc.PROBES = cc.PROBES, (("groq", "GROQ_API_KEY", _boom),)
        try:
            rows = cc.check(environ={})["credentials"]
        finally:
            cc.PROBES = real
        self.assertEqual(rows[0]["status"], cc.UNSET)

    def test_a_probe_that_explodes_is_UNREACHABLE_not_dead(self):
        """A checker that reports a dead key because DNS hiccuped costs a
        credential rotation nobody needed."""
        def _boom(_):
            raise OSError("dns")
        real, cc.PROBES = cc.PROBES, (("groq", "GROQ_API_KEY", _boom),)
        try:
            rows = cc.check(environ={"GROQ_API_KEY": "x"})["credentials"]
        finally:
            cc.PROBES = real
        self.assertEqual(rows[0]["status"], cc.UNREACHABLE)


class TheWorkflowMatchesTheScript(unittest.TestCase):
    WF = Path(__file__).resolve().parent.parent / ".github" / "workflows" \
        / "credentials.yml"

    def test_it_passes_every_credential_the_script_probes(self):
        wf = self.WF.read_text()
        for _name, env, _p in cc.PROBES:
            self.assertIn(env, wf, f"{env} is probed but never passed in")

    def test_a_dead_key_does_not_fail_the_run(self):
        """The heartbeat's job is to SAY so. A red workflow beside a green
        pipeline is the same ignorable noise as a daily alarm."""
        self.assertIn("continue-on-error: true", self.WF.read_text())

    def test_it_alerts_on_newly_dead_only(self):
        wf = self.WF.read_text()
        self.assertIn("steps.probe.outputs.newly_dead != ''", wf)


if __name__ == "__main__":
    unittest.main()
