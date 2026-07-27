from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .contracts import CommandPlan, RequestPlan
from .providers import CreatomateAdapter, RunwayAdapter, SyncAdapter


@dataclass(frozen=True)
class Clip:
    path: str
    start: float
    duration: float
    role: str
    crop: str = "fill"
    speed: float = 1.0


@dataclass(frozen=True)
class EditAction:
    at_second: float
    kind: str
    value: str
    duration: float = 0.0


@dataclass(frozen=True)
class Timeline:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    clips: tuple[Clip, ...] = ()
    actions: tuple[EditAction, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


class TimelineEditor:
    def ffmpeg_concat_plan(self, timeline: Timeline, output: str) -> CommandPlan:
        if not timeline.clips:
            raise ValueError("timeline has no clips")
        argv: list[str] = ["ffmpeg", "-y"]
        for clip in timeline.clips:
            argv.extend(("-ss", f"{clip.start:.3f}", "-t", f"{clip.duration:.3f}", "-i", clip.path))
        filters: list[str] = []
        concat_inputs: list[str] = []
        for index, clip in enumerate(timeline.clips):
            filters.append(f"[{index}:v]setpts=PTS/{max(clip.speed, 0.01):.5f},scale={timeline.width}:{timeline.height}:force_original_aspect_ratio=increase,crop={timeline.width}:{timeline.height},fps={timeline.fps},format=yuv420p[v{index}]")
            concat_inputs.append(f"[v{index}]")
        filters.append("".join(concat_inputs) + f"concat=n={len(timeline.clips)}:v=1:a=0[outv]")
        argv.extend(("-filter_complex", ";".join(filters), "-map", "[outv]", "-r", str(timeline.fps), "-c:v", "libx264", "-crf", "18", output))
        return CommandPlan("ffmpeg", tuple(argv), inputs=tuple(clip.path for clip in timeline.clips), outputs=(output,))

    def auto_editor_plan(self, input_video: str, output: str, *, margin: str = "0.08sec", silent_speed: str = "99999") -> CommandPlan:
        return CommandPlan("auto-editor", ("auto-editor", input_video, "--margin", margin, "--silent-speed", silent_speed, "--output-file", output), inputs=(input_video,), outputs=(output,))

    def remotion_plan(self, composition: str, props_json: str, output: str) -> CommandPlan:
        return CommandPlan("remotion", ("npx", "remotion", "render", composition, output, "--props", props_json), inputs=(props_json,), outputs=(output,))

    def creatomate_plan(self, template_id: str, modifications: Mapping[str, Any]) -> RequestPlan:
        return CreatomateAdapter().render(template_id=template_id, modifications=modifications)


class VisualEnhancer:
    def upscale(self, input_path: str, output_path: str, *, scale: int = 2, model: str = "realesrgan-x4plus") -> CommandPlan:
        return CommandPlan("realesrgan-ncnn-vulkan", ("realesrgan-ncnn-vulkan", "-i", input_path, "-o", output_path, "-s", str(scale), "-n", model), inputs=(input_path,), outputs=(output_path,))

    def interpolate(self, input_path: str, output_path: str, *, target_fps: int = 60) -> CommandPlan:
        return CommandPlan("rife-ncnn-vulkan", ("rife-ncnn-vulkan", "-i", input_path, "-o", output_path, "-f", str(target_fps)), inputs=(input_path,), outputs=(output_path,))

    def remove_background(self, input_path: str, output_path: str) -> CommandPlan:
        return CommandPlan("rembg", ("rembg", "i", input_path, output_path), inputs=(input_path,), outputs=(output_path,))

    def color_grade(self, input_path: str, output_path: str, *, contrast: float = 1.05, saturation: float = 1.08, gamma: float = 1.0) -> CommandPlan:
        vf = f"eq=contrast={contrast}:saturation={saturation}:gamma={gamma}"
        return CommandPlan("ffmpeg", ("ffmpeg", "-y", "-i", input_path, "-vf", vf, "-c:v", "libx264", "-crf", "18", "-c:a", "copy", output_path), inputs=(input_path,), outputs=(output_path,))

    def normalize_audio(self, input_path: str, output_path: str, *, target_lufs: float = -14.0) -> CommandPlan:
        return CommandPlan("ffmpeg", ("ffmpeg", "-y", "-i", input_path, "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11", "-c:v", "copy", output_path), inputs=(input_path,), outputs=(output_path,))


@dataclass(frozen=True)
class ReferencePack:
    subject_images: tuple[str, ...] = ()
    palette_hex: tuple[str, ...] = ()
    style_prompt: str = ""
    forbidden_changes: tuple[str, ...] = ()

    def prompt_suffix(self) -> str:
        constraints = "; ".join(self.forbidden_changes)
        palette = ", ".join(self.palette_hex)
        return f"Maintain the same subject identity and design. Style: {self.style_prompt}. Palette: {palette}. Never change: {constraints}."


class GenerativeVideoPlanner:
    def text_to_video(self, prompt: str, *, duration: int = 5) -> RequestPlan:
        return RunwayAdapter().text_to_video(prompt=prompt, duration=duration)

    def image_to_video(self, image_url: str, prompt: str, reference: ReferencePack | None = None, *, duration: int = 5) -> RequestPlan:
        full_prompt = prompt if reference is None else f"{prompt} {reference.prompt_suffix()}"
        return RunwayAdapter().image_to_video(image_url=image_url, prompt=full_prompt, duration=duration)

    def hero_shot_budget(self, estimated_video_value: float, *, cost_per_shot: float, max_shots: int = 2) -> int:
        if cost_per_shot <= 0:
            return max_shots
        affordable = int(max(0.0, estimated_video_value * 0.08) // cost_per_shot)
        return max(0, min(max_shots, affordable))


class LipSyncPlanner:
    def plan(self, video_url: str, audio_url: str) -> RequestPlan:
        return SyncAdapter().lipsync(video_url=video_url, audio_url=audio_url)
