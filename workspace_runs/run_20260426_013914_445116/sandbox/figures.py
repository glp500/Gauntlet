from __future__ import annotations

import os
from typing import List

import matplotlib.pyplot as plt
import pandas as pd


def create_figures(data: dict[str, pd.DataFrame], results: dict[str, pd.DataFrame], output_dir: str) -> list[str]:
    """Create figures that summarize the analysis."""
    os.makedirs(output_dir, exist_ok=True)
    df = data["teens"]
    paths: list[str] = []

    # Figure 1: depression label distribution
    if "depression_label" in df.columns:
        counts = df["depression_label"].value_counts().sort_index()
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(counts.index.astype(str), counts.values, color=["#4C78A8", "#F58518"])
        ax.set_title("Distribution of Depression Label")
        ax.set_xlabel("depression_label")
        ax.set_ylabel("Count")
        ax.grid(axis="y", alpha=0.25)
        path = os.path.join(output_dir, "depression_label_distribution.png")
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)

    # Figure 2: group comparison for a few key measures
    key_cols = [
        "daily_social_media_hours",
        "sleep_hours",
        "screen_time_before_sleep",
        "academic_performance",
        "physical_activity",
    ]
    key_cols = [c for c in key_cols if c in df.columns and "depression_label" in df.columns]
    if key_cols:
        summary = df.groupby("depression_label")[key_cols].mean().T
        fig, ax = plt.subplots(figsize=(9, max(4, 0.6 * len(key_cols) + 1)))
        summary.plot(kind="barh", ax=ax, width=0.8)
        ax.set_title("Average Key Measures by Depression Label")
        ax.set_xlabel("Mean value")
        ax.set_ylabel("Variable")
        ax.grid(axis="x", alpha=0.25)
        ax.legend(title="depression_label")
        path = os.path.join(output_dir, "key_measures_by_depression.png")
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)

    return paths
