"""Only the newest render of a story stays open in the review mailbox.

2026-09-28 filed fourteen requests for `iss-sixteen-sunrises` in one day
and the mailbox reached 61 open: a grader working oldest-first spends its
round on renders the pipeline already replaced. A request that already has
a verdict is never superseded — the claim step decides it.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.test_the_judge_of_last_resort_is_chatgpt import RM, _Sandbox  # noqa: E402


class OnlyTheNewestCutStaysOpen(_Sandbox):
    def _file_distinct(self, slug, n):
        self.mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + bytes([n]) * 4000)
        rid = self._file(slug=slug)
        rp = next(self.reviews.glob(f"*/{rid}.request.json"))
        req = json.loads(rp.read_text())
        req["filed"] = f"2026-09-28T0{n}:00:00Z"
        rp.write_text(json.dumps(req))
        return rid

    def test_older_unanswered_cuts_are_superseded(self):
        a = self._file_distinct("iss", 1)
        b = self._file_distinct("iss", 2)
        c = self._file_distinct("iss", 3)
        other = self._file_distinct("kelp", 4)
        gone = RM.supersede_stale(self.reviews)
        self.assertEqual(sorted(gone), sorted([a, b]))
        self.assertEqual(sorted(r["id"] for r in RM.open_requests(self.reviews)),
                         sorted([c, other]))
        done = json.loads(next(self.reviews.glob(f"*/{a}.done.json")).read_text())
        self.assertEqual(done["decision"], "superseded")
        self.assertIn(c, done["reason"])

    def test_an_answered_older_cut_is_left_for_the_claim(self):
        a = self._file_distinct("iss", 1)
        self._file_distinct("iss", 2)
        req = next(r for r in RM.open_requests(self.reviews) if r["id"] == a)
        (Path(req["_path"]).parent / f"{a}.verdict.json").write_text("{}")
        self.assertEqual(RM.supersede_stale(self.reviews), [])


class TheIndexesAreWhatAGraderShouldDoFirst(_Sandbox):
    """2026-09-30: the rewrite index listed 681 requests for 98 stories, and
    the roll-up ChatGPT opens first (exchange/OPEN.json) was never committed
    by any workflow, so it said 'reviews: 0 open' from 09-22 on while 61
    reviews waited."""

    def test_the_rewrite_index_lists_each_story_once_newest_first(self):
        import tempfile
        from shared import rewrite_mailbox as RW
        d = Path(tempfile.mkdtemp())
        for day, slug, rid in (("20260928", "a", "a__1"), ("20260929", "a", "a__2"),
                               ("20260927", "b", "b__1")):
            (d / day).mkdir(parents=True, exist_ok=True)
            (d / day / f"{rid}.request.json").write_text(json.dumps(
                {"schema": RW.SCHEMA, "id": rid, "slug": slug, "filed": f"{day}T00:00:00Z"}))
        RW.write_index(d)
        idx = json.loads((d / "OPEN.json").read_text())
        self.assertEqual([o["id"] for o in idx["open"]], ["a__2", "b__1"])

    def test_every_workflow_that_persists_a_mailbox_persists_the_roll_up(self):
        root = Path(__file__).resolve().parents[1]
        for wf in (root / ".github" / "workflows").glob("*.yml"):
            src = wf.read_text()
            if "exchange/reviews exchange" in src:
                self.assertIn("exchange/OPEN.json", src, wf.name)
