from __future__ import annotations

from dataclasses import dataclass, field
import asyncio
import hashlib
import logging
import secrets
import threading
from typing import Protocol
from weakref import WeakValueDictionary

from app.models import AssistantChatResponse, AssistantSourcePayload, AssistantToolCallPayload
from app.services.assistant_tools import AssistantSource
from app.services.conversation_store import ConversationStore


logger = logging.getLogger(__name__)
MAX_MESSAGE_LENGTH = 4000


class AssistantUnavailableError(RuntimeError):
    pass


@dataclass
class AssistantProviderResult:
    message: str
    sources: list[AssistantSource] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)


class AssistantProvider(Protocol):
    async def run(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        centre_id: str,
    ) -> AssistantProviderResult: ...


class AssistantService:
    def __init__(self, *, provider: AssistantProvider, conversations: ConversationStore):
        self.provider = provider
        self.conversations = conversations
        self._session_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        self._session_locks_guard = threading.Lock()

    def _session_lock(self, storage_session: str) -> asyncio.Lock:
        with self._session_locks_guard:
            lock = self._session_locks.get(storage_session)
            if lock is None:
                lock = asyncio.Lock()
                self._session_locks[storage_session] = lock
            return lock

    @staticmethod
    def _session_keys(session_id: str | None, centre_id: str) -> tuple[str, str]:
        public_session = (session_id or "").strip()
        if len(public_session) > 128:
            raise ValueError("session_id is too long")
        if not public_session:
            public_session = secrets.token_urlsafe(24)
        storage_session = hashlib.sha256(
            f"{centre_id}\0{public_session}".encode("utf-8")
        ).hexdigest()
        return public_session, storage_session

    async def chat(
        self,
        *,
        message: str,
        session_id: str | None,
        centre_id: str,
    ) -> AssistantChatResponse:
        normalized = message.strip()
        if not normalized:
            raise ValueError("message must not be empty")
        if len(normalized) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"message must be at most {MAX_MESSAGE_LENGTH} characters")

        active_session, storage_session = self._session_keys(session_id, centre_id)
        lock = self._session_lock(storage_session)
        async with lock:
            self.conversations.ensure_session(storage_session)
            history = self.conversations.get_messages(storage_session)
            logger.info(
                "assistant request started for centre %s session %s",
                centre_id,
                active_session,
            )
            try:
                result = await self.provider.run(
                    message=normalized,
                    history=history,
                    centre_id=centre_id,
                )
                if not result or not isinstance(result.message, str) or not result.message.strip():
                    raise ValueError("Assistant provider returned an empty response")
            except Exception as exc:
                logger.exception("assistant provider failed for session %s", active_session)
                raise AssistantUnavailableError(
                    "Kaushal Assistant is temporarily unavailable."
                ) from exc

            answer = result.message.strip()
            self.conversations.append_exchange(storage_session, normalized, answer)
            logger.info(
                "assistant request completed for centre %s session %s",
                centre_id,
                active_session,
            )

        seen_sources: set[tuple[str, str]] = set()
        sources = []
        for source in result.sources:
            key = (source.kind, source.id)
            if key in seen_sources:
                continue
            seen_sources.add(key)
            sources.append(AssistantSourcePayload(**source.__dict__))

        tool_calls = [AssistantToolCallPayload.model_validate(item) for item in result.tool_calls]
        return AssistantChatResponse(
            message=answer,
            session_id=active_session,
            sources=sources,
            tool_calls=tool_calls,
        )
