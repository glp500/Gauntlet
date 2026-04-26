from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def create_figures(data: dict[str, pd.DataFrame], results: dict[str, pd.DataFrame], output_dir: str) -> list[str]:
    """Create simple figures that support the written summary."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    saved_files: list[str] = []

    item_type_summary = results.get("item_type_summary", pd.DataFrame())
    if not item_type_summary.empty and "ITEM TYPE" in item_type_summary.columns:
        sales_col = "RETAIL SALES" if "RETAIL SALES" in item_type_summary.columns else item_type_summary.columns[1]
        plot_df = item_type_summary[["ITEM TYPE", sales_col]].copy()
        plot_df["ITEM TYPE"] = plot_df["ITEM TYPE"].fillna("Unknown").astype(str)
        plot_df[sales_col] = pd.to_numeric(plot_df[sales_col], errors="coerce").fillna(0.0)
        plot_df = plot_df.sort_values(by=sales_col, ascending=True)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(plot_df["ITEM TYPE"], plot_df[sales_col])
        ax.set_xlabel("Total Retail Sales")
        ax.set_ylabel("Item Type")
        ax.set_title("Total Retail Sales by Item Type")
        plt.tight_layout()

        file_path = output_path / "sales_by_item_type.png"
        fig.savefig(file_path, dpi=150)
        plt.close(fig)
        saved_files.append(str(file_path))

    monthly_summary = results.get("monthly_summary", pd.DataFrame())
    if not monthly_summary.empty and {"YEAR", "MONTH"}.issubset(monthly_summary.columns):
        sales_cols = [c for c in ["RETAIL SALES", "RETAIL TRANSFERS", "WAREHOUSE SALES"] if c in monthly_summary.columns]
        if sales_cols:
            fig, ax = plt.subplots(figsize=(12, 6))
            x = monthly_summary["YEAR"].astype(str) + "-" + monthly_summary["MONTH"].astype(str).str.zfill(2)
            for col in sales_cols:
                ax.plot(x, pd.to_numeric(monthly_summary[col], errors="coerce"), marker="o", linewidth=1.5, label=col)
            ax.set_xlabel("Year-Month")
            ax.set_ylabel("Total Amount")
            ax.set_title("Monthly Sales Trends")
            ax.legend()
            ax.tick_params(axis="x", rotation=45)
            plt.tight_layout()

            file_path = output_path / "monthly_trends.png"
            fig.savefig(file_path, dpi=150)
            plt.close(fig)
            saved_files.append(str(file_path))

    return saved_files
