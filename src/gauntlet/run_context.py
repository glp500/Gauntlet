"""Run-specific paths and metadata management."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gauntlet.config import Settings


def _timestamp_now() -> datetime:
    """Return a timezone-aware timestamp for metadata."""
    return datetime.now(UTC)


@dataclass(slots=True)
class RunContext:
    """Own the directory layout and metadata for one pipeline run."""

    run_id: str
    created_at: str
    run_root: Path
    sandbox_dir: Path
    outputs_dir: Path
    results_dir: Path
    figures_dir: Path
    logs_dir: Path
    prompts_dir: Path
    responses_dir: Path
    metadata_path: Path
    summary_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, settings: Settings) -> "RunContext":
        """Create a fresh run directory layout and seed metadata."""
        now = _timestamp_now()
        run_id = now.strftime("run_%Y%m%d_%H%M%S_%f")
        run_root = settings.workspace_runs_dir / run_id
        sandbox_dir = run_root / "sandbox"
        outputs_dir = run_root / "outputs"
        results_dir = outputs_dir / "results"
        figures_dir = outputs_dir / "figures"
        logs_dir = run_root / "logs"
        prompts_dir = run_root / "prompts"
        responses_dir = run_root / "responses"
        metadata_path = run_root / "metadata.json"
        summary_path = outputs_dir / "summary.json"

        for path in [
            run_root,
            sandbox_dir,
            outputs_dir,
            results_dir,
            figures_dir,
            logs_dir,
            prompts_dir,
            responses_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

        context = cls(
            run_id=run_id,
            created_at=now.isoformat(),
            run_root=run_root,
            sandbox_dir=sandbox_dir,
            outputs_dir=outputs_dir,
            results_dir=results_dir,
            figures_dir=figures_dir,
            logs_dir=logs_dir,
            prompts_dir=prompts_dir,
            responses_dir=responses_dir,
            metadata_path=metadata_path,
            summary_path=summary_path,
            metadata={
                "run_id": run_id,
                "created_at": now.isoformat(),
                "status": "created",
                "attempt_count": 0,
                "attempts": [],
                "steps": [],
            },
        )
        context.write_metadata()
        return context

    def record_step(
        self,
        step_name: str,
        *,
        status: str,
        attempt_number: int | None = None,
        backend: str | None = None,
        model: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append one step entry to the run metadata."""
        entry: dict[str, Any] = {
            "step": step_name,
            "status": status,
            "recorded_at": _timestamp_now().isoformat(),
        }

        if attempt_number is not None:
            entry["attempt_number"] = attempt_number

        if backend is not None:
            entry["backend"] = backend

        if model is not None:
            entry["model"] = model

        if details:
            entry["details"] = details

        self.metadata.setdefault("steps", []).append(entry)
        self.write_metadata()

    def record_attempt(
        self,
        *,
        attempt_number: int,
        stage: str,
        status: str,
        retryable: bool,
        failure_reason: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Append one attempt result entry to run metadata."""
        entry: dict[str, Any] = {
            "attempt_number": attempt_number,
            "stage": stage,
            "status": status,
            "retryable": retryable,
            "recorded_at": _timestamp_now().isoformat(),
        }

        if failure_reason is not None:
            entry["failure_reason"] = failure_reason

        if details:
            entry["details"] = details

        attempts = self.metadata.setdefault("attempts", [])
        attempts.append(entry)
        self.metadata["attempt_count"] = len(attempts)
        self.write_metadata()

    def set_status(self, status: str, failure_reason: str | None = None) -> None:
        """Update the high-level run status."""
        self.metadata["status"] = status
        if failure_reason:
            self.metadata["failure_reason"] = failure_reason
        self.write_metadata()

    def attach_value(self, key: str, value: Any) -> None:
        """Store one metadata field and persist it immediately."""
        self.metadata[key] = value
        self.write_metadata()

    def write_metadata(self) -> None:
        """Persist metadata in a deterministic JSON format."""
        self.metadata_path.write_text(
            json.dumps(self.metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
