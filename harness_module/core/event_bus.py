import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any


class EventBus:
    """Simple asyncio pub/sub for SSE clients. One queue per subscriber."""

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[dict[str, Any] | None]] = []

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        payload = {"type": event_type, **data}
        for q in self._queues:
            await q.put(payload)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._queues.append(q)
        try:
            while True:
                event = await q.get()
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            self._queues.remove(q)

    async def shutdown(self) -> None:
        for q in self._queues:
            await q.put(None)


event_bus = EventBus()
