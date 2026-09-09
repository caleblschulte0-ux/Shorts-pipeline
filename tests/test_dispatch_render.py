"""The render handoff, tested by RUNNING it.

Doctor finding d486c2fbfdaf. The regression test for the critical Phase B ->
Daily handoff (itself the repair for doctor finding 2fc5cbb21cca, a full
zero-render day with every check green) parsed the workflow YAML and looked
for the substring `204`, a `HTTP.*!=.*204` regex, and an `exit 1` within 400
characters of it. It never executed the branch or mocked the API. A refactor
could leave those tokens in a comment or an unreachable branch while a
rejected dispatch exited zero, and every assertion still passed.

The logic is `scripts/dispatch_render.py` now, so the failure modes are
executable: 204, 401/403/404/422, a timeout, a malformed response, a missing
token. The workflow keeps one thin wiring assertion.

The rule these encode: **we may only report a render was queued when GitHub
said so.** Every other outcome — a refusal, a 202, a socket reset — means we
do not know, and not knowing must be loud.
"""
from __future__ import annotations

import importlib.util
import io
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "dispatch_render", ROOT / "scripts" / "dispatch_render.py")
dr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dr)


def _resp(status: int, body: bytes = b""):
    r = mock.MagicMock()
    r.status = status
    r.getcode.return_value = status
    r.read.return_value = body
    r.__enter__.return_value = r
    return r


def _opener(resp):
    return lambda req, timeout=None: resp


class AcceptedMeansAccepted(unittest.TestCase):
    def test_204_is_the_only_success(self):
        self.assertEqual(
            dr.dispatch("o/r", "daily.yml", "main", "t",
                        opener=_opener(_resp(204))), 204)

    def test_the_request_is_the_one_we_mean_to_send(self):
        seen = {}

        def opener(req, timeout=None):
            seen["url"] = req.full_url
            seen["method"] = req.get_method()
            seen["body"] = req.data
            seen["auth"] = req.get_header("Authorization")
            return _resp(204)

        dr.dispatch("owner/name", "daily.yml", "main", "tok", opener=opener)
        self.assertIn("owner/name/actions/workflows/daily.yml/dispatches",
                      seen["url"])
        self.assertEqual(seen["method"], "POST")
        self.assertIn(b'"ref": "main"', seen["body"])
        self.assertEqual(seen["auth"], "Bearer tok")

    def test_a_202_is_not_a_204(self):
        """A different success code is a contract change we should hear
        about, not guess at."""
        with self.assertRaises(dr.DispatchRefused):
            dr.dispatch("o/r", "daily.yml", "main", "t",
                        opener=_opener(_resp(202)))


class EveryRefusalFailsLoudly(unittest.TestCase):
    def _http_error(self, code):
        def opener(req, timeout=None):
            raise urllib.error.HTTPError(
                req.full_url, code, "nope", {}, io.BytesIO(b'{"message":"x"}'))
        return opener

    def test_the_four_statuses_the_finding_named(self):
        for code in (401, 403, 404, 422):
            with self.subTest(status=code):
                with self.assertRaises(dr.DispatchRefused) as ctx:
                    dr.dispatch("o/r", "daily.yml", "main", "t",
                                opener=self._http_error(code))
                self.assertEqual(ctx.exception.status, code)

    def test_a_server_error_is_a_refusal_too(self):
        with self.assertRaises(dr.DispatchRefused):
            dr.dispatch("o/r", "daily.yml", "main", "t",
                        opener=self._http_error(500))

    def test_a_timeout_is_not_a_success(self):
        def opener(req, timeout=None):
            raise TimeoutError("timed out")
        with self.assertRaises(dr.DispatchRefused) as ctx:
            dr.dispatch("o/r", "daily.yml", "main", "t", opener=opener)
        self.assertEqual(ctx.exception.status, "no-response")

    def test_a_reset_connection_is_not_a_success(self):
        def opener(req, timeout=None):
            raise OSError("connection reset by peer")
        with self.assertRaises(dr.DispatchRefused):
            dr.dispatch("o/r", "daily.yml", "main", "t", opener=opener)

    def test_a_malformed_response_object_is_not_a_success(self):
        junk = mock.MagicMock()
        junk.__enter__.return_value = junk
        del junk.status
        junk.getcode.side_effect = AttributeError("no status")
        with self.assertRaises(dr.DispatchRefused):
            dr.dispatch("o/r", "daily.yml", "main", "t", opener=_opener(junk))

    def test_a_missing_token_never_reaches_the_network(self):
        def opener(req, timeout=None):
            raise AssertionError("must not send an unauthenticated dispatch")
        with self.assertRaises(dr.DispatchRefused) as ctx:
            dr.dispatch("o/r", "daily.yml", "main", "", opener=opener)
        self.assertEqual(ctx.exception.status, "no-token")


class TheProcessExitCodeIsTheContract(unittest.TestCase):
    """What the workflow actually reads."""

    def _run(self, opener, token="t"):
        buf = io.StringIO()
        # Both names, explicitly: main() falls back to GITHUB_TOKEN, which
        # a real environment often has set.
        env = {"GH_TOKEN": token, "GITHUB_TOKEN": token}
        with mock.patch.dict("os.environ", env, clear=False), \
             mock.patch.object(dr.urllib.request, "urlopen", opener), \
             mock.patch("sys.stdout", buf):
            rc = dr.main(["--repo", "o/r", "--workflow", "daily.yml",
                          "--ref", "main", "--date", "20260909"])
        return rc, buf.getvalue()

    def test_an_accepted_dispatch_exits_zero_and_says_so(self):
        rc, out = self._run(_opener(_resp(204)))
        self.assertEqual(rc, 0)
        self.assertIn("::notice::", out)
        self.assertIn("20260909", out)

    def test_a_rejected_dispatch_exits_one(self):
        """The whole point. Previously provable only by grepping for the
        characters 'exit 1'."""
        def opener(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 403, "no", {},
                                         io.BytesIO(b"forbidden"))
        rc, out = self._run(opener)
        self.assertEqual(rc, 1)
        self.assertIn("::error::", out)
        self.assertIn("403", out)

    def test_the_failure_says_how_to_recover_by_hand(self):
        def opener(req, timeout=None):
            raise TimeoutError("slow")
        rc, out = self._run(opener)
        self.assertEqual(rc, 1)
        self.assertIn("gh workflow run daily.yml", out)

    def test_a_missing_token_exits_one(self):
        rc, out = self._run(_opener(_resp(204)), token="")
        self.assertEqual(rc, 1)


class TheWorkflowStillCallsIt(unittest.TestCase):
    """One thin wiring assertion, per the finding's own proposal."""

    def setUp(self):
        import yaml
        wf = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "exchange_phase_b.yml").read_text())
        job = wf["jobs"][next(iter(wf["jobs"]))]
        self.step = next(s for s in job["steps"]
                         if s.get("name") == "Hand off to render")

    def test_it_runs_the_tested_script(self):
        self.assertIn("scripts/dispatch_render.py", self.step["run"])

    def test_it_carries_a_token(self):
        self.assertIn("GH_TOKEN", str(self.step.get("env", {})))

    def test_only_after_a_real_non_dry_run_apply(self):
        guard = " ".join(str(self.step.get("if", "")).split())
        self.assertIn("steps.guard.outputs.skip != 'true'", guard)
        self.assertIn("dry_run != true", guard)


if __name__ == "__main__":
    unittest.main()
