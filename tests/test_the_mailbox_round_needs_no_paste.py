"""THE MAILBOX ROUND LIVES IN THE REPO, AND EVERY CHATGPT FIRING RUNS IT.

Operator, 2026-09-22: *"I should not have to paste anything in a ChatGPT.
ChatGPT should be reading the instructions somewhere on the GitHub that you
can update at will."*

`doctor/PROMPTS.md` is that place — every scheduled task's app prompt is a
one-line pointer to a numbered section read fresh from `main`. Held here:

  1. section 7 exists and names all three mailboxes, the roll-up index,
     and the rules a rewrite is measured against;
  2. the media worker (4), the finalizer (5) and the router (6) each end by
     executing section 7 — so no firing can skip it;
  3. every mailbox refreshes the roll-up `exchange/OPEN.json` whenever its
     own index changes, so the round opens ONE url;
  4. the contract doc points at section 7 instead of carrying a second copy
     of the round.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import exchange_index as XI                      # noqa: E402
from shared import llm_mailbox as LM                         # noqa: E402
from shared import rewrite_mailbox as RW                     # noqa: E402

PROMPTS = (ROOT / "doctor" / "PROMPTS.md").read_text()


def _section(n: int) -> str:
    i = PROMPTS.index(f"\n## {n}. ")
    j = PROMPTS.find(f"\n## {n + 1}. ")
    return PROMPTS[i:j if j > 0 else None]


class TheRoundIsWrittenDown(unittest.TestCase):
    def test_section_7_exists_and_names_everything(self):
        s7 = _section(7)
        for must in ("exchange/OPEN.json", "exchange/reviews/OPEN.json",
                     "exchange/asks/OPEN.json", "exchange/rewrites/OPEN.json",
                     "NEVER output ship or block", "data.points",
                     "never edit a request file", "FINISH by stating"):
            self.assertIn(must, s7, must)

    def test_the_rules_it_states_are_the_gates_rules(self):
        """The prompt restates the gate's word rules; the code decides. Keep
        the two saying the same thing."""
        s7 = _section(7)
        self.assertIn(str(RW.MAX_TOPIC_WORDS), s7)
        self.assertIn(str(RW.MAX_SAY_WORDS), s7)

    def test_the_contract_doc_points_here_instead_of_a_second_copy(self):
        doc = (ROOT / "docs" / "REVIEW_MAILBOX.md").read_text()
        self.assertIn("section 7 of `doctor/PROMPTS.md`", doc)
        self.assertNotIn("paste into the scheduled task", doc)


class EveryFiringRunsIt(unittest.TestCase):
    def test_the_media_worker_ends_with_the_round(self):
        s4 = _section(4)
        self.assertIn("MAILBOX ROUND: execute section 7", s4)
        self.assertLess(s4.index("MAILBOX ROUND"), s4.index("FINISH by stating"))

    def test_the_finalizer_runs_it_after_DONE(self):
        s5 = _section(5)
        self.assertIn("MAILBOX ROUND: after DONE, execute section 7", s5)
        self.assertLess(s5.index("commit DONE as a SEPARATE commit"), s5.index("MAILBOX ROUND"))

    def test_the_router_runs_it_at_every_firing_including_the_doctor(self):
        s6 = _section(6)
        self.assertIn("AT EVERY FIRING (Doctor firing included)", s6)
        self.assertIn("execute section 7 completely", s6)

    def test_no_app_prompt_changed(self):
        """The paste table is the ONE thing that must never need re-pasting."""
        i = PROMPTS.index("## PASTE THESE")
        j = PROMPTS.index("## 1. ")
        table = PROMPTS[i:j]
        self.assertIn("section 6", table)
        self.assertNotIn("section 7", table, "a new paste was introduced")


class OneIndexRollsUpEveryMailbox(unittest.TestCase):
    def test_the_roll_up_counts_each_mailbox(self):
        with tempfile.TemporaryDirectory() as td:
            ex = Path(td)
            (ex / "reviews").mkdir(); (ex / "asks").mkdir(); (ex / "rewrites").mkdir()
            (ex / "reviews" / "OPEN.json").write_text(json.dumps({"open": [1, 2]}))
            (ex / "rewrites" / "OPEN.json").write_text(json.dumps({"open": [1]}))
            p = XI.refresh(ex)
            got = json.loads(p.read_text())
        self.assertEqual(got["open_total"], 3)
        self.assertEqual(got["mailboxes"]["reviews"]["open"], 2)
        self.assertEqual(got["mailboxes"]["asks"]["open"], 0)
        self.assertEqual(got["mailboxes"]["rewrites"]["index"], "exchange/rewrites/OPEN.json")
        self.assertIn("section 7", got["how"])

    def test_a_mailbox_refreshes_the_roll_up_when_its_index_changes(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(LM, "ASKS_DIR", Path(td) / "asks"), \
                mock.patch.dict("os.environ", {"LLM_MAILBOX": "1"}):
            with self.assertRaises(LM.AnswerPending):
                LM.call("SYS", "q-for-the-roll-up")
            master = json.loads((Path(td) / "OPEN.json").read_text())
        self.assertEqual(master["mailboxes"]["asks"]["open"], 1)
        self.assertEqual(master["open_total"], 1)


if __name__ == "__main__":
    unittest.main()
