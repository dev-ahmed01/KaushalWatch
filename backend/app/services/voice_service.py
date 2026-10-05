from __future__ import annotations

import logging
import os
from time import perf_counter

from openai import AsyncOpenAI


logger = logging.getLogger(__name__)
GROQ_OPENAI_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_STT_MODEL = "whisper-large-v3-turbo"
DEFAULT_TTS_MODEL = "canopylabs/orpheus-v1-english"
DEFAULT_TTS_VOICE = "hannah"
MAX_GROQ_TTS_CHARS = 200


def _spoken_excerpt(text: str, limit: int = MAX_GROQ_TTS_CHARS) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    if limit <= 3:
        return normalized[:limit]
    prefix = normalized[: limit - 3]
    if " " in prefix:
        prefix = prefix.rsplit(" ", 1)[0]
    return prefix.rstrip(" ,.;:-") + "..."


class VoiceService:
    def __init__(self, *, client=None, timeout_seconds: float = 60.0):
        self.timeout_seconds = timeout_seconds
        self.client = client or AsyncOpenAI(
            api_key=(os.getenv("GROQ_API_KEY") or "").strip() or None,
            base_url=os.getenv("KAUSHAL_GROQ_BASE_URL", GROQ_OPENAI_BASE_URL),
            timeout=timeout_seconds,
            max_retries=0,
        )
        self.transcription_model = os.getenv("KAUSHAL_STT_MODEL", DEFAULT_STT_MODEL)
        self.speech_model = os.getenv("KAUSHAL_TTS_MODEL", DEFAULT_TTS_MODEL)
        self.voice = os.getenv("KAUSHAL_TTS_VOICE", DEFAULT_TTS_VOICE)

    async def transcribe(self, *, filename: str, content_type: str, data: bytes) -> str:
        started = perf_counter()
        transcript = await self.client.audio.transcriptions.create(
            model=self.transcription_model,
            file=(filename, data, content_type),
        )
        text = str(getattr(transcript, "text", "") or "").strip()
        if not text:
            raise ValueError("Transcription returned no text")
        logger.info(
            "assistant transcription completed in %dms",
            round((perf_counter() - started) * 1000),
        )
        return text

    async def speech(self, text: str) -> bytes:
        started = perf_counter()
        spoken_text = _spoken_excerpt(text)
        if not spoken_text:
            raise ValueError("Speech input is empty")
        response = await self.client.audio.speech.create(
            model=self.speech_model,
            voice=self.voice,
            input=spoken_text,
            response_format="wav",
        )
        if hasattr(response, "aread"):
            data = await response.aread()
        elif hasattr(response, "read"):
            data = response.read()
        else:
            data = getattr(response, "content", b"")
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise ValueError("Speech generation returned no audio")
        logger.info(
            "assistant speech completed in %dms",
            round((perf_counter() - started) * 1000),
        )
        return bytes(data)
