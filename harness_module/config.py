from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HARNESS_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    api_key: str
    backend_type: Literal["ollama", "comfyui"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    comfyui_base_url: str = "http://localhost:8188"
    storage_path: Path = Path("./storage")
    volume_path: str = "/workspace"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"
    test_mode: bool = False


settings = Settings()
