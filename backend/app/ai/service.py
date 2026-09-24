"""The one AI entry point every module uses.

`AIService.run_json` renders a versioned prompt, calls the provider, parses the reply
as JSON, validates it against a Pydantic schema, and retries (with the validation
error fed back to the model) when the output is invalid. Transient provider errors
(429, 5xx, timeouts) are retried with backoff. Token counts and latency are logged;
prompt and reply text are never logged, because they can contain student data.
"""

import base64
import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from functools import lru_cache
from typing import Literal, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.base import AIError, ChatProvider
from app.ai.groq_provider import GroqProvider
from app.ai.prompts import render_prompt
from app.config import Settings, get_settings

log = logging.getLogger("ai")

T = TypeVar("T", bound=BaseModel)
ModelKind = Literal["main", "fast", "vision"]

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> object:
    """Parse JSON from a model reply, tolerating code fences and surrounding prose."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


class AIService:
    def __init__(
        self,
        provider: ChatProvider,
        settings: Settings | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._provider = provider
        self._settings = settings or get_settings()
        self._sleep = sleep

    def _model_name(self, kind: ModelKind) -> str:
        s = self._settings
        return {"main": s.llm_model_main, "fast": s.llm_model_fast, "vision": s.vision_model}[kind]

    def run_json(
        self,
        prompt: str,
        variables: dict | None,
        schema: type[T],
        *,
        model: ModelKind = "main",
        images: Sequence[tuple[bytes, str]] | None = None,
        version: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """Render `prompt`, ask the model, and return a validated `schema` instance.

        `images` is a list of (bytes, mime_type) pairs, used with model="vision".
        Raises AIError (with a user-safe message) when it cannot get valid output.
        """
        rendered = render_prompt(prompt, variables, version)
        schema_text = json.dumps(schema.model_json_schema())
        system = (rendered.system or "") + (
            "\n\nReply with ONLY a single JSON object that matches this JSON Schema. "
            f"No prose, no code fences.\n{schema_text}"
        )
        user_content: str | list = rendered.user
        if images:
            user_content = [{"type": "text", "text": rendered.user}] + [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}
                for data, mime in images
            ]
        messages: list[dict] = [
            {"role": "system", "content": system.strip()},
            {"role": "user", "content": user_content},
        ]
        model_name = self._model_name(model)

        last_error = "invalid output"
        for attempt in range(self._settings.ai_max_retries + 1):
            result = self._chat_with_backoff(model_name, messages, temperature, max_tokens)
            log.info(
                "ai_call prompt=%s.v%s model=%s attempt=%s prompt_tokens=%s completion_tokens=%s latency=%.2fs",
                rendered.name,
                rendered.version,
                model_name,
                attempt + 1,
                result.prompt_tokens,
                result.completion_tokens,
                result.latency_s,
            )
            try:
                return schema.model_validate(extract_json(result.text))
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)[:500]
                log.warning("ai_invalid_output prompt=%s attempt=%s", rendered.name, attempt + 1)
                messages += [
                    {"role": "assistant", "content": result.text},
                    {
                        "role": "user",
                        "content": f"That reply was not valid: {last_error}\nReply again with ONLY the corrected JSON object.",
                    },
                ]
        raise AIError("The AI returned an unusable answer. Please try again.")

    def _chat_with_backoff(self, model: str, messages: list[dict], temperature, max_tokens):
        max_tries = self._settings.ai_max_transport_retries + 1
        for attempt in range(max_tries):
            try:
                return self._provider.chat(
                    model=model, messages=messages, json_mode=True, temperature=temperature, max_tokens=max_tokens
                )
            except AIError as exc:
                if not exc.retryable or attempt == max_tries - 1:
                    raise
                delay = exc.retry_after if exc.retry_after is not None else 2**attempt
                self._sleep(min(delay, 20))
        raise AIError("The AI service is unavailable.")  # unreachable


@lru_cache
def get_ai_service() -> AIService:
    """Shared instance for the app. Built lazily so the app starts without an API key."""
    settings = get_settings()
    return AIService(GroqProvider(settings), settings)
