"""Collect run outputs and refresh the latest output snapshot."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from gauntlet.config import Settings
from gauntlet.run_context import RunContext


def collect_artifacts(context: RunContext, settings: Settings) -> dict[str, list[str]]:
    """List produced artifacts and refresh `outputs/latest`."""
    artifacts = {
        "results": _relative_paths(context.run_root, context.results_dir.glob("*.csv")),
        "figures": _relative_paths(context.run_root, context.figures_dir.glob("*.png")),
    }

    _refresh_latest_snapshot(
        latest_output_dir=settings.latest_output_dir,
        run_output_dir=context.outputs_dir,
    )
    return artifacts


def _relative_paths(root: Path, paths: Iterable[Path]) -> list[str]:
    """Render sorted relative paths for summaries."""
    resolved_paths = sorted(Path(path) for path in paths)
    return [path.relative_to(root).as_posix() for path in resolved_paths]


def _refresh_latest_snapshot(latest_output_dir: Path, run_output_dir: Path) -> None:
    """Copy the current run outputs into `outputs/latest`."""
    latest_output_dir.mkdir(parents=True, exist_ok=True)

    for child in latest_output_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    for child in run_output_dir.iterdir():
        destination = latest_output_dir / child.name
        if child.is_dir():
            shutil.copytree(child, destination)
        else:
            shutil.copy2(child, destination)
