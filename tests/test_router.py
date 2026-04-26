"""Tests for step routing policy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from gauntlet.config import Settings
from gauntlet.llm.base import LLMResponse
from gauntlet.orchestrator.router import StepRouter


@dataclass
class StubBackend:
    """Simple backend stub for routing tests."""

    backend_name: str
    model: str
    available: bool = True

    def generate(self, system_prompt: str, user_prompt: str, response_format: str | None = None) -> LLMResponse:
        raise NotImplementedError

    def is_available(self) -> bool:
        return self.available


def test_router_uses_openai_for_codegen_by_default(tmp_path: Path) -> None:
    """Code generation should default to OpenAI when not configured otherwise."""
    settings = Settings.from_env(project_root=tmp_path)
    router = StepRouter(
        settings=settings,
        openai_backend=StubBackend("openai", "openai-model"),
        ollama_backend=StubBackend("ollama", "ollama-model"),
        llama_cpp_backend=StubBackend("llama_cpp", "llama-cpp-model"),
    )

    backend = router.select_backend("generate_code")

    assert backend.backend_name == "openai"


def test_router_uses_ollama_for_codegen_when_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Code generation should route to Ollama when generation backend requests it."""
    monkeypatch.setenv("GENERATION_BACKEND", "ollama")
    settings = Settings.from_env(project_root=tmp_path)
    router = StepRouter(
        settings=settings,
        openai_backend=StubBackend("openai", "openai-model"),
        ollama_backend=StubBackend("ollama", "ollama-model"),
        llama_cpp_backend=StubBackend("llama_cpp", "llama-cpp-model"),
    )

    backend = router.select_backend("generate_code")

    assert backend.backend_name == "ollama"


def test_router_requires_healthy_ollama_for_review(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Review routing should fail cleanly when Ollama is explicitly requested but unavailable."""
    monkeypatch.setenv("REVIEW_BACKEND", "ollama")
    settings = Settings.from_env(project_root=tmp_path)
    router = StepRouter(
        settings=settings,
        openai_backend=StubBackend("openai", "openai-model"),
        ollama_backend=StubBackend("ollama", "ollama-model", available=False),
        llama_cpp_backend=StubBackend("llama_cpp", "llama-cpp-model"),
    )

    with pytest.raises(RuntimeError, match="unavailable"):
        router.select_backend("review_code")


def test_router_requires_healthy_ollama_for_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Generation routing should fail cleanly when Ollama is explicitly requested but unavailable."""
    monkeypatch.setenv("GENERATION_BACKEND", "ollama")
    settings = Settings.from_env(project_root=tmp_path)
    router = StepRouter(
        settings=settings,
        openai_backend=StubBackend("openai", "openai-model"),
        ollama_backend=StubBackend("ollama", "ollama-model", available=False),
        llama_cpp_backend=StubBackend("llama_cpp", "llama-cpp-model"),
    )

    with pytest.raises(RuntimeError, match="unavailable"):
        router.select_backend("generate_code")


def test_router_uses_llama_cpp_when_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Code generation should route to llama.cpp when generation backend requests it."""
    monkeypatch.setenv("GENERATION_BACKEND", "llama_cpp")
    settings = Settings.from_env(project_root=tmp_path)
    router = StepRouter(
        settings=settings,
        openai_backend=StubBackend("openai", "openai-model"),
        ollama_backend=StubBackend("ollama", "ollama-model"),
        llama_cpp_backend=StubBackend("llama_cpp", "llama-cpp-model"),
    )

    backend = router.select_backend("generate_code")

    assert backend.backend_name == "llama_cpp"


def test_router_requires_healthy_llama_cpp_for_generation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Generation routing should fail cleanly when llama.cpp is explicitly requested but unavailable."""
    monkeypatch.setenv("GENERATION_BACKEND", "llama_cpp")
    settings = Settings.from_env(project_root=tmp_path)
    router = StepRouter(
        settings=settings,
        openai_backend=StubBackend("openai", "openai-model"),
        ollama_backend=StubBackend("ollama", "ollama-model"),
        llama_cpp_backend=StubBackend("llama_cpp", "llama-cpp-model", available=False),
    )

    with pytest.raises(RuntimeError, match="unavailable"):
        router.select_backend("generate_code")
