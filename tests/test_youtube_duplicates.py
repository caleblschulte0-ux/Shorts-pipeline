"""The duplicate cleanup keeps the copy the audience found and touches
nothing without an explicit, doubled confirmation (2026-10-02)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import youtube_duplicates as yd  # noqa: E402


class ThePlan(unittest.TestCase):
    VIDS = [
        {"id": "a", "title": "China Pulled Away In Electric Car Sales",
         "published_at": "2026-09-27T11:57:00Z", "views": 40},
        {"id": "b", "title": "China Pulled Away In Electric Car Sales",
         "published_at": "2026-09-27T13:00:00Z", "views": 3},
        {"id": "c", "title": "Only Once", "published_at": "2026-09-28T00:00:00Z",
         "views": 9},
        {"id": "d", "title": "  china pulled away in electric car sales ",
         "published_at": "2026-09-30T00:00:00Z", "views": 1},
    ]

    def test_it_keeps_the_most_watched_and_lists_the_rest(self):
        groups = yd.plan(self.VIDS)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["keep"]["id"], "a")
        self.assertEqual([e["id"] for e in groups[0]["extras"]], ["b", "d"])

    def test_a_tie_on_views_keeps_the_earliest(self):
        vids = [dict(v, views=0) for v in self.VIDS]
        groups = yd.plan(vids)
        self.assertEqual(groups[0]["keep"]["id"], "a")

    def test_a_title_live_once_is_not_touched(self):
        self.assertEqual(yd.plan(self.VIDS[2:3]), [])


class NothingIsDeletedWithoutSayingSoTwice(unittest.TestCase):
    def _svc(self):
        svc = mock.MagicMock()
        return svc

    def test_a_dry_run_deletes_nothing(self):
        svc = self._svc()
        with mock.patch.object(yd, "_service", return_value=svc), \
                mock.patch.object(yd, "list_uploads", return_value=ThePlan.VIDS):
            for argv in ([], ["--delete"], ["--yes"]):
                rc = yd.main(argv)
                self.assertEqual(rc, 0)
                svc.videos.return_value.delete.assert_not_called()

    def test_delete_plus_yes_removes_only_the_extras(self):
        svc = self._svc()
        with mock.patch.object(yd, "_service", return_value=svc), \
                mock.patch.object(yd, "list_uploads", return_value=ThePlan.VIDS):
            rc = yd.main(["--delete", "--yes"])
        self.assertEqual(rc, 0)
        gone = [c.kwargs["id"] for c in svc.videos.return_value.delete.call_args_list]
        self.assertEqual(sorted(gone), ["b", "d"])

    def test_a_scope_refusal_is_reported_not_retried(self):
        svc = self._svc()
        svc.videos.return_value.delete.return_value.execute.side_effect = \
            RuntimeError("HttpError 403 insufficientPermissions")
        with mock.patch.object(yd, "_service", return_value=svc), \
                mock.patch.object(yd, "list_uploads", return_value=ThePlan.VIDS):
            rc = yd.main(["--delete", "--yes"])
        self.assertEqual(rc, 1)
        self.assertEqual(svc.videos.return_value.delete.call_count, 2)


class TheWorkflowIsManualOnly(unittest.TestCase):
    def test_no_schedule_and_delete_needs_the_word(self):
        wf = (ROOT / ".github/workflows/youtube_duplicates.yml").read_text()
        self.assertNotIn("schedule:", wf)
        self.assertIn("workflow_dispatch", wf)
        self.assertIn('= "DELETE"', wf)
        self.assertIn("--delete --yes", wf)


if __name__ == "__main__":
    unittest.main()
