"""Tests for artifact collection and latest snapshot refresh."""

from __future__ import annotations

from pathlib import Path

from gauntlet.config import Settings
from gauntlet.io.artifact_collector import collect_artifacts
from gauntlet.run_context import RunContext


def test_collect_artifacts_refreshes_latest_snapshot(tmp_path: Path) -> None:
    """The latest snapshot should mirror the current run outputs."""
    settings = Settings.from_env(project_root=tmp_path)
    settings.latest_output_dir.mkdir(parents=True, exist_ok=True)
    (settings.latest_output_dir / "stale.txt").write_text("old", encoding="utf-8")

    context = RunContext.create(settings)
    (context.results_dir / "table.csv").write_text("a\n1\n", encoding="utf-8")
    (context.figures_dir / "figure.png").write_bytes(b"png")

    artifacts = collect_artifacts(context, settings)

    assert artifacts["results"] == ["outputs/results/table.csv"]
    assert artifacts["figures"] == ["outputs/figures/figure.png"]
    assert not (settings.latest_output_dir / "stale.txt").exists()
    assert (settings.latest_output_dir / "results" / "table.csv").exists()
    assert (settings.latest_output_dir / "figures" / "figure.png").exists()
