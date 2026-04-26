from __future__ import annotations

from typing import Dict

import pandas as pd


def preprocess(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Clean and standardize the loaded sales data.

    This function keeps the schema limited to the provided columns and performs
    conservative cleaning so the analysis is explicit and reproducible.
    """
    df = data["sales"].copy()

    expected_columns = [
        "YEAR",
        "MONTH",
        "SUPPLIER",
        "ITEM CODE",
        "ITEM DESCRIPTION",
        "ITEM TYPE",
        "RETAIL SALES",
        "RETAIL TRANSFERS",
        "WAREHOUSE SALES",
    ]
    df = df[expected_columns]

    text_columns = ["SUPPLIER", "ITEM CODE", "ITEM DESCRIPTION", "ITEM TYPE"]
    for col in text_columns:
        df[col] = df[col].astype("string").str.strip()

    numeric_columns = ["YEAR", "MONTH", "RETAIL SALES", "RETAIL TRANSFERS", "WAREHOUSE SALES"]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["YEAR", "MONTH"])
    df["YEAR"] = df["YEAR"].astype(int)
    df["MONTH"] = df["MONTH"].astype(int)

    for col in ["RETAIL SALES", "RETAIL TRANSFERS", "WAREHOUSE SALES"]:
        df[col] = df[col].fillna(0.0)

    df = df.dropna(subset=text_columns)
    df = df[(df["MONTH"] >= 1) & (df["MONTH"] <= 12)]

    return {"sales": df}
