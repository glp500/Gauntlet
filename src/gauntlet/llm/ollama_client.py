"""Thin Ollama API client for local fallback and review steps."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import requests

from gauntlet.config import Settings
from gauntlet.llm.base import LLMBackend, LLMBackendError, LLMResponse


class OllamaBackend(LLMBackend):
    """Call a local Ollama instance through its HTTP API."""

    backend_name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model = settings.ollama_model
        self._base_url = settings.ollama_base_url.rstrip("/")

    def is_available(self) -> bool:
        """Treat Ollama as available only when the endpoint responds."""
        try:
            response = requests.get(
                f"{self._base_url}/tags",
                timeout=min(5, self._settings.request_timeout_seconds),
            )
            response.raise_for_status()
        except requests.RequestException:
            return False

        return True

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: str | None = None,
    ) -> LLMResponse:
        """Submit one non-streaming generate request to Ollama."""
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
        }

        if response_format == "json":
            payload["format"] = "json"

        endpoint = f"{self._base_url}/generate"
        started_at = datetime.now(UTC).isoformat()
        started = perf_counter()
        response: requests.Response | None = None

        try:
            response = requests.post(
                endpoint,
                json=payload,
                timeout=self._settings.request_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise LLMBackendError(
                backend=self.backend_name,
                model=self.model,
                message=f"Ollama request failed: {exc}",
                request_details=_build_request_details(
                    endpoint=endpoint,
                    started_at=started_at,
                    started=started,
                    response=response,
                    error_type=type(exc).__name__,
                ),
                raw_response=_safe_json_payload(response),
            ) from exc

        usage = {
            "prompt_tokens": data.get("prompt_eval_count"),
            "completion_tokens": data.get("eval_count"),
            "total_duration": data.get("total_duration"),
        }
        request_details = _build_request_details(
            endpoint=endpoint,
            started_at=started_at,
            started=started,
            response=response,
        )

        return LLMResponse(
            content=data.get("response", ""),
            model=data.get("model", self.model),
            backend=self.backend_name,
            usage=usage,
            raw_response=data,
            request_details=request_details,
        )


def _build_request_details(
    *,
    endpoint: str,
    started_at: str,
    started: float,
    response: requests.Response | None,
    error_type: str | None = None,
) -> dict[str, Any]:
    """Capture consistent request metadata for debugging and run logs."""
    details: dict[str, Any] = {
        "endpoint": endpoint,
        "started_at": started_at,
        "ended_at": datetime.now(UTC).isoformat(),
        "duration_seconds": round(perf_counter() - started, 3),
    }

    if response is not None:
        details["status_code"] = response.status_code

    if error_type is not None:
        details["error_type"] = error_type

    return details


def _safe_json_payload(response: requests.Response | None) -> dict[str, Any]:
    """Best-effort JSON extraction for failed Ollama responses."""
    if response is None:
        return {}

    try:
        payload = response.json()
    except ValueError:
        return {}

    if isinstance(payload, dict):
        return payload

    return {}
