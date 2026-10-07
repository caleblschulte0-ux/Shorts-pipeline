"""A long-form is never built on invented numbers.

On 2026-10-07, 22 of the 23 published stories that cleared long-form
readiness ran on datasets whose source was `"publisher": "Illustrative"`;
the week's pick, poisonous-plants, rendered "1,000%" over a plant chart.

    python -m unittest tests.test_longform_sourced -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import build_longform as BL  # noqa: E402


def _story(files):
    say = " ".join(["word"] * 40)
    return {"slug": "s", "hook": say, "closing": say,
            "segments": [{"say": say, "topic": f, "params": {"file": f}}
                         for f in files]}


class TestOnlyOfficialDataGoesLong(unittest.TestCase):

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="lf-src-"))
        for name, off in (("ok.json", "official"),
                          ("made_up.json", "illustrative")):
            (self.d / name).write_text(
                json.dumps({"source": {"officiality": off}}))
        self.p = mock.patch.object(BL, "DATA_DIR", self.d)
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_official_story_is_ready(self):
        self.assertTrue(BL.readiness(_story(["ok.json"] * 4))[0])

    def test_one_invented_beat_holds_it(self):
        ok, why = BL.readiness(_story(["ok.json"] * 3 + ["made_up.json"]))
        self.assertFalse(ok)
        self.assertIn("unofficial", why)

    def test_a_missing_dataset_is_not_official(self):
        self.assertFalse(BL.readiness(_story(["ok.json"] * 3 + ["gone.json"]))[0])

    def test_the_real_queue_never_offers_an_illustrative_story(self):
        cfg = json.loads(BL.CONFIG.read_text())
        self.p.stop()
        try:
            for st in cfg.get("stories", []):
                if BL.readiness(st)[0]:
                    self.assertEqual(BL.unsourced_beats(st), [], st["slug"])
        finally:
            self.p.start()


if __name__ == "__main__":
    unittest.main()
