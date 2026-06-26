import asyncio
import os
import signal

from fastapi import APIRouter

from config import settings

router = APIRouter(prefix="/admin", tags=["admin"])

VOLUME_PATH = settings.volume_path


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
