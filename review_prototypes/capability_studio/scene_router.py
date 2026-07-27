from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .toolchain_catalog import TOOL_BY_ID


class SceneKind(str, Enum):
    STOCK_OR_ARCHIVE = "stock_or_archive"
    AUTHORIZED_WEB_CLIP = "authorized_web_clip"
    WEB_EVIDENCE = "web_evidence"
    OFFICE_DOCUMENT = "office_document"
    SIMPLE_CHART = "simple_chart"
    COMPARISON_CARD = "comparison_card"
    EQUATION = "equation"
    PROCESS_DIAGRAM = "process_diagram"
    NETWORK_DIAGRAM = "network_diagram"
    THREE_D = "three_d"
    PHOTO_COMPOSITE = "photo_composite"
    SUBJECT_CUTOUT = "subject_cutout"
    PRESENTER_TRACKING = "presenter_tracking"
    AUDIO_CLEANUP = "audio_cleanup"
    SHOT_EXTRACTION = "shot_extraction"
    FINAL_ASSEMBLY = "final_assembly"


@dataclass(frozen=True)
class SceneIntent:
    scene_id: str
    kind: SceneKind
    duration_seconds: float
    rights_verified: bool = False
    complexity: int = 1
    needs_equations: bool = False
    needs_depth: bool = False
    needs_object_mask: bool = False
    needs_tracking: bool = False
    source_extension: str = ""

    def __post_init__(self) -> None:
        if not self.scene_id.strip():
            raise ValueError("scene_id is required")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if not 1 <= self.complexity <= 5:
            raise ValueError("complexity must be between 1 and 5")


@dataclass(frozen=True)
class RunnerProfile:
    available_tools: frozenset[str]
    allow_heavy: bool = False
    allow_gpu: bool = False
    max_scene_seconds: float = 60.0

    @classmethod
    def all_planned(cls, *, allow_heavy: bool = True, allow_gpu: bool = True) -> "RunnerProfile":
        return cls(frozenset(TOOL_BY_ID), allow_heavy=allow_heavy, allow_gpu=allow_gpu)


@dataclass(frozen=True)
class RouteDecision:
    scene_id: str
    primary_chain: tuple[str, ...]
    fallback_chains: tuple[tuple[str, ...], ...]
    blocked: bool
    block_reason: str = ""
    reason: str = ""
    shadow_only: bool = True


ROUTES: Mapping[SceneKind, tuple[tuple[str, ...], ...]] = {
    SceneKind.STOCK_OR_ARCHIVE: (("stock-media", "ffmpeg"), ("svg-motion", "cairosvg", "ffmpeg")),
    SceneKind.AUTHORIZED_WEB_CLIP: (("yt-dlp", "scenedetect", "ffmpeg"),),
    SceneKind.WEB_EVIDENCE: (("playwright", "imagemagick", "ffmpeg"), ("svg-motion", "cairosvg", "ffmpeg")),
    SceneKind.OFFICE_DOCUMENT: (("libreoffice", "pdftoppm", "imagemagick", "ffmpeg"), ("ocrmypdf", "pdftoppm", "ffmpeg")),
    SceneKind.SIMPLE_CHART: (("svg-motion", "cairosvg", "ffmpeg"), ("pillow", "ffmpeg")),
    SceneKind.COMPARISON_CARD: (("svg-motion", "cairosvg", "ffmpeg"), ("imagemagick", "ffmpeg")),
    SceneKind.EQUATION: (("manim", "ffmpeg"), ("svg-motion", "cairosvg", "ffmpeg")),
    SceneKind.PROCESS_DIAGRAM: (("mermaid", "cairosvg", "ffmpeg"), ("graphviz", "ffmpeg"), ("svg-motion", "ffmpeg")),
    SceneKind.NETWORK_DIAGRAM: (("graphviz", "ffmpeg"), ("mermaid", "cairosvg", "ffmpeg")),
    SceneKind.THREE_D: (("blender", "ffmpeg"), ("svg-motion", "cairosvg", "ffmpeg")),
    SceneKind.PHOTO_COMPOSITE: (("imagemagick", "ffmpeg"), ("pillow", "ffmpeg")),
    SceneKind.SUBJECT_CUTOUT: (("sam2", "ffmpeg"), ("rembg", "ffmpeg")),
    SceneKind.PRESENTER_TRACKING: (("mediapipe", "opencv", "ffmpeg"), ("opencv", "ffmpeg")),
    SceneKind.AUDIO_CLEANUP: (("demucs", "rubberband", "ffmpeg"), ("audacity", "ffmpeg"), ("ffmpeg",)),
    SceneKind.SHOT_EXTRACTION: (("scenedetect", "ffmpeg"), ("ffmpeg",)),
    SceneKind.FINAL_ASSEMBLY: (("opentimelineio", "ffmpeg"), ("moviepy", "ffmpeg"), ("ffmpeg",)),
}


class FreeSceneRouter:
    def route(self, intent: SceneIntent, runner: RunnerProfile) -> RouteDecision:
        if intent.duration_seconds > runner.max_scene_seconds:
            return RouteDecision(intent.scene_id, (), (), True, "scene_exceeds_runner_limit")
        if intent.kind == SceneKind.AUTHORIZED_WEB_CLIP and not intent.rights_verified:
            return RouteDecision(intent.scene_id, (), (), True, "rights_record_required_for_web_download")

        candidates = list(ROUTES[intent.kind])
        if intent.needs_equations and intent.kind not in {SceneKind.EQUATION, SceneKind.SIMPLE_CHART}:
            candidates.insert(0, ("manim", "ffmpeg"))
        if intent.needs_depth and intent.kind != SceneKind.THREE_D:
            candidates.insert(0, ("blender", "ffmpeg"))
        if intent.needs_object_mask and intent.kind != SceneKind.SUBJECT_CUTOUT:
            candidates.insert(0, ("sam2", "ffmpeg"))
        if intent.needs_tracking and intent.kind != SceneKind.PRESENTER_TRACKING:
            candidates.insert(0, ("mediapipe", "opencv", "ffmpeg"))

        viable: list[tuple[str, ...]] = []
        rejected: list[str] = []
        for chain in candidates:
            if self._chain_viable(chain, runner):
                viable.append(chain)
            else:
                rejected.append("+".join(chain))
        if not viable:
            return RouteDecision(intent.scene_id, (), tuple(candidates), True, "no_viable_tool_chain", reason=f"rejected={','.join(rejected)}")
        return RouteDecision(
            scene_id=intent.scene_id,
            primary_chain=viable[0],
            fallback_chains=tuple(viable[1:]),
            blocked=False,
            reason=f"semantic route for {intent.kind.value}; complexity={intent.complexity}",
        )

    @staticmethod
    def _chain_viable(chain: tuple[str, ...], runner: RunnerProfile) -> bool:
        for tool_id in chain:
            if tool_id in {"stock-media", "playwright", "python-tabular-render", "json-timeline", "ffmpeg-atempo", "local-heuristics"}:
                continue
            if tool_id not in runner.available_tools:
                return False
            spec = TOOL_BY_ID.get(tool_id)
            if spec and spec.heavy and not runner.allow_heavy:
                return False
            if spec and spec.gpu_helpful and tool_id in {"sam2", "blender", "clip"} and not runner.allow_gpu and intent_requires_gpu(tool_id):
                return False
        return True


def intent_requires_gpu(tool_id: str) -> bool:
    """Tools that are intentionally treated as GPU-gated in automatic routing."""
    return tool_id in {"sam2"}
