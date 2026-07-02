"""
Generation router — image generation via ComfyUI backend.
"""
import asyncio
import base64
import random
import secrets
import time
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_sdxl_workflow(
    checkpoint: str,
    positive: str,
    negative: str,
    loras: list[dict],
    seed: int,
    cfg: float,
    steps: int,
    sampler: str,
    width: int,
    height: int,
) -> dict:
    """Build a ComfyUI API-format workflow dict for SDXL txt2img with optional LoRAs."""
    workflow: dict = {}

    # Node 1: Load checkpoint
    workflow["1"] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": checkpoint},
    }

    # LoRA chain starting from checkpoint outputs
    model_ref: list = ["1", 0]
    clip_ref: list = ["1", 1]

    for i, lora in enumerate(loras):
        node_id = str(10 + i)
        workflow[node_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora["name"],
                "strength_model": lora["strength"],
                "strength_clip": lora["strength"],
                "model": model_ref,
                "clip": clip_ref,
            },
        }
        model_ref = [node_id, 0]
        clip_ref = [node_id, 1]

    # Node 2: Positive CLIP encode
    workflow["2"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": positive, "clip": clip_ref},
    }

    # Node 3: Negative CLIP encode
    workflow["3"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": negative, "clip": clip_ref},
    }

    # Node 4: Empty latent image
    workflow["4"] = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": width, "height": height, "batch_size": 1},
    }

    # Node 5: KSampler
    workflow["5"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": "karras",
            "denoise": 1.0,
            "model": model_ref,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
        },
    }

    # Node 6: VAE decode
    workflow["6"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
    }

    # Node 7: Save image
    workflow["7"] = {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "harness_", "images": ["6", 0]},
    }

    return workflow


# --- Image / Video generation ---

@router.post("/generate/image")
async def generate_image(body: ImageGenerateRequest, request: Request) -> dict:
    """
    Submit an image generation job to ComfyUI and wait for completion.
    Returns the generated image as base64 in image_b64.
    """
    comfyui = request.app.state.comfyui

    # Resolve checkpoint
    checkpoint = body.params.model.strip()
    if not checkpoint:
        models = await comfyui.list_models()
        if not models:
            raise HTTPException(status_code=503, detail="No checkpoints found in ComfyUI. Make sure ComfyUI is running and has models in models/checkpoints/.")
        checkpoint = models[0].model_id

    # Resolve seed
    seed = body.params.seed if body.params.seed != -1 else random.randint(0, 2**32 - 1)

    # Build workflow
    loras = [{"name": l.name, "strength": l.strength} for l in body.params.loras]
    workflow = _build_sdxl_workflow(
        checkpoint=checkpoint,
        positive=body.prompt,
        negative=body.negative_prompt,
        loras=loras,
        seed=seed,
        cfg=body.params.cfg,
        steps=body.params.steps,
        sampler=body.params.sampler,
        width=body.params.width,
        height=body.params.height,
    )

    # Submit to ComfyUI
    try:
        prompt_id = await comfyui.submit_workflow(workflow)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"ComfyUI submit failed: {e}")

    # Poll until done (up to 5 minutes)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        await asyncio.sleep(2)
        try:
            history = await comfyui.get_job_status(prompt_id)
        except Exception:
            continue

        if not history:
            continue

        job = history.get(prompt_id, {})
        status = job.get("status", {})

        if status.get("status_str") == "error":
            msgs = status.get("messages", [])
            raise HTTPException(status_code=500, detail=f"ComfyUI generation error: {msgs}")

        if status.get("completed"):
            outputs = job.get("outputs", {})
            for _node_id, node_out in outputs.items():
                images = node_out.get("images", [])
                if not images:
                    continue
                img_info = images[0]
                try:
                    img_bytes = await comfyui.download_output(
                        img_info["filename"],
                        img_info.get("subfolder", ""),
                        img_info.get("type", "output"),
                    )
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to download output: {e}")

                img_b64 = base64.b64encode(img_bytes).decode()
                return {
                    "job_id": prompt_id,
                    "character_id": body.character_id,
                    "status": "completed",
                    "progress": 1.0,
                    "created_at": _now_iso(),
                    "image_b64": img_b64,
                    "seed": seed,
                    "checkpoint": checkpoint,
                }

    raise HTTPException(status_code=408, detail="Generation timed out after 5 minutes.")


@router.post("/generate/video", response_model=GenerationJobResponse)
async def generate_video(body: VideoGenerateRequest, request: Request) -> GenerationJobResponse:
    raise HTTPException(status_code=501, detail="Video generation not yet implemented.")


@router.get("/generate/checkpoints")
async def list_checkpoints(request: Request) -> dict:
    """List available checkpoints from the running ComfyUI instance."""
    comfyui = request.app.state.comfyui
    models = await comfyui.list_models()
    return {"checkpoints": [m.model_id for m in models]}


@router.get("/generate/loras")
async def list_loras_comfyui(request: Request) -> dict:
    """List available LoRAs from the running ComfyUI instance."""
    comfyui = request.app.state.comfyui
    loras = await comfyui.list_loras()
    return {"loras": loras}


@router.get("/jobs")
async def list_jobs(
    character_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    request: Request = None,
) -> list[GenerationJobResponse]:
    raise HTTPException(status_code=501, detail="Job history not yet implemented.")


@router.get("/jobs/{job_id}", response_model=GenerationJobResponse)
async def get_job(job_id: str, request: Request) -> GenerationJobResponse:
    raise HTTPException(status_code=501, detail="Job polling not yet implemented.")


@router.get("/jobs/{job_id}/output")
async def get_job_output(job_id: str, request: Request):
    raise HTTPException(status_code=501, detail="Job output not yet implemented.")


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


# --- LoRA registry (harness database, not ComfyUI) ---

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
