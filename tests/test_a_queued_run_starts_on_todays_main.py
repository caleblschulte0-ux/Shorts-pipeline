"""A queued posting run starts on main as it is when the run STARTS.

2026-10-13: the explainer run queued at 23:36 started at 04:11 on the
commit main was at when it was queued. The run before it had drawn and
persisted scenes for twelve stories at 04:11:36; the queued run never saw
them, and began redrawing the same twelve from scratch, without any of the
fixes merged in between. daily.yml learned the same lesson on 2026-09-29.
Every checkout in a queued posting workflow names a ref, so it fetches the
branch tip instead of the event's SHA.
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUEUED = ("explainer.yml", "daily.yml")


def checkouts(text: str) -> list[str]:
    """Each checkout step's `with:` block."""
    out = []
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if "actions/checkout@" not in l:
            continue
        ind = len(l) - len(l.lstrip())
        block = []
        for m in lines[i + 1:]:
            if m.strip() and len(m) - len(m.lstrip()) <= ind - 2:
                break
            if m.strip().startswith("- ") and len(m) - len(m.lstrip()) <= ind:
                break
            block.append(m)
        out.append("\n".join(block))
    return out


class EveryCheckoutFetchesTheTip(unittest.TestCase):
    def test_each_queued_workflow_names_a_ref(self):
        for wf in QUEUED:
            text = (REPO / ".github" / "workflows" / wf).read_text()
            blocks = checkouts(text)
            self.assertTrue(blocks, wf)
            for b in blocks:
                self.assertRegex(b, r"\bref:\s*\$\{\{\s*github\.ref\s*\}\}",
                                 f"{wf}: a checkout with no ref starts on the "
                                 f"commit main was at when the run was queued")


if __name__ == "__main__":
    unittest.main()
