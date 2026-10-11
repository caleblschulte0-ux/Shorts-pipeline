"""Every third-party action in a workflow is pinned to a full commit SHA
(doctor finding b507d603aefb): a mutable tag can change what runs with
contents:write without any commit here changing."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)", re.M)
PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")


class ActionsArePinned(unittest.TestCase):
    def test_every_remote_action_is_a_full_sha(self):
        bad = []
        for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            for ref in USES.findall(wf.read_text()):
                if ref.startswith("./"):
                    continue
                if not PINNED.match(ref):
                    bad.append(f"{wf.name}: {ref}")
        self.assertEqual(bad, [], "pin to a commit SHA, keep the tag in a comment")

    def test_dependabot_keeps_the_pins_current(self):
        cfg = (ROOT / ".github" / "dependabot.yml").read_text()
        self.assertIn("github-actions", cfg)


if __name__ == "__main__":
    unittest.main()
