"""Prepare preprocessing metadata for the early sandbox pipeline."""

from __future__ import annotations

from typing import Any


def preprocess(data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Return a pass-through preprocessing report without modifying the dataset."""
    dataframe = data["dataframe"]
    profile = data["profile"]

    report = {
        "status": "completed",
        "mode": "pass_through_placeholder",
        "row_count": int(len(dataframe)),
        "column_count": int(len(dataframe.columns)),
        "applied_steps": [
            "validated dataset is readable",
            "preserved original columns",
            "deferred feature engineering to a later slice",
        ],
        "notes": [
            "No rows were dropped in this prototype preprocessing step.",
            "No target column is fixed yet in this slice.",
        ],
    }

    return {
        "dataframe": dataframe,
        "profile": profile,
        "report": report,
    }
