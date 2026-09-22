"""OpenRangeInteractive documentaries: the script contract, the author, the
publisher's gate order, and a cut that is really as long as its beat.

    python -m unittest tests.test_ori_documentary -v
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

from data_learning import ori_documentary as OD      # noqa: E402
import ori_author as AU                               # noqa: E402
import post_ori as PO                                 # noqa: E402

OCEAN = OD.load("how-deep-is-the-ocean")


class TestTheScriptContract(unittest.TestCase):

    def test_every_shipped_episode_is_valid(self):
        for p in sorted(OD.EPISODES.glob("*.json")):
            with self.subTest(p.name):
                ep = json.loads(p.read_text())
                self.assertEqual(OD.validate(ep), [])
                self.assertEqual(ep["slug"], p.stem)

    def test_a_stat_on_screen_must_be_said(self):
        """A number on screen that the narrator never says is a number the
        viewer cannot place — and usually a number the author made up."""
        ep = copy.deepcopy(OCEAN)
        ep["chapters"][1]["beats"][0]["stat"] = {"value": "93%", "label": "x"}
        self.assertTrue(any("not said" in b for b in OD.validate(ep)))

    def test_too_short_to_be_long_form_is_refused(self):
        ep = copy.deepcopy(OCEAN)
        ep["chapters"] = ep["chapters"][:5]
        self.assertTrue(any("narrated words" in b for b in OD.validate(ep)))

    def test_a_shot_query_is_a_few_plain_words(self):
        ep = copy.deepcopy(OCEAN)
        ep["chapters"][1]["beats"][0]["shots"] = [
            "a sweeping cinematic establishing shot of the ocean at dawn"]
        self.assertTrue(any("shot query" in b for b in OD.validate(ep)))

    def test_sources_need_real_urls(self):
        ep = copy.deepcopy(OCEAN)
        ep["sources"][0]["url"] = "NOAA website"
        self.assertTrue(any("http url" in b for b in OD.validate(ep)))

    def test_shots_change_every_few_seconds(self):
        for total in (3.0, 7.5, 12.0, 23.0):
            parts = OD.split(total)
            self.assertAlmostEqual(sum(parts), total, places=6)
            self.assertTrue(all(OD.SHOT_MIN_S <= p <= 6.5 for p in parts)
                            or len(parts) == 1, (total, parts))

    def test_every_chapter_after_the_intro_opens_with_a_card(self):
        segs = OD.plan(OCEAN)
        cards = [s for s in segs if s.kind == "card"]
        self.assertEqual(len(cards), len(OCEAN["chapters"]) - 1)
        self.assertEqual(segs[0].kind, "beat", "the cold open is not a card")


class TestTheAuthor(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ori-"))
        self._saved = OD.EPISODES
        OD.EPISODES = self.tmp

    def tearDown(self):
        OD.EPISODES = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _valid(self, slug="how-lightning-works"):
        ep = copy.deepcopy(OCEAN)
        ep["slug"] = slug
        for k in ("topic", "added", "authored_by"):
            ep.pop(k, None)
        return json.dumps(ep)

    def test_a_valid_reply_is_kept_and_stamped(self):
        ep = AU.author("How lightning works", ask=lambda s, u: self._valid())
        self.assertEqual(ep["slug"], "how-lightning-works")
        self.assertEqual(ep["topic"], "How lightning works")
        self.assertEqual(ep["authored_by"], "ori_author")

    def test_an_invalid_reply_gets_one_retry_with_the_reasons(self):
        seen = []

        def ask(system, user):
            seen.append(user)
            return '{"slug": "x"}' if len(seen) == 1 else self._valid()
        ep = AU.author("t", ask=ask)
        self.assertIsNotNone(ep)
        self.assertIn("REJECTED FOR", seen[1])

    def test_a_reply_that_stays_invalid_is_dropped(self):
        self.assertIsNone(AU.author("t", ask=lambda s, u: '{"slug": "x"}'))

    def test_a_fenced_reply_still_parses(self):
        ep = AU.author("t", ask=lambda s, u: "```json\n" + self._valid() + "\n```")
        self.assertIsNotNone(ep)

    def test_it_never_overwrites_an_existing_episode(self):
        (self.tmp / "how-lightning-works.json").write_text("{}")
        self.assertIsNone(AU.author("t", ask=lambda s, u: self._valid()))

    def test_the_mailbox_is_never_the_author(self):
        src = (ROOT / "scripts" / "ori_author.py").read_text()
        self.assertNotIn('"mailbox": ', src)
        self.assertIn('order = {"claude_cli": 0', src)


class TestThePublisher(unittest.TestCase):
    SRC = (ROOT / "scripts" / "post_ori.py").read_text()

    def test_the_gate_runs_before_the_upload_and_knows_it_is_a_publish(self):
        self.assertLess(self.SRC.index("showrunner_gate.run("),
                        self.SRC.index("up.upload("))
        self.assertIn("will_upload=will_upload", self.SRC)
        self.assertIn("will_upload = not args.dry_run", self.SRC)

    def test_a_claim_is_written_before_the_upload_and_a_receipt_after(self):
        self.assertLess(self.SRC.index('"phase": "uploading"'),
                        self.SRC.index("up.upload("))
        self.assertLess(self.SRC.index("up.upload("),
                        self.SRC.index('"phase": "uploaded"'))

    def test_description_carries_chapters_sources_and_credits(self):
        d = PO.description(OCEAN, {"chapters": [
            {"t": 0, "label": "Intro"}, {"t": 65, "label": "A"},
            {"t": 130, "label": "B"}]})
        self.assertIn("0:00 Intro", d)
        self.assertIn("1:05 A", d)
        self.assertIn("oceanservice.noaa.gov", d)
        self.assertIn("Kevin MacLeod", d)
        self.assertIn("Pexels", d)

    def test_the_technical_floor(self):
        tmp = Path(tempfile.mkdtemp(prefix="ori-floor-"))
        try:
            out = tmp / "x.mp4"
            self.assertEqual(PO.technical_floor(out, {}, {}),
                             ["no rendered video on disk"])
            out.write_bytes(b"x")
            from PIL import Image
            Image.new("RGB", (1920, 1080)).save(out.with_suffix(".jpg"))
            meta = {"duration": 300, "footage": [{}] * 8,
                    "footage_misses": [["q"]] * 2}
            bad = PO.technical_floor(out, meta, {"min_seconds": 480,
                                                 "max_footage_miss_ratio": 0.12})
            self.assertTrue(any("long-form floor" in b for b in bad))
            self.assertTrue(any("found no footage" in b for b in bad))
            ok = {"duration": 560, "footage": [{}] * 50, "footage_misses": []}
            self.assertEqual(PO.technical_floor(out, ok, {"min_seconds": 480}), [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_an_unconfirmed_upload_stops_the_run(self):
        tmp = Path(tempfile.mkdtemp(prefix="ori-pend-"))
        saved = (PO.PENDING, PO.LOG)
        PO.PENDING, PO.LOG = tmp / "p.json", tmp / "l.json"
        try:
            log = {"posted": {}}
            self.assertEqual(PO.reconcile(log), 0)
            PO._write(PO.PENDING, {"slug": "a", "phase": "uploading"})
            self.assertNotEqual(PO.reconcile(log), 0)
            PO._write(PO.PENDING, {"slug": "a", "phase": "uploaded",
                                   "url": "https://y/1", "title": "A"})
            self.assertEqual(PO.reconcile(log), 0)
            self.assertIn("a", json.loads(PO.LOG.read_text())["posted"])
        finally:
            PO.PENDING, PO.LOG = saved
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_blocked_episode_never_reaches_the_uploader(self):
        tmp = Path(tempfile.mkdtemp(prefix="ori-main-"))
        saved = (PO.PENDING, PO.LOG, PO.OUT, PO.KILL, sys.argv)
        PO.PENDING, PO.LOG, PO.OUT = tmp / "p.json", tmp / "l.json", tmp
        PO.KILL = tmp / "kill"
        sys.argv = ["post_ori.py", "--slug", "how-deep-is-the-ocean"]

        def fake_render(ep, out, **_):
            from PIL import Image
            out.write_bytes(b"x")
            Image.new("RGB", (1920, 1080)).save(out.with_suffix(".jpg"))
            return {"duration": 560, "chapters": [], "footage": [{}] * 40,
                    "footage_misses": []}
        try:
            with mock.patch.object(OD, "render", side_effect=fake_render), \
                 mock.patch("shared.showrunner_gate.run",
                            return_value={"blocked": True, "reason": "dull"}), \
                 mock.patch("publish_security.scan_upload",
                            return_value=(True, [])), \
                 mock.patch("shared.uploaders.YouTubeUploader") as up:
                rc = PO.main()
            self.assertNotEqual(rc, 0)
            up.return_value.upload.assert_not_called()
        finally:
            PO.PENDING, PO.LOG, PO.OUT, PO.KILL, sys.argv = saved
            shutil.rmtree(tmp, ignore_errors=True)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class TestACutIsExactlyItsBeat(unittest.TestCase):

    def test_the_motion_probe_is_the_showrunners_detector(self):
        """The clip probe must call a pair of frames a duplicate exactly when
        the gate would, or it picks footage the gate then reads as frozen.
        EQUIVALENCE against the gate's own function, over generated frames."""
        import numpy as np
        from scripts import showrunner_review as SR
        rng = np.random.default_rng(7)
        tmp = Path(tempfile.mkdtemp(prefix="ori-motion-"))
        try:
            frames = []
            base = rng.integers(0, 255, (108, 192), dtype=np.uint8)
            for i in range(24):
                f = base.copy()
                if i % 3:                       # some pairs move, some hold
                    y, x = rng.integers(0, 90), rng.integers(0, 170)
                    f[y:y + 12, x:x + 20] = rng.integers(0, 255)
                    base = f
                frames.append(f)
            raw = b"".join(f.tobytes() for f in frames)
            src = tmp / "m.mkv"
            import subprocess
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f",
                            "rawvideo", "-pix_fmt", "gray", "-s", "192x108",
                            "-r", "24", "-i", "-", "-c:v", "ffv1", str(src)],
                           input=raw, check=True)
            dup, run = OD.motion_profile(src, 0.0, 1.0)
            ref = [SR._max_block_diff(a.ravel().tolist(), b.ravel().tolist(), 192)
                   < SR.BLOCK_MOTION_THRESH for a, b in zip(frames, frames[1:])]
            self.assertAlmostEqual(dup, sum(ref) / len(ref), places=2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_missing_source_still_fills_the_beat(self):
        tmp = Path(tempfile.mkdtemp(prefix="ori-cut-"))
        try:
            out = OD.cut(None, 2.5, tmp / "c.mp4",
                         OD.chapter_overlay(3, "The Midnight Zone",
                                            tmp / "o.png"))
            self.assertAlmostEqual(OD.probe_duration(out), 2.5, delta=0.1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
