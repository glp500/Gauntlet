"""Evaluate the prototype baseline model on the held-out split."""

from __future__ import annotations

from typing import Any

from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def evaluate(model: dict[str, Any], data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Compute compact classification metrics for the trained baseline model."""
    y_test = model["evaluation_inputs"]["y_test"]
    y_pred = model["evaluation_inputs"]["y_pred"]
    y_score = model["evaluation_inputs"]["y_score"]
    matrix = confusion_matrix(y_test, y_pred, labels=[0, 1])

    return {
        "status": "completed",
        "target_column": model["target_column"],
        "metrics": {
            "accuracy": round(float(accuracy_score(y_test, y_pred)), 6),
            "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 6),
            "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 6),
            "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 6),
            "roc_auc": round(float(roc_auc_score(y_test, y_score)), 6),
        },
        "confusion_matrix": [
            [int(matrix[0][0]), int(matrix[0][1])],
            [int(matrix[1][0]), int(matrix[1][1])],
        ],
        "class_balance": {
            "test_positive_count": int(sum(y_test)),
            "test_negative_count": int(len(y_test) - sum(y_test)),
        },
        "notes": [
            "Metrics are computed on the held-out test split.",
            f"Training status: {model['status']}",
        ],
    }
