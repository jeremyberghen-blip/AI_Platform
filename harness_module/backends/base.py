from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass


@dataclass
class ModelInfo:
    model_id: str
    size_mb: int | None = None
    quantization: str | None = None
    context_length: int | None = None
    family: str | None = None


@dataclass
class VRAMState:
    used_mb: int | None
    total_mb: int | None


@dataclass
class ContextStats:
    token_count: int
    context_max: int | None


@dataclass
class LoadProgress:
    status: str          # pulling | verifying | loading | ready | error
    progress: float      # 0.0 – 1.0
    message: str = ""


@dataclass
class ChatChunk:
    content: str
    done: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0


class BackendAdapter(ABC):
    """
    Common interface for all inference backends.
    Chat adapters (Ollama, vLLM) implement the full interface.
    Generation adapters (ComfyUI) implement only what applies and raise
    NotImplementedError for chat methods.
    """

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]: ...

    @abstractmethod
    async def load_model(self, model_id: str) -> AsyncGenerator[LoadProgress, None]: ...

    @abstractmethod
    async def unload_model(self) -> None: ...

    @abstractmethod
    async def get_vram_state(self) -> VRAMState: ...

    @abstractmethod
    async def get_loaded_model(self) -> str | None: ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        system_prompt: str,
        params: dict,
    ) -> AsyncGenerator[ChatChunk, None]: ...

    @abstractmethod
    async def reset_context(self) -> None: ...

    @property
    @abstractmethod
    def backend_name(self) -> str: ...
