"""
Module-level system state. Tracks installation, update, and runtime health.
The /health endpoint reports this without requiring authentication so the
frontend can distinguish failure modes before credentials are verified.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum


class ModuleStatus(str, Enum):
    STARTING = "starting"
    INSTALLING = "installing"
    UPDATING = "updating"
    READY = "ready"
    ERROR = "error"


@dataclass
class SystemState:
    status: ModuleStatus = ModuleStatus.STARTING
    progress: float = 0.0          # 0.0–1.0 during installing/updating
    message: str = ""              # human-readable detail
    error: str = ""                # set when status=error
    update_available: bool = False
    installed_version: str = "dev"
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def set_ready(self) -> None:
        async with self._lock:
            self.status = ModuleStatus.READY
            self.progress = 1.0
            self.message = ""
            self.error = ""

    async def set_installing(self, progress: float, message: str) -> None:
        async with self._lock:
            self.status = ModuleStatus.INSTALLING
            self.progress = progress
            self.message = message

    async def set_updating(self, progress: float, message: str) -> None:
        async with self._lock:
            self.status = ModuleStatus.UPDATING
            self.progress = progress
            self.message = message

    async def set_error(self, error: str) -> None:
        async with self._lock:
            self.status = ModuleStatus.ERROR
            self.error = error
            self.message = error

    def snapshot(self) -> dict:
        return {
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "installed_version": self.installed_version,
        }


system_state = SystemState()
