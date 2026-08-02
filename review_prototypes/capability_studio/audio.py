from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Mapping, Sequence

from .contracts import CommandPlan, RequestPlan
from .providers import CartesiaAdapter, ElevenLabsAdapter, PlayHTAdapter, faster_whisper_plan


@dataclass(frozen=True)
class DirectedLine:
    text: str
    emotion: str = "neutral"
    pace: str = "normal"
    emphasis: tuple[str, ...] = ()
    pause_after_ms: int = 0


@dataclass(frozen=True)
class VoiceDirection:
    voice_id: str
    provider: str
    lines: tuple[DirectedLine, ...]
    pronunciation_overrides: Mapping[str, str] = field(default_factory=dict)

    def rendered_text(self) -> str:
        pieces: list[str] = []
        for line in self.lines:
            text = line.text
            for source, replacement in self.pronunciation_overrides.items():
                text = re.sub(rf"\b{re.escape(source)}\b", replacement, text, flags=re.IGNORECASE)
            direction = f"[{line.emotion}; pace={line.pace}] " if line.emotion != "neutral" or line.pace != "normal" else ""
            for word in line.emphasis:
                text = re.sub(rf"\b({re.escape(word)})\b", r"*\1*", text, flags=re.IGNORECASE)
            pieces.append(direction + text)
            if line.pause_after_ms:
                pieces.append(f"<break time=\"{line.pause_after_ms}ms\"/>")
        return " ".join(pieces)


class PronunciationLexicon:
    def __init__(self, initial: Mapping[str, str] | None = None) -> None:
        self._entries = dict(initial or {})

    def add(self, written: str, spoken: str) -> None:
        if not written.strip() or not spoken.strip():
            raise ValueError("pronunciation entries cannot be empty")
        self._entries[written] = spoken

    def apply(self, text: str) -> str:
        result = text
        for written, spoken in sorted(self._entries.items(), key=lambda item: len(item[0]), reverse=True):
            result = re.sub(rf"\b{re.escape(written)}\b", spoken, result, flags=re.IGNORECASE)
        return result


class TTSRouter:
    def __init__(self) -> None:
        self.elevenlabs = ElevenLabsAdapter()
        self.cartesia = CartesiaAdapter()
        self.playht = PlayHTAdapter()

    def plan(self, direction: VoiceDirection) -> RequestPlan | CommandPlan:
        text = direction.rendered_text()
        provider = direction.provider.lower()
        if provider == "elevenlabs":
            return self.elevenlabs.text_to_speech(voice_id=direction.voice_id, text=text)
        if provider == "cartesia":
            return self.cartesia.text_to_speech(voice_id=direction.voice_id, text=text)
        if provider == "playht":
            return self.playht.text_to_speech(voice=direction.voice_id, text=text)
        if provider == "kokoro":
            return CommandPlan(tool="kokoro", argv=("python", "-m", "kokoro", "--voice", direction.voice_id, "--text", text, "--output", "narration.wav"), outputs=("narration.wav",), notes=("Local fallback; exact CLI should be adapted to the installed Kokoro wrapper.",))
        raise KeyError(f"unsupported TTS provider: {direction.provider}")

    def fallback_order(self, configured_providers: Sequence[str]) -> tuple[str, ...]:
        preference = ("elevenlabs", "cartesia", "playht", "kokoro")
        configured = {provider.lower() for provider in configured_providers}
        return tuple(provider for provider in preference if provider in configured)


class SubtitlePlanner:
    def transcribe(self, input_audio: str, output_dir: str) -> CommandPlan:
        return faster_whisper_plan(input_audio, output_dir)

    def burn_ass(self, video: str, subtitle_file: str, output: str) -> CommandPlan:
        return CommandPlan(tool="ffmpeg", argv=("ffmpeg", "-y", "-i", video, "-vf", f"ass={subtitle_file}", "-c:a", "copy", output), inputs=(video, subtitle_file), outputs=(output,))


@dataclass(frozen=True)
class SoundCue:
    at_second: float
    kind: str
    description: str
    gain_db: float = -8.0
    duration_seconds: float = 1.0


class SoundDesignPlanner:
    def generate_sfx(self, cue: SoundCue) -> RequestPlan:
        return ElevenLabsAdapter().sound_effect(prompt=cue.description, duration_seconds=cue.duration_seconds)

    def mix_plan(self, narration: str, music: str, sfx_files: Sequence[tuple[SoundCue, str]], output: str) -> CommandPlan:
        inputs = ["-i", narration, "-i", music]
        filter_parts = ["[1:a]volume=0.12[bed]", "[0:a][bed]amix=inputs=2:duration=first:dropout_transition=2[base]"]
        last = "base"
        for index, (cue, path) in enumerate(sfx_files, start=2):
            inputs.extend(("-i", path))
            delay = max(0, int(cue.at_second * 1000))
            gain = 10 ** (cue.gain_db / 20)
            filter_parts.append(f"[{index}:a]adelay={delay}|{delay},volume={gain:.4f}[sfx{index}]")
            filter_parts.append(f"[{last}][sfx{index}]amix=inputs=2:duration=longest[mix{index}]")
            last = f"mix{index}"
        argv = ("ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filter_parts), "-map", f"[{last}]", output)
        return CommandPlan("ffmpeg", tuple(argv), inputs=(narration, music, *(path for _, path in sfx_files)), outputs=(output,))
