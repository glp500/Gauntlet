from __future__ import annotations

from pathlib import Path
import pandas as pd


def load_data(input_dir: str) -> dict[str, pd.DataFrame]:
    """Load the warehouse and retail sales CSV into a dict of DataFrames."""
    input_path = Path(input_dir)
    csv_path = input_path / "Warehouse_and_Retail_Sales.csv"

    df = pd.read_csv(
        csv_path,
        low_memory=False,
    )

    return {"sales": df}
