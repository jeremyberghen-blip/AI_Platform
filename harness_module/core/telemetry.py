import time
from dataclasses import dataclass, field


@dataclass
class RequestTelemetry:
    session_id: str
    character_id: str
    model_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0

    _start: float = field(default_factory=time.perf_counter, repr=False)
    _first_token: float | None = field(default=None, repr=False)
    _end: float | None = field(default=None, repr=False)

    def mark_first_token(self) -> None:
        if self._first_token is None:
            self._first_token = time.perf_counter()

    def mark_done(self) -> None:
        self._end = time.perf_counter()

    @property
    def first_token_ms(self) -> int | None:
        if self._first_token is None:
            return None
        return int((self._first_token - self._start) * 1000)

    @property
    def total_ms(self) -> int | None:
        if self._end is None:
            return None
        return int((self._end - self._start) * 1000)

    @property
    def tokens_per_second(self) -> float | None:
        if self._end is None or self.completion_tokens == 0 or self._first_token is None:
            return None
        duration = self._end - self._first_token
        if duration <= 0:
            return None
        return self.completion_tokens / duration

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "character_id": self.character_id,
            "model_id": self.model_id,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "first_token_ms": self.first_token_ms,
            "total_ms": self.total_ms,
            "tokens_per_second": self.tokens_per_second,
        }
