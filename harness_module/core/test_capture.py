import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Capture:
    capture_id: str
    timestamp: str
    character_id: str
    session_id: str | None
    system_prompt: str
    messages_sent: list[dict[str, Any]]
    backend_request: dict[str, Any] = field(default_factory=dict)
    backend_response_raw: str = ""
    parsed_output: str = ""
    first_token_ms: int | None = None
    backend_total_ms: int | None = None
    output_parsing_ms: int | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0

    _start: float = field(default_factory=time.perf_counter, repr=False)
    _first_token_time: float | None = field(default=None, repr=False)
    _backend_done_time: float | None = field(default=None, repr=False)

    def mark_first_token(self) -> None:
        if self._first_token_time is None:
            self._first_token_time = time.perf_counter()
            self.first_token_ms = int((self._first_token_time - self._start) * 1000)

    def mark_backend_done(self) -> None:
        self._backend_done_time = time.perf_counter()
        self.backend_total_ms = int((self._backend_done_time - self._start) * 1000)

    def mark_parsing_done(self) -> None:
        if self._backend_done_time:
            done = time.perf_counter()
            self.output_parsing_ms = int((done - self._backend_done_time) * 1000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "timestamp": self.timestamp,
            "character_id": self.character_id,
            "session_id": self.session_id,
            "system_prompt": self.system_prompt,
            "messages_sent": self.messages_sent,
            "backend_request": self.backend_request,
            "backend_response_raw": self.backend_response_raw,
            "parsed_output": self.parsed_output,
            "timing": {
                "backend_first_token_ms": self.first_token_ms,
                "backend_total_ms": self.backend_total_ms,
                "output_parsing_ms": self.output_parsing_ms,
            },
            "token_counts": {
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
            },
        }

    def to_summary(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "timestamp": self.timestamp,
            "character_id": self.character_id,
            "session_id": self.session_id,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_latency_ms": self.backend_total_ms,
        }


import secrets


class TestCaptureManager:
    def __init__(self, storage_path: Path | None = None, flush_to_disk: bool = True) -> None:
        self.enabled = False
        self.flush_to_disk = flush_to_disk
        self._storage_path = storage_path
        self._buffer: list[Capture] = []
        self._lock = asyncio.Lock()

    def enable(self, flush_to_disk: bool = True) -> None:
        self.enabled = True
        self.flush_to_disk = flush_to_disk

    def disable(self) -> None:
        self.enabled = False

    def start_capture(
        self,
        character_id: str,
        session_id: str | None,
        system_prompt: str,
        messages: list[dict[str, Any]],
    ) -> Capture | None:
        if not self.enabled:
            return None
        capture_id = f"cap_{secrets.token_hex(8)}"
        return Capture(
            capture_id=capture_id,
            timestamp=_now_iso(),
            character_id=character_id,
            session_id=session_id,
            system_prompt=system_prompt,
            messages_sent=messages,
        )

    async def finish_capture(self, capture: Capture | None) -> None:
        if capture is None:
            return
        async with self._lock:
            self._buffer.append(capture)
        if self.flush_to_disk and self._storage_path:
            await self._write_to_disk(capture)

    async def _write_to_disk(self, capture: Capture) -> None:
        capture_dir = self._storage_path / "captures" / capture.capture_id
        capture_dir.mkdir(parents=True, exist_ok=True)
        data = capture.to_dict()
        path = capture_dir / "capture.json"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, path.write_text, json.dumps(data, indent=2))

    async def get_captures(self, character_id: str | None = None, limit: int = 50) -> list[dict]:
        async with self._lock:
            captures = self._buffer
            if character_id:
                captures = [c for c in captures if c.character_id == character_id]
            return [c.to_summary() for c in reversed(captures[-limit:])]

    async def get_capture(self, capture_id: str) -> dict | None:
        async with self._lock:
            for c in self._buffer:
                if c.capture_id == capture_id:
                    return c.to_dict()
        if self._storage_path:
            path = self._storage_path / "captures" / capture_id / "capture.json"
            if path.exists():
                loop = asyncio.get_event_loop()
                text = await loop.run_in_executor(None, path.read_text)
                return json.loads(text)
        return None

    async def clear(self) -> int:
        async with self._lock:
            count = len(self._buffer)
            self._buffer.clear()
            return count

    @property
    def capture_count(self) -> int:
        return len(self._buffer)
