"""Return placeholder model-training metadata for the early sandbox loop."""

from __future__ import annotations

from typing import Any


def train_model(data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Return explicit placeholder training status without fitting a model."""
    return {
        "status": "not_implemented",
        "baseline_only": bool(config.get("modeling", {}).get("baseline_only", True)),
        "model_name": None,
        "notes": [
            "Model training is intentionally deferred in this slice.",
            "A target column has not been fixed yet.",
        ],
    }
