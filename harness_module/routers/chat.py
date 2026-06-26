import asyncio
import json
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from core.context_assembler import assembler
from core.event_bus import event_bus
from core.system_prompts import get_system_prompt, get_thought_prompt
from core.telemetry import RequestTelemetry
from schemas.requests import ChatRequest

router = APIRouter()


async def _generate_and_store_thought(
    backend,
    storage,
    character_id: str,
    session_id: str,
    seq: int,
    user_message: str,
    thought_prompt: str,
) -> None:
    """Runs in parallel with the response stream. Best-effort — errors are silently dropped."""
    try:
        chunks: list[str] = []
        async for chunk in backend.chat_stream(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=thought_prompt,
            params={"temperature": 0.6, "max_tokens": 150},
        ):
            if chunk.done:
                break
            chunks.append(chunk.content)
        thought = "".join(chunks).strip()
        if thought:
            await storage.write_thought(character_id, session_id, seq, thought, trigger_seq=seq - 1)
    except Exception:
        pass  # thought generation is non-critical


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

    # System prompt — LOD driven by model profile
    lod = assembler.get_lod(loaded_model)
    system_prompt = body.system_prompt or get_system_prompt(body.character_id, lod)

    # Assemble context-budgeted history (excludes the current user message)
    raw_history = [{"role": m.role, "content": m.content} for m in body.messages[:-1]]
    current_user_content = body.messages[-1].content if body.messages else ""

    trimmed_history = assembler.assemble(
        model_id=loaded_model,
        system_prompt=system_prompt,
        history=raw_history,
        user_message=current_user_content,
    )

    # Final messages list sent to the model
    messages_as_dicts = trimmed_history + [{"role": "user", "content": current_user_content}]

    session.context.set_messages(body.messages)

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
            "options": body.params.model_dump(),
        }

    telemetry = RequestTelemetry(
        session_id=session.session_id,
        character_id=body.character_id,
        model_id=loaded_model,
    )

    # Sequence numbers for this exchange
    user_seq = session.message_count * 2
    thought_seq = user_seq
    assistant_seq = user_seq + 1

    # Save user message
    await storage.write_message(
        body.character_id, session.session_id, user_seq,
        "user", current_user_content,
    )

    # Fire thought generation in parallel — doesn't block the response stream
    asyncio.create_task(_generate_and_store_thought(
        backend=backend,
        storage=storage,
        character_id=body.character_id,
        session_id=session.session_id,
        seq=thought_seq,
        user_message=current_user_content,
        thought_prompt=get_thought_prompt(body.character_id),
    ))

    async def generate():
        full_response: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0

        try:
            async for chunk in backend.chat_stream(
                messages=messages_as_dicts,
                system_prompt=system_prompt,
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

        await storage.write_message(
            body.character_id, session.session_id, assistant_seq,
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
