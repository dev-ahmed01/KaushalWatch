import asyncio
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.main as app_main
from app.models import AssistantChatResponse, AssistantSourcePayload, AssistantToolCallPayload
from app.services.assistant_service import AssistantUnavailableError
from app.services.voice_service import VoiceService


class FakeAssistantService:
    def __init__(self, error: Exception | None = None):
        self.calls = []
        self.error = error

    async def chat(self, *, message, session_id, centre_id):
        self.calls.append(
            {"message": message, "session_id": session_id, "centre_id": centre_id}
        )
        if self.error:
            raise self.error
        return AssistantChatResponse(
            message="The system recorded one analysis.",
            session_id=session_id or "generated-session",
            sources=[
                AssistantSourcePayload(
                    kind="analysis",
                    id="AN-1",
                    label="Attendance analysis",
                    href=f"/centres/{centre_id}/history",
                )
            ],
            tool_calls=[
                AssistantToolCallPayload(
                    name="get_operational_history", status="success", duration_ms=3
                )
            ],
        )


class SlowAssistantService:
    async def chat(self, **kwargs):
        await asyncio.sleep(0.05)
        raise AssertionError("timeout did not fire")


class FakeVoiceService:
    def __init__(self, error: Exception | None = None):
        self.transcription_calls = []
        self.speech_calls = []
        self.error = error

    async def transcribe(self, *, filename, content_type, data):
        self.transcription_calls.append((filename, content_type, data))
        if self.error:
            raise self.error
        return "What happened today?"

    async def speech(self, text):
        self.speech_calls.append(text)
        if self.error:
            raise self.error
        return b"RIFF-fake-wav"


class SlowVoiceService:
    def __init__(self):
        self.transcription_cancelled = False
        self.speech_cancelled = False

    async def transcribe(self, **_kwargs):
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.transcription_cancelled = True
            raise

    async def speech(self, _text):
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.speech_cancelled = True
            raise


def _client(monkeypatch, assistant=None, voice=None):
    monkeypatch.setattr(app_main, "ASSISTANT_SERVICE", assistant)
    monkeypatch.setattr(app_main, "VOICE_SERVICE", voice)
    return TestClient(app_main.app)


def test_chat_endpoint_returns_message_session_sources_and_tool_metadata(monkeypatch):
    service = FakeAssistantService()
    client = _client(monkeypatch, assistant=service)

    response = client.post(
        "/api/assistant/chat",
        json={
            "message": "What happened today?",
            "session_id": "existing-session",
            "centre_id": "DEMO-KA-104",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "The system recorded one analysis.",
        "session_id": "existing-session",
        "sources": [
            {
                "kind": "analysis",
                "id": "AN-1",
                "label": "Attendance analysis",
                "href": "/centres/DEMO-KA-104/history",
                "timestamp": None,
            }
        ],
        "tool_calls": [
            {"name": "get_operational_history", "status": "success", "duration_ms": 3}
        ],
    }
    assert service.calls[0]["message"] == "What happened today?"


def test_chat_endpoint_validates_centre_and_message(monkeypatch):
    client = _client(monkeypatch, assistant=FakeAssistantService())

    assert client.post(
        "/api/assistant/chat",
        json={"message": "Hello", "centre_id": "NOT-A-CENTRE"},
    ).status_code == 404
    empty = client.post(
        "/api/assistant/chat",
        json={"message": "   ", "centre_id": "DEMO-KA-104"},
    )
    assert empty.status_code == 422


def test_chat_endpoint_reports_missing_configuration_without_affecting_health(
    monkeypatch,
):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = _client(monkeypatch)

    response = client.post(
        "/api/assistant/chat",
        json={"message": "What happened?", "centre_id": "DEMO-KA-104"},
    )

    assert response.status_code == 503
    assert "requires AI configuration" in response.json()["detail"]
    assert client.get("/api/health").status_code == 200


def test_assistant_status_reports_enabled_and_configuration_state(monkeypatch):
    monkeypatch.setenv("KAUSHAL_AI_ENABLED", "true")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = _client(monkeypatch)

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert client.get("/api/assistant/status").json() == {
        "enabled": True,
        "configured": False,
        "available": False,
        "voice_configured": False,
        "voice_available": False,
    }

    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    assert client.get("/api/assistant/status").json()["configured"] is False

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert client.get("/api/assistant/status").json() == {
        "enabled": True,
        "configured": True,
        "available": True,
        "voice_configured": False,
        "voice_available": False,
    }

    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    assert client.get("/api/assistant/status").json() == {
        "enabled": True,
        "configured": True,
        "available": True,
        "voice_configured": True,
        "voice_available": True,
    }


def test_chat_endpoint_sanitizes_provider_failure(monkeypatch):
    client = _client(
        monkeypatch,
        assistant=FakeAssistantService(
            AssistantUnavailableError("provider leaked internal detail")
        ),
    )

    response = client.post(
        "/api/assistant/chat",
        json={"message": "What happened?", "centre_id": "DEMO-KA-104"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Kaushal Assistant is temporarily unavailable. "
        "Monitoring and analysis continue to work normally."
    )


def test_chat_endpoint_times_out_stalled_provider(monkeypatch):
    monkeypatch.setenv("KAUSHAL_AI_TIMEOUT_SECONDS", "0.001")
    client = _client(monkeypatch, assistant=SlowAssistantService())

    response = client.post(
        "/api/assistant/chat",
        json={"message": "What happened?", "centre_id": "DEMO-KA-104"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Kaushal Assistant is temporarily unavailable. "
        "Monitoring and analysis continue to work normally."
    )


def test_supported_audio_upload_returns_transcript(monkeypatch):
    voice = FakeVoiceService()
    client = _client(monkeypatch, voice=voice)

    response = client.post(
        "/api/assistant/transcribe",
        files={"audio": ("recording.webm", b"audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "What happened today?"}
    assert voice.transcription_calls == [
        ("recording.webm", "audio/webm", b"audio-bytes")
    ]


def test_audio_upload_rejects_empty_unsupported_and_mismatched_files(monkeypatch):
    voice = FakeVoiceService()
    client = _client(monkeypatch, voice=voice)

    empty = client.post(
        "/api/assistant/transcribe",
        files={"audio": ("recording.webm", b"", "audio/webm")},
    )
    unsupported = client.post(
        "/api/assistant/transcribe",
        files={"audio": ("recording.ogg", b"audio", "audio/ogg")},
    )
    mismatched = client.post(
        "/api/assistant/transcribe",
        files={"audio": ("recording.wav", b"audio", "video/webm")},
    )

    assert empty.status_code == 400
    assert unsupported.status_code == 415
    assert mismatched.status_code == 415
    assert voice.transcription_calls == []


def test_audio_upload_rejects_more_than_25_mb(monkeypatch):
    voice = FakeVoiceService()
    client = _client(monkeypatch, voice=voice)

    response = client.post(
        "/api/assistant/transcribe",
        files={
            "audio": (
                "recording.webm",
                b"x" * (25 * 1024 * 1024 + 1),
                "audio/webm",
            )
        },
    )

    assert response.status_code == 413
    assert voice.transcription_calls == []


def test_speech_endpoint_returns_wav_and_validates_text(monkeypatch):
    voice = FakeVoiceService()
    client = _client(monkeypatch, voice=voice)

    response = client.post(
        "/api/assistant/speech", json={"text": "The system found no discrepancies."}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF-fake-wav"
    assert voice.speech_calls == ["The system found no discrepancies."]
    assert client.post("/api/assistant/speech", json={"text": " "}).status_code == 422
    assert client.post(
        "/api/assistant/speech", json={"text": "x" * 4001}
    ).status_code == 422


def test_voice_provider_errors_are_sanitized(monkeypatch):
    client = _client(monkeypatch, voice=FakeVoiceService(RuntimeError("secret")))

    transcript = client.post(
        "/api/assistant/transcribe",
        files={"audio": ("recording.webm", b"audio", "audio/webm")},
    )
    speech = client.post("/api/assistant/speech", json={"text": "Hello"})

    assert transcript.status_code == 503
    assert transcript.json()["detail"] == "Speech transcription is temporarily unavailable."
    assert speech.status_code == 503
    assert speech.json()["detail"] == "Speech generation is temporarily unavailable."


def test_voice_provider_timeout_cancels_async_request(monkeypatch):
    monkeypatch.setenv("KAUSHAL_AI_TIMEOUT_SECONDS", "0.001")
    voice = SlowVoiceService()
    client = _client(monkeypatch, voice=voice)

    transcript = client.post(
        "/api/assistant/transcribe",
        files={"audio": ("recording.webm", b"audio", "audio/webm")},
    )
    speech = client.post("/api/assistant/speech", json={"text": "Hello"})

    assert transcript.status_code == 503
    assert speech.status_code == 503
    assert voice.transcription_cancelled is True
    assert voice.speech_cancelled is True


class FakeTranscriptions:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Transcript", (), {"text": "Recorded question"})()


class FakeSpeech:
    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        async def aread(_self):
            return b"wav-bytes"
        return type("SpeechResponse", (), {"aread": aread})()


class FakeOpenAIClient:
    def __init__(self):
        self.audio = type("Audio", (), {})()
        self.audio.transcriptions = FakeTranscriptions()
        self.audio.speech = FakeSpeech()


def test_voice_service_uses_current_models_and_in_memory_audio():
    client = FakeOpenAIClient()
    service = VoiceService(client=client)

    transcript = asyncio.run(service.transcribe(
        filename="recording.webm", content_type="audio/webm", data=b"audio"
    ))
    speech = asyncio.run(service.speech("Grounded response"))

    assert transcript == "Recorded question"
    assert client.audio.transcriptions.calls[0]["model"] == "whisper-large-v3-turbo"
    assert client.audio.transcriptions.calls[0]["file"] == (
        "recording.webm",
        b"audio",
        "audio/webm",
    )
    assert speech == b"wav-bytes"
    assert client.audio.speech.calls[0]["model"] == "canopylabs/orpheus-v1-english"
    assert client.audio.speech.calls[0]["voice"] == "hannah"\n    assert client.audio.speech.calls[0]["response_format"] == "wav"\n    assert "instructions" not in client.audio.speech.calls[0]




def test_voice_service_trims_spoken_output_to_orpheus_limit():
    client = FakeOpenAIClient()
    service = VoiceService(client=client)

    asyncio.run(service.speech("word " * 100))

    spoken = client.audio.speech.calls[0]["input"]
    assert len(spoken) <= 200
    assert spoken.endswith("...")


def test_voice_service_configures_async_client_timeout(monkeypatch):
    import app.services.voice_service as voice_module

    captured = {}
    fake_client = FakeOpenAIClient()

    def build_client(**kwargs):
        captured.update(kwargs)
        return fake_client

    monkeypatch.setattr(voice_module, "AsyncOpenAI", build_client)
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")

    service = voice_module.VoiceService(timeout_seconds=7.5)

    assert service.client is fake_client
    assert captured == {
        "api_key": "groq-test-key",
        "base_url": "https://api.groq.com/openai/v1",
        "timeout": 7.5,
        "max_retries": 0,
    }
