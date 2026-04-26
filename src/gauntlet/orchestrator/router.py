"""Backend routing rules for the v1 pipeline."""

from __future__ import annotations

from gauntlet.config import Settings
from gauntlet.llm.base import LLMBackend


class StepRouter:
    """Choose the backend for each pipeline step."""

    def __init__(
        self,
        settings: Settings,
        openai_backend: LLMBackend,
        ollama_backend: LLMBackend,
        llama_cpp_backend: LLMBackend,
    ) -> None:
        self._settings = settings
        self._openai_backend = openai_backend
        self._ollama_backend = ollama_backend
        self._llama_cpp_backend = llama_cpp_backend

    def select_backend(self, step_name: str) -> LLMBackend:
        """Return the configured backend for a known step."""
        if step_name in {"refine_prompt", "generate_code"}:
            return self._select_configured_backend(
                backend_name=self._settings.generation_backend,
                setting_name="GENERATION_BACKEND",
            )

        if step_name == "review_code":
            return self._select_configured_backend(
                backend_name=self._settings.review_backend,
                setting_name="REVIEW_BACKEND",
            )

        raise ValueError(f"Unsupported pipeline step for routing: {step_name}")

    def _select_configured_backend(
        self,
        *,
        backend_name: str,
        setting_name: str,
    ) -> LLMBackend:
        """Return the configured backend and validate local backend health when needed."""
        if backend_name == "openai":
            return self._openai_backend

        backend = self._get_local_backend(backend_name)
        if backend.is_available():
            return backend

        display_name = "Ollama" if backend_name == "ollama" else "llama.cpp"
        raise RuntimeError(
            f"{setting_name} is set to '{backend_name}', but the {display_name} endpoint is unavailable."
        )

    def _get_local_backend(self, backend_name: str) -> LLMBackend:
        """Return one configured non-OpenAI backend."""
        if backend_name == "ollama":
            return self._ollama_backend

        if backend_name == "llama_cpp":
            return self._llama_cpp_backend

        raise ValueError(f"Unsupported backend configuration: {backend_name}")
