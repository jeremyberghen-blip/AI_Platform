import json
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from core.event_bus import event_bus
from core.telemetry import RequestTelemetry
from schemas.requests import ChatRequest

router = APIRouter()


@router.post("/chat")
async def chat(body: ChatRequest, request: Request) -> StreamingResponse:
    app = request.app
    backend = app.state.backend
    session_mgr = app.state.session_manager
    storage = app.state.storage
    capture_mgr = app.state.test_capture

    loaded_model = await backend.get_loaded_model()
    if not loaded_model:
        raise HTTPException(status_code=409, detail="No model loaded. Call POST /v1/models/load first.")

    session = await session_mgr.get_or_create(body.character_id, loaded_model)

    messages_as_dicts = [{"role": m.role, "content": m.content} for m in body.messages]
    session.context.set_messages(body.messages)

    capture = capture_mgr.start_capture(
        character_id=body.character_id,
        session_id=session.session_id,
        system_prompt=body.system_prompt,
        messages=messages_as_dicts,
    )
    if capture:
        capture.backend_request = {
            "model": loaded_model,
            "messages": messages_as_dicts,
            "system": body.system_prompt,
            "options": body.params.model_dump(),
        }

    telemetry = RequestTelemetry(
        session_id=session.session_id,
        character_id=body.character_id,
        model_id=loaded_model,
    )

    # Save user messages to log
    for i, msg in enumerate(body.messages):
        if msg.role == "user":
            seq = session.message_count * 2 + i
            await storage.write_message(
                body.character_id, session.session_id, seq,
                "user", msg.content,
            )

    async def generate():
        full_response = []
        prompt_tokens = 0
        completion_tokens = 0

        try:
            async for chunk in backend.chat_stream(
                messages=messages_as_dicts,
                system_prompt=body.system_prompt,
                params=body.params.model_dump(),
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
        telemetry.prompt_tokens = prompt_tokens
        telemetry.completion_tokens = completion_tokens

        if capture:
            capture.backend_response_raw = assistant_content
            capture.parsed_output = assistant_content
            capture.mark_parsing_done()
            await capture_mgr.finish_capture(capture)

        session.context.append_assistant(assistant_content)
        session.record_exchange(prompt_tokens, completion_tokens)

        seq = session.message_count * 2
        await storage.write_message(
            body.character_id, session.session_id, seq,
            "assistant", assistant_content,
            tokens=completion_tokens,
            latency_ms=telemetry.total_ms,
        )
        await storage.write_telemetry(
            body.character_id, session.session_id, telemetry.to_dict()
        )
        await storage.upsert_session(session.to_dict())

        done_payload = {
            "type": "done",
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
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
