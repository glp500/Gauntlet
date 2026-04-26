"""Fixed sandbox runtime that orchestrates generated analysis modules."""

from __future__ import annotations

import traceback
from pathlib import Path

import pandas as pd

from analysis import run_analysis
from data_loader import load_data
from figures import create_figures
from preprocessing import preprocess


def _write_results(results: dict[str, pd.DataFrame], output_dir: Path) -> list[str]:
    """Persist result tables returned by the generated analysis module."""
    written_paths: list[str] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for table_name, frame in results.items():
        if not isinstance(frame, pd.DataFrame):
            raise TypeError(f"Analysis result '{table_name}' is not a pandas DataFrame.")

        destination = output_dir / f"{table_name}.csv"
        frame.to_csv(destination, index=False)
        written_paths.append(str(destination))

    return written_paths


def main() -> None:
    """Run the generated analysis pipeline with deterministic paths."""
    sandbox_dir = Path(__file__).resolve().parent
    run_root = sandbox_dir.parent
    input_dir = sandbox_dir / "inputs" / "data"
    results_dir = run_root / "outputs" / "results"
    figures_dir = run_root / "outputs" / "figures"

    data = load_data(str(input_dir))
    processed_data = preprocess(data)
    analysis_results = run_analysis(processed_data)

    written_results = _write_results(analysis_results, results_dir)
    written_figures = create_figures(processed_data, analysis_results, str(figures_dir))

    print("Results written:")
    for path in written_results:
        print(path)

    print("Figures written:")
    for path in written_figures:
        print(path)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
