from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


def load_data(input_dir: str) -> dict[str, pd.DataFrame]:
    """Load the warehouse and retail sales dataset from the input directory.

    Parameters
    ----------
    input_dir:
        Directory containing Warehouse_and_Retail_Sales.csv.

    Returns
    -------
    dict[str, pd.DataFrame]
        A dictionary with a single DataFrame under the key "sales".
    """
    input_path = Path(input_dir)
    file_path = input_path / "Warehouse_and_Retail_Sales.csv"

    df = pd.read_csv(file_path)

    return {"sales": df}
