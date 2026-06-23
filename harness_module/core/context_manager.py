from schemas.requests import Message


class ContextManager:
    """
    Owns the live message history for one session.
    The harness sends messages; this manager tracks them and feeds the backend.
    """

    def __init__(self, session_id: str, character_id: str) -> None:
        self.session_id = session_id
        self.character_id = character_id
        self._messages: list[Message] = []

    def set_messages(self, messages: list[Message]) -> None:
        """Replace the full message history (harness-authoritative mode)."""
        self._messages = list(messages)

    def append_assistant(self, content: str) -> None:
        self._messages.append(Message(role="assistant", content=content))

    def get_messages(self) -> list[Message]:
        return list(self._messages)

    def message_count(self) -> int:
        return len(self._messages)

    def estimated_tokens(self) -> int:
        """Very rough estimate: 4 chars ≈ 1 token."""
        total_chars = sum(len(m.content) for m in self._messages)
        return total_chars // 4

    def reset(self) -> None:
        self._messages = []
