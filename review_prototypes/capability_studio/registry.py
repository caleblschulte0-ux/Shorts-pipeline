from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from .config import LOCAL_TOOLS, PROVIDERS
from .contracts import CapabilityKind, CapabilitySpec, CostClass


class CapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, CapabilitySpec] = {}

    def register(self, spec: CapabilitySpec) -> None:
        if spec.capability_id in self._items:
            raise ValueError(f"duplicate capability: {spec.capability_id}")
        self._items[spec.capability_id] = spec

    def get(self, capability_id: str) -> CapabilitySpec:
        return self._items[capability_id]

    def list(self, *, kind: CapabilityKind | None = None) -> tuple[CapabilitySpec, ...]:
        items = self._items.values()
        if kind is not None:
            items = (item for item in items if item.kind == kind)
        return tuple(sorted(items, key=lambda item: item.capability_id))

    def as_dicts(self) -> tuple[dict[str, object], ...]:
        return tuple(asdict(item) for item in self.list())


def _provider_secrets(*provider_ids: str):
    return tuple(secret for provider_id in provider_ids for secret in PROVIDERS[provider_id].secrets)


def _tools(*tool_ids: str):
    return tuple(LOCAL_TOOLS[tool_id] for tool_id in tool_ids)


def default_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    specs: Iterable[CapabilitySpec] = (
        CapabilitySpec("audience-demand-miner", "Audience demand miner", CapabilityKind.RESEARCH, "Extract repeated questions, requests, corrections, conflicts, and native audience language from comments.", secret_requirements=_provider_secrets("youtube"), cost_class=CostClass.FREE_API),
        CapabilitySpec("competitor-reverse-engineer", "Competitor video reverse engineer", CapabilityKind.RESEARCH, "Measure hooks, pacing, cuts, captions, payoff timing, and age-normalized performance.", secret_requirements=_provider_secrets("youtube"), tool_requirements=_tools("faster-whisper", "ffmpeg"), cost_class=CostClass.FREE_API),
        CapabilitySpec("creative-candidate-studio", "Creative candidate studio", CapabilityKind.CREATIVE, "Generate and compare multiple hooks, titles, structures, openings, and endings before full rendering."),
        CapabilitySpec("global-idea-router", "Global idea router", CapabilityKind.CREATIVE, "Route one discovery pool into channel-specific opportunities while preventing semantic duplication."),
        CapabilitySpec("broll-planner", "Intentional B-roll planner", CapabilityKind.MEDIA, "Translate each script beat into concrete evidence, footage, diagram, or generated-shot requirements."),
        CapabilitySpec("multi-provider-media-search", "Multi-provider media search", CapabilityKind.MEDIA, "Plan searches across Pexels, Openverse, Wikimedia Commons, and Internet Archive.", secret_requirements=_provider_secrets("pexels"), cost_class=CostClass.FREE_API),
        CapabilitySpec("rights-normalizer", "Rights and attribution normalizer", CapabilityKind.MEDIA, "Normalize provider licenses and preserve attribution and source lineage."),
        CapabilitySpec("asset-recall", "Asset recall and duplicate detection", CapabilityKind.MEDIA, "Find every run using an asset and detect exact or perceptual duplicates."),
        CapabilitySpec("browser-evidence-capture", "Browser and document evidence capture", CapabilityKind.MEDIA, "Capture, crop, highlight, and animate real web pages, filings, charts, and PDFs.", tool_requirements=_tools("playwright", "tesseract", "ffmpeg")),
        CapabilitySpec("directed-voice", "Expressive directed voice", CapabilityKind.AUDIO, "Route performance-directed narration with pronunciation control across premium and local TTS providers.", secret_requirements=_provider_secrets("elevenlabs", "cartesia", "playht"), tool_requirements=_tools("ffmpeg"), cost_class=CostClass.METERED),
        CapabilitySpec("local-transcription", "Local transcription and subtitle timing", CapabilityKind.AUDIO, "Generate word timestamps and subtitle files locally.", tool_requirements=_tools("faster-whisper", "ffmpeg")),
        CapabilitySpec("sound-design", "Music and sound-effects planner", CapabilityKind.AUDIO, "Plan ducking, emphasis hits, transitions, ambience, and generated SFX.", secret_requirements=_provider_secrets("elevenlabs"), tool_requirements=_tools("ffmpeg"), cost_class=CostClass.METERED),
        CapabilitySpec("timeline-editor", "Programmatic timeline editor", CapabilityKind.VIDEO, "Produce deterministic edit plans for FFmpeg, Auto-Editor, Remotion, or Creatomate.", secret_requirements=_provider_secrets("creatomate"), tool_requirements=_tools("ffmpeg", "auto-editor", "remotion")),
        CapabilitySpec("visual-enhancement", "Visual enhancement suite", CapabilityKind.VIDEO, "Upscale, interpolate, remove backgrounds, color-grade, and normalize final media.", tool_requirements=_tools("ffmpeg", "realesrgan-ncnn-vulkan", "rife-ncnn-vulkan", "rembg")),
        CapabilitySpec("custom-generative-video", "Custom generative video B-roll", CapabilityKind.VIDEO, "Generate short hero shots from text, images, or video references.", secret_requirements=_provider_secrets("runway"), cost_class=CostClass.EXPENSIVE),
        CapabilitySpec("visual-consistency", "Visual consistency and reference locking", CapabilityKind.VIDEO, "Carry subject, character, product, palette, and set references across generated shots.", secret_requirements=_provider_secrets("runway", "openai"), cost_class=CostClass.EXPENSIVE),
        CapabilitySpec("lip-sync", "Lip-sync adapter", CapabilityKind.VIDEO, "Create optional lip-synced presenter or character footage.", secret_requirements=_provider_secrets("sync"), cost_class=CostClass.METERED),
        CapabilitySpec("thumbnail-tournament", "Thumbnail tournament", CapabilityKind.QA, "Generate and rank multiple thumbnail candidates using legibility, novelty, contrast, and promise clarity."),
        CapabilitySpec("format-aware-final-gate", "Format-aware final-video gate", CapabilityKind.QA, "Apply different technical and editorial checks to text cards, charts, narrated explainers, and clips.", tool_requirements=_tools("ffmpeg", "ffprobe")),
        CapabilitySpec("capability-truth-report", "Capability truth report", CapabilityKind.LEARNING, "Separate code existence, configuration, workflow wiring, actual invocation, recent success, and fallback status."),
        CapabilitySpec("replay-bundles", "Deterministic replay bundles", CapabilityKind.STORAGE, "Persist source, package, media, narration, captions, render, QA, upload, and analytics lineage."),
        CapabilitySpec("shared-evidence-contract", "Shared evidence contract", CapabilityKind.LEARNING, "Attach exact source, date, confidence, rights, and supported script or graph element to every factual claim."),
        CapabilitySpec("technical-learning-store", "Shared technical learning", CapabilityKind.LEARNING, "Share provider, renderer, FFmpeg, TTS, caption, and safe-area failures without merging channel creative doctrine."),
    )
    for spec in specs:
        registry.register(spec)
    return registry
