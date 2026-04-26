from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def save_depression_by_social_media_hours(df: pd.DataFrame, output_dir: str | Path) -> str:
    """Save a figure showing average depression label by social media hour bins."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = df.copy()
    if data.empty:
        raise ValueError("Input DataFrame is empty.")

    hours = data["daily_social_media_hours"]
    bins = [hours.min() - 1e-9, 1, 2, 3, 4, hours.max() + 1e-9]
    labels = ["<=1", "1-2", "2-3", "3-4", ">4"]
    data["social_media_bin"] = pd.cut(hours, bins=bins, labels=labels, include_lowest=True, duplicates="drop")

    plot_data = (
        data.groupby("social_media_bin", observed=False)["depression_label"]
        .mean()
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(plot_data["social_media_bin"].astype(str), plot_data["depression_label"], color="#4C78A8")
    ax.set_xlabel("Daily social media hours (binned)")
    ax.set_ylabel("Mean depression label")
    ax.set_title("Depression prevalence by daily social media use")
    ax.set_ylim(0, 1)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    output_path = out_dir / "depression_by_social_media_hours.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(output_path)
