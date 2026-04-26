from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


DEFAULT_FILENAME = "Teen_Mental_Health_Dataset.csv"


def load_dataset(input_dir: str | Path, filename: str = DEFAULT_FILENAME) -> pd.DataFrame:
    """Load the teen mental health dataset from the provided input directory.

    Parameters
    ----------
    input_dir:
        Directory containing the CSV file.
    filename:
        CSV filename. Defaults to the expected dataset file name.

    Returns
    -------
    pd.DataFrame
        Loaded dataset.
    """
    input_path = Path(input_dir)
    csv_path = input_path / filename
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")
    return pd.read_csv(csv_path)
