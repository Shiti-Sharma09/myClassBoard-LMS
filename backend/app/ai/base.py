"""Provider-neutral types for the AI layer."""

from dataclasses import dataclass
from typing import Protocol


class AIError(Exception):
    """Raised when an AI call fails for good. `message` is safe to show to a user."""

    def __init__(self, message: str, *, retryable: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.retry_after = retry_after


@dataclass
class ChatResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0


class ChatProvider(Protocol):
    """Anything that can answer a chat request. Groq today; swap by writing another class."""

    def chat(
        self,
        *,
        model: str,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult: ...
