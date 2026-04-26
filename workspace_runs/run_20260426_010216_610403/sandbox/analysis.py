import pandas as pd

def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    frame = data["sample"]
    summary = frame.groupby("region", as_index=False)["revenue"].sum()
    return {"revenue_by_region": summary}
