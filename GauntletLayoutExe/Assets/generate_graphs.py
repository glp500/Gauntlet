import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

FIG_BG = "#1e1e1e"
AX_BG = "#252526"
TEXT = "#d4d4d4"
GRID = "#3c3c3c"
BAR = "#007acc"
LINE = "#4ec9b0"


def ensure_numeric_columns(df: pd.DataFrame):
    numeric_df = df.apply(pd.to_numeric, errors="coerce")
    usable = [c for c in numeric_df.columns if numeric_df[c].notna().mean() >= 0.6]
    return numeric_df, usable


def save_histogram(series: pd.Series, output_path: str, title: str, xlabel: str, ylabel: str):
    cleaned = series.dropna()
    if cleaned.empty:
        return False
    fig, ax = plt.subplots(figsize=(12, 7), dpi=150, facecolor=FIG_BG)
    ax.set_facecolor(AX_BG)
    ax.hist(cleaned, bins=max(6, min(20, int(len(cleaned) ** 0.5))), color=BAR, edgecolor=GRID)
    ax.set_title(title, color=TEXT)
    ax.set_xlabel(xlabel, color=TEXT)
    ax.set_ylabel(ylabel, color=TEXT)
    ax.tick_params(colors=TEXT)
    ax.grid(alpha=0.2, color=GRID)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    plt.tight_layout()
    plt.savefig(output_path, facecolor=FIG_BG)
    plt.close()
    return True


def save_line(x_series: pd.Series, y_series: pd.Series, output_path: str, title: str, xlabel: str, ylabel: str):
    frame = pd.DataFrame({"x": x_series, "y": y_series}).dropna()
    if frame.empty:
        return False
    if frame["x"].nunique() <= 1:
        frame["x"] = range(1, len(frame) + 1)
    frame = frame.sort_values("x")
    fig, ax = plt.subplots(figsize=(12, 7), dpi=150, facecolor=FIG_BG)
    ax.set_facecolor(AX_BG)
    ax.plot(frame["x"], frame["y"], marker="o", linewidth=2, markersize=3, color=LINE)
    ax.set_title(title, color=TEXT)
    ax.set_xlabel(xlabel, color=TEXT)
    ax.set_ylabel(ylabel, color=TEXT)
    ax.tick_params(colors=TEXT)
    ax.grid(alpha=0.2, color=GRID)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    plt.tight_layout()
    plt.savefig(output_path, facecolor=FIG_BG)
    plt.close()
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--xcol", default="")
    parser.add_argument("--ycol", default="")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    df = pd.read_csv(args.input)
    numeric_df, numeric_cols = ensure_numeric_columns(df)

    generated = []
    x_col = args.xcol if args.xcol in numeric_df.columns else ""
    y_col = args.ycol if args.ycol in numeric_df.columns else ""

    if not x_col and numeric_cols:
        x_col = numeric_cols[0]
    if not y_col:
        if len(numeric_cols) >= 2:
            y_col = numeric_cols[1]
        elif numeric_cols:
            y_col = numeric_cols[0]

    histogram_columns = []
    for col in [x_col, y_col]:
        if col and col in numeric_cols and col not in histogram_columns:
            histogram_columns.append(col)
    if not histogram_columns:
        histogram_columns = numeric_cols[:2]

    for col in histogram_columns:
        title = f"{col} Distribution"
        out_path = os.path.join(args.output, f"hist_{col}.png")
        x_label = col
        y_label = "Count"
        if save_histogram(numeric_df[col], out_path, title, x_label, y_label):
            generated.append((title, out_path))

    if x_col and y_col and x_col in numeric_cols and y_col in numeric_cols:
        title = f"{x_col} vs {y_col}"
        out_path = os.path.join(args.output, f"line_{x_col}_{y_col}.png")
        x_label = x_col
        y_label = y_col
        if save_line(numeric_df[x_col], numeric_df[y_col], out_path, title, x_label, y_label):
            generated.append((title, out_path))

    with open(args.manifest, "w", encoding="utf-8") as f:
        for title, path in generated:
            f.write(f"{title}\t{path}\n")


if __name__ == "__main__":
    main()
