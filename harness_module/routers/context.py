from fastapi import APIRouter, HTTPException, Request

from core.event_bus import event_bus
from schemas.responses import ContextInfo

router = APIRouter()


@router.get("/context", response_model=ContextInfo)
async def get_context(character_id: str, request: Request) -> ContextInfo:
    session_mgr = request.app.state.session_manager
    session = await session_mgr.get_active(character_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"No active session for character '{character_id}'")

    return ContextInfo(
        session_id=session.session_id,
        message_count=session.context.message_count(),
        estimated_tokens=session.context.estimated_tokens(),
        context_max=None,
    )


@router.post("/context/reset")
async def reset_context(character_id: str, request: Request) -> dict:
    """
    Closes the current session for this character (archiving it to disk)
    and opens a fresh one. The context window is cleared.
    """
    app = request.app
    session_mgr = app.state.session_manager
    storage = app.state.storage

    old_session = await session_mgr.close_session(character_id)
    if old_session:
        await storage.write_session_metadata(old_session.to_dict())
        await storage.upsert_session(old_session.to_dict())
        await event_bus.publish("session_closed", {
            "character_id": character_id,
            "session_id": old_session.session_id,
        })

    new_session = await session_mgr.create_new(character_id)
    await event_bus.publish("session_created", {
        "character_id": character_id,
        "session_id": new_session.session_id,
    })

    return {
        "ok": True,
        "closed_session_id": old_session.session_id if old_session else None,
        "new_session_id": new_session.session_id,
    }
