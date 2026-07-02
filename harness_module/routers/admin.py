import asyncio
import os
import signal
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings

router = APIRouter(prefix="/admin", tags=["admin"])

VOLUME_PATH = settings.volume_path
MODELS_FILE = Path(settings.models_file)

VALID_TYPES = {"checkpoint", "lora", "controlnet", "vae", "upscale"}


class ModelEntry(BaseModel):
    type: str
    filename: str
    url: str


async def _flag_and_exit(flag_file: str) -> None:
    await asyncio.sleep(0.3)  # Let the response flush before we exit
    os.makedirs(os.path.dirname(flag_file), exist_ok=True)
    with open(flag_file, "w") as f:
        f.write("1")
    os.kill(os.getpid(), signal.SIGTERM)


@router.post("/update")
async def trigger_update():
    """Pull latest code from GitHub and restart. Supervisor handles the actual restart."""
    asyncio.create_task(_flag_and_exit(os.path.join(VOLUME_PATH, ".do_update")))
    return {"status": "update initiated", "message": "Harness will update and restart in a moment"}


@router.post("/restart")
async def trigger_restart():
    """Restart the harness module without updating code."""
    asyncio.create_task(_flag_and_exit(os.path.join(VOLUME_PATH, ".do_restart")))
    return {"status": "restart initiated", "message": "Harness will restart in a moment"}


@router.get("/status")
async def supervisor_status():
    """Check for any pending flags."""
    return {
        "update_pending": os.path.exists(os.path.join(VOLUME_PATH, ".do_update")),
        "restart_pending": os.path.exists(os.path.join(VOLUME_PATH, ".do_restart")),
        "volume_path": VOLUME_PATH,
    }


@router.get("/models")
async def list_models():
    """Return all model entries from the models file."""
    if not MODELS_FILE.exists():
        return {"models": [], "file": str(MODELS_FILE)}

    entries = []
    for line in MODELS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 3:
            entries.append({"type": parts[0], "filename": parts[1], "url": parts[2]})

    return {"models": entries, "file": str(MODELS_FILE)}


@router.post("/models")
async def add_model(entry: ModelEntry):
    """Append a model entry to the models file. Sable uses this when given a CivitAI URL."""
    if entry.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of: {', '.join(sorted(VALID_TYPES))}")
    if not entry.filename.endswith(".safetensors"):
        raise HTTPException(status_code=400, detail="filename must end with .safetensors")
    if "civitai.com" not in entry.url:
        raise HTTPException(status_code=400, detail="url must be a CivitAI download URL")

    MODELS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Check for duplicate filename
    if MODELS_FILE.exists():
        for line in MODELS_FILE.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 3 and parts[1] == entry.filename:
                raise HTTPException(status_code=409, detail=f"{entry.filename} already exists in models file")

    with MODELS_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{entry.type} | {entry.filename} | {entry.url}\n")

    return {"status": "added", "entry": entry, "file": str(MODELS_FILE)}


@router.delete("/models/{filename}")
async def remove_model(filename: str):
    """Remove a model entry by filename."""
    if not MODELS_FILE.exists():
        raise HTTPException(status_code=404, detail="Models file not found")

    lines = MODELS_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = []
    removed = False
    for line in lines:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 3 and parts[1] == filename:
            removed = True
        else:
            new_lines.append(line)

    if not removed:
        raise HTTPException(status_code=404, detail=f"{filename} not found in models file")

    MODELS_FILE.write_text("".join(new_lines), encoding="utf-8")
    return {"status": "removed", "filename": filename}
