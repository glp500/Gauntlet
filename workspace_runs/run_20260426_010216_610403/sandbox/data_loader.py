from pathlib import Path

import pandas as pd

def load_data(input_dir: str) -> dict[str, pd.DataFrame]:
    data = {}
    for csv_path in sorted(Path(input_dir).glob("*.csv")):
        data[csv_path.stem] = pd.read_csv(csv_path)
    return data
