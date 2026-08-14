"""The media worker's output must survive a finalizer that never closes.

2026-08-09/10, found live: the 6:00 media worker delivered 14-16 VERIFIED
images a day — uploaded, byte-checked, checkpointed — and the 7:00 finalizer
stopped writing `response.json`. Phase B read media pointers only from that
response, so every one of those images was discarded and the day self-filled
with unrelated stock. That stock is what the showrunner then blocked
trending's reddit stories for, two days running. Real work, verified, thrown
away for want of an envelope.

A checkpoint is written at the instant the bytes verify and carries the same
file_id / sha256 / dimensions a pointer does. It IS the evidence. These tests
hold that recovery open, and — just as importantly — hold it HONEST: a
recovered pointer takes the identical contract validation and byte-level
fetch as any other, and never overrides what the response actually said.

    python -m unittest tests.test_checkpoint_recovery -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import media_checkpoint as mc                # noqa: E402


def checkpoint(rid="req-1", status="verified", **over):
    cp = {
        "schema": mc.SCHEMA, "schema_version": mc.SCHEMA_VERSION,
        "date": "20260810", "request_id": rid, "status": status,
        "request_kind": "bundle_request",
        "drive": {"file_id": "1abcFILEID", "folder_id": "1folder",
                  "filename": f"20260810__{rid}.png",
                  "download_url": "https://drive.google.com/uc?id=1abcFILEID",
                  "sharing": "anyone_with_link"},
        "image": {"sha256": "a" * 64, "bytes": 1002732, "format": "png",
                  "width": 1080, "height": 1080},
    }
    cp.update(over)
    return cp


class TestACheckpointIsAUsablePointer(unittest.TestCase):
    def test_a_verified_checkpoint_becomes_a_pointer(self):
        p = mc.pointer_from_checkpoint(checkpoint())
        self.assertIsNotNone(p)
        self.assertEqual(p["request_id"], "req-1")
        self.assertEqual(p["drive"]["file_id"], "1abcFILEID")
        self.assertEqual(p["image"]["sha256"], "a" * 64)

    def test_it_is_labelled_as_recovered(self):
        """Phase B's report and any later audit must be able to tell a
        recovered pointer from one ChatGPT actually declared."""
        self.assertTrue(
            mc.pointer_from_checkpoint(checkpoint())["recovered_from_checkpoint"])

    def test_an_unverified_checkpoint_is_NOT_a_pointer(self):
        for bad in ("pending", "failed", "", None):
            self.assertIsNone(
                mc.pointer_from_checkpoint(checkpoint(status=bad)), bad)

    def test_a_checkpoint_missing_its_evidence_is_refused(self):
        self.assertIsNone(mc.pointer_from_checkpoint(
            checkpoint(drive={"folder_id": "x"})))          # no file_id
        self.assertIsNone(mc.pointer_from_checkpoint(
            checkpoint(image={"bytes": 10})))               # no sha256

    def test_junk_never_raises(self):
        for junk in (None, "", [], {}, {"request_id": "x"}):
            self.assertIsNone(mc.pointer_from_checkpoint(junk))


class TestRecoveryFillsGapsAndNeverOverrides(unittest.TestCase):
    """The response always wins where it spoke. Recovery is for silence."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="cprec-"))
        self._saved = mc.ROOT if hasattr(mc, "ROOT") else None
        self._saved_dir = mc.progress_dir
        d = self.tmp / "media-progress"
        d.mkdir(parents=True)
        mc.progress_dir = lambda date: d                  # noqa: ARG005
        self.dir = d

    def tearDown(self):
        import shutil
        mc.progress_dir = self._saved_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, cp):
        import json
        (self.dir / f"{cp['request_id']}.json").write_text(json.dumps(cp))

    def test_recovers_only_what_the_response_left_out(self):
        self.write(checkpoint("answered"))
        self.write(checkpoint("silent"))
        got = mc.recovered_media("20260810", have={"answered"})
        self.assertEqual(set(got), {"silent"},
                         "a request the response answered must not be "
                         "overridden by a checkpoint")

    def test_recovers_everything_when_the_response_is_absent(self):
        """The 08-09/08-10 shape: no response at all, 2 verified images."""
        self.write(checkpoint("a"))
        self.write(checkpoint("b"))
        self.assertEqual(set(mc.recovered_media("20260810", have=set())),
                         {"a", "b"})

    def test_unverified_checkpoints_are_skipped(self):
        self.write(checkpoint("good"))
        self.write(checkpoint("half", status="pending"))
        self.assertEqual(set(mc.recovered_media("20260810")), {"good"})

    def test_a_started_marker_is_not_media(self):
        """The heartbeat file has no request_id and must never look like an
        image."""
        import json
        (self.dir / "STARTED.json").write_text(json.dumps(
            {"schema": "chatgpt-media-start/v1", "task": "media_worker"}))
        self.assertEqual(mc.recovered_media("20260810"), {})

    def test_no_checkpoints_is_an_empty_dict_not_a_crash(self):
        self.assertEqual(mc.recovered_media("20260810"), {})


class TestRecoveryIsNotASideDoor(unittest.TestCase):
    """A checkpoint that would be REFUSED as a response pointer must be
    refused identically when it is recovered instead. Found live 2026-08-14:
    `pointer_from_checkpoint` only required status + file_id + sha256, and
    Phase B validated the raw response object rather than the checkpoint-
    augmented index, so a verified-looking-but-stale checkpoint (wrong
    schema, wrong day, wrong bundle, no folder/sharing/filename/dimensions)
    was recovered, merged in, and pinned without ever going through
    `checkpoint_problems` — the exact trust contract a response pointer's
    own checkpoint is held to inside `validate_response_media`."""

    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp(prefix="cprec-badcp-"))
        self._saved_dir = mc.progress_dir
        d = self.tmp / "media-progress"
        d.mkdir(parents=True)
        mc.progress_dir = lambda date: d                  # noqa: ARG005
        self.dir = d

    def tearDown(self):
        import shutil
        mc.progress_dir = self._saved_dir
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, cp):
        import json
        (self.dir / f"{cp['request_id']}.json").write_text(json.dumps(cp))

    def test_a_verified_but_contractually_broken_checkpoint_is_refused(self):
        bad = checkpoint(
            "req-1", schema="wrong-schema", date="20200101",
            bundle={"identity": "not-the-current-bundle"},
            drive={"file_id": "1abcFILEID"},               # no folder/sharing/filename
            image={"sha256": "a" * 64},                    # no dims/format
        )
        self.write(bad)

        got = mc.recovered_media(
            "20260810", have=set(),
            bundle={"requests": [{"request_id": "req-1",
                                  "prompt_verbatim": "a red bicycle"}]},
            bundle_id="the-real-current-bundle-identity")

        self.assertEqual(got, {},
                         "a checkpoint that fails checkpoint_problems on "
                         "schema, date, bundle identity, folder_id, sharing, "
                         "filename and image dimensions must never be "
                         "returned as a usable recovered pointer")

    def test_refused_recovered_checkpoints_are_reported(self):
        bad = checkpoint("req-1", date="20200101")
        self.write(bad)
        refused: dict = {}
        got = mc.recovered_media("20260810", have=set(), refused_out=refused)
        self.assertEqual(got, {})
        self.assertIn("req-1", refused)
        self.assertTrue(refused["req-1"])

    def test_a_genuinely_current_checkpoint_still_recovers(self):
        """The fix must not turn recovery off — only stale/foreign checkpoints
        are refused; a checkpoint made for THIS bundle, THIS prompt, on THIS
        day still fills the gap."""
        prompt = "irrelevant here"
        good = checkpoint(
            "req-1", bundle={"identity": "the-current-bundle"},
            prompt_sha256=mc.prompt_sha256(prompt))
        self.write(good)
        got = mc.recovered_media(
            "20260810", have=set(),
            bundle={"requests": [{"request_id": "req-1",
                                  "prompt_verbatim": prompt}]},
            bundle_id="the-current-bundle")
        self.assertEqual(set(got), {"req-1"})


class TestPhaseBActuallyUsesIt(unittest.TestCase):
    """Wiring, pinned: the module can be perfect and still be dead code."""

    SRC = (ROOT / "scripts" / "exchange_phase_b.py").read_text()

    def test_phase_b_calls_recovered_media(self):
        self.assertIn("recovered_media", self.SRC,
                      "Phase B must recover the media worker's checkpoints — "
                      "without this the 6:00 worker's output is hostage to "
                      "the 7:00 finalizer writing an envelope")

    def test_recovery_happens_BEFORE_validation_and_fetch(self):
        """Recovered pointers must go through the same contract validation
        and the same byte-level fetch as any other — recovery must not become
        a side door that skips them."""
        i_rec = self.SRC.index("mc.recovered_media(")
        self.assertLess(i_rec, self.SRC.index("mc.validate_response_media("),
                        "recovery must precede validation, so recovered "
                        "pointers are validated like every other pointer")
        self.assertLess(i_rec, self.SRC.index('fetch_media(rid, idx["media"]'),
                        "recovery must precede the fetch loop, so recovered "
                        "pointers take the same byte-level verification")

    def test_recovery_is_passed_the_current_bundle_and_identity(self):
        """The whole point of the fix: recovery must be told what "current"
        means, or it has nothing to compare a stale checkpoint against."""
        call = self.SRC[self.SRC.index("mc.recovered_media("):
                        self.SRC.index("mc.recovered_media(") + 400]
        self.assertIn("bundle_id=bundle_id", call)
        self.assertIn("bundle=bundle", call)


if __name__ == "__main__":
    unittest.main()
