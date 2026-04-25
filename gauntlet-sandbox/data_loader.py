"""Load the configured dataset and build the first structured data profile."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def load_data(config: dict[str, Any]) -> dict[str, Any]:
    """Load the configured CSV file and return the dataset plus profile metadata."""
    dataset_path = Path(config["resolved_paths"]["dataset_file"])
    if not dataset_path.exists():
        raise FileNotFoundError(f"Configured dataset file not found: {dataset_path}")

    dataframe = pd.read_csv(dataset_path)
    profile = _build_profile(dataframe, dataset_path)

    return {
        "dataframe": dataframe,
        "profile": profile,
    }


def _build_profile(dataframe: pd.DataFrame, dataset_path: Path) -> dict[str, Any]:
    """Create a JSON-friendly summary of the loaded dataframe."""
    numeric_columns = list(dataframe.select_dtypes(include="number").columns)
    categorical_columns = [
        column_name for column_name in dataframe.columns if column_name not in numeric_columns
    ]

    return {
        "dataset": {
            "path": str(dataset_path),
            "file_name": dataset_path.name,
            "row_count": int(len(dataframe)),
            "column_count": int(len(dataframe.columns)),
        },
        "columns": list(dataframe.columns),
        "numeric_columns": numeric_columns,
        "categorical_columns": categorical_columns,
        "dtypes": {
            column_name: str(dtype) for column_name, dtype in dataframe.dtypes.items()
        },
        "missing_values": _build_missing_value_summary(dataframe),
        "numeric_summary": _build_numeric_summary(dataframe[numeric_columns]),
        "categorical_summary": _build_categorical_summary(dataframe[categorical_columns]),
        "preview_rows": _build_preview_rows(dataframe),
    }


def _build_missing_value_summary(dataframe: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    """Summarize missing values for every column."""
    row_count = max(len(dataframe), 1)
    summary: dict[str, dict[str, float | int]] = {}

    for column_name in dataframe.columns:
        missing_count = int(dataframe[column_name].isna().sum())
        summary[column_name] = {
            "count": missing_count,
            "fraction": round(missing_count / row_count, 6),
        }

    return summary


def _build_numeric_summary(dataframe: pd.DataFrame) -> dict[str, dict[str, float | int | None]]:
    """Create compact numeric statistics for each numeric column."""
    if dataframe.empty:
        return {}

    described = dataframe.describe().transpose()
    summary: dict[str, dict[str, float | int | None]] = {}

    for column_name in described.index:
        row = described.loc[column_name]
        summary[column_name] = {
            "count": int(row["count"]),
            "mean": _to_float(row["mean"]),
            "std": _to_float(row["std"]),
            "min": _to_float(row["min"]),
            "median": _to_float(row["50%"]),
            "max": _to_float(row["max"]),
        }

    return summary


def _build_categorical_summary(dataframe: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Create compact categorical summaries with the most common values."""
    if dataframe.empty:
        return {}

    summary: dict[str, dict[str, Any]] = {}

    for column_name in dataframe.columns:
        series = dataframe[column_name].fillna("MISSING").astype(str)
        value_counts = series.value_counts().head(5)
        top_values = [
            {"value": value, "count": int(count)}
            for value, count in value_counts.items()
        ]
        summary[column_name] = {
            "unique_count": int(series.nunique(dropna=False)),
            "top_values": top_values,
        }

    return summary


def _build_preview_rows(dataframe: pd.DataFrame, limit: int = 5) -> list[dict[str, Any]]:
    """Return a small row preview that is safe to serialize to JSON."""
    preview_frame = dataframe.head(limit).copy()
    preview_frame = preview_frame.where(pd.notna(preview_frame), None)

    return [
        {
            column_name: _clean_value(value)
            for column_name, value in row.items()
        }
        for row in preview_frame.to_dict(orient="records")
    ]


def _clean_value(value: Any) -> Any:
    """Normalize pandas scalar values to plain JSON-friendly values."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return _to_float(value)
    return value


def _to_float(value: Any) -> float | None:
    """Convert pandas numeric values to plain floats while preserving missing values."""
    if pd.isna(value):
        return None
    return round(float(value), 6)
