import json
from collections.abc import AsyncGenerator

import httpx

from backends.base import BackendAdapter, ChatChunk, ContextStats, LoadProgress, ModelInfo, VRAMState


class OllamaAdapter(BackendAdapter):
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=300.0)
        self._loaded_model: str | None = None

    @property
    def backend_name(self) -> str:
        return "ollama"

    async def health_check(self) -> bool:
        try:
            r = await self._client.get("/api/tags", timeout=5.0)
            return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[ModelInfo]:
        r = await self._client.get("/api/tags")
        r.raise_for_status()
        data = r.json()
        models = []
        for m in data.get("models", []):
            details = m.get("details", {})
            size_bytes = m.get("size", 0)
            models.append(ModelInfo(
                model_id=m["name"],
                size_mb=size_bytes // (1024 * 1024) if size_bytes else None,
                quantization=details.get("quantization_level"),
                context_length=None,
                family=details.get("family"),
            ))
        return models

    async def load_model(self, model_id: str) -> AsyncGenerator[LoadProgress, None]:
        """
        Ollama loads models on first use, but we can pre-pull them.
        Streams pull progress if the model isn't already present.
        After pulling, warms up the model by sending an empty generate request.
        """
        async with self._client.stream(
            "POST",
            "/api/pull",
            json={"name": model_id, "stream": True},
            timeout=600.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                status = data.get("status", "")
                total = data.get("total", 0)
                completed = data.get("completed", 0)
                progress = (completed / total) if total > 0 else 0.0

                if "error" in data:
                    yield LoadProgress(status="error", progress=0.0, message=data["error"])
                    return

                yield LoadProgress(status="pulling", progress=progress, message=status)

        # Warm up: send an empty prompt so the model loads into VRAM
        yield LoadProgress(status="loading", progress=0.95, message="Loading into memory")
        try:
            await self._client.post(
                "/api/generate",
                json={"model": model_id, "prompt": "", "stream": False},
                timeout=120.0,
            )
            self._loaded_model = model_id
            yield LoadProgress(status="ready", progress=1.0, message=f"{model_id} ready")
        except Exception as e:
            yield LoadProgress(status="error", progress=0.0, message=str(e))

    async def unload_model(self) -> None:
        if not self._loaded_model:
            return
        # Setting keep_alive=0 tells Ollama to unload the model from memory immediately
        await self._client.post(
            "/api/generate",
            json={"model": self._loaded_model, "keep_alive": 0},
            timeout=30.0,
        )
        self._loaded_model = None

    async def get_vram_state(self) -> VRAMState:
        try:
            r = await self._client.get("/api/ps", timeout=5.0)
            r.raise_for_status()
            data = r.json()
            models = data.get("models", [])
            if models:
                m = models[0]
                size_vram = m.get("size_vram", 0)
                return VRAMState(used_mb=size_vram // (1024 * 1024), total_mb=None)
        except Exception:
            pass
        return VRAMState(used_mb=None, total_mb=None)

    async def get_loaded_model(self) -> str | None:
        try:
            r = await self._client.get("/api/ps", timeout=5.0)
            r.raise_for_status()
            models = r.json().get("models", [])
            if models:
                self._loaded_model = models[0]["name"]
                return self._loaded_model
        except Exception:
            pass
        return self._loaded_model

    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        params: dict,
    ) -> AsyncGenerator[ChatChunk, None]:
        # /api/chat requires system prompt as the first message, not a top-level field
        messages_with_system = (
            [{"role": "system", "content": system_prompt}] + messages
            if system_prompt
            else messages
        )
        payload = {
            "model": self._loaded_model or params.get("model", ""),
            "messages": messages_with_system,
            "stream": True,
            "options": {
                "temperature": params.get("temperature", 0.8),
                "num_predict": params.get("max_tokens", 2048),
                "top_p": params.get("top_p", 0.9),
                "top_k": params.get("top_k", 40),
                "repeat_penalty": params.get("repeat_penalty", 1.1),
            },
        }

        async with self._client.stream(
            "POST",
            "/api/chat",
            json=payload,
            timeout=300.0,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if data.get("done"):
                    yield ChatChunk(
                        content="",
                        done=True,
                        prompt_tokens=data.get("prompt_eval_count", 0),
                        completion_tokens=data.get("eval_count", 0),
                    )
                else:
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield ChatChunk(content=content, done=False)

    async def reset_context(self) -> None:
        # Ollama manages KV cache per-request via the messages array.
        # "Resetting context" from the module's perspective means the
        # session_manager clears its message history. Nothing to do here.
        pass

    async def close(self) -> None:
        await self._client.aclose()
