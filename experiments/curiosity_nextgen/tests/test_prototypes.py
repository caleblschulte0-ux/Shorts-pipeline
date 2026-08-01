from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from experiments.curiosity_nextgen.artifact_manifest import (
    bind_report,
    build_manifest,
    validate_manifest,
    validate_report_binding,
)
from experiments.curiosity_nextgen.judge_contract import (
    JudgeDecision,
    JudgeVerdict,
    decide_consensus,
)
from experiments.curiosity_nextgen.media_ranker import (
    MediaCandidate,
    MediaRequirements,
    select_best,
)
from experiments.curiosity_nextgen.quality import (
    QualityDecision,
    QualityDimension,
    QualityObservation,
    evaluate_quality,
)
from experiments.curiosity_nextgen.shot_cache import (
    ShotFingerprint,
    TimelineShot,
    plan_repair,
)
from experiments.curiosity_nextgen.story_catalog import (
    StoryCatalog,
    StoryRecord,
    StoryStatus,
)


class ArtifactManifestTests(unittest.TestCase):
    def test_changed_artifact_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            video = root / "video.mp4"
            video.write_bytes(b"first")
            manifest = build_manifest(
                root=root,
                slug="demo",
                renderer_commit="abc123",
                render_profile="review",
                files=[video],
            )
            self.assertTrue(validate_manifest(root, manifest).valid)
            report = bind_report({"pass": True}, manifest,
                                 report_type="visual", producer="test")
            self.assertTrue(validate_report_binding(report, manifest)[0])
            video.write_bytes(b"second")
            result = validate_manifest(root, manifest)
            self.assertFalse(result.valid)
            self.assertIn("video.mp4", result.changed)


class QualityTests(unittest.TestCase):
    def test_hard_floor_rejects_high_average(self) -> None:
        observations = [QualityObservation(dimension, 9.0)
                        for dimension in QualityDimension]
        observations = [
            QualityObservation(
                item.dimension,
                4.0 if item.dimension is QualityDimension.FACTUAL_CONFIDENCE else item.score,
            )
            for item in observations
        ]
        result = evaluate_quality(observations)
        self.assertEqual(result.decision, QualityDecision.REJECT)


class MediaRankerTests(unittest.TestCase):
    def test_wrong_geography_is_rejected(self) -> None:
        requirements = MediaRequirements(
            query="American gas station",
            required_subjects=frozenset({"gas_station"}),
            geography="United States",
        )
        wrong = MediaCandidate(
            asset_id="jp",
            source="provider",
            width=1920,
            height=1080,
            semantic_score=0.95,
            composition_score=0.8,
            continuity_score=0.8,
            uniqueness_score=0.8,
            license="provider_api",
            subjects=frozenset({"gas_station"}),
            geography="Japan",
            detected_text=("セルフ",),
        )
        right = MediaCandidate(
            asset_id="us",
            source="provider",
            width=1920,
            height=1080,
            semantic_score=0.8,
            composition_score=0.8,
            continuity_score=0.8,
            uniqueness_score=0.8,
            license="provider_api",
            subjects=frozenset({"gas_station"}),
            geography="United States",
        )
        selected = select_best([wrong, right], requirements)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.candidate.asset_id, "us")


class StoryCatalogTests(unittest.TestCase):
    def test_only_verified_candidates_schedule(self) -> None:
        story = StoryRecord("demo", StoryStatus.RENDERABLE, priority=90)
        story.transition(
            StoryStatus.PRODUCTION_CANDIDATE,
            quality_score=8.1,
            pass_sha="deadbeef",
        )
        catalog = StoryCatalog([story])
        self.assertEqual([item.slug for item in catalog.production_candidates()], ["demo"])


class ShotCacheTests(unittest.TestCase):
    def test_repair_invalidates_only_changed_shot_and_neighbors(self) -> None:
        timeline = [
            TimelineShot("s1", "b1", "k1", transition_out_id="t12"),
            TimelineShot("s2", "b2", "k2", transition_in_id="t12", transition_out_id="t23"),
            TimelineShot("s3", "b3", "k3", transition_in_id="t23"),
        ]
        plan = plan_repair(timeline, changed_beats=["b2"])
        self.assertEqual(plan.rerender_shots, ("s2",))
        self.assertEqual(plan.reusable_shots, ("s1", "s3"))
        self.assertEqual(plan.rerender_transitions, ("t12", "t23"))

    def test_fingerprint_is_deterministic(self) -> None:
        common = dict(
            beat_id="b1",
            scene_kind="chart",
            narration_text="hello",
            narration_duration_ms=1200,
            media_sha256=("abc",),
            renderer_version="v1",
            render_profile="draft",
            width=1280,
            height=720,
            fps=30,
        )
        first = ShotFingerprint(scene_parameters={"b": 2, "a": 1}, **common)
        second = ShotFingerprint(scene_parameters={"a": 1, "b": 2}, **common)
        self.assertEqual(first.key, second.key)


class JudgeTests(unittest.TestCase):
    @staticmethod
    def verdict(judge_id: str, score: float) -> JudgeVerdict:
        return JudgeVerdict(
            judge_id=judge_id,
            judge_version="1",
            manifest_sha256="hash",
            overall_score=score,
            personality=4.5,
            hook=8.0,
            visual_relevance=8.0,
            payoff=7.5,
            pass_boolean=score >= 7.5,
        )

    def test_borderline_requires_second_review(self) -> None:
        result = decide_consensus(
            [self.verdict("one", 7.0)],
            expected_manifest_sha256="hash",
        )
        self.assertEqual(result.decision, JudgeDecision.SECOND_REVIEW)

    def test_disagreement_quarantines(self) -> None:
        result = decide_consensus(
            [self.verdict("one", 8.5), self.verdict("two", 6.8)],
            expected_manifest_sha256="hash",
        )
        self.assertEqual(result.decision, JudgeDecision.QUARANTINE)


if __name__ == "__main__":
    unittest.main()
