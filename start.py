"""CLI entrypoint for the Proto-Gauntlet vertical slice."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gauntlet.config import DEFAULT_LOCAL_MODEL, LARGE_LOCAL_MODEL, Settings
from gauntlet.orchestrator.pipeline import build_pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI flags for one pipeline run."""
    parser = argparse.ArgumentParser(description="Run one Proto-Gauntlet analysis pipeline.")
    parser.add_argument(
        "--large-local-model",
        action="store_true",
        help=(
            "Use the larger local Gemma profile for Ollama and llama.cpp discovery "
            f"({LARGE_LOCAL_MODEL}) instead of the default {DEFAULT_LOCAL_MODEL}."
        ),
    )
    return parser.parse_args(argv)


def _apply_cli_overrides(args: argparse.Namespace) -> None:
    """Apply non-destructive environment overrides from CLI flags."""
    if args.large_local_model:
        os.environ["OLLAMA_MODEL"] = LARGE_LOCAL_MODEL
    else:
        os.environ.setdefault("OLLAMA_MODEL", DEFAULT_LOCAL_MODEL)


def main(argv: list[str] | None = None) -> int:
    """Run one Proto-Gauntlet analysis pipeline."""
    args = parse_args(argv)
    _apply_cli_overrides(args)
    settings = Settings.from_env(project_root=PROJECT_ROOT)
    pipeline = build_pipeline(settings=settings)
    summary = pipeline.run()

    print(f"Run ID: {summary['run_id']}")
    print(f"Status: {summary['status']}")
    print(f"Summary: {summary['summary_path']}")

    if summary["status"] != "completed":
        failure_reason = summary.get("failure_reason") or "Unknown failure"
        print(f"Failure: {failure_reason}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
