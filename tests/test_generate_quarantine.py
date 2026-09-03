"""A package that fails QA never lands in the consumable output directory.

Doctor finding 5171aa14cc8d: `data_learning/generate.py` wrote every
package to `out_dir` BEFORE reading the QA result, so a failing package
sat beside the passing ones where any downstream glob would render it.
Now the consumable directory only ever holds packages QA passed; a
failure is quarantined one directory down with its errors attached.

    python -m unittest tests.test_generate_quarantine -v
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "data_learning" / "generate.py").read_text()
# the batch loop: from the QA call to the end of the per-video handling
LOOP = SRC.split("errors = qa.validate(", 1)[1]


class TestFailedQAIsQuarantinedNotPublished(unittest.TestCase):

    def test_the_publish_write_lives_in_the_passing_branch(self):
        """`out_path.write_text` must appear AFTER the `else:` that the QA
        check guards — never between validate() and the errors check."""
        before_branch = LOOP.split("if errors:", 1)[0]
        self.assertNotIn("out_path.write_text", before_branch,
                         "the package is written before QA is consulted "
                         "— the finding is back")
        else_branch = LOOP.split("else:", 1)[1]
        self.assertIn("out_path.write_text", else_branch)

    def test_the_failure_branch_quarantines_with_the_errors(self):
        fail_branch = LOOP.split("if errors:", 1)[1].split("else:", 1)[0]
        self.assertIn("quarantine", fail_branch)
        self.assertIn("qa_errors", fail_branch)
        self.assertNotIn("out_path.write_text", fail_branch)

    def test_the_quarantine_is_out_of_the_consumable_glob(self):
        """The quarantine file must live in a SUBdirectory, so a consumer
        globbing out_dir/*.json cannot pick it up."""
        fail_branch = LOOP.split("if errors:", 1)[1].split("else:", 1)[0]
        self.assertTrue(re.search(r'out_dir / "quarantine"', fail_branch))


if __name__ == "__main__":
    unittest.main()
