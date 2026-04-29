from __future__ import annotations

import pandas as pd


def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Compute summary tables for the warehouse and retail sales dataset."""
    df = data["sales"].copy()

    numeric_cols = [c for c in ["RETAIL SALES", "RETAIL TRANSFERS", "WAREHOUSE SALES"] if c in df.columns]
    cat_cols = [c for c in ["SUPPLIER", "ITEM TYPE"] if c in df.columns]

    results: dict[str, pd.DataFrame] = {}

    # Basic shape and column types.
    results["schema"] = pd.DataFrame(
        {
            "column": df.columns,
            "dtype": [str(df[c].dtype) for c in df.columns],
            "missing_count": [int(df[c].isna().sum()) for c in df.columns],
        }
    )

    results["shape"] = pd.DataFrame(
        {
            "rows": [int(df.shape[0])],
            "columns": [int(df.shape[1])],
        }
    )

    # Descriptive statistics for numeric fields.
    if numeric_cols:
        stats = df[numeric_cols].describe().T.reset_index().rename(columns={"index": "column"})
        stats["missing_count"] = [int(df[c].isna().sum()) for c in numeric_cols]
        results["numeric_summary"] = stats
    else:
        results["numeric_summary"] = pd.DataFrame(columns=["column"])

    # Category summaries.
    if "ITEM TYPE" in df.columns:
        item_type_summary = (
            df.groupby("ITEM TYPE", dropna=False)[numeric_cols]
            .sum(numeric_only=True)
            .reset_index()
        )
        if "RETAIL SALES" in item_type_summary.columns:
            item_type_summary = item_type_summary.sort_values("RETAIL SALES", ascending=False)
        results["item_type_summary"] = item_type_summary
    else:
        results["item_type_summary"] = pd.DataFrame()

    if "SUPPLIER" in df.columns:
        supplier_summary = (
            df.groupby("SUPPLIER", dropna=False)[numeric_cols]
            .sum(numeric_only=True)
            .reset_index()
        )
        if "RETAIL SALES" in supplier_summary.columns:
            supplier_summary = supplier_summary.sort_values("RETAIL SALES", ascending=False).head(10)
        results["top_suppliers"] = supplier_summary
    else:
        results["top_suppliers"] = pd.DataFrame()

    # Time patterns using YEAR and MONTH.
    if {"YEAR", "MONTH"}.issubset(df.columns) and numeric_cols:
        yearly = df.groupby("YEAR")[numeric_cols].sum(numeric_only=True).reset_index().sort_values("YEAR")
        results["yearly_trend"] = yearly

        monthly = df.groupby(["YEAR", "MONTH"])[numeric_cols].sum(numeric_only=True).reset_index()
        monthly = monthly.sort_values(["YEAR", "MONTH"])
        results["monthly_trend"] = monthly
    else:
        results["yearly_trend"] = pd.DataFrame()
        results["monthly_trend"] = pd.DataFrame()

    # Overall totals for a concise summary.
    if numeric_cols:
        totals = df[numeric_cols].sum(numeric_only=True).to_frame(name="total").reset_index().rename(columns={"index": "metric"})
        results["totals"] = totals
    else:
        results["totals"] = pd.DataFrame(columns=["metric", "total"])

    return results
