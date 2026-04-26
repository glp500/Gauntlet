"""Thin llama.cpp server client for local generation and review steps."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import requests

from gauntlet.config import Settings
from gauntlet.llm.base import LLMBackend, LLMBackendError, LLMResponse


class LlamaCppBackend(LLMBackend):
    """Call a running llama.cpp server through its OpenAI-compatible API."""

    backend_name = "llama_cpp"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.llama_cpp_base_url.rstrip("/")
        self.model = _default_model_name(settings.llama_cpp_model_path)

    def is_available(self) -> bool:
        """Treat llama.cpp as available only when its health endpoint responds."""
        try:
            response = requests.get(
                f"{self._base_url}/health",
                timeout=min(5, self._settings.llama_cpp_timeout_seconds),
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
        """Submit one chat completion request to llama.cpp."""
        payload: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }

        if self.model:
            payload["model"] = self.model

        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        endpoint = f"{self._base_url}/v1/chat/completions"
        started_at = datetime.now(UTC).isoformat()
        started = perf_counter()
        response: requests.Response | None = None

        try:
            response = requests.post(
                endpoint,
                json=payload,
                timeout=self._settings.llama_cpp_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            content = _extract_content(data)
        except (requests.RequestException, ValueError) as exc:
            raise LLMBackendError(
                backend=self.backend_name,
                model=self.model,
                message=f"llama.cpp request failed: {exc}",
                request_details=_build_request_details(
                    endpoint=endpoint,
                    started_at=started_at,
                    started=started,
                    response=response,
                    error_type=type(exc).__name__,
                ),
                raw_response=_safe_json_payload(response),
            ) from exc

        request_details = _build_request_details(
            endpoint=endpoint,
            started_at=started_at,
            started=started,
            response=response,
        )
        usage = data.get("usage")

        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            backend=self.backend_name,
            usage=usage if isinstance(usage, dict) else None,
            raw_response=data,
            request_details=request_details,
        )


def _extract_content(payload: dict[str, Any]) -> str:
    """Read the first assistant text block from a chat completion payload."""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("llama.cpp response did not include any choices.")

    first_choice = choices[0]
    message = first_choice.get("message", {})
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content

    raise ValueError("llama.cpp response did not include assistant text content.")


def _default_model_name(model_path: Path | None) -> str:
    """Derive a stable model name for OpenAI-compatible llama.cpp requests."""
    if model_path is None:
        return "local-model"

    return model_path.stem


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
    """Best-effort JSON extraction for failed llama.cpp responses."""
    if response is None:
        return {}

    try:
        payload = response.json()
    except ValueError:
        return {}

    if isinstance(payload, dict):
        return payload

    return {}
