import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from core.event_bus import event_bus
from schemas.requests import LoadModelRequest
from schemas.responses import LoadJobResponse, ModelInfo, ModelListResponse

router = APIRouter()

_load_task: asyncio.Task | None = None


@router.get("/models", response_model=ModelListResponse)
async def list_models(request: Request) -> ModelListResponse:
    backend = request.app.state.backend
    try:
        models = await backend.list_models()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Backend error: {e}")

    loaded = await backend.get_loaded_model()
    return ModelListResponse(
        models=[
            ModelInfo(
                model_id=m.model_id,
                size_mb=m.size_mb,
                quantization=m.quantization,
                context_length=m.context_length,
                family=m.family,
            )
            for m in models
        ],
        loaded=loaded,
    )


@router.post("/models/load", response_model=LoadJobResponse)
async def load_model(body: LoadModelRequest, request: Request) -> LoadJobResponse:
    global _load_task
    backend = request.app.state.backend

    if _load_task and not _load_task.done():
        raise HTTPException(status_code=409, detail="A model load is already in progress")

    async def _run_load() -> None:
        try:
            async for progress in backend.load_model(body.model_id):
                await event_bus.publish("model_load_progress", {
                    "model_id": body.model_id,
                    "status": progress.status,
                    "progress": progress.progress,
                    "message": progress.message,
                })
        except Exception as e:
            await event_bus.publish("model_load_progress", {
                "model_id": body.model_id,
                "status": "error",
                "progress": 0.0,
                "message": str(e),
            })

    _load_task = asyncio.create_task(_run_load())

    return LoadJobResponse(
        job_id=f"load_{body.model_id}",
        model_id=body.model_id,
        status="loading",
    )


@router.post("/models/unload")
async def unload_model(request: Request) -> dict:
    backend = request.app.state.backend
    try:
        await backend.unload_model()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Backend error: {e}")
    await event_bus.publish("model_unloaded", {"message": "Model unloaded"})
    return {"ok": True}
