import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.assistant_service import (
    AssistantProviderResult,
    AssistantService,
    AssistantUnavailableError,
)
from app.services.assistant_tools import AssistantSource
from app.services.conversation_store import InMemoryConversationStore
from app.services.openai_assistant import AGENT_INSTRUCTIONS, OpenAIAssistantProvider


def test_conversation_store_bounds_sessions_turns_and_expires():
    clock = [100.0]
    store = InMemoryConversationStore(
        max_sessions=2,
        max_turns=2,
        ttl_seconds=10,
        now_provider=lambda: clock[0],
    )
    first = store.ensure_session()
    assert len(first) >= 20
    store.append_exchange(first, "u1", "a1")
    store.append_exchange(first, "u2", "a2")
    store.append_exchange(first, "u3", "a3")
    assert [item["content"] for item in store.get_messages(first)] == [
        "u2", "a2", "u3", "a3"
    ]

    second = store.ensure_session()
    third = store.ensure_session()
    assert store.get_messages(first) == []
    assert second != third

    clock[0] = 111.0
    assert store.get_messages(second) == []


def test_conversation_store_appends_complete_exchanges_concurrently():
    store = InMemoryConversationStore(max_sessions=5, max_turns=50, ttl_seconds=60)
    session_id = store.ensure_session("session-1")

    def append(index: int):
        store.append_exchange(session_id, f"user-{index}", f"assistant-{index}")

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append, range(20)))

    messages = store.get_messages(session_id)
    assert len(messages) == 40
    for index in range(0, len(messages), 2):
        user = messages[index]
        assistant = messages[index + 1]
        assert user["role"] == "user"
        assert assistant["role"] == "assistant"
        assert assistant["content"].replace("assistant", "user") == user["content"]


class RecordingProvider:
    def __init__(self):
        self.calls = []

    async def run(self, *, message, history, centre_id):
        self.calls.append({"message": message, "history": history, "centre_id": centre_id})
        if len(self.calls) == 1:
            return AssistantProviderResult(
                message="The system recorded one attendance discrepancy.",
                sources=[
                    AssistantSource(
                        kind="analysis",
                        id="AN-000001",
                        label="Attendance analysis",
                        href="/centres/DEMO-KA-104/history",
                        timestamp="2026-10-05T06:00:00+00:00",
                    )
                ],
                tool_calls=[
                    {"name": "get_attendance_summary", "status": "success", "duration_ms": 4}
                ],
            )
        return AssistantProviderResult(
            message="The attendance discrepancy was the only flagged issue.",
            sources=[],
            tool_calls=[],
        )


def test_assistant_service_preserves_session_context_and_sources():
    provider = RecordingProvider()
    service = AssistantService(
        provider=provider,
        conversations=InMemoryConversationStore(),
    )

    first = asyncio.run(
        service.chat(
            message="What happened today?",
            session_id=None,
            centre_id="DEMO-KA-104",
        )
    )
    second = asyncio.run(
        service.chat(
            message="Which issue was most serious?",
            session_id=first.session_id,
            centre_id="DEMO-KA-104",
        )
    )

    assert first.message == "The system recorded one attendance discrepancy."
    assert first.sources[0].id == "AN-000001"
    assert first.tool_calls[0].name == "get_attendance_summary"
    assert second.session_id == first.session_id
    assert provider.calls[1]["history"] == [
        {"role": "user", "content": "What happened today?"},
        {
            "role": "assistant",
            "content": "The system recorded one attendance discrepancy.",
        },
    ]


def test_assistant_service_scopes_public_session_to_selected_centre():
    provider = RecordingProvider()
    service = AssistantService(provider=provider, conversations=InMemoryConversationStore())

    first = asyncio.run(service.chat(
        message="What happened?", session_id="shared-browser-session", centre_id="DEMO-KA-104"
    ))
    second = asyncio.run(service.chat(
        message="What happened here?", session_id=first.session_id, centre_id="DEMO-KA-112"
    ))

    assert second.session_id == first.session_id
    assert provider.calls[1]["centre_id"] == "DEMO-KA-112"
    assert provider.calls[1]["history"] == []


class OrderedProvider:
    def __init__(self):
        self.calls = []

    async def run(self, *, message, history, centre_id):
        self.calls.append({"message": message, "history": history})
        if message == "first":
            await asyncio.sleep(0.02)
        return AssistantProviderResult(message=f"answer-{message}")


def test_assistant_service_serializes_same_session_requests():
    provider = OrderedProvider()
    service = AssistantService(provider=provider, conversations=InMemoryConversationStore())

    async def exercise():
        return await asyncio.gather(
            service.chat(message="first", session_id="ordered", centre_id="DEMO-KA-104"),
            service.chat(message="second", session_id="ordered", centre_id="DEMO-KA-104"),
        )

    asyncio.run(exercise())

    assert provider.calls[0]["message"] == "first"
    assert provider.calls[1]["message"] == "second"
    assert provider.calls[1]["history"] == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "answer-first"},
    ]


@pytest.mark.parametrize("message", ["", "   ", "x" * 4001])
def test_assistant_service_rejects_invalid_messages(message):
    service = AssistantService(
        provider=RecordingProvider(),
        conversations=InMemoryConversationStore(),
    )

    with pytest.raises(ValueError):
        asyncio.run(service.chat(message=message, session_id=None, centre_id="DEMO-KA-104"))


class BrokenProvider:
    def __init__(self, result=None):
        self.result = result

    async def run(self, **_kwargs):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.parametrize(
    "provider",
    [BrokenProvider(RuntimeError("provider secret")), BrokenProvider(None)],
)
def test_assistant_service_sanitizes_provider_failures(provider):
    service = AssistantService(
        provider=provider,
        conversations=InMemoryConversationStore(),
    )

    with pytest.raises(AssistantUnavailableError) as exc_info:
        asyncio.run(
            service.chat(
                message="What happened?",
                session_id=None,
                centre_id="DEMO-KA-104",
            )
        )

    assert str(exc_info.value) == "Kaushal Assistant is temporarily unavailable."
    assert "secret" not in str(exc_info.value)


def test_assistant_service_rejects_empty_provider_message_without_saving_turn():
    conversations = InMemoryConversationStore()
    session_id = conversations.ensure_session("session-empty")
    service = AssistantService(
        provider=BrokenProvider(AssistantProviderResult(message=" ")),
        conversations=conversations,
    )

    with pytest.raises(AssistantUnavailableError):
        asyncio.run(
            service.chat(
                message="What happened?",
                session_id=session_id,
                centre_id="DEMO-KA-104",
            )
        )

    assert conversations.get_messages(session_id) == []


class FakeToolset:
    pass


class FakeRunResult:
    final_output = "Grounded answer"


class FakeRunner:
    def __init__(self):
        self.calls = []

    async def run(self, agent, input, context, run_config):
        self.calls.append({
            "agent": agent,
            "input": input,
            "context": context,
            "run_config": run_config,
        })
        context.sources.append(
            AssistantSource(
                kind="analysis",
                id="AN-1",
                label="Analysis",
                href="/centres/DEMO-KA-104/history",
            )
        )
        context.tool_calls.append(
            {"name": "get_operational_history", "status": "success", "duration_ms": 2}
        )
        return FakeRunResult()


def test_openai_provider_configures_one_grounded_agent_and_all_tools():
    provider = OpenAIAssistantProvider(toolset=FakeToolset(), runner=FakeRunner(), client=object())

    assert provider.agent.name == "Kaushal Assistant"
    assert provider.model_name == "gemini-3.8-flash"
    assert provider.agent.model.model == "gemini-3.8-flash"
    assert {tool.name for tool in provider.agent.tools} == {
        "get_centre_overview",
        "get_runtime_readiness",
        "get_operational_history",
        "get_analysis_details",
        "get_attendance_summary",
        "get_practical_work_summary",
        "get_escalations",
        "get_case_evidence",
    }
    assert "Never invent" in AGENT_INSTRUCTIONS
    assert "anonymous" in AGENT_INSTRUCTIONS.lower()
    assert provider.agent.handoffs == []


def test_gemini_provider_builds_openai_compatible_client(monkeypatch):
    import app.services.openai_assistant as assistant_module

    captured = {}

    class FakeClient:
        pass

    def build_client(**kwargs):
        captured.update(kwargs)
        return FakeClient()

    monkeypatch.setattr(assistant_module, "AsyncOpenAI", build_client)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("KAUSHAL_AI_TIMEOUT_SECONDS", "7.5")

    provider = assistant_module.OpenAIAssistantProvider(
        toolset=FakeToolset(),
        runner=FakeRunner(),
    )

    assert provider.client.__class__ is FakeClient
    assert captured == {
        "api_key": "gemini-test-key",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "timeout": 7.5,
        "max_retries": 0,
        "default_headers": {"x-goog-api-client": "kaushalwatch-oai/1.0"},
    }


def test_openai_provider_passes_history_and_collects_run_provenance():
    runner = FakeRunner()
    provider = OpenAIAssistantProvider(toolset=FakeToolset(), runner=runner, client=object())

    result = asyncio.run(
        provider.run(
            message="Which one is serious?",
            history=[{"role": "user", "content": "Any discrepancies?"}],
            centre_id="DEMO-KA-104",
        )
    )

    assert runner.calls[0]["input"] == [
        {"role": "user", "content": "Any discrepancies?"},
        {"role": "user", "content": "Which one is serious?"},
    ]
    assert runner.calls[0]["context"].centre_id == "DEMO-KA-104"
    assert runner.calls[0]["run_config"].trace_include_sensitive_data is False
    assert runner.calls[0]["run_config"].workflow_name == "Kaushal Assistant"
    assert result.message == "Grounded answer"
    assert result.sources[0].id == "AN-1"
    assert result.tool_calls[0]["name"] == "get_operational_history"
