from typing import Any
from pydantic import BaseModel


class StatusResponse(BaseModel):
    ok: bool
    backend: str
    backend_url: str
    model_loaded: str | None
    vram_used_mb: int | None
    vram_total_mb: int | None
    context_tokens: int
    context_max: int | None
    session_id: str | None
    active_character: str | None
    uptime_seconds: float
    test_mode: bool


class ModelInfo(BaseModel):
    model_id: str
    size_mb: int | None
    quantization: str | None
    context_length: int | None
    family: str | None


class ModelListResponse(BaseModel):
    models: list[ModelInfo]
    loaded: str | None


class LoadJobResponse(BaseModel):
    job_id: str
    model_id: str
    status: str


class SessionInfo(BaseModel):
    session_id: str
    character_id: str
    model_id: str | None
    started_at: str
    closed_at: str | None
    message_count: int
    total_prompt_tokens: int
    total_completion_tokens: int


class SessionListResponse(BaseModel):
    sessions: list[SessionInfo]
    total: int


class SessionLogEntry(BaseModel):
    seq: int
    role: str
    content: str
    timestamp: str
    tokens: int | None = None
    latency_ms: int | None = None


class ContextInfo(BaseModel):
    session_id: str
    message_count: int
    estimated_tokens: int
    context_max: int | None


class CaptureInfo(BaseModel):
    capture_id: str
    timestamp: str
    character_id: str
    session_id: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_latency_ms: int | None


class CaptureTiming(BaseModel):
    backend_first_token_ms: int | None
    backend_total_ms: int | None
    output_parsing_ms: int | None


class CaptureDetail(BaseModel):
    capture_id: str
    timestamp: str
    character_id: str
    session_id: str | None
    system_prompt: str
    messages_sent: list[dict[str, Any]]
    backend_request: dict[str, Any]
    backend_response_raw: str
    parsed_output: str
    timing: CaptureTiming
    token_counts: dict[str, int]


class TestStatus(BaseModel):
    enabled: bool
    flush_to_disk: bool
    capture_count: int


# --- Generation (ComfyUI) ---

class GenerationJobResponse(BaseModel):
    job_id: str
    character_id: str
    status: str
    progress: float = 0.0
    estimated_seconds: int | None = None
    created_at: str
    image_b64: str | None = None
    seed: int | None = None
    checkpoint: str | None = None


class WorkflowInfo(BaseModel):
    workflow_id: str
    name: str
    description: str
    base_model: str | None
    tags: list[str]
    created_at: str
    updated_at: str


class LoraInfo(BaseModel):
    lora_id: str
    name: str
    filename: str
    base_model: str
    trigger_word: str | None
    recommended_strength: float
    description: str
    character_tag: str | None
    created_at: str


class ImageCatalogEntry(BaseModel):
    image_id: str
    character_id: str
    session_id: str
    filename: str
    prompt: str
    negative_prompt: str | None
    model: str
    loras: list[dict[str, Any]]
    controlnet_type: str | None
    seed: int | None
    cfg: float | None
    steps: int | None
    width: int | None
    height: int | None
    character_tags: list[str]
    style_tags: list[str]
    rating: int | None
    notes: str | None
    created_at: str


class PromptTemplate(BaseModel):
    template_id: str
    name: str
    category: str
    content: str
    notes: str
    created_at: str
