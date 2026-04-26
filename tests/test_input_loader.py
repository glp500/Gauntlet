"""Tests for task and CSV manifest loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from gauntlet.config import Settings
from gauntlet.io.input_loader import load_input_manifest


def _write_inputs(root: Path) -> None:
    inputs_dir = root / "inputs" / "data"
    inputs_dir.mkdir(parents=True)
    (root / "inputs" / "input.txt").write_text("Analyze the CSV.", encoding="utf-8")
    (inputs_dir / "sample.csv").write_text(
        "city,value\nBerlin,1\nParis,2\nBerlin,3\n",
        encoding="utf-8",
    )


def test_load_input_manifest_builds_dataset_summary(tmp_path: Path) -> None:
    """A valid input folder should produce a structured manifest."""
    _write_inputs(tmp_path)
    settings = Settings.from_env(project_root=tmp_path)

    manifest = load_input_manifest(settings)

    assert manifest.task_text == "Analyze the CSV."
    assert len(manifest.datasets) == 1
    assert manifest.datasets[0].file_name == "sample.csv"
    assert manifest.datasets[0].rows == 3
    assert manifest.datasets[0].sample_values["city"] == ["Berlin", "Paris"]


def test_load_input_manifest_requires_task_file(tmp_path: Path) -> None:
    """Missing `input.txt` should fail with a direct error."""
    (tmp_path / "inputs" / "data").mkdir(parents=True)
    (tmp_path / "inputs" / "data" / "sample.csv").write_text("a\n1\n", encoding="utf-8")
    settings = Settings.from_env(project_root=tmp_path)

    with pytest.raises(FileNotFoundError, match="input.txt"):
        load_input_manifest(settings)
