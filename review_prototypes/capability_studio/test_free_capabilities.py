from __future__ import annotations

import json
import unittest

from .config import FREE_STACK_OPTIONAL_SECRETS, LOCAL_TOOLS, PROVIDERS
from .free_audio import AudioChainPlanner, FreeAudioPlanner
from .free_graphics import GraphicsCommandPlanner, SvgBar, SvgMotionBuilder, graphviz_dot
from .free_media import EvidenceIngestPlanner, SceneExtractionPlanner, YtDlpPlanner
from .free_pipeline import FreeFirstPipelinePlanner, FreePipelineProject, PipelineStage
from .free_research import FreeResearchAdapters, PublicDataResearchPlanner, ResearchTopic
from .free_timeline import TimelineClip, TimelineDocument
from .free_vision import LocalVisualRanker, VisualCandidateMetrics, VisionCommandPlanner
from .registry import default_registry


class FreeResearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapters = FreeResearchAdapters()

    def test_gdelt_is_keyless(self) -> None:
        plan = self.adapters.gdelt("small business lending")
        self.assertEqual(plan.secret_names, ())
        self.assertIn("gdeltproject.org", plan.url)

    def test_fred_declares_free_key(self) -> None:
        plan = self.adapters.fred("CPIAUCSL")
        self.assertEqual(plan.secret_names, ("FRED_API_KEY",))
        self.assertEqual(plan.query["series_id"], "CPIAUCSL")

    def test_census_key_is_required_for_census_requests(self) -> None:
        plan = self.adapters.census_acs5(year=2024, variables=("B19013_001E",), geography="state:46")
        self.assertEqual(plan.secret_names, ("CENSUS_API_KEY",))
        self.assertEqual(plan.query["key"], "${CENSUS_API_KEY}")

    def test_discovery_bundle_contains_multiple_sources(self) -> None:
        bundle = PublicDataResearchPlanner().discovery_bundle(ResearchTopic("printer ink"))
        self.assertGreaterEqual(len(bundle.plans), 4)
        self.assertIn("primary_source", bundle.source_priority)


class FreeMediaTests(unittest.TestCase):
    def test_ytdlp_clip_is_rights_guarded_in_notes(self) -> None:
        plan = YtDlpPlanner().authorized_clip("https://example.com/video", "clip.%(ext)s", start=3, end=8)
        self.assertIn("rights record", " ".join(plan.notes).lower())

    def test_scene_detection_plan(self) -> None:
        plan = SceneExtractionPlanner().detect("input.mp4", "scenes.csv")
        self.assertEqual(plan.tool, "scenedetect")
        self.assertIn("detect-content", plan.argv)

    def test_ocr_plan_preserves_inputs_outputs(self) -> None:
        plan = EvidenceIngestPlanner().ocr_pdf("source.pdf", "ocr.pdf")
        self.assertEqual(plan.inputs, ("source.pdf",))
        self.assertEqual(plan.outputs, ("ocr.pdf",))


class GraphicsTests(unittest.TestCase):
    def test_svg_bar_chart_is_animated_and_vertical(self) -> None:
        svg = SvgMotionBuilder().bar_chart("Revenue", (SvgBar("A", 10), SvgBar("B", 20)))
        self.assertIn("1080", svg)
        self.assertIn("1920", svg)
        self.assertIn("<animate", svg)

    def test_graphviz_dot(self) -> None:
        dot = graphviz_dot((("Research", "Script"), ("Script", "Edit")))
        self.assertIn('"Research" -> "Script"', dot)

    def test_blender_plan_is_headless(self) -> None:
        plan = GraphicsCommandPlanner().blender("scene.blend", "frames/frame_#####")
        self.assertIn("-b", plan.argv)
        self.assertIn("-a", plan.argv)


class VisionTests(unittest.TestCase):
    def test_clip_plan_stays_local(self) -> None:
        plan = VisionCommandPlanner().clip_score(("one.png", "two.png"), "clear promise", "scores.json")
        self.assertEqual(plan.tool, "clip")
        self.assertEqual(plan.env_names, ())

    def test_ranker_rejects_unsafe_candidate(self) -> None:
        score = LocalVisualRanker().score(VisualCandidateMetrics("bad", .9, .9, .9, .9, .2))
        self.assertIn("unsafe_text_or_subject_placement", score.hard_failures)

    def test_ranker_selects_eligible_winner(self) -> None:
        winner = LocalVisualRanker().winner((
            VisualCandidateMetrics("one", .8, .8, .8, .8, .9),
            VisualCandidateMetrics("two", .9, .9, .7, .8, .9),
        ))
        self.assertEqual(winner.candidate_id, "two")


class AudioTests(unittest.TestCase):
    def test_demucs_plan(self) -> None:
        plan = FreeAudioPlanner().separate_stems("song.wav", "stems")
        self.assertEqual(plan.tool, "demucs")

    def test_audio_chain_has_required_mix_and_master(self) -> None:
        stages = AudioChainPlanner().build("voice.wav", "music.wav", "master.wav")
        self.assertEqual([stage.name for stage in stages], ["mix", "master"])
        self.assertTrue(all(stage.required for stage in stages))


class TimelineTests(unittest.TestCase):
    def test_otio_export_preserves_gaps(self) -> None:
        document = TimelineDocument("Short", 30, (
            TimelineClip("first", "first.mp4", 0, 0, 2),
            TimelineClip("second", "second.mp4", 3, 0, 2),
        ))
        payload = document.to_otio_dict()
        children = payload["tracks"]["children"][0]["children"]
        self.assertTrue(any(child["OTIO_SCHEMA"].startswith("Gap") for child in children))

    def test_timeline_id_is_deterministic(self) -> None:
        clip = TimelineClip("first", "first.mp4", 0, 0, 2)
        self.assertEqual(TimelineDocument("Short", 30, (clip,)).timeline_id, TimelineDocument("Short", 30, (clip,)).timeline_id)


class PipelineTests(unittest.TestCase):
    def test_blueprint_has_full_pipeline(self) -> None:
        blueprint = FreeFirstPipelinePlanner().build(FreePipelineProject("printer ink", "consumer facts"))
        self.assertEqual(tuple(stage.stage for stage in blueprint.stages), tuple(PipelineStage))
        self.assertEqual(blueprint.required_secret_names, ())
        self.assertEqual(blueprint.estimated_metered_cost_usd, 0.0)
        self.assertFalse(blueprint.production_wiring)

    def test_authorized_video_is_opt_in(self) -> None:
        default = FreeFirstPipelinePlanner().build(FreePipelineProject("topic", "channel"))
        enabled = FreeFirstPipelinePlanner().build(FreePipelineProject("topic", "channel", allow_authorized_web_video=True))
        default_tools = next(stage.primary_tools for stage in default.stages if stage.stage == PipelineStage.SOURCE_MEDIA)
        enabled_tools = next(stage.primary_tools for stage in enabled.stages if stage.stage == PipelineStage.SOURCE_MEDIA)
        self.assertNotIn("yt-dlp-authorized-ingest", default_tools)
        self.assertIn("yt-dlp-authorized-ingest", enabled_tools)

    def test_blueprint_json(self) -> None:
        blueprint = FreeFirstPipelinePlanner().build(FreePipelineProject("topic", "channel"))
        parsed = json.loads(blueprint.to_json())
        self.assertEqual(parsed["metadata"]["operating_mode"], "free_first")

    def test_integration_slots_match_existing_pipeline_shape(self) -> None:
        slots = FreeFirstPipelinePlanner().integration_slots()
        self.assertIn("topic_discovery", slots)
        self.assertIn("quality_gate", slots)
        self.assertIn("run_lineage", slots)


class RegistryTests(unittest.TestCase):
    def test_registry_contains_large_free_expansion(self) -> None:
        registry = default_registry()
        for capability_id in (
            "free-public-data-research", "evidence-media-ingest", "vector-motion-graphics",
            "procedural-3d-animation", "scene-detection", "open-timeline-export",
            "object-segmentation", "source-separation", "local-thumbnail-semantic-scoring",
            "free-first-orchestration",
        ):
            self.assertEqual(registry.get(capability_id).capability_id, capability_id)

    def test_free_tools_registered(self) -> None:
        for tool in ("yt-dlp", "blender", "manim", "imagemagick", "graphviz", "mermaid", "scenedetect", "demucs", "rubberband"):
            self.assertIn(tool, LOCAL_TOOLS)

    def test_free_data_providers_registered(self) -> None:
        for provider in ("gdelt", "wikidata", "common_crawl", "fred", "census", "noaa", "our_world_in_data", "sec_edgar"):
            self.assertIn(provider, PROVIDERS)

    def test_new_keys_are_optional(self) -> None:
        self.assertEqual(FREE_STACK_OPTIONAL_SECRETS, ("FRED_API_KEY", "NOAA_TOKEN", "CENSUS_API_KEY"))


if __name__ == "__main__":
    unittest.main()
