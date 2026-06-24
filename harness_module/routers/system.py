"""
System management endpoints: update, rollback, version info.
Update mechanism: pulls new code from git onto the network volume,
restarts the harness module process without replacing the pod.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from core.event_bus import event_bus
from core.system_state import ModuleStatus, system_state

router = APIRouter()


class UpdateRequest(BaseModel):
    source: str = "git"                    # git | url
    ref: str = "main"                      # git branch/tag/sha
    repo: str = ""                         # git repo URL (if different from installed)
    components: list[str] = ["harness_module"]


@router.get("/system/status")
async def system_status_detail() -> dict:
    """Full system status including backend, version, update availability."""
    return system_state.snapshot()


@router.post("/system/update")
async def trigger_update(body: UpdateRequest, background_tasks: BackgroundTasks, request: Request) -> dict:
    """
    Trigger a code update without replacing the pod.
    Returns 202 immediately. Progress streams on /v1/events.

    Phase 1: stubs the update logic and documents the full implementation plan.
    Phase 2: implement git pull + graceful restart.
    """
    if system_state.status in (ModuleStatus.INSTALLING, ModuleStatus.UPDATING):
        raise HTTPException(status_code=409, detail=f"Cannot update while status is {system_state.status.value}")

    background_tasks.add_task(_run_update, body, request.app)
    return {"accepted": True, "message": "Update started. Watch /v1/events for progress."}


@router.post("/system/rollback")
async def trigger_rollback(request: Request) -> dict:
    """
    Roll back to the previous version (harness_module_prev/ on the volume).
    Returns 202 immediately. Progress streams on /v1/events.
    """
    if system_state.status in (ModuleStatus.INSTALLING, ModuleStatus.UPDATING):
        raise HTTPException(status_code=409, detail="Cannot rollback while update/install is in progress")

    # Phase 2: swap harness_module/ and harness_module_prev/ then restart
    raise HTTPException(status_code=501, detail="Rollback not yet implemented. See Phase 2 plan.")


async def _run_update(body: UpdateRequest, app) -> None:
    """
    Full update procedure (Phase 2 implementation):

    1. Download new code to volume/harness_module_next/
       - git: git clone --depth 1 --branch {ref} {repo} harness_module_next/
       - url: download tarball, extract to harness_module_next/

    2. Verify: python -m py_compile on all .py files

    3. Stop harness module process (supervisorctl stop harness OR send SIGTERM to self)
       - Ollama process is NOT stopped — only harness module restarts

    4. Rotate:
       mv harness_module/ harness_module_prev/    (keep for rollback)
       mv harness_module_next/ harness_module/

    5. Install new deps:
       pip install -r harness_module/requirements.txt

    6. Restart:
       exec python harness_module/main.py   (or supervisorctl start harness)

    Current: placeholder that simulates progress and publishes events.
    """
    await system_state.set_updating(0.0, "Starting update")
    await event_bus.publish("system_update", {"step": "start", "ref": body.ref})

    # Placeholder steps — replace with real implementation in Phase 2
    steps = [
        (0.1, "Downloading new version"),
        (0.4, "Verifying code"),
        (0.6, "Stopping services"),
        (0.8, "Swapping code"),
        (0.9, "Installing dependencies"),
        (1.0, "Restarting"),
    ]

    for progress, message in steps:
        await asyncio.sleep(0.5)
        await system_state.set_updating(progress, message)
        await event_bus.publish("system_update", {"step": message, "progress": progress})

    # TODO Phase 2: exec restart here. For now, just go back to ready.
    await system_state.set_ready()
    await event_bus.publish("system_update", {"step": "complete", "progress": 1.0})
    await event_bus.publish("server_ready", {"message": "Update complete"})
