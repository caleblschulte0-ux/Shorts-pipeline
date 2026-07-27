from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .contracts import CommandPlan


class FreeAudioPlanner:
    def separate_stems(self, input_audio: str, output_dir: str, *, model: str = "htdemucs") -> CommandPlan:
        return CommandPlan(
            tool="demucs",
            argv=("demucs", "-n", model, "--out", output_dir, input_audio),
            inputs=(input_audio,), outputs=(output_dir,),
            notes=("Use only on audio the project is permitted to process.",),
        )

    def time_stretch(self, input_audio: str, output_audio: str, *, tempo: float = 1.0, pitch_semitones: float = 0.0) -> CommandPlan:
        if not 0.5 <= tempo <= 2.0:
            raise ValueError("tempo must be between 0.5 and 2.0")
        return CommandPlan(
            tool="rubberband",
            argv=("rubberband", "--tempo", f"{tempo:g}", "--pitch", f"{pitch_semitones:g}", input_audio, output_audio),
            inputs=(input_audio,), outputs=(output_audio,),
        )

    def audacity_macro(self, input_audio: str, output_audio: str, *, macro_name: str = "ShortsCleanup") -> CommandPlan:
        return CommandPlan(
            tool="audacity",
            argv=("audacity", "--batch", f"Import2:Filename={input_audio}", f"Macro_{macro_name}", f"Export2:Filename={output_audio}"),
            inputs=(input_audio,), outputs=(output_audio,),
            notes=("Audacity command-line and macro support varies by platform; validate the installed build before adoption.",),
        )

    def ffmpeg_master(self, input_audio: str, output_audio: str, *, target_lufs: float = -14.0) -> CommandPlan:
        return CommandPlan(
            tool="ffmpeg",
            argv=("ffmpeg", "-y", "-i", input_audio, "-af", f"highpass=f=70,lowpass=f=16000,acompressor=threshold=-18dB:ratio=3,loudnorm=I={target_lufs}:TP=-1.5:LRA=11", output_audio),
            inputs=(input_audio,), outputs=(output_audio,),
        )


@dataclass(frozen=True)
class AudioStage:
    name: str
    plan: CommandPlan
    required: bool


class AudioChainPlanner:
    def build(self, narration: str, music: str, output: str, *, separate_music: bool = False) -> tuple[AudioStage, ...]:
        planner = FreeAudioPlanner()
        stages: list[AudioStage] = []
        music_source = music
        if separate_music:
            stages.append(AudioStage("separate_music_stems", planner.separate_stems(music, "stems"), False))
            music_source = "stems/htdemucs/track/no_vocals.wav"
        mixed = "audio_mix.wav"
        stages.append(AudioStage("mix", CommandPlan("ffmpeg", ("ffmpeg", "-y", "-i", narration, "-stream_loop", "-1", "-i", music_source, "-filter_complex", "[1:a]volume=0.10[bed];[0:a][bed]amix=inputs=2:duration=first:dropout_transition=2", mixed), inputs=(narration, music_source), outputs=(mixed,)), True))
        stages.append(AudioStage("master", planner.ffmpeg_master(mixed, output), True))
        return tuple(stages)
