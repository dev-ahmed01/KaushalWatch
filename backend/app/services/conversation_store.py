from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import secrets
import threading
import time
from typing import Callable, Protocol


class ConversationStore(Protocol):
    def ensure_session(self, session_id: str | None = None) -> str: ...
    def get_messages(self, session_id: str) -> list[dict[str, str]]: ...
    def append_exchange(
        self, session_id: str, user_message: str, assistant_message: str
    ) -> None: ...
    def clear(self, session_id: str) -> None: ...


@dataclass
class _Session:
    messages: list[dict[str, str]]
    touched_at: float


class InMemoryConversationStore:
    """Bounded, process-local conversation memory for the V1 assistant."""

    def __init__(
        self,
        max_sessions: int = 500,
        max_turns: int = 12,
        ttl_seconds: int = 60 * 60,
        now_provider: Callable[[], float] = time.monotonic,
    ):
        if min(max_sessions, max_turns, ttl_seconds) < 1:
            raise ValueError("Conversation store limits must be positive")
        self.max_sessions = max_sessions
        self.max_turns = max_turns
        self.ttl_seconds = ttl_seconds
        self.now_provider = now_provider
        self._sessions: OrderedDict[str, _Session] = OrderedDict()
        self._lock = threading.RLock()

    def _purge_expired(self, now: float) -> None:
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.touched_at > self.ttl_seconds
        ]
        for session_id in expired:
            self._sessions.pop(session_id, None)

    def ensure_session(self, session_id: str | None = None) -> str:
        normalized = (session_id or "").strip()
        if len(normalized) > 128:
            raise ValueError("session_id is too long")
        with self._lock:
            now = self.now_provider()
            self._purge_expired(now)
            if not normalized:
                normalized = secrets.token_urlsafe(24)
            existing = self._sessions.get(normalized)
            if existing:
                existing.touched_at = now
                self._sessions.move_to_end(normalized)
                return normalized
            self._sessions[normalized] = _Session([], now)
            while len(self._sessions) > self.max_sessions:
                self._sessions.popitem(last=False)
            return normalized

    def get_messages(self, session_id: str) -> list[dict[str, str]]:
        with self._lock:
            now = self.now_provider()
            self._purge_expired(now)
            session = self._sessions.get(session_id)
            if not session:
                return []
            session.touched_at = now
            self._sessions.move_to_end(session_id)
            return [dict(message) for message in session.messages]

    def append_exchange(
        self, session_id: str, user_message: str, assistant_message: str
    ) -> None:
        with self._lock:
            normalized = self.ensure_session(session_id)
            session = self._sessions[normalized]
            session.messages.extend(
                [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": assistant_message},
                ]
            )
            session.messages = session.messages[-self.max_turns * 2 :]
            session.touched_at = self.now_provider()
            self._sessions.move_to_end(normalized)

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
