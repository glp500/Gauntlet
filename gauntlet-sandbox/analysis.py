"""Create a human-readable analysis summary from the structured profile."""

from __future__ import annotations

from typing import Any


def analyze(data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Generate a lightweight markdown summary of the loaded dataset."""
    profile = data["profile"]
    prompt_text = config["prompt_text"].strip()

    summary_markdown = _build_summary_markdown(profile, prompt_text)

    return {
        "status": "completed",
        "summary_markdown": summary_markdown,
        "notes": [
            "This analysis is descriptive only.",
            "Modeling and figure generation are deferred in this slice.",
        ],
    }


def _build_summary_markdown(profile: dict[str, Any], prompt_text: str) -> str:
    """Format the first analysis artifact as markdown."""
    dataset = profile["dataset"]
    numeric_columns = profile["numeric_columns"]
    categorical_columns = profile["categorical_columns"]
    preview_columns = ", ".join(profile["columns"][:6])

    lines = [
        "# Analysis Summary",
        "",
        "## Prompt Context",
        prompt_text or "No prompt text was provided.",
        "",
        "## Dataset Snapshot",
        f"- File: `{dataset['file_name']}`",
        f"- Rows: {dataset['row_count']}",
        f"- Columns: {dataset['column_count']}",
        f"- Numeric columns: {len(numeric_columns)}",
        f"- Categorical columns: {len(categorical_columns)}",
        "",
        "## Initial Observations",
        f"- The first columns in the dataset are: {preview_columns}.",
        "- The dataset includes behavioral, sleep, stress, anxiety, and social media usage signals.",
        "- This slice only profiles the data and prepares the runner contract for later modeling work.",
    ]

    return "\n".join(lines) + "\n"
