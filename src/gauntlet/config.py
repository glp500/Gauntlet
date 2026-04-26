"""Configuration for the local analysis pipeline."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LOCAL_MODEL = "hf.co/mradermacher/IBM-Grok4-UltraFast-Coder-1B-GGUF:Q4_K_M"
#DEFAULT_LOCAL_MODEL = "gemma4:e2b"

LARGE_LOCAL_MODEL = "gemma4:26b"


def _parse_bool(value: str | None, default: bool) -> bool:
    """Parse a boolean-like environment variable."""
    if value is None:
        return default

    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    """Environment-backed settings for one local install."""

    project_root: Path
    inputs_dir: Path
    input_task_path: Path
    input_data_dir: Path
    workspace_runs_dir: Path
    outputs_dir: Path
    latest_output_dir: Path
    sandbox_template_dir: Path
    openai_api_key: str | None
    openai_model: str
    openai_base_url: str
    ollama_base_url: str
    ollama_model: str
    llama_cpp_base_url: str
    llama_cpp_model_path: Path | None
    llama_cpp_mmproj_path: Path | None
    llama_cpp_ctx_size: int
    llama_cpp_n_gpu_layers: int
    llama_cpp_threads: int
    llama_cpp_timeout_seconds: int
    generation_backend: str
    review_backend: str
    run_timeout_seconds: int
    request_timeout_seconds: int
    max_codegen_attempts: int
    max_review_rounds: int
    enable_web: bool
    max_manifest_sample_values: int

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "Settings":
        """Load settings from the current process environment."""
        root = (project_root or Path.cwd()).resolve()
        inputs_dir = root / "inputs"
        outputs_dir = root / "outputs"

        supported_backends = {"openai", "ollama", "llama_cpp"}
        generation_backend = os.getenv("GENERATION_BACKEND", "openai").strip().lower()
        if generation_backend not in supported_backends:
            raise ValueError(
                "GENERATION_BACKEND must be one of: openai, ollama, llama_cpp."
            )

        review_backend = os.getenv("REVIEW_BACKEND", "openai").strip().lower()
        if review_backend not in supported_backends:
            raise ValueError(
                "REVIEW_BACKEND must be one of: openai, ollama, llama_cpp."
            )

        llama_cpp_model_path = _resolve_optional_path(
            os.getenv("LLAMA_CPP_MODEL_PATH")
        ) or _discover_ollama_model_blob(os.getenv("OLLAMA_MODEL", DEFAULT_LOCAL_MODEL))
        llama_cpp_mmproj_path = _resolve_optional_path(os.getenv("LLAMA_CPP_MMPROJ_PATH"))

        return cls(
            project_root=root,
            inputs_dir=inputs_dir,
            input_task_path=inputs_dir / "input.txt",
            input_data_dir=inputs_dir / "data",
            workspace_runs_dir=root / "workspace_runs",
            outputs_dir=outputs_dir,
            latest_output_dir=outputs_dir / "latest",
            sandbox_template_dir=root / "sandbox_template",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini-2026-03-17"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api"),
            ollama_model=os.getenv("OLLAMA_MODEL", DEFAULT_LOCAL_MODEL),
            llama_cpp_base_url=os.getenv("LLAMA_CPP_BASE_URL", "http://localhost:8080"),
            llama_cpp_model_path=llama_cpp_model_path,
            llama_cpp_mmproj_path=llama_cpp_mmproj_path,
            llama_cpp_ctx_size=int(os.getenv("LLAMA_CPP_CTX_SIZE", "4096")),
            llama_cpp_n_gpu_layers=int(os.getenv("LLAMA_CPP_N_GPU_LAYERS", "-1")),
            llama_cpp_threads=int(os.getenv("LLAMA_CPP_THREADS", "-1")),
            llama_cpp_timeout_seconds=int(
                os.getenv("LLAMA_CPP_TIMEOUT_SECONDS", "180")
            ),
            generation_backend=generation_backend,
            review_backend=review_backend,
            run_timeout_seconds=int(os.getenv("RUN_TIMEOUT_SECONDS", "120")),
            request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120")),
            max_codegen_attempts=int(os.getenv("MAX_CODEGEN_ATTEMPTS", "5")),
            max_review_rounds=int(os.getenv("MAX_REVIEW_ROUNDS", "1")),
            enable_web=_parse_bool(os.getenv("ENABLE_WEB"), default=False),
            max_manifest_sample_values=int(os.getenv("MAX_MANIFEST_SAMPLE_VALUES", "3")),
        )

    def require_openai_api_key(self) -> str:
        """Return the API key or raise a clear error."""
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI-backed pipeline steps.")
        return self.openai_api_key


def _resolve_optional_path(raw_value: str | None) -> Path | None:
    """Normalize optional path environment variables."""
    if raw_value is None:
        return None

    cleaned = raw_value.strip()
    if not cleaned:
        return None

    return Path(cleaned).expanduser().resolve()


def _discover_ollama_model_blob(model_name: str) -> Path | None:
    """Best-effort discovery of the GGUF blob behind an installed Ollama model."""
    cleaned_model_name = model_name.strip()
    if not cleaned_model_name:
        return None

    namespace = "library"
    local_name = cleaned_model_name
    if "/" in cleaned_model_name:
        namespace, local_name = cleaned_model_name.split("/", maxsplit=1)

    if ":" in local_name:
        model_slug, model_tag = local_name.split(":", maxsplit=1)
    else:
        model_slug, model_tag = local_name, "latest"

    manifest_path = (
        Path.home()
        / ".ollama"
        / "models"
        / "manifests"
        / "registry.ollama.ai"
        / namespace
        / model_slug
        / model_tag
    )
    if not manifest_path.exists():
        return None

    try:
        manifest = manifest_path.read_text(encoding="utf-8")
    except OSError:
        return None

    model_digest = None
    for line in manifest.splitlines():
        if '"mediaType":"application/vnd.ollama.image.model"' not in line:
            continue

        digest_marker = '"digest":"'
        digest_start = line.find(digest_marker)
        if digest_start == -1:
            continue

        digest_start += len(digest_marker)
        digest_end = line.find('"', digest_start)
        if digest_end == -1:
            continue

        model_digest = line[digest_start:digest_end]
        break

    if not model_digest:
        return None

    blob_path = Path.home() / ".ollama" / "models" / "blobs" / model_digest.replace(":", "-")
    if not blob_path.exists():
        return None

    return blob_path.resolve()
