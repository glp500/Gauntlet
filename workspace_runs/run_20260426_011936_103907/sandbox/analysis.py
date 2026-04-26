from __future__ import annotations

import pandas as pd


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


def summarize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Return a compact dataset summary including missing values and dtypes."""
    summary = pd.DataFrame({
        "column": df.columns,
        "dtype": [str(df[col].dtype) for col in df.columns],
        "missing_count": [int(df[col].isna().sum()) for col in df.columns],
        "n_unique": [int(df[col].nunique(dropna=True)) for col in df.columns],
    })
    return summary


def numeric_descriptives(df: pd.DataFrame) -> pd.DataFrame:
    """Basic descriptive statistics for numeric columns."""
    desc = df[NUMERIC_COLUMNS].describe().T.reset_index().rename(columns={"index": "column"})
    return desc


def categorical_frequencies(df: pd.DataFrame) -> pd.DataFrame:
    """Frequency counts for categorical variables."""
    frames = []
    for col in CATEGORICAL_COLUMNS:
        counts = df[col].value_counts(dropna=False).reset_index()
        counts.columns = ["value", "count"]
        counts.insert(0, "column", col)
        counts["share"] = counts["count"] / len(df)
        frames.append(counts)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["column", "value", "count", "share"])


def depression_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Distribution of depression_label values."""
    dist = df["depression_label"].value_counts(dropna=False).sort_index().reset_index()
    dist.columns = ["depression_label", "count"]
    dist["share"] = dist["count"] / len(df)
    return dist


def grouped_comparisons(df: pd.DataFrame) -> pd.DataFrame:
    """Compare key numeric variables by depression label."""
    grouped = (
        df.groupby("depression_label", dropna=False)[
            ["daily_social_media_hours", "sleep_hours", "stress_level", "anxiety_level", "addiction_level", "academic_performance", "physical_activity"]
        ]
        .agg(["mean", "median", "count"])
    )
    grouped.columns = [f"{col}_{stat}" for col, stat in grouped.columns]
    return grouped.reset_index()


def subgroup_summary(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Mean depression label and selected numeric averages by a categorical subgroup."""
    if group_col not in df.columns:
        raise ValueError(f"Unknown group column: {group_col}")
    out = (
        df.groupby(group_col, dropna=False)
        .agg(
            n=("depression_label", "size"),
            depression_rate=("depression_label", "mean"),
            daily_social_media_hours=("daily_social_media_hours", "mean"),
            sleep_hours=("sleep_hours", "mean"),
            stress_level=("stress_level", "mean"),
            anxiety_level=("anxiety_level", "mean"),
            addiction_level=("addiction_level", "mean"),
        )
        .reset_index()
    )
    return out
