"""Doctor 500b791bc671: executable pushes to main must run the full suite."""
import pathlib
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows" / "main_verify.yml"


class MainPushesRunTheSuite(unittest.TestCase):
    def setUp(self):
        self.doc = yaml.safe_load(WF.read_text())
        # YAML 1.1 parses the key `on` as True
        self.on = self.doc.get("on", self.doc.get(True))

    def test_fires_on_main_pushes_to_code_tests_and_workflows(self):
        push = self.on["push"]
        self.assertEqual(push["branches"], ["main"])
        paths = " ".join(push["paths"])
        for needle in ("**.py", "tests/", ".github/workflows/"):
            self.assertIn(needle, paths)

    def test_runs_the_same_suite_as_the_pr_gate(self):
        text = WF.read_text()
        gate = (ROOT / ".github/workflows/auto-merge.yml").read_text()
        for cmd in ("python -m unittest discover -s tests -v",
                    "scripts/exchange_dry_run.py",
                    "scripts/registry_acceptance.py",
                    "set -o pipefail"):
            self.assertIn(cmd, text)
            self.assertIn(cmd, gate)

    def test_cannot_recurse_or_write_state(self):
        self.assertEqual(self.doc["permissions"], {"contents": "read"})
        text = WF.read_text()
        self.assertNotIn("git push", text)
        self.assertNotIn("git commit", text)


if __name__ == "__main__":
    unittest.main()
