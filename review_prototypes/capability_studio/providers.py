from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.parse import quote_plus

from .contracts import CommandPlan, RequestPlan


class Transport(Protocol):
    def execute(self, request: RequestPlan) -> Mapping[str, Any]: ...


class NetworkDisabledError(RuntimeError):
    pass


class DisabledTransport:
    def execute(self, request: RequestPlan) -> Mapping[str, Any]:
        raise NetworkDisabledError(f"network execution is disabled in the review prototype: {request.request_id}")


@dataclass(frozen=True)
class ProviderAdapter:
    provider_id: str


class PexelsAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("pexels")

    def search_video(self, query: str, *, per_page: int = 15, orientation: str = "portrait") -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="GET", url="https://api.pexels.com/videos/search", headers={"Authorization": "${PEXELS_API_KEY}"}, query={"query": query, "per_page": str(per_page), "orientation": orientation}, secret_names=("PEXELS_API_KEY",))


class OpenverseAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("openverse")

    def search_images(self, query: str, *, page_size: int = 20) -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="GET", url="https://api.openverse.org/v1/images/", query={"q": query, "page_size": str(page_size), "mature": "false"})


class WikimediaAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("wikimedia")

    def search_files(self, query: str, *, limit: int = 20) -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="GET", url="https://commons.wikimedia.org/w/api.php", query={"action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": str(limit), "prop": "imageinfo", "iiprop": "url|extmetadata|size", "format": "json"})


class InternetArchiveAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("internet_archive")

    def search(self, query: str, *, rows: int = 20) -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="GET", url="https://archive.org/advancedsearch.php", query={"q": quote_plus(query), "fl[]": "identifier,title,description,mediatype,licenseurl", "rows": str(rows), "page": "1", "output": "json"})


class YouTubeAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("youtube")

    def search_videos(self, query: str, *, max_results: int = 25, published_after: str = "") -> RequestPlan:
        params = {"part": "snippet", "type": "video", "q": query, "maxResults": str(max_results), "order": "viewCount", "key": "${YOUTUBE_API_KEY}"}
        if published_after:
            params["publishedAfter"] = published_after
        return RequestPlan(provider=self.provider_id, method="GET", url="https://www.googleapis.com/youtube/v3/search", query=params, secret_names=("YOUTUBE_API_KEY",))

    def video_details(self, video_ids: tuple[str, ...]) -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="GET", url="https://www.googleapis.com/youtube/v3/videos", query={"part": "snippet,statistics,contentDetails", "id": ",".join(video_ids), "key": "${YOUTUBE_API_KEY}"}, secret_names=("YOUTUBE_API_KEY",))

    def comment_threads(self, video_id: str, *, max_results: int = 100) -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="GET", url="https://www.googleapis.com/youtube/v3/commentThreads", query={"part": "snippet,replies", "videoId": video_id, "maxResults": str(max_results), "textFormat": "plainText", "order": "relevance", "key": "${YOUTUBE_API_KEY}"}, secret_names=("YOUTUBE_API_KEY",))


class ElevenLabsAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("elevenlabs")

    def text_to_speech(self, *, voice_id: str, text: str, model_id: str = "eleven_multilingual_v2", settings: Mapping[str, float] | None = None) -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="POST", url=f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", headers={"xi-api-key": "${ELEVENLABS_API_KEY}", "Content-Type": "application/json"}, json_body={"text": text, "model_id": model_id, "voice_settings": dict(settings or {"stability": 0.45, "similarity_boost": 0.78, "style": 0.35})}, output_kind="audio", secret_names=("ELEVENLABS_API_KEY",))

    def sound_effect(self, *, prompt: str, duration_seconds: float = 2.0) -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="POST", url="https://api.elevenlabs.io/v1/sound-generation", headers={"xi-api-key": "${ELEVENLABS_API_KEY}", "Content-Type": "application/json"}, json_body={"text": prompt, "duration_seconds": duration_seconds, "prompt_influence": 0.5}, output_kind="audio", secret_names=("ELEVENLABS_API_KEY",))


class CartesiaAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("cartesia")

    def text_to_speech(self, *, voice_id: str, text: str, model_id: str = "sonic-3") -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="POST", url="https://api.cartesia.ai/tts/bytes", headers={"X-API-Key": "${CARTESIA_API_KEY}", "Cartesia-Version": "2025-04-16", "Content-Type": "application/json"}, json_body={"model_id": model_id, "transcript": text, "voice": {"mode": "id", "id": voice_id}, "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100}}, output_kind="audio", secret_names=("CARTESIA_API_KEY",))


class PlayHTAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("playht")

    def text_to_speech(self, *, voice: str, text: str) -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="POST", url="https://api.play.ht/api/v2/tts/stream", headers={"AUTHORIZATION": "${PLAYHT_API_KEY}", "X-USER-ID": "${PLAYHT_USER_ID}", "Content-Type": "application/json"}, json_body={"text": text, "voice": voice, "output_format": "wav", "voice_engine": "PlayDialog"}, output_kind="audio", secret_names=("PLAYHT_API_KEY", "PLAYHT_USER_ID"))


class RunwayAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("runway")

    def text_to_video(self, *, prompt: str, duration: int = 5, ratio: str = "720:1280", model: str = "gen4.5") -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="POST", url="https://api.dev.runwayml.com/v1/text_to_video", headers={"Authorization": "Bearer ${RUNWAYML_API_SECRET}", "X-Runway-Version": "2024-11-06", "Content-Type": "application/json"}, json_body={"model": model, "promptText": prompt, "ratio": ratio, "duration": duration}, secret_names=("RUNWAYML_API_SECRET",), notes=("Expensive provider: use only for selected hero shots.",))

    def image_to_video(self, *, image_url: str, prompt: str, duration: int = 5, ratio: str = "720:1280", model: str = "gen4_turbo") -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="POST", url="https://api.dev.runwayml.com/v1/image_to_video", headers={"Authorization": "Bearer ${RUNWAYML_API_SECRET}", "X-Runway-Version": "2024-11-06", "Content-Type": "application/json"}, json_body={"model": model, "promptImage": image_url, "promptText": prompt, "ratio": ratio, "duration": duration}, secret_names=("RUNWAYML_API_SECRET",))


class CreatomateAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("creatomate")

    def render(self, *, template_id: str, modifications: Mapping[str, Any]) -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="POST", url="https://api.creatomate.com/v2/renders", headers={"Authorization": "Bearer ${CREATOMATE_API_KEY}", "Content-Type": "application/json"}, json_body={"template_id": template_id, "modifications": dict(modifications)}, secret_names=("CREATOMATE_API_KEY",))


class SyncAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("sync")

    def lipsync(self, *, video_url: str, audio_url: str, model: str = "lipsync-2") -> RequestPlan:
        return RequestPlan(provider=self.provider_id, method="POST", url="https://api.sync.so/v2/generate", headers={"x-api-key": "${SYNC_API_KEY}", "Content-Type": "application/json"}, json_body={"model": model, "input": [{"type": "video", "url": video_url}, {"type": "audio", "url": audio_url}]}, secret_names=("SYNC_API_KEY",))


def faster_whisper_plan(input_audio: str, output_dir: str, *, model: str = "large-v3", language: str = "en") -> CommandPlan:
    return CommandPlan(tool="faster-whisper", argv=("faster-whisper", input_audio, "--model", model, "--language", language, "--word_timestamps", "True", "--output_dir", output_dir), inputs=(input_audio,), outputs=(output_dir,))
