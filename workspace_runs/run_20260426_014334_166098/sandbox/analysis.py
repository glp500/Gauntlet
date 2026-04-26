from __future__ import annotations

import pandas as pd


def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Compute summary tables describing the main patterns in the dataset."""
    df = data["sales"].copy()

    metric_cols = ["RETAIL SALES", "RETAIL TRANSFERS", "WAREHOUSE SALES"]

    overall_summary = pd.DataFrame(
        {
            "metric": metric_cols,
            "total": [df[col].sum() for col in metric_cols],
            "mean": [df[col].mean() for col in metric_cols],
            "median": [df[col].median() for col in metric_cols],
        }
    )

    year_summary = (
        df.groupby("YEAR", as_index=False)[metric_cols]
        .sum()
        .sort_values("YEAR")
        .reset_index(drop=True)
    )

    month_summary = (
        df.groupby("MONTH", as_index=False)[metric_cols]
        .sum()
        .sort_values("MONTH")
        .reset_index(drop=True)
    )

    item_type_summary = (
        df.groupby("ITEM TYPE", as_index=False)[metric_cols]
        .sum()
        .sort_values("RETAIL SALES", ascending=False)
        .reset_index(drop=True)
    )

    supplier_summary = (
        df.groupby("SUPPLIER", as_index=False)[metric_cols]
        .sum()
        .sort_values("RETAIL SALES", ascending=False)
        .reset_index(drop=True)
    )

    top_suppliers = supplier_summary.head(10).copy()
    top_items = (
        df.groupby(["ITEM CODE", "ITEM DESCRIPTION"], as_index=False)[metric_cols]
        .sum()
        .sort_values("RETAIL SALES", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )

    return {
        "overall_summary": overall_summary,
        "year_summary": year_summary,
        "month_summary": month_summary,
        "item_type_summary": item_type_summary,
        "supplier_summary": supplier_summary,
        "top_suppliers": top_suppliers,
        "top_items": top_items,
    }
