"""Unit tests for retry-loop helper behavior."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gauntlet.config import Settings
from gauntlet.llm.base import LLMResponse
from gauntlet.orchestrator.pipeline import (
    _build_semantic_guidance,
    _extract_execution_issues,
    _extract_semantic_validation_issues,
    _summarize_stderr,
    build_pipeline,
)


@dataclass
class StubBackend:
    """Minimal backend stub for helper-oriented pipeline tests."""

    backend_name: str = "openai"
    model: str = "mock-model"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: str | None = None,
    ) -> LLMResponse:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True


def test_extract_execution_issues_summarizes_stderr() -> None:
    """Runtime stderr should be converted into repairable issue text."""
    issues = _extract_execution_issues(
        {
            "failure_reason": "Sandbox execution failed with exit code 1.",
            "stderr": (
                "Traceback (most recent call last):\n"
                "  File \"run_analysis.py\", line 10, in <module>\n"
                "KeyError: 'missing_dataset'\n"
            ),
        }
    )

    assert any("missing key" in issue.lower() for issue in issues)
    assert any("stderr summary" in issue.lower() for issue in issues)


def test_summarize_stderr_uses_tail_lines() -> None:
    """The stderr summary should keep the most relevant tail lines."""
    summary = _summarize_stderr(
        "line 1\nline 2\nline 3\nline 4\n"
    )

    assert summary == "line 2 | line 3 | line 4"


def test_extract_semantic_validation_issues_includes_stderr_summary() -> None:
    """Semantic smoke stderr should be preserved in repairable issue text."""
    issues = _extract_semantic_validation_issues(
        {
            "failure_reason": "Semantic smoke check failed with exit code 1. NameError: name 'pd' is not defined",
            "raw_stderr": (
                "Traceback (most recent call last):\n"
                "  File \"<string>\", line 10, in <module>\n"
                "  File \"preprocessing.py\", line 1, in <module>\n"
                "NameError: name 'pd' is not defined\n"
            ),
        }
    )

    assert any("NameError" in issue for issue in issues)
    assert any("Semantic smoke stderr summary" in issue for issue in issues)


def test_build_semantic_guidance_targets_import_failure_file() -> None:
    """Import-time semantic failures should produce file-specific repair guidance."""
    guidance = _build_semantic_guidance(
        {
            "failure_reason": "Semantic smoke check failed with exit code 1. NameError: name 'pd' is not defined",
            "raw_stderr": (
                "Traceback (most recent call last):\n"
                "  File \"<string>\", line 10, in <module>\n"
                "  File \"preprocessing.py\", line 1, in <module>\n"
                "NameError: name 'pd' is not defined\n"
            ),
        }
    )

    assert "preprocessing.py" in guidance
    assert any("import-safe" in entry for entry in guidance["preprocessing.py"])
    assert any("module-level annotations" in entry for entry in guidance["preprocessing.py"])


def test_normalize_review_result_keeps_contract_issues_advisory(tmp_path: Path) -> None:
    """Deterministically checked contract issues should not block the run."""
    settings = Settings.from_env(project_root=tmp_path)
    pipeline = build_pipeline(
        settings=settings,
        openai_backend=StubBackend(),
        ollama_backend=StubBackend(),
        llama_cpp_backend=StubBackend(),
    )

    normalized = pipeline._normalize_review_result(
        {
            "status": "blocked",
            "summary": "Mixed review feedback.",
            "issues": [
                {
                    "category": "contract",
                    "message": "Missing required public function run_analysis.",
                    "blocking": True,
                },
                {
                    "category": "dependency",
                    "message": "Uses unsupported dependency seaborn.",
                    "blocking": True,
                },
            ],
        }
    )

    assert "Missing required public function run_analysis." in normalized["advisory_issues"]
    assert "Uses unsupported dependency seaborn." in normalized["blocking_issues"]
