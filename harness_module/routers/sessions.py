from fastapi import APIRouter, HTTPException, Query, Request

from schemas.responses import SessionInfo, SessionListResponse, SessionLogEntry

router = APIRouter()


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    character_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    request: Request = None,
) -> SessionListResponse:
    storage = request.app.state.storage
    rows = await storage.list_sessions(character_id, limit=limit, offset=offset)
    sessions = [SessionInfo(**row) for row in rows]
    return SessionListResponse(sessions=sessions, total=len(sessions))


@router.get("/sessions/{session_id}/log")
async def get_session_log(session_id: str, character_id: str, request: Request) -> list[SessionLogEntry]:
    storage = request.app.state.storage
    entries = await storage.read_session_log(character_id, session_id)
    if not entries:
        raise HTTPException(status_code=404, detail="Session log not found")
    return [SessionLogEntry(**e) for e in entries]
