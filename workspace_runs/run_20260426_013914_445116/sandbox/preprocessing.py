from __future__ import annotations

from typing import Dict

import pandas as pd


CATEGORICAL_COLUMNS = ["gender", "platform_usage", "social_interaction_level"]
NUMERIC_COLUMNS = [
    "age",
    "daily_social_media_hours",
    "sleep_hours",
    "screen_time_before_sleep",
    "academic_performance",
    "physical_activity",
    "stress_level",
    "anxiety_level",
    "addiction_level",
    "depression_label",
]


def preprocess(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Clean obvious issues while keeping the dataset faithful to the source."""
    processed: dict[str, pd.DataFrame] = {}

    for name, df in data.items():
        clean = df.copy()

        # Standardize column names and string categories.
        clean.columns = [c.strip() for c in clean.columns]
        for col in CATEGORICAL_COLUMNS:
            if col in clean.columns:
                clean[col] = clean[col].astype("string").str.strip().str.lower()

        # Keep only known columns in the expected order when available.
        ordered_cols = [c for c in NUMERIC_COLUMNS + CATEGORICAL_COLUMNS if c in clean.columns]
        extra_cols = [c for c in clean.columns if c not in ordered_cols]
        clean = clean[ordered_cols + extra_cols]

        # Ensure numeric fields are numeric, coercing invalid values to NaN.
        for col in NUMERIC_COLUMNS:
            if col in clean.columns:
                clean[col] = pd.to_numeric(clean[col], errors="coerce")

        processed[name] = clean

    return processed
