from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import Mapping

from .contracts import stable_id


class PipelineStage(str, Enum):
    DISCOVER = "discover"
    VERIFY = "verify"
    SCRIPT = "script"
    SOURCE_MEDIA = "source_media"
    BUILD_VISUALS = "build_visuals"
    NARRATE = "narrate"
    EDIT = "edit"
    ENHANCE = "enhance"
    QA = "qa"
    PACKAGE = "package"


@dataclass(frozen=True)
class FreePipelineProject:
    topic: str
    channel: str
    format: str = "narrated_explainer"
    duration_seconds: int = 45
    allow_authorized_web_video: bool = False
    require_primary_source: bool = True
    prefer_local_only: bool = True

    def __post_init__(self) -> None:
        if not self.topic.strip() or not self.channel.strip():
            raise ValueError("topic and channel are required")
        if not 10 <= self.duration_seconds <= 180:
            raise ValueError("duration_seconds must be between 10 and 180")


@dataclass(frozen=True)
class StagePlan:
    stage: PipelineStage
    capabilities: tuple[str, ...]
    primary_tools: tuple[str, ...]
    fallback_tools: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    hard_gates: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class FreePipelineBlueprint:
    project: FreePipelineProject
    stages: tuple[StagePlan, ...]
    required_secret_names: tuple[str, ...] = ()
    optional_secret_names: tuple[str, ...] = ()
    production_wiring: bool = False
    network_execution: bool = False
    estimated_metered_cost_usd: float = 0.0
    metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def blueprint_id(self) -> str:
        return stable_id("free_pipeline", asdict(self))

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, default=str)


class FreeFirstPipelinePlanner:
    """Maps free capabilities into the existing discover-to-package pipeline shape."""

    def build(self, project: FreePipelineProject) -> FreePipelineBlueprint:
        media_primary = ("pexels", "openverse", "wikimedia", "internet_archive")
        media_fallback = ("svg-motion", "graphviz", "mermaid", "manim", "blender")
        if project.allow_authorized_web_video:
            media_primary = (*media_primary, "yt-dlp-authorized-ingest")
        stages = (
            StagePlan(PipelineStage.DISCOVER, ("audience-demand-miner", "free-public-data-research", "historical-web-discovery"), ("youtube-data-api", "gdelt", "wikidata", "wikipedia"), ("common-crawl",), outputs=("topic_candidates.json", "research_queries.json"), hard_gates=("topic_is_channel_fit", "not_semantic_duplicate")),
            StagePlan(PipelineStage.VERIFY, ("shared-evidence-contract", "government-data-adapters", "browser-evidence-capture", "pdf-ocr"), ("sec-edgar", "fred", "census", "noaa", "our-world-in-data", "playwright", "ocrmypdf"), outputs=("evidence_packet.json", "evidence_captures/"), hard_gates=("material_claims_supported", "source_date_recorded", "rights_recorded")),
            StagePlan(PipelineStage.SCRIPT, ("creative-candidate-studio", "competitor-reverse-engineer", "global-idea-router"), ("local-template-engine",), inputs=("evidence_packet.json",), outputs=("script_candidates.json", "selected_script.json"), hard_gates=("no_unsupported_claims", "hook_matches_payoff")),
            StagePlan(PipelineStage.SOURCE_MEDIA, ("broll-planner", "multi-provider-media-search", "rights-normalizer", "evidence-media-ingest"), media_primary, media_fallback, inputs=("selected_script.json",), outputs=("asset_manifest.json", "source_media/"), hard_gates=("every_asset_has_rights_record", "no_unapproved_download")),
            StagePlan(PipelineStage.BUILD_VISUALS, ("vector-motion-graphics", "diagram-generation", "math-explainer-animation", "procedural-3d-animation", "object-segmentation", "pose-tracking"), ("svg-motion", "imagemagick", "pillow", "cairosvg", "graphviz", "mermaid"), ("manim", "blender", "sam2", "mediapipe"), inputs=("asset_manifest.json",), outputs=("visual_manifest.json", "generated_visuals/")),
            StagePlan(PipelineStage.NARRATE, ("directed-voice", "local-transcription", "source-separation", "audio-time-stretch"), ("kokoro", "faster-whisper", "ffmpeg"), ("demucs", "rubberband", "audacity"), inputs=("selected_script.json",), outputs=("narration.wav", "captions.ass", "audio_manifest.json")),
            StagePlan(PipelineStage.EDIT, ("open-timeline-export", "timeline-editor", "scene-detection"), ("opentimelineio", "ffmpeg"), ("moviepy", "auto-editor", "scenedetect"), inputs=("visual_manifest.json", "narration.wav", "captions.ass"), outputs=("timeline.otio", "rough_cut.mp4"), hard_gates=("timeline_is_deterministic",)),
            StagePlan(PipelineStage.ENHANCE, ("visual-enhancement",), ("ffmpeg",), ("realesrgan", "rife", "rembg"), inputs=("rough_cut.mp4",), outputs=("enhanced_cut.mp4",), notes=("Expensive local enhancement is optional and skipped when runner capacity is limited.",)),
            StagePlan(PipelineStage.QA, ("local-thumbnail-semantic-scoring", "thumbnail-tournament", "format-aware-final-gate", "asset-recall"), ("ffprobe", "clip", "pillow-phash"), ("opencv",), inputs=("enhanced_cut.mp4",), outputs=("qa_report.json", "selected_thumbnail.png"), hard_gates=("duration_valid", "audio_valid", "safe_area_valid", "no_near_duplicate", "evidence_overlay_readable")),
            StagePlan(PipelineStage.PACKAGE, ("replay-bundles", "capability-truth-report"), ("python-stdlib",), inputs=("qa_report.json",), outputs=("replay_bundle.json", "capability_report.json"), hard_gates=("publishing_disabled_in_review_package",)),
        )
        optional_keys = ("YOUTUBE_API_KEY", "PEXELS_API_KEY", "FRED_API_KEY", "NOAA_TOKEN", "CENSUS_API_KEY")
        return FreePipelineBlueprint(
            project=project,
            stages=stages,
            required_secret_names=(),
            optional_secret_names=optional_keys,
            metadata={
                "operating_mode": "free_first",
                "paid_provider_fallbacks_enabled": False,
                "review_only": True,
                "production_imports": 0,
                "workflow_changes": 0,
            },
        )

    def integration_slots(self) -> Mapping[str, tuple[str, ...]]:
        """Stable slots Claude can map to production one at a time later."""
        return {
            "topic_discovery": ("free-public-data-research", "audience-demand-miner"),
            "research_packet": ("shared-evidence-contract", "browser-evidence-capture", "pdf-ocr"),
            "media_manifest": ("broll-planner", "multi-provider-media-search", "rights-normalizer"),
            "scene_plan": ("vector-motion-graphics", "diagram-generation", "scene-detection"),
            "narration": ("directed-voice", "local-transcription"),
            "timeline": ("open-timeline-export", "timeline-editor"),
            "rough_cut": ("visual-enhancement",),
            "quality_gate": ("format-aware-final-gate", "local-thumbnail-semantic-scoring"),
            "run_lineage": ("replay-bundles", "capability-truth-report"),
        }
