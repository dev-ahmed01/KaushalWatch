from __future__ import annotations

import logging
import os
from time import perf_counter

from openai import AsyncOpenAI


logger = logging.getLogger(__name__)


class VoiceService:
    def __init__(self, *, client=None, timeout_seconds: float = 60.0):
        self.timeout_seconds = timeout_seconds
        self.client = client or AsyncOpenAI(
            timeout=timeout_seconds,
            max_retries=0,
        )
        self.transcription_model = os.getenv("KAUSHAL_STT_MODEL", "gpt-transcribe")
        self.speech_model = os.getenv("KAUSHAL_TTS_MODEL", "gpt-4o-mini-tts")
        self.voice = os.getenv("KAUSHAL_TTS_VOICE", "coral")

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
        response = await self.client.audio.speech.create(
            model=self.speech_model,
            voice=self.voice,
            input=text,
            instructions="Speak clearly, calmly, and concisely as an operational assistant.",
            response_format="mp3",
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
