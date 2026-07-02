import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import AuthMiddleware
from backends.comfyui import ComfyUIAdapter
from backends.ollama import OllamaAdapter
from config import settings
from core.event_bus import event_bus
from core.session_manager import SessionManager
from core.storage_manager import StorageManager
from core.system_state import system_state
from core.test_capture import TestCaptureManager
from routers import admin, chat, context, events, generate, models, sessions, status, system, test_router

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger("harness_module")


def _build_backend():
    if settings.backend_type == "comfyui":
        logger.info("Backend: ComfyUI at %s", settings.comfyui_base_url)
        return ComfyUIAdapter(settings.comfyui_base_url)
    logger.info("Backend: Ollama at %s", settings.ollama_base_url)
    return OllamaAdapter(settings.ollama_base_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Harness Module starting up")

    storage = StorageManager(settings.storage_path)
    await storage.init()

    backend = _build_backend()
    ok = await backend.health_check()
    if not ok:
        logger.warning("Backend health check failed — backend may not be ready yet")
    else:
        logger.info("Backend healthy")

    # ComfyUI is always available as a secondary adapter for image generation,
    # regardless of which backend handles chat.
    comfyui_adapter = ComfyUIAdapter(settings.comfyui_base_url)
    comfyui_ok = await comfyui_adapter.health_check()
    if comfyui_ok:
        logger.info("ComfyUI healthy at %s", settings.comfyui_base_url)
    else:
        logger.info("ComfyUI not reachable at %s (will retry on first generation request)", settings.comfyui_base_url)

    capture_mgr = TestCaptureManager(
        storage_path=settings.storage_path,
        flush_to_disk=True,
    )
    if settings.test_mode:
        capture_mgr.enable()
        logger.info("Test/inspection mode enabled at startup")

    app.state.backend = backend
    app.state.comfyui = comfyui_adapter
    app.state.session_manager = SessionManager()
    app.state.storage = storage
    app.state.test_capture = capture_mgr

    await system_state.set_ready()
    await event_bus.publish("server_ready", {
        "backend": backend.backend_name,
        "backend_url": str(settings.ollama_base_url if settings.backend_type == "ollama" else settings.comfyui_base_url),
        "test_mode": capture_mgr.enabled,
    })

    yield

    logger.info("Harness Module shutting down")
    closed_sessions = await app.state.session_manager.close_all()
    for session in closed_sessions:
        await storage.write_session_metadata(session.to_dict())
        await storage.upsert_session(session.to_dict())
        logger.info("Closed session %s", session.session_id)

    await storage.close()
    await event_bus.shutdown()

    if hasattr(backend, "close"):
        await backend.close()

    await comfyui_adapter.close()

    logger.info("Shutdown complete")


app = FastAPI(
    title="Harness Module",
    description="AI Harness — inference module with test/inspection layer",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",        # Tauri desktop app
        "https://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)

# All routes under /v1
app.include_router(status.router, prefix="/v1")
app.include_router(models.router, prefix="/v1")
app.include_router(chat.router, prefix="/v1")
app.include_router(context.router, prefix="/v1")
app.include_router(sessions.router, prefix="/v1")
app.include_router(events.router, prefix="/v1")
app.include_router(test_router.router, prefix="/v1")
app.include_router(generate.router, prefix="/v1")
app.include_router(system.router, prefix="/v1")
app.include_router(admin.router, prefix="/v1")


@app.get("/")
async def root():
    return {"service": "harness_module", "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def health():
    """
    Unauthenticated. Returns module health with enough detail for the
    frontend to distinguish failure modes without valid credentials.

    status values:
      starting    — process just launched, not yet ready
      installing  — first boot, installing software to network volume
      updating    — applying a code update
      ready       — fully operational
      error       — unrecoverable error (see 'error' field)
    """
    snap = system_state.snapshot()
    return {
        "ok": snap["status"] == "ready",
        "status": snap["status"],
        "progress": snap["progress"],
        "message": snap["message"],
        "error": snap["error"],
        "version": snap["installed_version"],
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )
