"""A superseded task contract must say so (doctor finding 825a41037aae).

docs/CHATGPT_MEDIA_HANDOFF.md once called itself "the only file a ChatGPT task
needs to read" and carried a paste-ready prompt for a branch nothing renders.
"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "CHATGPT_MEDIA_HANDOFF.md"


class SupersededContract(unittest.TestCase):
    def setUp(self):
        self.text = DOC.read_text()

    def test_banner_is_first_and_names_the_live_contract(self):
        head = "\n".join(self.text.splitlines()[:12])
        self.assertIn("SUPERSEDED", head)
        self.assertIn("doctor/PROMPTS.md", head)
        self.assertIn("docs/EXCHANGE_PIPELINE.md", head)

    def test_no_longer_claims_to_be_the_contract(self):
        self.assertNotIn("only file a ChatGPT task needs", self.text)

    def test_named_live_contract_files_exist(self):
        self.assertTrue((ROOT / "doctor" / "PROMPTS.md").exists())
        self.assertTrue((ROOT / "docs" / "EXCHANGE_PIPELINE.md").exists())


if __name__ == "__main__":
    unittest.main()
