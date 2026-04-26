from __future__ import annotations

import pandas as pd


EXPECTED_COLUMNS = [
    "age",
    "gender",
    "daily_social_media_hours",
    "platform_usage",
    "sleep_hours",
    "screen_time_before_sleep",
    "academic_performance",
    "physical_activity",
    "social_interaction_level",
    "stress_level",
    "anxiety_level",
    "addiction_level",
    "depression_label",
]

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

CATEGORICAL_COLUMNS = ["gender", "platform_usage", "social_interaction_level"]


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and clean the dataset, returning a transformed DataFrame only."""
    data = df.copy()

    missing_expected = [col for col in EXPECTED_COLUMNS if col not in data.columns]
    if missing_expected:
        raise ValueError(f"Missing expected columns: {missing_expected}")

    data = data[EXPECTED_COLUMNS].copy()

    for col in NUMERIC_COLUMNS:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    for col in CATEGORICAL_COLUMNS:
        data[col] = data[col].astype("string").str.strip()

    data = data.dropna(subset=EXPECTED_COLUMNS).copy()

    data["depression_label"] = data["depression_label"].round().astype(int)
    data["age"] = data["age"].round().astype(int)
    data["stress_level"] = data["stress_level"].round().astype(int)
    data["anxiety_level"] = data["anxiety_level"].round().astype(int)
    data["addiction_level"] = data["addiction_level"].round().astype(int)

    if not data["depression_label"].isin([0, 1]).all():
        raise ValueError("depression_label must contain only 0 and 1 after cleaning.")

    return data.reset_index(drop=True)
