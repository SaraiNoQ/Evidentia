from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LLMRequest:
    model: str
    messages: list[dict[str, str]]
    temperature: float = 0.0
    response_format: dict[str, Any] | None = None


@dataclass(frozen=True)
class LLMResponse:
    model: str
    content: str
    raw: dict[str, Any]


class LLMAdapter(ABC):
    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatibleLLMAdapter(LLMAdapter):
    """Phase 0 adapter skeleton; network calls are intentionally not implemented yet."""

    def __init__(self, *, base_url: str | None, api_key_env: str) -> None:
        self.base_url = base_url
        self.api_key_env = api_key_env

    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("LLM calls are introduced after the Paper IR kernel is stable.")
