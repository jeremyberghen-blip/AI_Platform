from typing import Any
from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str


class ChatParams(BaseModel):
    temperature: float = 0.8
    max_tokens: int = 2048
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1


class ChatRequest(BaseModel):
    character_id: str
    messages: list[Message]
    system_prompt: str = ""
    params: ChatParams = Field(default_factory=ChatParams)
    session_id: str | None = None


class LoadModelRequest(BaseModel):
    model_id: str


class TestEnableRequest(BaseModel):
    flush_to_disk: bool = True


class TestInjectRequest(BaseModel):
    character_id: str
    input: str
    system_prompt_override: str | None = None
    params_override: dict[str, Any] | None = None
    session_id: str | None = None


# --- Generation (ComfyUI) ---

class LoraRef(BaseModel):
    name: str
    strength: float = 0.8


class ControlNetRef(BaseModel):
    type: str
    image_b64: str
    weight: float = 0.9


class GenerationParams(BaseModel):
    model: str = ""   # empty → auto-select first available checkpoint
    loras: list[LoraRef] = Field(default_factory=list)
    controlnet: ControlNetRef | None = None
    seed: int = -1    # -1 → random
    cfg: float = 7.0
    steps: int = 25
    sampler: str = "dpmpp_2m"
    width: int = 1024
    height: int = 1024


class ImageGenerateRequest(BaseModel):
    character_id: str
    workflow_id: str | None = None
    prompt: str
    negative_prompt: str = ""
    params: GenerationParams


class VideoGenerateRequest(BaseModel):
    character_id: str
    workflow_id: str | None = None
    prompt: str
    negative_prompt: str = ""
    params: GenerationParams


class SaveWorkflowRequest(BaseModel):
    name: str
    description: str = ""
    workflow_json: dict[str, Any]
    base_model: str | None = None
    tags: list[str] = Field(default_factory=list)


class RegisterLoraRequest(BaseModel):
    name: str
    filename: str
    base_model: str
    trigger_word: str | None = None
    recommended_strength: float = 0.8
    description: str = ""
    character_tag: str | None = None


class SavePromptTemplateRequest(BaseModel):
    name: str
    category: str
    content: str
    notes: str = ""


class RateImageRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


class NotesImageRequest(BaseModel):
    notes: str
