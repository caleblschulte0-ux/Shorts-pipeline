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
    "gdelt": ProviderDefinition("gdelt", "global news and event discovery", CostClass.FREE_API),
    "wikidata": ProviderDefinition("wikidata", "structured entity and relationship research", CostClass.FREE_API),
    "wikipedia": ProviderDefinition("wikipedia", "background discovery context", CostClass.FREE_API),
    "common_crawl": ProviderDefinition("common_crawl", "historical web discovery and archive lookup", CostClass.FREE_API),
    "our_world_in_data": ProviderDefinition("our_world_in_data", "public chart datasets", CostClass.FREE_API),
    "sec_edgar": ProviderDefinition("sec_edgar", "company filings and XBRL facts", CostClass.FREE_API),
    "fred": ProviderDefinition("fred", "Federal Reserve economic time series", CostClass.FREE_API, (SecretRequirement("FRED_API_KEY", "fred", False, "free FRED API access"),)),
    "census": ProviderDefinition("census", "US Census and ACS datasets", CostClass.FREE_API, (SecretRequirement("CENSUS_API_KEY", "census", False, "free Census Data API access"),)),
    "noaa": ProviderDefinition("noaa", "weather, climate, and historical event datasets", CostClass.FREE_API, (SecretRequirement("NOAA_TOKEN", "noaa", False, "free NOAA CDO access token"),)),
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
    "faster-whisper": ToolRequirement("python", "local transcription and word timestamps", True, "pip install faster-whisper"),
    "playwright": ToolRequirement("playwright", "browser evidence capture", True, "pip install playwright && playwright install chromium"),
    "tesseract": ToolRequirement("tesseract", "OCR for screenshots and documents", True, "apt-get install tesseract-ocr"),
    "realesrgan-ncnn-vulkan": ToolRequirement("realesrgan-ncnn-vulkan", "local image/video upscaling", True, "install Real-ESRGAN NCNN binary"),
    "rife-ncnn-vulkan": ToolRequirement("rife-ncnn-vulkan", "frame interpolation", True, "install RIFE NCNN binary"),
    "rembg": ToolRequirement("rembg", "background removal", True, "pip install rembg"),
    "remotion": ToolRequirement("remotion", "React-based motion graphics and template rendering", True, "npm install remotion"),
    "blender": ToolRequirement("blender", "3D and procedural animation", True, "install Blender"),
    "manim": ToolRequirement("manim", "programmatic diagrams and educational animation", True, "pip install manim"),
    "yt-dlp": ToolRequirement("yt-dlp", "authorized metadata, subtitle, thumbnail, and clip ingest", True, "pip install yt-dlp"),
    "imagemagick": ToolRequirement("magick", "image crop, composite, sharpen, typography, and format conversion", True, "install ImageMagick"),
    "libreoffice": ToolRequirement("libreoffice", "headless spreadsheet, chart, slide, and document conversion", True, "install LibreOffice"),
    "graphviz": ToolRequirement("dot", "flowcharts, networks, and relationship diagrams", True, "install Graphviz"),
    "mermaid": ToolRequirement("mmdc", "flowcharts, timelines, and sequence diagrams", True, "npm install -g @mermaid-js/mermaid-cli"),
    "scenedetect": ToolRequirement("scenedetect", "automatic scene boundary detection and clip splitting", True, "pip install scenedetect[opencv]"),
    "opentimelineio": ToolRequirement("otioconvert", "portable edit-decision and timeline interchange", True, "pip install opentimelineio"),
    "moviepy": ToolRequirement("python", "optional Python timeline rendering", True, "pip install moviepy"),
    "cairosvg": ToolRequirement("python", "SVG to PNG/PDF rendering", True, "pip install cairosvg"),
    "pillow": ToolRequirement("python", "local image composition and perceptual hashing", True, "pip install pillow"),
    "clip": ToolRequirement("python", "local semantic image and thumbnail scoring", True, "pip install torch transformers pillow"),
    "sam2": ToolRequirement("python", "promptable object segmentation and mask generation", True, "install a release-pinned SAM 2 package and model checkpoint"),
    "mediapipe": ToolRequirement("python", "face, hand, and pose tracking", True, "pip install mediapipe opencv-python"),
    "ocrmypdf": ToolRequirement("ocrmypdf", "searchable PDF OCR with page preservation", True, "pip install ocrmypdf"),
    "pdftoppm": ToolRequirement("pdftoppm", "render PDF pages to images", True, "install poppler-utils"),
    "demucs": ToolRequirement("demucs", "local vocal, music, and stem separation", True, "pip install demucs"),
    "rubberband": ToolRequirement("rubberband", "high-quality time stretching and pitch shifting", True, "install rubberband-cli"),
    "audacity": ToolRequirement("audacity", "optional macro-based cleanup", True, "install Audacity and validate command-line support"),
}

FREE_STACK_OPTIONAL_SECRETS: tuple[str, ...] = ("FRED_API_KEY", "NOAA_TOKEN", "CENSUS_API_KEY")


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
