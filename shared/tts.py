"""Text-to-speech stage (edge-tts).

Lifted verbatim from make_short.py. Voice is a parameter (default en-US-GuyNeural,
the main app's voice) so the localize module can pass an in-language voice.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from .constants import TTS_VOICE


async def _tts(text: str, out: Path, voice: str = TTS_VOICE) -> None:
    # Force edge_tts to use the system CA bundle so the egress proxy's
    # self-signed cert in the chain is trusted (certifi alone doesn't
    # include the egress gateway CA).
    import ssl
    import edge_tts.communicate as _ec
    _ec._SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
    import edge_tts
    await edge_tts.Communicate(text, voice).save(str(out))


def synthesize_voiceover(text: str, workdir: Path, voice: str = TTS_VOICE) -> Path:
    out = workdir / "voice.mp3"
    asyncio.run(_tts(text, out, voice))
    return out
