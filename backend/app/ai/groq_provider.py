"""Groq implementation of ChatProvider (OpenAI-compatible chat completions API)."""

import logging
import re
import time

import httpx

from app.ai.base import AIError, ChatResult
from app.config import Settings

log = logging.getLogger("ai")

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


class GroqProvider:
    def __init__(self, settings: Settings):
        if not settings.groq_api_key:
            raise AIError("The AI service is not configured. Set GROQ_API_KEY in .env.")
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.groq_base_url,
            headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            timeout=settings.ai_timeout_s,
        )

    def chat(
        self,
        *,
        model: str,
        messages: list[dict],
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        body: dict = {"model": model, "messages": messages}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_completion_tokens"] = max_tokens
        if model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = self._settings.llm_reasoning_effort

        started = time.perf_counter()
        try:
            resp = self._client.post("/chat/completions", json=body)
        except httpx.TimeoutException:
            raise AIError("The AI service took too long to respond.", retryable=True) from None
        except httpx.HTTPError:
            raise AIError("Couldn't reach the AI service. Check the internet connection.", retryable=True) from None

        if resp.status_code != 200:
            raise self._to_error(resp)

        data = resp.json()
        text = data["choices"][0]["message"].get("content") or ""
        usage = data.get("usage") or {}
        return ChatResult(
            text=_THINK_BLOCK.sub("", text).strip(),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_s=time.perf_counter() - started,
        )

    @staticmethod
    def _to_error(resp: httpx.Response) -> AIError:
        # Log the status only. Never log request bodies: they can contain student text.
        log.warning("Groq returned HTTP %s", resp.status_code)
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            return AIError(
                "The AI service is busy (rate limit). Please try again in a moment.",
                retryable=True,
                retry_after=float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else None,
            )
        if resp.status_code >= 500:
            return AIError("The AI service had a temporary problem.", retryable=True)
        if resp.status_code in (401, 403):
            return AIError("The AI service rejected the API key. Check GROQ_API_KEY in .env.")
        return AIError("The AI service couldn't process that request.")
