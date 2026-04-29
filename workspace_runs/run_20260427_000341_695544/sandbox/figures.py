from __future__ import annotations

from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd


def create_figures(data: dict[str, pd.DataFrame], results: dict[str, pd.DataFrame], output_dir: str) -> list[str]:
    """Create figures supporting the analysis and save them to output_dir."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[str] = []

    # Figure 1: total sales by item type.
    item_type = results.get("item_type_summary", pd.DataFrame())
    if not item_type.empty and "ITEM TYPE" in item_type.columns:
        y_col = "RETAIL SALES" if "RETAIL SALES" in item_type.columns else None
        if y_col is not None:
            fig, ax = plt.subplots(figsize=(10, 6))
            plot_df = item_type.sort_values(y_col, ascending=False).head(10)
            ax.bar(plot_df["ITEM TYPE"].astype(str), plot_df[y_col])
            ax.set_title("Top Item Types by Total Retail Sales")
            ax.set_xlabel("Item Type")
            ax.set_ylabel("Total Retail Sales")
            ax.tick_params(axis="x", rotation=45)
            fig.tight_layout()
            p = out_dir / "item_type_sales.png"
            fig.savefig(p, dpi=150)
            plt.close(fig)
            paths.append(str(p))

    # Figure 2: yearly sales trend.
    yearly = results.get("yearly_trend", pd.DataFrame())
    if not yearly.empty and "YEAR" in yearly.columns:
        fig, ax = plt.subplots(figsize=(10, 6))
        for col, label in [
            ("RETAIL SALES", "Retail Sales"),
            ("RETAIL TRANSFERS", "Retail Transfers"),
            ("WAREHOUSE SALES", "Warehouse Sales"),
        ]:
            if col in yearly.columns:
                ax.plot(yearly["YEAR"], yearly[col], marker="o", label=label)
        ax.set_title("Sales Trend by Year")
        ax.set_xlabel("Year")
        ax.set_ylabel("Total Sales")
        ax.legend()
        fig.tight_layout()
        p = out_dir / "yearly_sales_trend.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        paths.append(str(p))

    return paths
