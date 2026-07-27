from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from .audio import DirectedLine, PronunciationLexicon, TTSRouter, VoiceDirection
from .config import missing_secrets, required_secret_names
from .contracts import EvidenceClaim, ScoreCard, Verdict
from .creative import CandidateStudio, CandidateTournament, GlobalIdeaRouter, Idea
from .diagnostics import CapabilityTruthReport
from .fixtures import audience_signals, channels, competitor_observations, idea, media_assets
from .media import AssetDeduper, MediaQualityScorer, RightsNormalizer
from .providers import DisabledTransport, NetworkDisabledError, RunwayAdapter, YouTubeAdapter
from .qa import FinalVideoGate, ThumbnailCandidate, ThumbnailJudge
from .registry import default_registry
from .replay import AssetLineageIndex, ReplayBundleWriter, TechnicalLearningStore
from .research import CommentMiner, CompetitorAnalyzer
from .video import Clip, Timeline, TimelineEditor, VisualEnhancer


class CapabilityStudioTests(unittest.TestCase):
    def test_registry_contains_expected_capabilities(self) -> None:
        registry = default_registry()
        self.assertGreaterEqual(len(registry.list()), 20)
        self.assertEqual(registry.get("audience-demand-miner").maturity.value, "prototype")

    def test_review_truth_report_never_claims_runtime_wiring(self) -> None:
        records = CapabilityTruthReport(default_registry()).prototype_records(env={})
        self.assertTrue(records)
        self.assertTrue(all(not record.imported_by_runtime for record in records))
        self.assertTrue(all("isolated prototype" in record.status_note for record in records))

    def test_secret_names_are_stable(self) -> None:
        names = required_secret_names(("elevenlabs", "runway", "creatomate", "sync"))
        self.assertEqual(names, ("ELEVENLABS_API_KEY", "RUNWAYML_API_SECRET", "CREATOMATE_API_KEY", "SYNC_API_KEY"))
        self.assertEqual(missing_secrets(("runway",), env={}), ("RUNWAYML_API_SECRET",))

    def test_disabled_transport_fails_closed(self) -> None:
        request = YouTubeAdapter().search_videos("test")
        with self.assertRaises(NetworkDisabledError):
            DisabledTransport().execute(request)

    def test_comment_miner_finds_demand(self) -> None:
        clusters = CommentMiner().cluster(audience_signals(), minimum_count=1)
        self.assertTrue(any(cluster.category == "question" for cluster in clusters))
        self.assertTrue(any(cluster.category == "request" for cluster in clusters))

    def test_competitor_summary(self) -> None:
        pattern = CompetitorAnalyzer().summarize(competitor_observations())
        self.assertGreater(pattern.median_views_per_hour, 0)
        self.assertIn(pattern.common_hook_forms[0][0], {"question", "claim", "reveal", "number", "conflict"})

    def test_candidate_studio_and_tournament(self) -> None:
        candidates = CandidateStudio().create("A premise").hooks
        cards = [ScoreCard(candidate.variant_id, {"clarity": index + 1}) for index, candidate in enumerate(candidates)]
        result = CandidateTournament().rank(candidates, cards, {"clarity": 1.0})
        self.assertEqual(result.winner_id, candidates[-1].variant_id)

    def test_global_router(self) -> None:
        decision = GlobalIdeaRouter().route(idea(), channels())
        self.assertIn(decision.channel, {"daily", "curiosity"})
        prior = Idea("old", idea().title, idea().summary, idea().topic_tags, idea().format_hints)
        duplicate = GlobalIdeaRouter().route(idea(), channels(), (prior,))
        self.assertEqual(duplicate.duplicate_of, "old")

    def test_rights_and_quality(self) -> None:
        normalizer = RightsNormalizer()
        self.assertTrue(normalizer.is_reusable("CC BY-SA"))
        score = MediaQualityScorer().score(media_assets()[0])
        self.assertGreater(score.score, 50)

    def test_asset_deduper(self) -> None:
        self.assertEqual(AssetDeduper().duplicate_groups(media_assets()), (("a1", "a3"),))

    def test_directed_tts_plan(self) -> None:
        direction = VoiceDirection("voice-1", "elevenlabs", (DirectedLine("This is ninety hours.", "urgent", "fast", ("ninety",), 250),))
        request = TTSRouter().plan(direction)
        self.assertEqual(request.provider, "elevenlabs")
        self.assertIn("ELEVENLABS_API_KEY", request.secret_names)

    def test_pronunciation_lexicon(self) -> None:
        self.assertEqual(PronunciationLexicon({"SQL": "sequel"}).apply("SQL database"), "sequel database")

    def test_runway_portrait_plan(self) -> None:
        request = RunwayAdapter().text_to_video(prompt="test")
        self.assertEqual(request.json_body["ratio"], "720:1280")
        self.assertIn("RUNWAYML_API_SECRET", request.secret_names)

    def test_timeline_plan(self) -> None:
        timeline = Timeline(clips=(Clip("one.mp4", 0, 2, "hook"), Clip("two.mp4", 1, 3, "proof")))
        command = TimelineEditor().ffmpeg_concat_plan(timeline, "out.mp4")
        self.assertEqual(command.tool, "ffmpeg")
        self.assertIn("out.mp4", command.outputs)

    def test_visual_enhancement_plans(self) -> None:
        enhancer = VisualEnhancer()
        self.assertEqual(enhancer.upscale("in.png", "out.png").tool, "realesrgan-ncnn-vulkan")
        self.assertEqual(enhancer.interpolate("in.mp4", "out.mp4").tool, "rife-ncnn-vulkan")
        self.assertEqual(enhancer.remove_background("in.png", "out.png").tool, "rembg")

    def test_final_gate_is_format_aware(self) -> None:
        gate = FinalVideoGate()
        report = gate.evaluate("text_card", {check: True for check in gate.REQUIRED_BY_FORMAT["text_card"]})
        self.assertEqual(report.verdict, Verdict.PASS)
        blocked = gate.evaluate("graph_race", {"valid_mp4": True, "portrait": True, "labels_visible": False})
        self.assertEqual(blocked.verdict, Verdict.BLOCK)

    def test_thumbnail_tournament(self) -> None:
        candidates = (ThumbnailCandidate("a", "A clear promise", 1, 0.2, 80, 80, 90, 70), ThumbnailCandidate("b", "Too many words in this thumbnail that nobody can read", 4, 0.5, 90, 90, 50, 90))
        self.assertEqual(ThumbnailJudge().tournament(candidates)[0].candidate_id, "a")

    def test_evidence_claim_validation(self) -> None:
        claim = EvidenceClaim("Fact", "https://example.test", "Publisher", "2026-01-01", "primary", "sentence 1", 0.9)
        self.assertEqual(claim.validate(), ())

    def test_replay_bundle_and_recall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "package.json"
            file.write_text("{}", encoding="utf-8")
            bundle = ReplayBundleWriter().build(channel="test", artifacts={"package": file}, metadata={"source_urls": ["https://example.test"]})
            output = ReplayBundleWriter().write(bundle, root / "bundle")
            self.assertTrue(output.is_file())
            index = AssetLineageIndex(); index.add_bundle(bundle)
            self.assertEqual(index.recall_source("https://example.test")[0][0], bundle.run_id)

    def test_technical_learning_store(self) -> None:
        store = TechnicalLearningStore(); store.record(subsystem="ffmpeg", failure="bad crop", resolution="force aspect ratio", version="1")
        self.assertEqual(len(store.query(subsystem="ffmpeg")), 1)


if __name__ == "__main__":
    unittest.main()
