from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import importlib.util
import shutil
from typing import Iterable, Mapping


class InstallGroup(str, Enum):
    CORE = "core"
    GRAPHICS = "graphics"
    DOCUMENTS = "documents"
    VISION = "vision"
    AUDIO = "audio"
    HEAVY = "heavy"
    NODE = "node"
    MODELS = "models"


@dataclass(frozen=True)
class FreeToolSpec:
    tool_id: str
    title: str
    stages: tuple[str, ...]
    use_for: tuple[str, ...]
    executable: str | None = None
    python_module: str | None = None
    install_group: InstallGroup = InstallGroup.CORE
    heavy: bool = False
    gpu_helpful: bool = False
    network_at_runtime: bool = False
    default_enabled: bool = True
    fallback_ids: tuple[str, ...] = ()
    warning: str = ""

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.tool_id or not self.title:
            failures.append("identity_missing")
        if not self.executable and not self.python_module and self.tool_id != "svg-motion" and not self.network_at_runtime:
            failures.append("probe_missing")
        if not self.stages:
            failures.append("stage_missing")
        if not self.use_for:
            failures.append("use_case_missing")
        return tuple(failures)


TOOLS: tuple[FreeToolSpec, ...] = (
    FreeToolSpec("ffmpeg", "FFmpeg", ("edit", "enhance", "qa"), ("final assembly", "transitions", "captions", "audio mixing", "encoding"), executable="ffmpeg", fallback_ids=()),
    FreeToolSpec("ffprobe", "ffprobe", ("qa",), ("duration and stream inspection",), executable="ffprobe"),
    FreeToolSpec("yt-dlp", "yt-dlp", ("source_media",), ("owned or licensed metadata", "subtitles", "thumbnails", "authorized clips"), executable="yt-dlp", network_at_runtime=True, warning="Never treat downloadability as reuse permission."),
    FreeToolSpec("svg-motion", "Native SVG motion", ("build_visuals",), ("charts", "comparison cards", "arrows", "counters", "maps", "lightweight motion graphics"), fallback_ids=("pillow", "imagemagick")),
    FreeToolSpec("cairosvg", "CairoSVG", ("build_visuals",), ("rasterizing deterministic SVG frames",), executable="cairosvg", python_module="cairosvg", install_group=InstallGroup.GRAPHICS, fallback_ids=("imagemagick",)),
    FreeToolSpec("imagemagick", "ImageMagick", ("build_visuals", "enhance"), ("crop", "composite", "sharpen", "mask", "thumbnail normalization"), executable="magick", install_group=InstallGroup.GRAPHICS, fallback_ids=("pillow", "ffmpeg")),
    FreeToolSpec("pillow", "Pillow", ("build_visuals", "qa"), ("cards", "text overlays", "thumbnails", "perceptual hashes"), python_module="PIL", install_group=InstallGroup.GRAPHICS, fallback_ids=("imagemagick",)),
    FreeToolSpec("manim", "Manim", ("build_visuals",), ("equations", "axes", "financial formulas", "technical explainers"), executable="manim", python_module="manim", install_group=InstallGroup.HEAVY, heavy=True, fallback_ids=("svg-motion", "graphviz")),
    FreeToolSpec("blender", "Blender", ("build_visuals",), ("3D spatial explanations", "product shots", "camera moves", "procedural scenes"), executable="blender", install_group=InstallGroup.HEAVY, heavy=True, gpu_helpful=True, fallback_ids=("svg-motion", "stock-media")),
    FreeToolSpec("graphviz", "Graphviz", ("build_visuals",), ("networks", "hierarchies", "decision trees", "dependency graphs"), executable="dot", python_module="graphviz", install_group=InstallGroup.GRAPHICS, fallback_ids=("mermaid", "svg-motion")),
    FreeToolSpec("mermaid", "Mermaid CLI", ("build_visuals",), ("flowcharts", "timelines", "sequence diagrams", "simple process graphics"), executable="mmdc", install_group=InstallGroup.NODE, fallback_ids=("graphviz", "svg-motion")),
    FreeToolSpec("libreoffice", "LibreOffice headless", ("verify", "build_visuals"), ("spreadsheets", "presentations", "office documents", "source-faithful PDF conversion"), executable="libreoffice", install_group=InstallGroup.DOCUMENTS, heavy=True, fallback_ids=("python-tabular-render",)),
    FreeToolSpec("ocrmypdf", "OCRmyPDF", ("verify",), ("searchable evidence PDFs", "deskewed document ingestion"), executable="ocrmypdf", python_module="ocrmypdf", install_group=InstallGroup.DOCUMENTS, fallback_ids=("tesseract",)),
    FreeToolSpec("tesseract", "Tesseract", ("verify",), ("OCR for screenshots and rendered pages",), executable="tesseract", install_group=InstallGroup.DOCUMENTS),
    FreeToolSpec("pdftoppm", "Poppler PDF renderer", ("verify", "build_visuals"), ("PDF pages to PNG evidence frames",), executable="pdftoppm", install_group=InstallGroup.DOCUMENTS),
    FreeToolSpec("scenedetect", "PySceneDetect", ("source_media", "edit"), ("cut detection", "shot splitting", "B-roll indexing"), executable="scenedetect", python_module="scenedetect", install_group=InstallGroup.CORE, fallback_ids=("ffmpeg",)),
    FreeToolSpec("opentimelineio", "OpenTimelineIO", ("edit", "package"), ("portable deterministic timeline documents", "editor interchange"), executable="otioconvert", python_module="opentimelineio", install_group=InstallGroup.CORE, fallback_ids=("json-timeline",)),
    FreeToolSpec("moviepy", "MoviePy", ("edit",), ("Python-level compositing prototypes", "timeline previews"), python_module="moviepy", install_group=InstallGroup.CORE, fallback_ids=("ffmpeg",), warning="FFmpeg remains the canonical final renderer."),
    FreeToolSpec("clip", "CLIP", ("qa",), ("semantic image ranking", "thumbnail relevance", "best-frame selection"), python_module="transformers", install_group=InstallGroup.VISION, heavy=True, gpu_helpful=True, fallback_ids=("local-heuristics",)),
    FreeToolSpec("sam2", "SAM 2", ("build_visuals",), ("subject isolation", "object masks", "tracked cutouts"), python_module="sam2", install_group=InstallGroup.MODELS, heavy=True, gpu_helpful=True, default_enabled=False, fallback_ids=("rembg",), warning="Pin the exact SAM 2 release and checkpoint before enabling."),
    FreeToolSpec("mediapipe", "MediaPipe", ("build_visuals", "qa"), ("face", "hand", "pose tracking", "auto-reframe guidance"), python_module="mediapipe", install_group=InstallGroup.VISION, fallback_ids=("opencv",)),
    FreeToolSpec("opencv", "OpenCV", ("build_visuals", "qa"), ("frame analysis", "tracking fallback", "safe-area and blur checks"), python_module="cv2", install_group=InstallGroup.VISION),
    FreeToolSpec("rembg", "rembg", ("build_visuals",), ("local background removal fallback",), executable="rembg", python_module="rembg", install_group=InstallGroup.VISION),
    FreeToolSpec("demucs", "Demucs", ("narrate", "edit"), ("stem separation", "vocal removal", "music cleanup"), executable="demucs", python_module="demucs", install_group=InstallGroup.AUDIO, heavy=True, gpu_helpful=True, fallback_ids=("ffmpeg",)),
    FreeToolSpec("rubberband", "Rubber Band", ("narrate", "edit"), ("high-quality time stretching", "pitch correction"), executable="rubberband", install_group=InstallGroup.AUDIO, fallback_ids=("ffmpeg-atempo",)),
    FreeToolSpec("audacity", "Audacity macros", ("narrate", "edit"), ("repeatable cleanup macros", "manual-compatible audio processing"), executable="audacity", install_group=InstallGroup.AUDIO, default_enabled=False, fallback_ids=("ffmpeg",), warning="CLI and macro behavior varies by installed build."),
    FreeToolSpec("gdelt", "GDELT", ("discover", "verify"), ("news-event discovery", "global story monitoring"), network_at_runtime=True, default_enabled=True, fallback_ids=("rss",)),
    FreeToolSpec("common-crawl", "Common Crawl", ("discover", "verify"), ("historical web discovery", "page-index lookup"), network_at_runtime=True, fallback_ids=("internet-archive",)),
    FreeToolSpec("wikidata", "Wikidata", ("discover", "verify"), ("structured entity facts", "relationships", "dates"), network_at_runtime=True, fallback_ids=("wikipedia",)),
    FreeToolSpec("wikipedia", "Wikipedia", ("discover", "verify"), ("topic orientation", "source discovery"), network_at_runtime=True),
    FreeToolSpec("owid", "Our World in Data", ("verify",), ("public datasets", "chart-ready series"), network_at_runtime=True),
    FreeToolSpec("fred", "FRED", ("verify",), ("economic series", "rates", "inflation", "employment"), network_at_runtime=True),
    FreeToolSpec("census", "US Census Data API", ("verify",), ("population", "income", "housing", "demographic data"), network_at_runtime=True),
    FreeToolSpec("noaa", "NOAA", ("verify",), ("weather", "climate", "storm", "historical conditions"), network_at_runtime=True),
)

TOOL_BY_ID: Mapping[str, FreeToolSpec] = {tool.tool_id: tool for tool in TOOLS}


@dataclass(frozen=True)
class ToolProbe:
    tool_id: str
    available: bool
    probe: str
    heavy: bool
    default_enabled: bool
    warning: str = ""


class ToolchainDoctor:
    def probe(self, tool_ids: Iterable[str] | None = None) -> tuple[ToolProbe, ...]:
        selected = tuple(tool_ids or TOOL_BY_ID.keys())
        results: list[ToolProbe] = []
        for tool_id in selected:
            spec = TOOL_BY_ID[tool_id]
            executable_ok = bool(spec.executable and shutil.which(spec.executable))
            module_ok = bool(spec.python_module and importlib.util.find_spec(spec.python_module))
            if spec.tool_id == "svg-motion":
                available, probe = True, "python-stdlib"
            elif spec.executable and spec.python_module:
                available = executable_ok or module_ok
                probe = f"executable={executable_ok},module={module_ok}"
            elif spec.executable:
                available, probe = executable_ok, f"executable={executable_ok}"
            elif spec.python_module:
                available, probe = module_ok, f"module={module_ok}"
            else:
                available, probe = spec.network_at_runtime, "remote-adapter"
            results.append(ToolProbe(tool_id, available, probe, spec.heavy, spec.default_enabled, spec.warning))
        return tuple(results)

    def as_dicts(self, tool_ids: Iterable[str] | None = None) -> tuple[dict[str, object], ...]:
        return tuple(asdict(item) for item in self.probe(tool_ids))


def required_secret_names() -> tuple[str, ...]:
    """The local toolchain has no mandatory secret."""
    return ()


def optional_secret_names() -> tuple[str, ...]:
    return (
        "GEMINI_API_KEY",
        "YOUTUBE_API_KEY",
        "PEXELS_API_KEY",
        "FRED_API_KEY",
        "NOAA_TOKEN",
        "CENSUS_API_KEY",
    )
