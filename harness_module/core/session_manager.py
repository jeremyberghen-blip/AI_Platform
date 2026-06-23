import asyncio
import secrets
import time
from datetime import datetime, timezone

from core.context_manager import ContextManager


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_session_id(character_id: str) -> str:
    return f"{character_id}_{int(time.time())}_{secrets.token_hex(4)}"


class Session:
    def __init__(self, session_id: str, character_id: str, model_id: str | None = None) -> None:
        self.session_id = session_id
        self.character_id = character_id
        self.model_id = model_id
        self.started_at = _now_iso()
        self.closed_at: str | None = None
        self.message_count = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.context = ContextManager(session_id, character_id)
        self._started_epoch = time.monotonic()

    def record_exchange(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.message_count += 1
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens

    def close(self) -> None:
        self.closed_at = _now_iso()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "character_id": self.character_id,
            "model_id": self.model_id,
            "started_at": self.started_at,
            "closed_at": self.closed_at,
            "message_count": self.message_count,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
        }


class SessionManager:
    """
    One active session per character at a time.
    Multiple characters can have concurrent active sessions.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}  # session_id → Session
        self._active: dict[str, str] = {}         # character_id → session_id
        self._lock = asyncio.Lock()

    async def get_or_create(self, character_id: str, model_id: str | None = None) -> Session:
        async with self._lock:
            if character_id in self._active:
                session = self._sessions[self._active[character_id]]
                if model_id and session.model_id != model_id:
                    session.model_id = model_id
                return session
            return self._create_locked(character_id, model_id)

    async def create_new(self, character_id: str, model_id: str | None = None) -> Session:
        """Close any existing session for this character and open a fresh one."""
        async with self._lock:
            if character_id in self._active:
                old = self._sessions[self._active[character_id]]
                old.close()
            return self._create_locked(character_id, model_id)

    def _create_locked(self, character_id: str, model_id: str | None) -> Session:
        session_id = _make_session_id(character_id)
        session = Session(session_id, character_id, model_id)
        self._sessions[session_id] = session
        self._active[character_id] = session_id
        return session

    async def get_active(self, character_id: str) -> Session | None:
        async with self._lock:
            sid = self._active.get(character_id)
            return self._sessions.get(sid) if sid else None

    async def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def close_session(self, character_id: str) -> Session | None:
        async with self._lock:
            sid = self._active.pop(character_id, None)
            if sid and sid in self._sessions:
                self._sessions[sid].close()
                return self._sessions[sid]
            return None

    async def close_all(self) -> list[Session]:
        async with self._lock:
            closed = []
            for character_id in list(self._active):
                sid = self._active.pop(character_id)
                if sid in self._sessions:
                    self._sessions[sid].close()
                    closed.append(self._sessions[sid])
            return closed

    def all_sessions(self) -> list[Session]:
        return list(self._sessions.values())
