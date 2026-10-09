"""The roster scout ranks who we are missing, never who we have."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

import twitch_roster_scout as rs  # noqa: E402


class WhoWeAreMissing(unittest.TestCase):
    def test_ranked_english_and_not_on_the_list(self):
        clips = [
            {"broadcaster_id": "1", "broadcaster_name": "New", "view_count": 50,
             "language": "en", "title": "a", "game": "GTA V"},
            {"broadcaster_id": "1", "broadcaster_name": "New", "view_count": 70,
             "language": "en", "title": "b", "game": "Just Chatting"},
            {"broadcaster_id": "2", "broadcaster_name": "KaiCenat",
             "view_count": 999, "language": "en", "title": "c"},
            {"broadcaster_id": "3", "broadcaster_name": "Bigger",
             "view_count": 500, "language": "en", "title": "d"},
            {"broadcaster_id": "4", "broadcaster_name": "Otro",
             "view_count": 900, "language": "es", "title": "e"}]
        rows = rs.tally(clips, {"kaicenat"})
        self.assertEqual([r["name"] for r in rows], ["Bigger", "New"])
        self.assertEqual((rows[1]["views"], rows[1]["clips"], rows[1]["best"]),
                         (120, 2, 70))


if __name__ == "__main__":
    unittest.main()
