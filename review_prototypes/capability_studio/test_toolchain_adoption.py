from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from .contracts import CommandPlan
from .integration_compiler import SceneBuildRequest, ToolchainIntegrationCompiler
from .scene_router import FreeSceneRouter, RunnerProfile, SceneIntent, SceneKind
from .toolchain_catalog import TOOL_BY_ID, required_secret_names
from .toolchain_executor import ExecutionMode, ReviewToolExecutor


EXPECTED = {
    "yt-dlp", "manim", "blender", "svg-motion", "imagemagick", "libreoffice",
    "graphviz", "moviepy", "ffmpeg", "scenedetect", "opentimelineio", "pillow",
    "cairosvg", "mermaid", "clip", "sam2", "mediapipe", "ocrmypdf",
    "common-crawl", "gdelt", "wikipedia", "wikidata", "owid", "fred", "census",
    "noaa", "demucs", "audacity", "rubberband",
}


class ToolchainAdoptionTests(unittest.TestCase):
    def test_catalog_covers_full_free_list(self) -> None:
        self.assertTrue(EXPECTED.issubset(TOOL_BY_ID))
        self.assertTrue(all(not spec.validate() for spec in TOOL_BY_ID.values()))

    def test_new_toolchain_requires_no_secret(self) -> None:
        self.assertEqual(required_secret_names(), ())

    def test_simple_chart_prefers_svg(self) -> None:
        intent = SceneIntent("chart", SceneKind.SIMPLE_CHART, 5)
        decision = FreeSceneRouter().route(intent, RunnerProfile.all_planned())
        self.assertFalse(decision.blocked)
        self.assertEqual(decision.primary_chain[:2], ("svg-motion", "cairosvg"))

    def test_equation_falls_back_without_heavy_tools(self) -> None:
        runner = RunnerProfile(frozenset({"svg-motion", "cairosvg", "ffmpeg"}), allow_heavy=False)
        decision = FreeSceneRouter().route(SceneIntent("math", SceneKind.EQUATION, 6), runner)
        self.assertEqual(decision.primary_chain, ("svg-motion", "cairosvg", "ffmpeg"))

    def test_web_download_is_rights_gated(self) -> None:
        runner = RunnerProfile.all_planned()
        blocked = FreeSceneRouter().route(SceneIntent("clip", SceneKind.AUTHORIZED_WEB_CLIP, 4), runner)
        self.assertTrue(blocked.blocked)
        allowed = FreeSceneRouter().route(SceneIntent("clip", SceneKind.AUTHORIZED_WEB_CLIP, 4, rights_verified=True), runner)
        self.assertFalse(allowed.blocked)

    def test_compiler_maps_office_document(self) -> None:
        request = SceneBuildRequest(SceneIntent("office", SceneKind.OFFICE_DOCUMENT, 5), "/tmp/review", source="sheet.xlsx")
        compiled = ToolchainIntegrationCompiler().compile(request, RunnerProfile.all_planned())
        self.assertEqual(compiled.plans[0].tool, "libreoffice")
        self.assertEqual(compiled.plans[-1].tool, "ffmpeg")
        self.assertFalse(compiled.production_wiring)

    def test_compiler_requires_rights_record_path(self) -> None:
        request = SceneBuildRequest(SceneIntent("clip", SceneKind.AUTHORIZED_WEB_CLIP, 5, rights_verified=True), "/tmp/review", source="https://example.test/video")
        compiled = ToolchainIntegrationCompiler().compile(request, RunnerProfile.all_planned())
        self.assertTrue(compiled.decision.blocked)
        self.assertEqual(compiled.decision.block_reason, "rights_record_path_required")

    def test_executor_is_plan_only_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = ReviewToolExecutor(Path(tmp), mode=ExecutionMode.PLAN_ONLY)
            plan = CommandPlan("ffmpeg", ("ffmpeg", "-version"), outputs=())
            result = executor.run(plan)
            self.assertFalse(result.executed)
            self.assertEqual(result.reason, "plan_only")
            self.assertTrue((Path(tmp) / "logs" / f"{plan.command_id}.plan.json").is_file())

    def test_executor_blocks_workspace_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = ReviewToolExecutor(Path(tmp))
            plan = CommandPlan("ffmpeg", ("ffmpeg", "-version"), outputs=("/etc/not-allowed.mp4",))
            self.assertTrue(any("output_escapes_workspace" in item for item in executor.validate(plan)))


if __name__ == "__main__":
    unittest.main()
