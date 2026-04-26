"""Tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from gauntlet.config import Settings


def test_settings_load_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Defaults should produce the expected project-relative paths."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GENERATION_BACKEND", raising=False)
    monkeypatch.delenv("REVIEW_BACKEND", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    settings = Settings.from_env(project_root=tmp_path)

    assert settings.project_root == tmp_path
    assert settings.input_task_path == tmp_path / "inputs" / "input.txt"
    assert settings.generation_backend == "openai"
    assert settings.review_backend == "openai"
    assert settings.ollama_model == "gemma4:e2b"
    assert settings.max_codegen_attempts == 5
    assert settings.enable_web is False


def test_require_openai_api_key_raises_when_missing(tmp_path: Path) -> None:
    """The OpenAI-backed steps should fail clearly without an API key."""
    settings = Settings.from_env(project_root=tmp_path)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        settings.require_openai_api_key()


def test_generation_backend_accepts_ollama(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Generation backend should be configurable to Ollama."""
    monkeypatch.setenv("GENERATION_BACKEND", "ollama")

    settings = Settings.from_env(project_root=tmp_path)

    assert settings.generation_backend == "ollama"


def test_generation_backend_accepts_llama_cpp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Generation backend should be configurable to llama.cpp."""
    monkeypatch.setenv("GENERATION_BACKEND", "llama_cpp")
    monkeypatch.setenv("LLAMA_CPP_MODEL_PATH", str(tmp_path / "models" / "gemma.gguf"))

    settings = Settings.from_env(project_root=tmp_path)

    assert settings.generation_backend == "llama_cpp"
    assert settings.llama_cpp_model_path == (tmp_path / "models" / "gemma.gguf").resolve()
