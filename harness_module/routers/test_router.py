import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from core.telemetry import RequestTelemetry
from schemas.requests import TestEnableRequest, TestInjectRequest
from schemas.responses import CaptureDetail, CaptureInfo, CaptureTiming, TestStatus

router = APIRouter()


@router.post("/test/enable")
async def enable_test_mode(body: TestEnableRequest, request: Request) -> TestStatus:
    capture_mgr = request.app.state.test_capture
    capture_mgr.enable(flush_to_disk=body.flush_to_disk)
    return TestStatus(enabled=True, flush_to_disk=body.flush_to_disk, capture_count=capture_mgr.capture_count)


@router.post("/test/disable")
async def disable_test_mode(request: Request) -> TestStatus:
    capture_mgr = request.app.state.test_capture
    capture_mgr.disable()
    return TestStatus(enabled=False, flush_to_disk=capture_mgr.flush_to_disk, capture_count=capture_mgr.capture_count)


@router.get("/test/status", response_model=TestStatus)
async def test_status(request: Request) -> TestStatus:
    capture_mgr = request.app.state.test_capture
    return TestStatus(
        enabled=capture_mgr.enabled,
        flush_to_disk=capture_mgr.flush_to_disk,
        capture_count=capture_mgr.capture_count,
    )


@router.post("/test/inject")
async def inject(body: TestInjectRequest, request: Request) -> StreamingResponse:
    """
    Injects a prompt directly into the pipeline, bypassing the normal harness flow.
    Test mode is automatically enabled for this request even if globally disabled.
    Returns the same SSE stream as /v1/chat.
    """
    app = request.app
    backend = app.state.backend
    session_mgr = app.state.session_manager
    storage = app.state.storage
    capture_mgr = app.state.test_capture

    loaded_model = await backend.get_loaded_model()
    if not loaded_model:
        raise HTTPException(status_code=409, detail="No model loaded. Call POST /v1/models/load first.")

    session = await session_mgr.get_or_create(body.character_id, loaded_model)

    from schemas.requests import ChatParams, Message
    params_dict = ChatParams().model_dump()
    if body.params_override:
        params_dict.update(body.params_override)

    user_message = {"role": "user", "content": body.input}
    messages = session.context.get_messages()
    messages_as_dicts = [{"role": m.role, "content": m.content} for m in messages] + [user_message]

    system_prompt = body.system_prompt_override or ""

    # Force capture for inject, regardless of global test mode state
    was_enabled = capture_mgr.enabled
    capture_mgr.enable()
    capture = capture_mgr.start_capture(
        character_id=body.character_id,
        session_id=session.session_id,
        system_prompt=system_prompt,
        messages=messages_as_dicts,
    )
    if capture:
        capture.backend_request = {
            "model": loaded_model,
            "messages": messages_as_dicts,
            "system": system_prompt,
            "options": params_dict,
        }
    if not was_enabled:
        capture_mgr.disable()

    telemetry = RequestTelemetry(
        session_id=session.session_id,
        character_id=body.character_id,
        model_id=loaded_model,
    )

    async def generate():
        full_response = []
        prompt_tokens = 0
        completion_tokens = 0

        try:
            async for chunk in backend.chat_stream(
                messages=messages_as_dicts,
                system_prompt=system_prompt,
                params=params_dict,
            ):
                if chunk.done:
                    telemetry.mark_done()
                    prompt_tokens = chunk.prompt_tokens
                    completion_tokens = chunk.completion_tokens
                    if capture:
                        capture.mark_backend_done()
                        capture.prompt_tokens = prompt_tokens
                        capture.completion_tokens = completion_tokens
                    break

                telemetry.mark_first_token()
                if capture:
                    capture.mark_first_token()

                full_response.append(chunk.content)
                yield f"data: {json.dumps({'type': 'token', 'content': chunk.content})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        assistant_content = "".join(full_response)

        if capture:
            capture.backend_response_raw = assistant_content
            capture.parsed_output = assistant_content
            capture.mark_parsing_done()
            # Always finish the capture for inject, regardless of global enable state
            saved = capture_mgr.enabled
            capture_mgr.enable()
            await capture_mgr.finish_capture(capture)
            if not saved:
                capture_mgr.disable()

        done_payload = {
            "type": "done",
            "capture_id": capture.capture_id if capture else None,
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
            "latency_ms": telemetry.total_ms,
            "first_token_ms": telemetry.first_token_ms,
            "tokens_per_second": telemetry.tokens_per_second,
            "session_id": session.session_id,
        }
        yield f"data: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/test/captures", response_model=list[CaptureInfo])
async def list_captures(
    character_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    request: Request = None,
) -> list[CaptureInfo]:
    capture_mgr = request.app.state.test_capture
    captures = await capture_mgr.get_captures(character_id=character_id, limit=limit)
    return [CaptureInfo(**c) for c in captures]


@router.get("/test/captures/{capture_id}", response_model=CaptureDetail)
async def get_capture(capture_id: str, request: Request) -> CaptureDetail:
    capture_mgr = request.app.state.test_capture
    data = await capture_mgr.get_capture(capture_id)
    if not data:
        raise HTTPException(status_code=404, detail="Capture not found")
    return CaptureDetail(
        capture_id=data["capture_id"],
        timestamp=data["timestamp"],
        character_id=data["character_id"],
        session_id=data.get("session_id"),
        system_prompt=data["system_prompt"],
        messages_sent=data["messages_sent"],
        backend_request=data["backend_request"],
        backend_response_raw=data["backend_response_raw"],
        parsed_output=data["parsed_output"],
        timing=CaptureTiming(**data["timing"]),
        token_counts=data["token_counts"],
    )


@router.delete("/test/captures")
async def clear_captures(request: Request) -> dict:
    capture_mgr = request.app.state.test_capture
    count = await capture_mgr.clear()
    return {"ok": True, "cleared": count}
