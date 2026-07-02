"""
ComfyUI backend adapter — image/video generation via ComfyUI REST API.

ComfyUI API reference:
  GET  /object_info/CheckpointLoaderSimple — list available checkpoints
  GET  /system_stats  — VRAM and device info
  POST /prompt        — submit workflow JSON, returns { prompt_id }
  GET  /history/{id} — check completion, retrieve output filenames
  GET  /view          — download output file (?filename=&subfolder=&type=output)
  POST /free          — evict models from VRAM
"""

import uuid
from collections.abc import AsyncGenerator

import httpx

from backends.base import BackendAdapter, ChatChunk, ContextStats, LoadProgress, ModelInfo, VRAMState


class ComfyUIAdapter(BackendAdapter):
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=30.0)
        self._client_id = str(uuid.uuid4())
        self._last_checkpoint: str | None = None

    @property
    def backend_name(self) -> str:
        return "comfyui"

    async def health_check(self) -> bool:
        try:
            r = await self._client.get("/system_stats", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[ModelInfo]:
        try:
            r = await self._client.get("/object_info/CheckpointLoaderSimple", timeout=10.0)
            r.raise_for_status()
            data = r.json()
            node = data.get("CheckpointLoaderSimple", {})
            names = node.get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            return [ModelInfo(model_id=name) for name in names]
        except Exception:
            return []

    async def list_loras(self) -> list[str]:
        """Return LoRA filenames available in ComfyUI."""
        try:
            r = await self._client.get("/object_info/LoraLoader", timeout=10.0)
            r.raise_for_status()
            data = r.json()
            node = data.get("LoraLoader", {})
            names = node.get("input", {}).get("required", {}).get("lora_name", [[]])[0]
            return list(names)
        except Exception:
            return []

    async def load_model(self, model_id: str) -> AsyncGenerator[LoadProgress, None]:
        self._last_checkpoint = model_id
        yield LoadProgress(status="ready", progress=1.0, message=f"Will use {model_id} on next generation")

    async def unload_model(self) -> None:
        r = await self._client.post(
            "/free",
            json={"unload_models": True, "free_memory": True},
            timeout=15.0,
        )
        r.raise_for_status()

    async def get_vram_state(self) -> VRAMState:
        try:
            r = await self._client.get("/system_stats", timeout=5.0)
            r.raise_for_status()
            data = r.json()
            devices = data.get("devices", [{}])
            d = devices[0] if devices else {}
            total = d.get("vram_total", 0)
            free = d.get("vram_free", 0)
            used = total - free
            return VRAMState(
                used_mb=used // (1024 * 1024) if total else None,
                total_mb=total // (1024 * 1024) if total else None,
            )
        except Exception:
            return VRAMState(used_mb=None, total_mb=None)

    async def get_loaded_model(self) -> str | None:
        return self._last_checkpoint

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        params: dict,
    ) -> AsyncGenerator[ChatChunk, None]:
        raise NotImplementedError("ComfyUI does not support text chat.")
        yield

    async def reset_context(self) -> None:
        pass

    # --- ComfyUI-specific generation methods ---

    async def submit_workflow(self, workflow: dict) -> str:
        """POST /prompt — returns prompt_id."""
        payload = {"prompt": workflow, "client_id": self._client_id}
        r = await self._client.post("/prompt", json=payload, timeout=30.0)
        r.raise_for_status()
        return r.json()["prompt_id"]

    async def get_job_status(self, prompt_id: str) -> dict:
        """GET /history/{prompt_id} — returns full job dict or {} if not yet queued."""
        r = await self._client.get(f"/history/{prompt_id}", timeout=10.0)
        r.raise_for_status()
        return r.json()

    async def download_output(
        self, filename: str, subfolder: str = "", file_type: str = "output"
    ) -> bytes:
        """GET /view — returns raw image bytes."""
        r = await self._client.get(
            "/view",
            params={"filename": filename, "subfolder": subfolder, "type": file_type},
            timeout=60.0,
        )
        r.raise_for_status()
        return r.content

    async def close(self) -> None:
        await self._client.aclose()
