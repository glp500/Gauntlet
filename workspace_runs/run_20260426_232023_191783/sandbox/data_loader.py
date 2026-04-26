from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_data(input_dir: str) -> dict[str, pd.DataFrame]:
    """Load the warehouse and retail sales dataset.

    Returns a dictionary keyed by the shared contract name expected by the
    preprocessing and analysis steps.
    """
    csv_path = Path(input_dir) / "Warehouse_and_Retail_Sales.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Could not find input file: {csv_path}")

    dtype_map = {
        "YEAR": "Int64",
        "MONTH": "Int64",
        "SUPPLIER": "string",
        "ITEM CODE": "string",
        "ITEM DESCRIPTION": "string",
        "ITEM TYPE": "string",
        "RETAIL SALES": "float64",
        "RETAIL TRANSFERS": "float64",
        "WAREHOUSE SALES": "float64",
    }

    df = pd.read_csv(csv_path, dtype=dtype_map)
    return {"sales": df}
