"""Doctor ab49431193c5 (first slice): the response envelope is checked and
reported — against the real captured 2026-08-14 response, and on junk."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared import exchange_bundle as xb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class Envelope(unittest.TestCase):
    def good(self):
        return {"schema": xb.RESPONSE_SCHEMA, "date": "20260814",
                "status": "fulfilled", "contract": {}, "media": []}

    def test_valid_is_clean(self):
        self.assertEqual(xb.response_envelope_problems(self.good(), "20260814"), [])

    def test_captured_historical_response_is_clean(self):
        p = ROOT / "exchange/bundles/20260814/response.json"
        if p.exists():
            self.assertEqual(xb.response_envelope_problems(
                json.loads(p.read_text()), "20260814"), [])

    def test_each_defect_is_named(self):
        r = {"media": [], "weird": 1, "packages": "x"}
        text = " | ".join(xb.response_envelope_problems(r, "20260814"))
        for needle in ("schema", "date", "status", "contract", "weird", "packages"):
            self.assertIn(needle, text)

    def test_wrong_date_and_junk_never_raise(self):
        g = self.good()
        g["date"] = "20260101"
        self.assertTrue(xb.response_envelope_problems(g, "20260814"))
        for junk in (None, [], "x", 3):
            self.assertTrue(xb.response_envelope_problems(junk, "20260814"))


if __name__ == "__main__":
    unittest.main()
