"""Tests for the llama.cpp backend client."""

from __future__ import annotations

from pathlib import Path

import pytest

from gauntlet.config import Settings
from gauntlet.llm.base import LLMBackendError
from gauntlet.llm.llama_cpp_client import LlamaCppBackend


class FakeResponse:
    """Small fake requests response object for backend tests."""

    def __init__(self, payload: dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")

    def json(self) -> dict[str, object]:
        return self._payload


def test_llama_cpp_backend_parses_chat_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The backend should normalize a llama.cpp chat completion payload."""
    monkeypatch.setenv("LLAMA_CPP_MODEL_PATH", str(tmp_path / "models" / "gemma.gguf"))
    settings = Settings.from_env(project_root=tmp_path)
    backend = LlamaCppBackend(settings)

    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        assert url == "http://localhost:8080/v1/chat/completions"
        assert json["response_format"] == {"type": "json_object"}
        assert timeout == settings.llama_cpp_timeout_seconds
        return FakeResponse(
            {
                "model": "local-model",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": '{"status":"ok"}'},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        )

    monkeypatch.setattr("gauntlet.llm.llama_cpp_client.requests.post", fake_post)

    response = backend.generate("system", "user", response_format="json")

    assert response.backend == "llama_cpp"
    assert response.content == '{"status":"ok"}'
    assert response.usage == {"prompt_tokens": 10, "completion_tokens": 5}
    assert response.request_details is not None
    assert response.request_details["status_code"] == 200


def test_llama_cpp_backend_raises_structured_error_on_invalid_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The backend should preserve context when the server returns an unreadable payload."""
    settings = Settings.from_env(project_root=tmp_path)
    backend = LlamaCppBackend(settings)

    def fake_post(url: str, json: dict[str, object], timeout: int) -> FakeResponse:
        return FakeResponse({"choices": []})

    monkeypatch.setattr("gauntlet.llm.llama_cpp_client.requests.post", fake_post)

    with pytest.raises(LLMBackendError, match="llama.cpp request failed"):
        backend.generate("system", "user")
