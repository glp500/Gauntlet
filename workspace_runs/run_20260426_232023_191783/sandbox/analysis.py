from __future__ import annotations

import pandas as pd


def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Compute descriptive summaries and key aggregates for the dataset."""
    if "sales" not in data:
        raise KeyError("Expected key 'sales' in input data dictionary.")

    df = data["sales"].copy()
    results: dict[str, pd.DataFrame] = {}

    results["structure"] = pd.DataFrame(
        {
            "rows": [len(df)],
            "columns": [df.shape[1]],
            "missing_values_total": [int(df.isna().sum().sum())],
            "duplicate_rows": [int(df.duplicated().sum())],
        }
    )

    numeric_cols = [c for c in ["RETAIL SALES", "RETAIL TRANSFERS", "WAREHOUSE SALES"] if c in df.columns]
    results["numeric_describe"] = df[numeric_cols].describe().T if numeric_cols else pd.DataFrame()

    if {"YEAR", "MONTH"}.issubset(df.columns) and numeric_cols:
        monthly = (
            df.dropna(subset=["YEAR", "MONTH"])
            .groupby(["YEAR", "MONTH"], dropna=False)[numeric_cols]
            .sum()
            .reset_index()
            .sort_values(["YEAR", "MONTH"])
        )
        monthly["YEAR_MONTH"] = monthly["YEAR"].astype(str) + "-" + monthly["MONTH"].astype(str).str.zfill(2)
        results["monthly_summary"] = monthly
    else:
        results["monthly_summary"] = pd.DataFrame()

    if "ITEM TYPE" in df.columns and numeric_cols:
        results["item_type_summary"] = (
            df.groupby("ITEM TYPE", dropna=False)[numeric_cols]
            .sum()
            .sort_values(by=numeric_cols[0], ascending=False)
            .reset_index()
        )
    else:
        results["item_type_summary"] = pd.DataFrame()

    if "SUPPLIER" in df.columns and numeric_cols:
        results["supplier_summary"] = (
            df.groupby("SUPPLIER", dropna=False)[numeric_cols]
            .sum()
            .sort_values(by=numeric_cols[0], ascending=False)
            .reset_index()
            .head(10)
        )
    else:
        results["supplier_summary"] = pd.DataFrame()

    if "ITEM DESCRIPTION" in df.columns and numeric_cols:
        results["top_products"] = (
            df.groupby("ITEM DESCRIPTION", dropna=False)[numeric_cols]
            .sum()
            .sort_values(by=numeric_cols[0], ascending=False)
            .reset_index()
            .head(10)
        )
    else:
        results["top_products"] = pd.DataFrame()

    return results
