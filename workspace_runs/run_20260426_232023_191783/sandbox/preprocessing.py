from __future__ import annotations

import pandas as pd


def preprocess(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Clean text fields and standardize numeric/time columns."""
    if "sales" not in data:
        raise KeyError("Expected key 'sales' in input data dictionary.")

    df = data["sales"].copy()

    for col in ["SUPPLIER", "ITEM CODE", "ITEM DESCRIPTION", "ITEM TYPE"]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    for col in ["YEAR", "MONTH"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in ["RETAIL SALES", "RETAIL TRANSFERS", "WAREHOUSE SALES"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(how="all").reset_index(drop=True)
    return {"sales": df}
