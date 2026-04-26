"""Thin OpenAI Responses API client."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import requests

from gauntlet.config import Settings
from gauntlet.llm.base import LLMBackend, LLMBackendError, LLMResponse


class OpenAIBackend(LLMBackend):
    """Call the OpenAI Responses API through `requests`."""

    backend_name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.model = settings.openai_model
        self._base_url = settings.openai_base_url.rstrip("/")

    def is_available(self) -> bool:
        """OpenAI is considered available when the API key is present."""
        return bool(self._settings.openai_api_key)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: str | None = None,
    ) -> LLMResponse:
        """Submit one prompt pair to the Responses API."""
        api_key = self._settings.require_openai_api_key()
        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": system_prompt,
            "input": user_prompt,
        }

        endpoint = f"{self._base_url}/responses"
        started_at = datetime.now(UTC).isoformat()
        started = perf_counter()
        response: requests.Response | None = None

        try:
            response = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._settings.request_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            content = self._extract_text(data)
        except (requests.RequestException, ValueError) as exc:
            raise LLMBackendError(
                backend=self.backend_name,
                model=self.model,
                message=f"OpenAI request failed: {exc}",
                request_details=_build_request_details(
                    endpoint=endpoint,
                    started_at=started_at,
                    started=started,
                    response=response,
                    error_type=type(exc).__name__,
                ),
            ) from exc

        request_details = _build_request_details(
            endpoint=endpoint,
            started_at=started_at,
            started=started,
            response=response,
        )

        return LLMResponse(
            content=content,
            model=data.get("model", self.model),
            backend=self.backend_name,
            usage=data.get("usage"),
            raw_response=data,
            request_details=request_details,
        )

    def _extract_text(self, payload: dict[str, Any]) -> str:
        """Read the first assistant text block from a Responses payload."""
        direct_output = payload.get("output_text")
        if isinstance(direct_output, str) and direct_output.strip():
            return direct_output

        output_items = payload.get("output", [])
        content_parts: list[str] = []

        for item in output_items:
            for content in item.get("content", []):
                text_value = content.get("text")
                if isinstance(text_value, str):
                    content_parts.append(text_value)

        if content_parts:
            return "\n".join(content_parts)

        raise ValueError(
            "OpenAI response did not include readable text content: "
            f"{json.dumps(payload)[:500]}"
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
