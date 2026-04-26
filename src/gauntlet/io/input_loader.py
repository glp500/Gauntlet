"""Load the task file and summarize CSV inputs for prompting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from gauntlet.config import Settings


@dataclass(slots=True)
class DatasetManifestEntry:
    """Structured metadata for one input CSV file."""

    file_name: str
    rows: int
    columns: list[str]
    dtypes: dict[str, str]
    sample_values: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entry for logging or prompt rendering."""
        return {
            "file_name": self.file_name,
            "rows": self.rows,
            "columns": self.columns,
            "dtypes": self.dtypes,
            "sample_values": self.sample_values,
        }


@dataclass(slots=True)
class InputManifest:
    """Task text plus dataset summaries."""

    task_text: str
    datasets: list[DatasetManifestEntry]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the manifest to a JSON-friendly shape."""
        return {
            "task_text": self.task_text,
            "datasets": [entry.to_dict() for entry in self.datasets],
        }

    def describe_for_prompt(self) -> str:
        """Render a compact manifest summary for model prompts."""
        lines = ["Datasets:"]
        for dataset in self.datasets:
            lines.append(
                f"- {dataset.file_name}: {dataset.rows} rows, columns={dataset.columns}"
            )
            for column_name, sample_values in dataset.sample_values.items():
                lines.append(
                    f"  - sample {column_name}: {', '.join(sample_values) or '[no sample values]'}"
                )
        return "\n".join(lines)


def load_input_manifest(settings: Settings) -> InputManifest:
    """Validate required inputs and build the manifest."""
    if not settings.input_task_path.exists():
        raise FileNotFoundError(
            f"Missing required task file: {settings.input_task_path}"
        )

    if not settings.input_data_dir.exists():
        raise FileNotFoundError(
            f"Missing required input data folder: {settings.input_data_dir}"
        )

    csv_paths = sorted(settings.input_data_dir.glob("*.csv"))
    if not csv_paths:
        raise FileNotFoundError(
            f"No CSV files found under required input folder: {settings.input_data_dir}"
        )

    task_text = settings.input_task_path.read_text(encoding="utf-8").strip()
    if not task_text:
        raise ValueError(f"Task file is empty: {settings.input_task_path}")

    datasets = [
        _summarize_csv(path, max_sample_values=settings.max_manifest_sample_values)
        for path in csv_paths
    ]
    return InputManifest(task_text=task_text, datasets=datasets)


def _summarize_csv(path: Path, max_sample_values: int) -> DatasetManifestEntry:
    """Read one CSV and capture a small schema snapshot."""
    frame = pd.read_csv(path)
    sample_values: dict[str, list[str]] = {}

    for column_name in frame.columns:
        unique_values = (
            frame[column_name]
            .dropna()
            .astype(str)
            .drop_duplicates()
            .head(max_sample_values)
            .tolist()
        )
        sample_values[str(column_name)] = unique_values

    return DatasetManifestEntry(
        file_name=path.name,
        rows=int(len(frame)),
        columns=[str(column) for column in frame.columns.tolist()],
        dtypes={str(name): str(dtype) for name, dtype in frame.dtypes.items()},
        sample_values=sample_values,
    )
