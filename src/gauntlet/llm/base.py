"""Shared LLM response types and backend protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(slots=True)
class LLMResponse:
    """Normalized response shape across model providers."""

    content: str
    model: str
    backend: str
    usage: dict[str, Any] | None
    raw_response: dict[str, Any]
    request_details: dict[str, Any] | None = None


class LLMBackendError(RuntimeError):
    """Structured backend failure that preserves request context."""

    def __init__(
        self,
        *,
        backend: str,
        model: str,
        message: str,
        request_details: dict[str, Any] | None = None,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        self.backend = backend
        self.model = model
        self.request_details = request_details or {}
        self.raw_response = raw_response or {}
        super().__init__(message)


class LLMBackend(Protocol):
    """Minimal protocol used by the orchestration layer."""

    backend_name: str
    model: str

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: str | None = None,
    ) -> LLMResponse:
        """Generate one response for a pair of prompts."""

    def is_available(self) -> bool:
        """Return whether the backend is healthy enough for routing."""
