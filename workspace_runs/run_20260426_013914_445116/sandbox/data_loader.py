from __future__ import annotations

import os
from typing import Dict

import pandas as pd


EXPECTED_FILENAME = "Teen_Mental_Health_Dataset.csv"


def load_data(input_dir: str) -> dict[str, pd.DataFrame]:
    """Load the dataset from the provided input directory.

    Returns a dictionary so the pipeline can remain flexible if more files are
    added later.
    """
    path = os.path.join(input_dir, EXPECTED_FILENAME)
    df = pd.read_csv(path)
    return {"teens": df}
