from __future__ import annotations

import pandas as pd


def preprocess(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Basic cleanup: standardize column names, types, and missing values."""
    processed: dict[str, pd.DataFrame] = {}

    for key, df in data.items():
        out = df.copy()

        # Standardize column names for easier downstream handling.
        out.columns = [str(c).strip() for c in out.columns]

        # Ensure expected categorical columns are strings when present.
        for col in ["SUPPLIER", "ITEM CODE", "ITEM DESCRIPTION", "ITEM TYPE"]:
            if col in out.columns:
                out[col] = out[col].astype("string").fillna("Unknown")

        # Ensure expected time columns are numeric.
        for col in ["YEAR", "MONTH"]:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

        # Ensure sales columns are numeric.
        for col in ["RETAIL SALES", "RETAIL TRANSFERS", "WAREHOUSE SALES"]:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce")

        # Drop rows missing essential time/category fields only if necessary.
        essential = [c for c in ["YEAR", "MONTH", "ITEM TYPE"] if c in out.columns]
        if essential:
            out = out.dropna(subset=essential)

        processed[key] = out

    return processed
