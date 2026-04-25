"""Return placeholder visualization output for the first runnable sandbox flow."""

from __future__ import annotations

from typing import Any


def create_visualizations(
    data: dict[str, Any],
    analysis: dict[str, Any],
    evaluation: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Return explicit placeholder figure metadata without creating files."""
    return {
        "status": "not_implemented",
        "figure_count": 0,
        "figures": [],
        "notes": [
            "Figure generation is deferred in this slice.",
            "No SVG, PNG, or JSON figure artifacts are written yet.",
        ],
    }
