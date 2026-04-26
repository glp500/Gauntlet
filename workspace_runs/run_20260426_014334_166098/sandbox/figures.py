from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def create_figures(data: dict[str, pd.DataFrame], results: dict[str, pd.DataFrame], output_dir: str) -> list[str]:
    """Create figures that support the written summary."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[str] = []

    year_summary = results["year_summary"]
    item_type_summary = results["item_type_summary"]
    top_suppliers = results["top_suppliers"]

    if not year_summary.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(year_summary["YEAR"], year_summary["RETAIL SALES"], marker="o", label="Retail Sales")
        ax.plot(year_summary["YEAR"], year_summary["RETAIL TRANSFERS"], marker="o", label="Retail Transfers")
        ax.plot(year_summary["YEAR"], year_summary["WAREHOUSE SALES"], marker="o", label="Warehouse Sales")
        ax.set_title("Sales Trend by Year")
        ax.set_xlabel("Year")
        ax.set_ylabel("Total Sales")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = out_dir / "year_trend.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved_paths.append(str(path))

    if not item_type_summary.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(item_type_summary["ITEM TYPE"].astype(str), item_type_summary["RETAIL SALES"], color="#4C78A8")
        ax.set_title("Retail Sales by Item Type")
        ax.set_xlabel("Item Type")
        ax.set_ylabel("Total Retail Sales")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        path = out_dir / "item_type_sales.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved_paths.append(str(path))

    if not top_suppliers.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        labels = top_suppliers["SUPPLIER"].astype(str)
        ax.barh(labels[::-1], top_suppliers["RETAIL SALES"].iloc[::-1], color="#F58518")
        ax.set_title("Top 10 Suppliers by Retail Sales")
        ax.set_xlabel("Total Retail Sales")
        ax.set_ylabel("Supplier")
        ax.grid(True, axis="x", alpha=0.3)
        fig.tight_layout()
        path = out_dir / "top_suppliers.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved_paths.append(str(path))

    return saved_paths
