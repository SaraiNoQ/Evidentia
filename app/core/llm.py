import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class LLMRequest:
    model: str
    messages: list[dict[str, str]]
    temperature: float = 0.0
    response_format: dict[str, Any] | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None
    thinking_enabled: bool | None = None


@dataclass(frozen=True)
class LLMResponse:
    model: str
    content: str
    raw: dict[str, Any]
    token_usage: dict[str, int]
    warnings: list[str]


class LLMAdapter(ABC):
    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatibleLLMAdapter(LLMAdapter):
    """Minimal OpenAI-compatible chat completions adapter."""

    def __init__(
        self,
        *,
        base_url: str | None,
        api_key_env: str = "OPENAI_API_KEY",
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.base_url = (base_url or "https://api.openai.com").rstrip("/")
        self.api_key_env = api_key_env
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def complete(self, request: LLMRequest) -> LLMResponse:
        api_key = self.api_key or os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key. Set {self.api_key_env} or adapter api_key.")

        payload = self._payload(request, include_provider_options=True)
        warnings: list[str] = []
        try:
            raw = await self._post(payload, api_key)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400 and self._has_provider_options(request):
                warnings.append("llm_provider_options_retry_without_reasoning_fields")
                raw = await self._post(
                    self._payload(request, include_provider_options=False),
                    api_key,
                )
            else:
                raise

        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        usage = raw.get("usage") or {}
        token_usage = {
            key: int(value)
            for key, value in usage.items()
            if isinstance(key, str) and isinstance(value, int)
        }
        return LLMResponse(
            model=str(raw.get("model") or request.model),
            content=str(content),
            raw=raw,
            token_usage=token_usage,
            warnings=warnings,
        )

    def _payload(self, request: LLMRequest, *, include_provider_options: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "stream": False,
        }
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if include_provider_options and request.reasoning_effort is not None:
            payload["reasoning_effort"] = request.reasoning_effort
        if include_provider_options and request.thinking_enabled is not None:
            payload["thinking"] = {"enabled": request.thinking_enabled}
        return payload

    def _has_provider_options(self, request: LLMRequest) -> bool:
        return request.reasoning_effort is not None or request.thinking_enabled is not None

    async def _post(self, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("LLM response must be a JSON object.")
            return data
