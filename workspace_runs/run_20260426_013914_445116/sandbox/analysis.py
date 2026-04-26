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


def _safe_mode(series: pd.Series):
    mode_values = series.dropna().mode()
    if len(mode_values) == 0:
        return pd.NA
    return mode_values.iloc[0]


def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Produce summary tables for the teen mental health dataset."""
    df = data["teens"].copy()
    results: dict[str, pd.DataFrame] = {}

    # Basic dataset overview
    overview = pd.DataFrame(
        {
            "metric": [
                "rows",
                "columns",
                "missing_values_total",
                "missing_rows_any_column",
                "depression_label_0_count",
                "depression_label_1_count",
                "depression_label_1_rate",
            ],
            "value": [
                len(df),
                df.shape[1],
                int(df.isna().sum().sum()),
                int(df.isna().any(axis=1).sum()),
                int((df["depression_label"] == 0).sum()),
                int((df["depression_label"] == 1).sum()),
                float(df["depression_label"].mean()) if "depression_label" in df.columns else pd.NA,
            ],
        }
    )
    results["overview"] = overview

    # Numeric descriptive statistics
    numeric_cols = [c for c in NUMERIC_COLUMNS if c in df.columns]
    numeric_summary = df[numeric_cols].describe().T.reset_index().rename(columns={"index": "variable"})
    numeric_summary["missing"] = df[numeric_cols].isna().sum().values
    results["numeric_summary"] = numeric_summary

    # Categorical summaries
    cat_frames = []
    for col in CATEGORICAL_COLUMNS:
        if col in df.columns:
            counts = df[col].value_counts(dropna=False).reset_index()
            counts.columns = ["category", "count"]
            counts.insert(0, "variable", col)
            counts["percent"] = counts["count"] / len(df)
            cat_frames.append(counts)
    categorical_summary = pd.concat(cat_frames, ignore_index=True) if cat_frames else pd.DataFrame(columns=["variable", "category", "count", "percent"])
    results["categorical_summary"] = categorical_summary

    # Comparison of key numeric variables by depression label
    compare_cols = [
        "daily_social_media_hours",
        "sleep_hours",
        "screen_time_before_sleep",
        "academic_performance",
        "physical_activity",
        "stress_level",
        "anxiety_level",
        "addiction_level",
    ]
    compare_cols = [c for c in compare_cols if c in df.columns]

    grouped = df.groupby("depression_label", dropna=False)
    comparison = grouped[compare_cols].agg(["mean", "median", "std"])
    comparison.columns = [f"{col}_{stat}" for col, stat in comparison.columns]
    comparison = comparison.reset_index()
    results["depression_comparison"] = comparison

    # Categorical distribution by depression label for useful group context
    cat_by_dep_frames = []
    for col in ["gender", "platform_usage", "social_interaction_level"]:
        if col in df.columns and "depression_label" in df.columns:
            temp = (
                df.groupby(["depression_label", col], dropna=False)
                .size()
                .reset_index(name="count")
            )
            temp["percent_within_label"] = temp["count"] / temp.groupby("depression_label")["count"].transform("sum")
            temp.insert(1, "variable", col)
            cat_by_dep_frames.append(temp)
    categorical_by_depression = pd.concat(cat_by_dep_frames, ignore_index=True) if cat_by_dep_frames else pd.DataFrame(columns=["depression_label", "variable", "category", "count", "percent_within_label"])
    results["categorical_by_depression"] = categorical_by_depression

    # Short narrative-friendly summary table
    summary_rows = []
    if "depression_label" in df.columns:
        d0 = df[df["depression_label"] == 0]
        d1 = df[df["depression_label"] == 1]
        for col in compare_cols:
            diff = d1[col].mean() - d0[col].mean()
            summary_rows.append(
                {
                    "variable": col,
                    "mean_depression_0": d0[col].mean(),
                    "mean_depression_1": d1[col].mean(),
                    "difference_1_minus_0": diff,
                }
            )
    results["group_differences"] = pd.DataFrame(summary_rows)

    return results
