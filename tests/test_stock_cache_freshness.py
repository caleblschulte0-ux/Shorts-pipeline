import tempfile
import unittest
from pathlib import Path
from unittest import mock

from data_learning import stock, stock_cache as sc


class Freshness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = mock.patch.object(sc, "ROOT", Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_fresh_record_is_used_expired_is_not(self):
        sc.save("pexels", "q", [{"url": "u1"}], now=1000)
        self.assertEqual(sc.load("pexels", "q", now=1000 + 10), [{"url": "u1"}])
        self.assertIsNone(sc.load("pexels", "q", now=1000 + sc.MAX_AGE_S + 1))

    def test_legacy_record_without_fetch_time_is_not_trusted(self):
        sc._slot("pexels", "old").parent.mkdir(exist_ok=True)
        sc._slot("pexels", "old").write_text(
            '{"provider":"pexels","query":"old","candidates":[{"url":"x"}]}')
        self.assertIsNone(sc.load("pexels", "old"))

    def test_dead_candidate_evicted_after_repeated_failures(self):
        sc.save("pexels", "q", [{"url": "dead"}, {"url": "ok"}])
        sc.report_dead("dead")
        self.assertEqual(len(sc.load("pexels", "q")), 2)
        sc.report_dead("dead")
        self.assertEqual(sc.load("pexels", "q"), [{"url": "ok"}])

    def test_live_answer_outranks_and_resets(self):
        sc.save("pexels", "q", [{"url": "dead"}])
        sc.report_dead("dead"); sc.report_dead("dead")
        self.assertEqual(sc.wrap("pexels", "q", lambda: [{"url": "dead"}]),
                         [{"url": "dead"}])
        self.assertEqual(sc.load("pexels", "q"), [{"url": "dead"}])

    def test_failed_download_is_reported(self):
        sc.save("pexels", "q", [{"url": "http://invalid.invalid/x"}])
        with mock.patch("urllib.request.urlopen", side_effect=OSError("dead")):
            for _ in range(2):
                with self.assertRaises(OSError):
                    stock.download("http://invalid.invalid/x",
                                   Path(self.tmp.name) / "o.mp4")
        self.assertIsNone(sc.load("pexels", "q"))


if __name__ == "__main__":
    unittest.main()
