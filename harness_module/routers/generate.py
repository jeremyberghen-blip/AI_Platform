"""
Generation router — image and video generation via ComfyUI backend.

All endpoints are stubbed for Phase 1. The schemas, database structure,
and routing are in place. Full implementation requires ComfyUIAdapter
to be completed (see backends/comfyui.py).

Phase 2 implementation notes are in each endpoint docstring.
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request

from schemas.requests import (
    ImageGenerateRequest,
    NotesImageRequest,
    RateImageRequest,
    RegisterLoraRequest,
    SavePromptTemplateRequest,
    SaveWorkflowRequest,
    VideoGenerateRequest,
)
from schemas.responses import (
    GenerationJobResponse,
    ImageCatalogEntry,
    LoraInfo,
    PromptTemplate,
    WorkflowInfo,
)

router = APIRouter()

_NOT_IMPLEMENTED = HTTPException(
    status_code=501,
    detail="ComfyUI backend not yet implemented. See backends/comfyui.py for Phase 2 plan.",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Image / Video generation ---

@router.post("/generate/image", response_model=GenerationJobResponse)
async def generate_image(body: ImageGenerateRequest, request: Request) -> GenerationJobResponse:
    """
    Phase 2: Submit an image generation job to ComfyUI.
    1. Load or select workflow JSON (from body.workflow_id or a default Flux/SDXL template)
    2. Inject body.prompt, body.params (model, LoRAs, ControlNet, seed, cfg, steps) into the workflow
    3. POST workflow to ComfyUI /prompt
    4. Return job_id for tracking via GET /v1/jobs/{job_id}
    5. On completion: save image to storage, insert into image catalog
    """
    raise _NOT_IMPLEMENTED


@router.post("/generate/video", response_model=GenerationJobResponse)
async def generate_video(body: VideoGenerateRequest, request: Request) -> GenerationJobResponse:
    """
    Phase 2: Submit a video generation job to ComfyUI with Wan 2.1 workflow.
    Same pattern as image generation. Outputs .mp4 to storage.
    """
    raise _NOT_IMPLEMENTED


@router.get("/jobs")
async def list_jobs(
    character_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    request: Request = None,
) -> list[GenerationJobResponse]:
    """Phase 2: Return recent generation jobs with status."""
    raise _NOT_IMPLEMENTED


@router.get("/jobs/{job_id}", response_model=GenerationJobResponse)
async def get_job(job_id: str, request: Request) -> GenerationJobResponse:
    """
    Phase 2: Poll job status.
    Query ComfyUI GET /history/{prompt_id} and return progress.
    """
    raise _NOT_IMPLEMENTED


@router.get("/jobs/{job_id}/output")
async def get_job_output(job_id: str, request: Request):
    """
    Phase 2: Stream the generated image/video bytes.
    Fetch from ComfyUI GET /view and proxy to client.
    """
    raise _NOT_IMPLEMENTED


# --- Workflows ---

@router.get("/workflows", response_model=list[WorkflowInfo])
async def list_workflows(request: Request) -> list[WorkflowInfo]:
    storage = request.app.state.storage
    rows = await storage.list_workflows()
    return [WorkflowInfo(**r) for r in rows]


@router.post("/workflows", response_model=dict)
async def save_workflow(body: SaveWorkflowRequest, request: Request) -> dict:
    storage = request.app.state.storage
    workflow_id = f"wf_{secrets.token_hex(8)}"
    await storage.insert_workflow({
        "workflow_id": workflow_id,
        "name": body.name,
        "description": body.description,
        "workflow_json": body.workflow_json,
        "base_model": body.base_model,
        "tags": body.tags,
    })
    return {"ok": True, "workflow_id": workflow_id}


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, request: Request) -> dict:
    storage = request.app.state.storage
    wf = await storage.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


# --- Image catalog ---

@router.get("/catalog", response_model=list[ImageCatalogEntry])
async def list_catalog(
    character_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    request: Request = None,
) -> list[ImageCatalogEntry]:
    storage = request.app.state.storage
    rows = await storage.list_images(character_id=character_id, limit=limit, offset=offset)
    return [ImageCatalogEntry(**r) for r in rows]


@router.post("/catalog/{image_id}/rate")
async def rate_image(image_id: str, body: RateImageRequest, request: Request) -> dict:
    storage = request.app.state.storage
    await storage.update_image_rating(image_id, body.rating)
    return {"ok": True}


@router.post("/catalog/{image_id}/notes")
async def update_notes(image_id: str, body: NotesImageRequest, request: Request) -> dict:
    storage = request.app.state.storage
    await storage.update_image_notes(image_id, body.notes)
    return {"ok": True}


# --- LoRA registry ---

@router.get("/loras", response_model=list[LoraInfo])
async def list_loras(request: Request) -> list[LoraInfo]:
    storage = request.app.state.storage
    rows = await storage.list_loras()
    return [LoraInfo(**r) for r in rows]


@router.post("/loras", response_model=dict)
async def register_lora(body: RegisterLoraRequest, request: Request) -> dict:
    storage = request.app.state.storage
    lora_id = f"lora_{secrets.token_hex(8)}"
    await storage.insert_lora({
        "lora_id": lora_id,
        "name": body.name,
        "filename": body.filename,
        "base_model": body.base_model,
        "trigger_word": body.trigger_word,
        "recommended_strength": body.recommended_strength,
        "description": body.description,
        "character_tag": body.character_tag,
    })
    return {"ok": True, "lora_id": lora_id}


# --- Prompt template library ---

@router.get("/prompts/templates", response_model=list[PromptTemplate])
async def list_prompt_templates(
    category: str | None = Query(default=None),
    request: Request = None,
) -> list[PromptTemplate]:
    storage = request.app.state.storage
    rows = await storage.list_prompt_templates(category=category)
    return [PromptTemplate(**r) for r in rows]


@router.post("/prompts/templates", response_model=dict)
async def save_prompt_template(body: SavePromptTemplateRequest, request: Request) -> dict:
    storage = request.app.state.storage
    template_id = f"tmpl_{secrets.token_hex(8)}"
    await storage.insert_prompt_template({
        "template_id": template_id,
        "name": body.name,
        "category": body.category,
        "content": body.content,
        "notes": body.notes,
    })
    return {"ok": True, "template_id": template_id}
