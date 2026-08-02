from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .contracts import CommandPlan
from .free_audio import FreeAudioPlanner
from .free_graphics import GraphicsCommandPlanner
from .free_media import EvidenceIngestPlanner, SceneExtractionPlanner, YtDlpPlanner
from .free_timeline import TimelineCommandPlanner
from .free_vision import VisionCommandPlanner
from .scene_router import FreeSceneRouter, RouteDecision, RunnerProfile, SceneIntent, SceneKind


@dataclass(frozen=True)
class SceneBuildRequest:
    intent: SceneIntent
    workspace: str
    source: str = ""
    secondary_source: str = ""
    data_file: str = ""
    scene_file: str = ""
    scene_name: str = "Scene"
    rights_record: str = ""
    output_name: str = "scene.mp4"


@dataclass(frozen=True)
class CompiledScenePlan:
    decision: RouteDecision
    plans: tuple[CommandPlan, ...]
    artifacts: Mapping[str, str]
    adoption_slot: str = "scene_plan"
    production_wiring: bool = False


class ToolchainIntegrationCompiler:
    """Compiles a semantic scene route into inspectable local command plans."""

    def __init__(self) -> None:
        self.router = FreeSceneRouter()
        self.graphics = GraphicsCommandPlanner()
        self.media = SceneExtractionPlanner()
        self.evidence = EvidenceIngestPlanner()
        self.ytdlp = YtDlpPlanner()
        self.timeline = TimelineCommandPlanner()
        self.vision = VisionCommandPlanner()
        self.audio = FreeAudioPlanner()

    def compile(self, request: SceneBuildRequest, runner: RunnerProfile) -> CompiledScenePlan:
        root = Path(request.workspace)
        decision = self.router.route(request.intent, runner)
        if decision.blocked:
            return CompiledScenePlan(decision, (), {}, production_wiring=False)
        chain = decision.primary_chain
        out = str(root / request.output_name)
        plans: list[CommandPlan] = []
        artifacts: dict[str, str] = {"scene_output": out}

        kind = request.intent.kind
        if kind == SceneKind.AUTHORIZED_WEB_CLIP:
            if not request.rights_record:
                blocked = RouteDecision(request.intent.scene_id, (), decision.fallback_chains, True, "rights_record_path_required")
                return CompiledScenePlan(blocked, (), {})
            raw = str(root / "authorized_source.%(ext)s")
            plans.append(self.ytdlp.authorized_clip(request.source, raw, start=0, end=request.intent.duration_seconds))
            plans.append(self.media.detect(str(root / "authorized_source.mp4"), str(root / "scenes.csv")))
            plans.append(CommandPlan("ffmpeg", ("ffmpeg", "-y", "-i", str(root / "authorized_source.mp4"), "-t", f"{request.intent.duration_seconds:g}", "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", "-r", "30", "-pix_fmt", "yuv420p", out), inputs=(str(root / "authorized_source.mp4"), request.rights_record), outputs=(out,)))
        elif kind == SceneKind.OFFICE_DOCUMENT:
            pdf_dir = str(root / "office_pdf")
            plans.append(self.graphics.libreoffice_to_pdf(request.source, pdf_dir))
            pdf = str(Path(pdf_dir) / (Path(request.source).stem + ".pdf"))
            plans.append(self.evidence.extract_pdf_pages(pdf, str(root / "page")))
            plans.append(CommandPlan("ffmpeg", ("ffmpeg", "-y", "-framerate", "1", "-i", str(root / "page-%d.png"), "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2", "-r", "30", "-pix_fmt", "yuv420p", out), inputs=(pdf,), outputs=(out,)))
        elif kind in {SceneKind.SIMPLE_CHART, SceneKind.COMPARISON_CARD}:
            frame_pattern = str(root / "svg_frames" / "frame_%04d.png")
            artifacts["svg_source"] = str(root / "scene.svg")
            artifacts["frame_pattern"] = frame_pattern
            plans.append(self.graphics.svg_frames_to_video(frame_pattern, out))
        elif kind == SceneKind.EQUATION:
            media_dir = str(root / "manim_media")
            plans.append(self.graphics.manim(request.scene_file, request.scene_name, media_dir))
            artifacts["manim_media"] = media_dir
        elif kind in {SceneKind.PROCESS_DIAGRAM, SceneKind.NETWORK_DIAGRAM}:
            diagram = str(root / "diagram.png")
            if chain[0] == "mermaid":
                plans.append(self.graphics.mermaid(request.source, diagram))
            else:
                plans.append(self.graphics.graphviz(request.source, diagram))
            plans.append(CommandPlan("ffmpeg", ("ffmpeg", "-y", "-loop", "1", "-i", diagram, "-t", f"{request.intent.duration_seconds:g}", "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,zoompan=z='min(zoom+0.0008,1.08)':d=1:s=1080x1920:fps=30", "-pix_fmt", "yuv420p", out), inputs=(diagram,), outputs=(out,)))
        elif kind == SceneKind.THREE_D:
            frames = str(root / "blender_frames" / "frame_####")
            plans.append(self.graphics.blender(request.source, frames, end_frame=max(1, round(request.intent.duration_seconds * 30))))
            plans.append(CommandPlan("ffmpeg", ("ffmpeg", "-y", "-framerate", "30", "-i", str(root / "blender_frames" / "frame_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", out), inputs=(str(root / "blender_frames"),), outputs=(out,)))
        elif kind == SceneKind.PHOTO_COMPOSITE:
            card = str(root / "composite.png")
            plans.append(self.graphics.imagemagick_card(request.source, request.secondary_source, card))
            plans.append(CommandPlan("ffmpeg", ("ffmpeg", "-y", "-loop", "1", "-i", card, "-t", f"{request.intent.duration_seconds:g}", "-r", "30", "-pix_fmt", "yuv420p", out), inputs=(card,), outputs=(out,)))
        elif kind == SceneKind.SUBJECT_CUTOUT:
            mask = str(root / "mask.png")
            if chain[0] == "sam2":
                plans.append(self.vision.sam2_mask(request.source, str(root / "models" / "sam2.pt"), str(root / "models" / "sam2.yaml"), mask, prompt_json=request.data_file))
            else:
                plans.append(CommandPlan("rembg", ("rembg", "i", request.source, mask), inputs=(request.source,), outputs=(mask,)))
            artifacts["mask"] = mask
        elif kind == SceneKind.PRESENTER_TRACKING:
            tracking = str(root / "tracking.json")
            plans.append(self.vision.mediapipe_track(request.source, tracking, mode="pose"))
            artifacts["tracking"] = tracking
        elif kind == SceneKind.AUDIO_CLEANUP:
            cleaned = str(root / "cleaned.wav")
            if chain[0] == "demucs":
                plans.append(self.audio.separate_stems(request.source, str(root / "stems")))
            plans.append(self.audio.ffmpeg_master(request.source, cleaned))
            artifacts["clean_audio"] = cleaned
        elif kind == SceneKind.SHOT_EXTRACTION:
            plans.append(self.media.split(request.source, str(root / "shots")))
            artifacts["shots"] = str(root / "shots")
        elif kind == SceneKind.FINAL_ASSEMBLY:
            plans.append(self.timeline.validate_otio(request.source))
            plans.append(self.timeline.ffmpeg_concat(request.secondary_source, out))
        else:
            plans.append(CommandPlan("ffmpeg", ("ffmpeg", "-y", "-i", request.source, "-t", f"{request.intent.duration_seconds:g}", "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920", "-r", "30", "-pix_fmt", "yuv420p", out), inputs=(request.source,), outputs=(out,)))

        return CompiledScenePlan(decision, tuple(plans), artifacts, production_wiring=False)
