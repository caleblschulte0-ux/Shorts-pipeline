from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest

from .fixtures import FIXED_TODAY, golden_story
from .models import PipelineStatus, ProofRun, RenderBundle, Verdict, sha256_file


class ModelTests(unittest.TestCase):
    def test_golden_story_validates_and_hashes_deterministically(self):
        story = golden_story()
        story.validate(today=FIXED_TODAY)
        self.assertEqual(story.digest, golden_story().digest)
        self.assertEqual(story.canonical_payload()["slug"], story.slug)

    def test_source_validation_failures(self):
        base = golden_story().source
        invalid = (
            replace(base, publisher=""),
            replace(base, url="http://example.com"),
            replace(base, accessed=FIXED_TODAY + timedelta(days=1)),
            replace(base, accessed=FIXED_TODAY - timedelta(days=366)),
            replace(base, claim=""),
            replace(base, unit=""),
        )
        for source in invalid:
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    source.validate(today=FIXED_TODAY)

    def test_story_validation_failures(self):
        story = golden_story()
        cases = (
            replace(story, slug=""),
            replace(story, title="A Blue Whale Heart", hook="No number here"),
            replace(story, beats=story.beats[:2]),
            replace(story, beats=(replace(story.beats[0], duration_seconds=1.6), *story.beats[1:])),
            replace(story, beats=tuple(replace(beat, mascot_action="same") for beat in story.beats)),
            replace(story, beats=(*story.beats[:-1], replace(story.beats[-1], tension=0.99))),
        )
        for bad in cases:
            with self.subTest(slug=bad.slug, hook=bad.hook):
                with self.assertRaises(ValueError):
                    bad.validate(today=FIXED_TODAY)

    def test_beat_validation_failures(self):
        beat = golden_story().beats[0]
        cases = (
            replace(beat, beat_id=""),
            replace(beat, narration=""),
            replace(beat, duration_seconds=0.1),
            replace(beat, duration_seconds=9),
            replace(beat, visual_family=""),
            replace(beat, mascot_action=""),
            replace(beat, tension=-0.1),
            replace(beat, tension=1.1),
        )
        for bad in cases:
            with self.assertRaises(ValueError):
                bad.validate()

    def test_render_bundle_validation_and_hash_function(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            video = root / "video.mp4"
            plan = root / "plan.json"
            video.write_bytes(b"video")
            plan.write_text("{}", encoding="utf-8")
            bundle = RenderBundle("s", "a", root, video, plan, sha256_file(video), sha256_file(plan), "v1")
            bundle.validate()
            video.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                bundle.validate()
            video.write_bytes(b"video")
            plan.write_text("{\"tampered\": true}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "plan hash"):
                bundle.validate()
            video.unlink()
            with self.assertRaises(ValueError):
                bundle.validate()

    def test_verdict_validation_and_shippable(self):
        verdict = Verdict(95, 9, 30, 0.02, True, (), "v1")
        self.assertTrue(verdict.shippable)
        self.assertFalse(replace(verdict, score=80).shippable)
        invalid = (
            replace(verdict, score=101),
            replace(verdict, lowest_dimension=11),
            replace(verdict, effective_fps=0),
            replace(verdict, duplicate_ratio=2),
            replace(verdict, watched_video=False),
            replace(verdict, judge_version=""),
            Verdict("x", 9, 30, 0.02, True, (), "v1"),  # type: ignore[arg-type]
        )
        for bad in invalid:
            with self.assertRaises(ValueError):
                bad.validate()

    def test_proof_run_digest_and_pipeline_status(self):
        run = ProofRun("r", "s", "rv", "jv", "vh", "jh", 95, 9, 30, 0.02, True)
        self.assertEqual(run.digest, run.digest)
        self.assertEqual(run.canonical_payload()["run_id"], "r")
        self.assertEqual(PipelineStatus.SHIPPED.value, "shipped")
