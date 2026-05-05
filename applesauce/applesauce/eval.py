from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .pipeline import run_pipeline


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def _cell_source(cell: dict[str, Any]) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _check(condition: bool, name: str, details: str = "") -> dict[str, Any]:
    return {"name": name, "passed": bool(condition), "details": details}


def evaluate_run(run_dir: Path) -> list[dict[str, Any]]:
    manifest_path = run_dir / "manifest.json"
    manifest = _load_json(manifest_path)
    notebook_path = Path(manifest["notebook_path"])
    if not notebook_path.is_absolute():
        notebook_path = Path.cwd() / notebook_path
    trace_path = Path(manifest.get("trace_path") or run_dir / "trace.jsonl")
    validation_path = Path(manifest.get("validation_report_path") or run_dir / "validation_report.json")
    if not trace_path.is_absolute():
        trace_path = Path.cwd() / trace_path
    if not validation_path.is_absolute():
        validation_path = Path.cwd() / validation_path

    notebook = _load_json(notebook_path)
    validation = _load_json(validation_path)
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    markdown_heads = [_cell_source(cell).splitlines()[0] for cell in notebook["cells"] if cell["cell_type"] == "markdown" and _cell_source(cell).strip()]
    trace_lines = trace_path.read_text(encoding="utf-8").splitlines()
    chart_specs = manifest["artifacts"]["chart_specs"]
    chart_signatures = {
        (chart["chart_type"], chart["x"], chart.get("y"), chart.get("color"), chart.get("aggregation"))
        for chart in chart_specs
    }
    explorer_index = next((index for index, head in enumerate(markdown_heads) if head.startswith("## Dataset Explorer")), None)
    first_chart_index = next((index for index, head in enumerate(markdown_heads) if head.startswith("## ") and "Dataset Explorer" not in head and "Data Card" not in head and "Analysis Plan" not in head and "Runtime Notes" not in head), None)

    checks = [
        _check(notebook_path.exists(), "notebook_exists", str(notebook_path)),
        _check(trace_path.exists() and len(trace_lines) >= 10, "trace_has_events", str(trace_path)),
        _check(validation_path.exists(), "validation_report_exists", str(validation_path)),
        _check(not any(item["action"] == "block" for item in validation), "validation_has_no_blocks"),
        _check(bool(code_cells), "notebook_has_code_cells"),
        _check(len(chart_signatures) == len(chart_specs), "chart_specs_are_unique"),
        _check(explorer_index is not None and (first_chart_index is None or explorer_index < first_chart_index), "dataset_explorer_before_charts"),
    ]

    for index, cell in enumerate(code_cells):
        try:
            compile(_cell_source(cell), f"<notebook-cell-{index}>", "exec")
        except SyntaxError as exc:
            checks.append(_check(False, "code_cells_compile", str(exc)))
            break
    else:
        checks.append(_check(True, "code_cells_compile"))

    if manifest["data_card"]["row_count"] > 20_000:
        checks.append(_check(manifest["notebook_executed"] is False, "large_run_skips_autoexecution"))
        checks.append(_check(notebook_path.stat().st_size < 1_000_000, "large_notebook_stays_small", f"{notebook_path.stat().st_size} bytes"))

    return checks


def _write_large_fixture(path: Path, rows: int = 25_000) -> None:
    df = pd.DataFrame(
        {
            "row_id": range(rows),
            "segment": [f"group_{index % 5}" for index in range(rows)],
            "metric": [float(index % 997) for index in range(rows)],
            "score": [float((index * 7) % 1000) / 10 for index in range(rows)],
        }
    )
    df.to_csv(path, index=False)


def run_eval(output_dir: Path, *, include_large: bool = False) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []

    mixed_run = output_dir / "mixed"
    run_pipeline(
        dataset_path=FIXTURE_DIR / "mixed.csv",
        spec="Explore revenue, cost, quality, and regional segments",
        output_dir=mixed_run,
        offline=True,
    )
    runs.append({"name": "mixed", "checks": evaluate_run(mixed_run)})

    if include_large:
        large_fixture = output_dir / "large_fixture.csv"
        _write_large_fixture(large_fixture)
        large_run = output_dir / "large"
        run_pipeline(
            dataset_path=large_fixture,
            spec="Explore metric and score patterns by segment",
            output_dir=large_run,
            offline=True,
        )
        runs.append({"name": "large", "checks": evaluate_run(large_run)})

    passed = sum(1 for run in runs for check in run["checks"] if check["passed"])
    total = sum(len(run["checks"]) for run in runs)
    report = {"passed": passed, "total": total, "runs": runs}
    (output_dir / "eval_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
