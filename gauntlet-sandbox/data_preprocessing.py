"""Prepare structured feature and target data for the prototype baseline model."""

from __future__ import annotations

from typing import Any


def preprocess(data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Split the loaded dataframe into explicit feature and target views."""
    dataframe = data["dataframe"]
    profile = data["profile"]
    modeling_config = config.get("modeling", {})
    target_column = modeling_config.get("target_column", "depression_label")

    if target_column not in dataframe.columns:
        raise ValueError(f"Configured target column was not found: {target_column}")

    feature_columns = [
        column_name for column_name in dataframe.columns if column_name != target_column
    ]
    feature_frame = dataframe[feature_columns].copy()
    target_series = dataframe[target_column].copy()

    numeric_feature_columns = [
        column_name
        for column_name in profile["numeric_columns"]
        if column_name != target_column
    ]
    categorical_feature_columns = [
        column_name
        for column_name in feature_columns
        if column_name not in numeric_feature_columns
    ]

    report = {
        "status": "completed",
        "mode": "baseline_feature_target_split",
        "row_count": int(len(dataframe)),
        "column_count": int(len(dataframe.columns)),
        "target_column": target_column,
        "feature_column_count": int(len(feature_columns)),
        "numeric_feature_columns": numeric_feature_columns,
        "categorical_feature_columns": categorical_feature_columns,
        "applied_steps": [
            "validated dataset is readable",
            "selected an explicit prototype target column",
            "split the dataframe into feature and target views",
            "deferred feature engineering to the sklearn pipeline",
        ],
        "notes": [
            "No rows were dropped in this preprocessing step.",
            "Missing values will be handled by the training pipeline.",
        ],
    }

    return {
        "dataframe": dataframe,
        "profile": profile,
        "feature_frame": feature_frame,
        "target_series": target_series,
        "target_column": target_column,
        "feature_columns": feature_columns,
        "numeric_feature_columns": numeric_feature_columns,
        "categorical_feature_columns": categorical_feature_columns,
        "report": report,
    }
