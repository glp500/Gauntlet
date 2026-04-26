from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

def create_figures(data: dict[str, pd.DataFrame], results: dict[str, pd.DataFrame], output_dir: str) -> list[str]:
    figure_dir = Path(output_dir)
    figure_dir.mkdir(parents=True, exist_ok=True)
    frame = results["revenue_by_region"]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(frame["region"], frame["revenue"])
    ax.set_title("Revenue by Region")
    destination = figure_dir / "revenue_by_region.png"
    fig.tight_layout()
    fig.savefig(destination)
    plt.close(fig)
    return [str(destination)]
