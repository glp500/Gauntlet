"""Generate the first reproducible figure artifacts for the sandbox run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt


def create_visualizations(
    data: dict[str, Any],
    analysis: dict[str, Any],
    evaluation: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Render a confusion-matrix figure and write reproducible figure artifacts."""
    figures_dir = Path(config["resolved_paths"]["outputs_dir"]) / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    figure_id = "figure_001"
    png_path = figures_dir / f"{figure_id}.png"
    svg_path = figures_dir / f"{figure_id}.svg"
    json_path = figures_dir / f"{figure_id}.json"
    python_path = figures_dir / f"{figure_id}.py"

    matrix = evaluation["confusion_matrix"]
    labels = ["0", "1"]
    title = "Confusion Matrix for Depression Label Baseline"

    figure_spec = {
        "figure_id": figure_id,
        "title": title,
        "type": "confusion_matrix",
        "x_label": "Predicted label",
        "y_label": "True label",
        "labels": labels,
        "matrix": matrix,
    }

    _render_confusion_matrix(matrix, labels, title, png_path, svg_path)
    _write_json(json_path, figure_spec)
    _write_python_repro(python_path, figure_spec)

    return {
        "status": "completed",
        "figure_count": 1,
        "figures": [
            {
                "figure_id": figure_id,
                "title": title,
                "png_path": str(png_path),
                "svg_path": str(svg_path),
                "json_path": str(json_path),
                "python_path": str(python_path),
            }
        ],
        "notes": [
            "The first figure artifact set is generated from evaluation output.",
            "Future slices can map manual edits back into the figure JSON and Python source.",
        ],
    }


def _render_confusion_matrix(
    matrix: list[list[int]],
    labels: list[str],
    title: str,
    png_path: Path,
    svg_path: Path,
) -> None:
    """Render the confusion matrix to PNG and SVG."""
    figure, axis = plt.subplots(figsize=(6, 5))
    image = axis.imshow(matrix, cmap="Blues")
    figure.colorbar(image, ax=axis)

    axis.set_title(title)
    axis.set_xlabel("Predicted label")
    axis.set_ylabel("True label")
    axis.set_xticks(range(len(labels)))
    axis.set_yticks(range(len(labels)))
    axis.set_xticklabels(labels)
    axis.set_yticklabels(labels)

    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            axis.text(column_index, row_index, str(value), ha="center", va="center", color="black")

    figure.tight_layout()
    figure.savefig(png_path, dpi=150)
    figure.savefig(svg_path)
    plt.close(figure)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a figure JSON artifact with stable formatting."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _write_python_repro(path: Path, figure_spec: dict[str, Any]) -> None:
    """Write a small Python script that reproduces the saved figure."""
    lines = [
        '"""Reproduce the prototype confusion-matrix figure."""',
        "",
        "import matplotlib",
        'matplotlib.use("Agg")',
        "import matplotlib.pyplot as plt",
        "",
        f"matrix = {figure_spec['matrix']}",
        f"labels = {figure_spec['labels']}",
        f"title = {figure_spec['title']!r}",
        "",
        "figure, axis = plt.subplots(figsize=(6, 5))",
        'image = axis.imshow(matrix, cmap="Blues")',
        "figure.colorbar(image, ax=axis)",
        "axis.set_title(title)",
        'axis.set_xlabel("Predicted label")',
        'axis.set_ylabel("True label")',
        "axis.set_xticks(range(len(labels)))",
        "axis.set_yticks(range(len(labels)))",
        "axis.set_xticklabels(labels)",
        "axis.set_yticklabels(labels)",
        "",
        "for row_index, row in enumerate(matrix):",
        "    for column_index, value in enumerate(row):",
        '        axis.text(column_index, row_index, str(value), ha="center", va="center", color="black")',
        "",
        "figure.tight_layout()",
        f"figure.savefig({str(path.with_suffix('.png').name)!r}, dpi=150)",
        f"figure.savefig({str(path.with_suffix('.svg').name)!r})",
    ]

    with path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
