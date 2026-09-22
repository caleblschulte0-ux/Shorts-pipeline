"""Doctor finding ad9061de9638, ruled `doing` 2026-09-09.

`shared/exchange_bundle.mark_ready()` converts every write failure (disk
full, permissions, a bad path) into `None` — correct, it fails soft on
purpose. The bug was on the caller's side: `scripts/exchange_phase_a.py`
only checked that `None`-ness to decide whether to PRINT a line, then
returned 0 unconditionally either way. A completion signal that failed to
write was reported as a successful Phase A run, and nothing downstream that
trusts READY (the 06:00 media worker's "has Phase A finished" check) could
tell the difference from a day that never had a Phase A at all.

Fault-injection, run in-process (like TestPhaseBPersistFailuresAreLoud in
test_authoring_takeover.py) so `mark_ready` can be made to fail on command
while bundle.json still writes for real.

    python -m unittest tests.test_phase_a_ready_signal -v
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

from tests.test_package_schema import reddit_pkg           # noqa: E402

import exchange_phase_a as pa                               # noqa: E402


class TestAFailedReadySignalFailsTheRun(unittest.TestCase):
    DATE = "29981231"

    def setUp(self):
        self.day = ROOT / "state" / "trending_packages" / self.DATE
        self.bundle_dir = ROOT / "exchange" / "bundles" / self.DATE
        self._clean()
        self.day.mkdir(parents=True)
        pkg = reddit_pkg(slug="ready-signal")
        (self.day / "01_ready-signal.json").write_text(json.dumps(pkg))
        self._argv = sys.argv[:]

    def tearDown(self):
        sys.argv = self._argv
        self._clean()

    def _clean(self):
        shutil.rmtree(self.day, ignore_errors=True)
        shutil.rmtree(self.bundle_dir, ignore_errors=True)

    def _run(self, ready_ok: bool):
        sys.argv = ["exchange_phase_a.py", "--date", self.DATE,
                    "--channel", "trending", "--target", "1",
                    "--no-resolve", "--json"]
        real_mark_ready = pa.xb.mark_ready
        patched = real_mark_ready if ready_ok else (lambda date: None)
        with mock.patch.object(pa.xb, "mark_ready", side_effect=patched), \
                contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = pa.main()
        return rc, buf.getvalue()

    def test_a_failed_ready_write_is_nonzero(self):
        rc, out = self._run(ready_ok=False)
        self.assertEqual(rc, 1, out)
        self.assertIn("ERROR", out)
        self.assertIn("READY", out)

    def test_a_failed_ready_write_still_keeps_the_valid_bundle(self):
        self._run(ready_ok=False)
        self.assertTrue((self.bundle_dir / "bundle.json").exists(),
                         "a valid bundle must not be thrown away just "
                         "because the completion signal failed")
        self.assertFalse((self.bundle_dir / "READY").exists())

    def test_a_successful_ready_write_is_still_exit_zero(self):
        rc, out = self._run(ready_ok=True)
        self.assertEqual(rc, 0, out)
        self.assertTrue((self.bundle_dir / "READY").exists())
        self.assertIn("commit these; ChatGPT answers next", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
