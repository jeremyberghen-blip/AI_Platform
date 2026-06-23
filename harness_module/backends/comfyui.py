"""
ComfyUI backend adapter — stub implementation.

This adapter will drive ComfyUI's REST + WebSocket API for image and video generation.
All methods currently raise NotImplementedError with notes on the intended implementation.

ComfyUI API reference:
  POST /prompt           — submit a workflow JSON, returns { prompt_id }
  GET  /history/{id}     — check completion, retrieve output filenames
  GET  /view             — download output file (?filename=&subfolder=&type=output)
  WS   /ws?clientId={id} — real-time progress events (execution_start, executing, progress, executed)
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
        # ComfyUI exposes /object_info which includes model lists per node type.
        # Will parse CheckpointLoaderSimple options to get available checkpoints.
        raise NotImplementedError(
            "ComfyUI list_models: query GET /object_info, extract "
            "object_info.CheckpointLoaderSimple.input.required.ckpt_name[0]"
        )

    async def load_model(self, model_id: str) -> AsyncGenerator[LoadProgress, None]:
        # ComfyUI loads models on first use within a workflow.
        # "Loading" here means verifying the model file exists on the network volume.
        raise NotImplementedError(
            "ComfyUI load_model: verify model exists at /models/checkpoints/{model_id} "
            "on the network volume. Actual loading happens at generation time."
        )
        yield  # make this a generator

    async def unload_model(self) -> None:
        # ComfyUI has no explicit unload; VRAM is managed by its model cache.
        # POST /free with { "unload_models": true } clears loaded models.
        raise NotImplementedError(
            "ComfyUI unload_model: POST /free with { 'unload_models': true, 'free_memory': true }"
        )

    async def get_vram_state(self) -> VRAMState:
        # GET /system_stats returns { "devices": [{ "vram_total": ..., "vram_free": ... }] }
        raise NotImplementedError(
            "ComfyUI get_vram_state: GET /system_stats, parse devices[0].vram_total and vram_free"
        )

    async def get_loaded_model(self) -> str | None:
        # ComfyUI tracks loaded models internally; no direct API to query the active checkpoint.
        raise NotImplementedError(
            "ComfyUI get_loaded_model: not directly exposed. "
            "Track last submitted workflow's checkpoint name in adapter state."
        )

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        params: dict,
    ) -> AsyncGenerator[ChatChunk, None]:
        raise NotImplementedError(
            "ComfyUI does not support text chat. "
            "Use the generation endpoints (/v1/generate/image, /v1/generate/video) instead."
        )
        yield  # make this a generator

    async def reset_context(self) -> None:
        # No context to reset for generation backend.
        pass

    # --- ComfyUI-specific methods (not in BackendAdapter base) ---

    async def submit_workflow(self, workflow: dict) -> str:
        """
        POST /prompt with the ComfyUI workflow JSON.
        Returns the prompt_id for tracking.

        Implementation plan:
        1. Add { "client_id": self._client_id } to the payload
        2. POST to /prompt
        3. Extract and return response["prompt_id"]
        4. Connect WebSocket at /ws?clientId={self._client_id} to stream progress events
        """
        raise NotImplementedError(
            "ComfyUI submit_workflow: POST /prompt with { 'prompt': workflow, 'client_id': client_id }"
        )

    async def get_job_status(self, prompt_id: str) -> dict:
        """
        GET /history/{prompt_id}
        Returns job status and output file list when complete.
        """
        raise NotImplementedError(
            "ComfyUI get_job_status: GET /history/{prompt_id}, "
            "check outputs[prompt_id].status.completed"
        )

    async def download_output(self, filename: str, subfolder: str = "", file_type: str = "output") -> bytes:
        """
        GET /view?filename={filename}&subfolder={subfolder}&type={file_type}
        Returns raw image/video bytes.
        """
        raise NotImplementedError(
            "ComfyUI download_output: GET /view with filename, subfolder, type params"
        )

    async def stream_progress(self, prompt_id: str) -> AsyncGenerator[dict, None]:
        """
        Connect to ws://{host}/ws?clientId={client_id} and stream progress events.
        Filter for events matching prompt_id.

        Event types: queue_remaining, execution_start, executing, progress, executed, error
        """
        raise NotImplementedError(
            "ComfyUI stream_progress: WebSocket at /ws?clientId={client_id}, "
            "filter messages where data.prompt_id == prompt_id"
        )
        yield  # make this a generator

    async def close(self) -> None:
        await self._client.aclose()
