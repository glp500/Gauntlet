"""Return placeholder evaluation output until the modeling slice exists."""

from __future__ import annotations

from typing import Any


def evaluate(model: dict[str, Any], data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic placeholder evaluation artifact."""
    return {
        "status": "not_implemented",
        "metrics": {},
        "notes": [
            "Evaluation is deferred because no model is trained in this slice.",
            f"Training status: {model['status']}",
        ],
    }
