from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from core.event_bus import event_bus

router = APIRouter()


@router.get("/events")
async def sse_events() -> StreamingResponse:
    """
    Persistent SSE connection. Pushes model load progress, ready signals,
    VRAM alerts, and session events. Used by the harness for async monitoring.
    """
    return StreamingResponse(
        event_bus.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
