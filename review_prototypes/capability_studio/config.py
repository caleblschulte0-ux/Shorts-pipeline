from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable, Mapping

from .contracts import CostClass, SecretRequirement, ToolRequirement


@dataclass(frozen=True)
class ProviderDefinition:
    provider_id: str
    purpose: str
    cost_class: CostClass
    secrets: tuple[SecretRequirement, ...] = ()
    optional: bool = True


PROVIDERS: dict[str, ProviderDefinition] = {
    "youtube": ProviderDefinition("youtube", "trend discovery, competitor metadata, comments, uploads, and analytics", CostClass.FREE_API, (SecretRequirement("YOUTUBE_API_KEY", "youtube", False, "public Data API requests"), SecretRequirement("YOUTUBE_TOKEN_JSON", "youtube", False, "OAuth uploads and channel-owned data"))),
    "pexels": ProviderDefinition("pexels", "stock video and photography", CostClass.FREE_API, (SecretRequirement("PEXELS_API_KEY", "pexels", False, "Pexels search"),)),
    "openverse": ProviderDefinition("openverse", "open-license media search", CostClass.FREE_API),
    "wikimedia": ProviderDefinition("wikimedia", "public-domain and freely licensed evidence media", CostClass.FREE_API),
    "internet_archive": ProviderDefinition("internet_archive", "historical and public-domain media", CostClass.FREE_API),
    "elevenlabs": ProviderDefinition("elevenlabs", "directed narration and generated sound effects", CostClass.METERED, (SecretRequirement("ELEVENLABS_API_KEY", "elevenlabs", False, "TTS and SFX"),)),
    "cartesia": ProviderDefinition("cartesia", "low-latency expressive TTS fallback", CostClass.METERED, (SecretRequirement("CARTESIA_API_KEY", "cartesia", False, "TTS"),)),
    "playht": ProviderDefinition("playht", "additional TTS fallback", CostClass.METERED, (SecretRequirement("PLAYHT_API_KEY", "playht", False, "TTS"), SecretRequirement("PLAYHT_USER_ID", "playht", False, "TTS account identifier"))),
    "runway": ProviderDefinition("runway", "custom text-to-video, image-to-video, and video-to-video shots", CostClass.EXPENSIVE, (SecretRequirement("RUNWAYML_API_SECRET", "runway", False, "generative video"),)),
    "creatomate": ProviderDefinition("creatomate", "cloud template rendering and timeline-based video editing", CostClass.METERED, (SecretRequirement("CREATOMATE_API_KEY", "creatomate", False, "cloud render jobs"),)),
    "sync": ProviderDefinition("sync", "lip-sync generation", CostClass.METERED, (SecretRequirement("SYNC_API_KEY", "sync", False, "lip sync"),)),
    "openai": ProviderDefinition("openai", "optional generated images and multimodal judging", CostClass.METERED, (SecretRequirement("OPENAI_API_KEY", "openai", False, "image generation or judging"),)),
}


LOCAL_TOOLS: dict[str, ToolRequirement] = {
    "ffmpeg": ToolRequirement("ffmpeg", "editing, audio mixing, color grading, probing, and final encoding", False, "apt-get install ffmpeg"),
    "ffprobe": ToolRequirement("ffprobe", "media metadata inspection", False, "installed with ffmpeg"),
    "auto-editor": ToolRequirement("auto-editor", "silence and dead-air removal", True, "pip install auto-editor"),
    "faster-whisper": ToolRequirement("faster-whisper", "local transcription and word timestamps", True, "pip install faster-whisper"),
    "playwright": ToolRequirement("playwright", "browser evidence capture", True, "pip install playwright && playwright install chromium"),
    "tesseract": ToolRequirement("tesseract", "OCR for screenshots and documents", True, "apt-get install tesseract-ocr"),
    "realesrgan-ncnn-vulkan": ToolRequirement("realesrgan-ncnn-vulkan", "local image/video upscaling", True, "install Real-ESRGAN NCNN binary"),
    "rife-ncnn-vulkan": ToolRequirement("rife-ncnn-vulkan", "frame interpolation", True, "install RIFE NCNN binary"),
    "rembg": ToolRequirement("rembg", "background removal", True, "pip install rembg"),
    "remotion": ToolRequirement("remotion", "React-based motion graphics and template rendering", True, "npm install remotion"),
    "blender": ToolRequirement("blender", "3D and procedural animation", True, "install Blender"),
    "manim": ToolRequirement("manim", "programmatic diagrams and educational animation", True, "pip install manim"),
}


def secret_status(env: Mapping[str, str] | None = None) -> dict[str, bool]:
    values = env if env is not None else os.environ
    names = {secret.name for provider in PROVIDERS.values() for secret in provider.secrets}
    return {name: bool(values.get(name, "").strip()) for name in sorted(names)}


def required_secret_names(provider_ids: Iterable[str]) -> tuple[str, ...]:
    names: list[str] = []
    for provider_id in provider_ids:
        definition = PROVIDERS[provider_id]
        names.extend(secret.name for secret in definition.secrets)
    return tuple(dict.fromkeys(names))


def missing_secrets(provider_ids: Iterable[str], env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    status = secret_status(env)
    return tuple(name for name in required_secret_names(provider_ids) if not status.get(name, False))
