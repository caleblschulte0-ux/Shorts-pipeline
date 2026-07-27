from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .contracts import CommandPlan


def _required(value: str, name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{name} cannot be empty")
    return value


@dataclass(frozen=True)
class DownloadPolicy:
    allow_video: bool = False
    allow_audio: bool = False
    allow_subtitles: bool = True
    allow_thumbnail: bool = True
    require_rights_record: bool = True
    max_height: int = 1080


class YtDlpPlanner:
    """Creates rights-aware yt-dlp command plans without executing them."""

    def metadata(self, url: str, output_json: str) -> CommandPlan:
        return CommandPlan(
            tool="yt-dlp",
            argv=("yt-dlp", "--skip-download", "--dump-single-json", _required(url, "url")),
            outputs=(_required(output_json, "output_json"),),
            notes=("Caller must redirect stdout to the declared JSON output.", "Metadata collection does not grant reuse rights."),
        )

    def subtitles_and_thumbnail(self, url: str, output_template: str, languages: Sequence[str] = ("en",)) -> CommandPlan:
        language_arg = ",".join(language.strip() for language in languages if language.strip()) or "en"
        return CommandPlan(
            tool="yt-dlp",
            argv=(
                "yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", language_arg,
                "--sub-format", "vtt", "--write-thumbnail", "--convert-thumbnails", "png", "-o", output_template,
                _required(url, "url"),
            ),
            outputs=(output_template,),
            notes=("Use only for owned, licensed, public-domain, or otherwise authorized material.",),
        )

    def authorized_clip(self, url: str, output_template: str, *, start: float, end: float, max_height: int = 1080) -> CommandPlan:
        if start < 0 or end <= start:
            raise ValueError("clip range must satisfy 0 <= start < end")
        return CommandPlan(
            tool="yt-dlp",
            argv=(
                "yt-dlp", "--download-sections", f"*{start:.3f}-{end:.3f}",
                "-f", f"bv*[height<={max_height}]+ba/b[height<={max_height}]", "--merge-output-format", "mp4",
                "-o", output_template, _required(url, "url"),
            ),
            outputs=(output_template,),
            notes=("Execution must be blocked unless a rights record explicitly authorizes downloading and reuse.",),
        )


class SceneExtractionPlanner:
    def detect(self, video: str, output_csv: str, *, threshold: float = 27.0) -> CommandPlan:
        if not 1.0 <= threshold <= 100.0:
            raise ValueError("threshold must be between 1 and 100")
        return CommandPlan(
            tool="scenedetect",
            argv=("scenedetect", "-i", video, "detect-content", "-t", f"{threshold:g}", "list-scenes", "-o", str(Path(output_csv).parent)),
            inputs=(video,),
            outputs=(output_csv,),
            notes=("The exact CSV filename produced by PySceneDetect should be normalized by the adopting wrapper.",),
        )

    def split(self, video: str, output_dir: str, *, threshold: float = 27.0) -> CommandPlan:
        return CommandPlan(
            tool="scenedetect",
            argv=("scenedetect", "-i", video, "detect-content", "-t", f"{threshold:g}", "split-video", "-o", output_dir),
            inputs=(video,),
            outputs=(output_dir,),
        )


class EvidenceIngestPlanner:
    def ocr_pdf(self, source_pdf: str, output_pdf: str, *, language: str = "eng") -> CommandPlan:
        return CommandPlan(
            tool="ocrmypdf",
            argv=("ocrmypdf", "--skip-text", "--deskew", "--clean", "-l", language, source_pdf, output_pdf),
            inputs=(source_pdf,),
            outputs=(output_pdf,),
            notes=("OCR output must retain the original source PDF hash and page mapping.",),
        )

    def extract_pdf_pages(self, source_pdf: str, output_pattern: str, *, dpi: int = 180) -> CommandPlan:
        return CommandPlan(
            tool="pdftoppm",
            argv=("pdftoppm", "-png", "-r", str(dpi), source_pdf, output_pattern),
            inputs=(source_pdf,),
            outputs=(output_pattern,),
        )
