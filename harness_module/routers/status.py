import time

from fastapi import APIRouter, Request

from schemas.responses import StatusResponse

router = APIRouter()

_start_time = time.monotonic()


@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request) -> StatusResponse:
    app = request.app
    backend = app.state.backend
    session_mgr = app.state.session_manager
    capture_mgr = app.state.test_capture

    vram = await backend.get_vram_state()
    loaded_model = await backend.get_loaded_model()

    active_character = None
    context_tokens = 0
    session_id = None
    active_session = None

    # Find any active session to report (first one found)
    for session in session_mgr.all_sessions():
        if session.closed_at is None:
            active_session = session
            active_character = session.character_id
            session_id = session.session_id
            context_tokens = session.context.estimated_tokens()
            break

    return StatusResponse(
        ok=await backend.health_check(),
        backend=backend.backend_name,
        backend_url=backend._base_url,
        model_loaded=loaded_model,
        vram_used_mb=vram.used_mb,
        vram_total_mb=vram.total_mb,
        context_tokens=context_tokens,
        context_max=None,
        session_id=session_id,
        active_character=active_character,
        uptime_seconds=time.monotonic() - _start_time,
        test_mode=capture_mgr.enabled,
    )
