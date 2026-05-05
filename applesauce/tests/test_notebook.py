import json
from pathlib import Path

from applesauce.models import ChartSpec, TableSpec
from applesauce.notebook import chart_code, table_code
from applesauce.pipeline import run_pipeline, should_autoexecute_notebook


FIXTURE = Path(__file__).parent / "fixtures" / "mixed.csv"


def _cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return source


def test_pipeline_writes_valid_notebook(tmp_path: Path, monkeypatch) -> None:
    history_root = tmp_path / "history"
    monkeypatch.setenv("APPLESAUCE_RUN_HISTORY_DIR", str(history_root))
    manifest = run_pipeline(
        dataset_path=FIXTURE,
        spec="Explore revenue, cost, and regional segments",
        output_dir=tmp_path,
        offline=True,
    )

    notebook_path = Path(manifest.notebook_path)
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

    assert notebook["nbformat"] == 4
    assert any("Data Card" in _cell_source(cell) for cell in notebook["cells"])
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert code_cells
    assert all(isinstance(cell["metadata"], dict) for cell in code_cells)
    assert any(cell.get("execution_count") is not None for cell in code_cells)
    assert any(cell.get("outputs") for cell in code_cells[1:])
    combined_source = "\n".join(_cell_source(cell) for cell in code_cells)
    assert "_display_data_grid" in combined_source
    assert "DataTable" in combined_source
    assert "applesauce-grid-viewport" in combined_source
    assert "pageLength: 50" in combined_source
    assert "nrows=50" in combined_source
    assert "_sample_plot_df" in combined_source
    assert 'colorway=PALETTE' in combined_source
    for cell in code_cells:
        compile(_cell_source(cell), "<notebook-cell>", "exec")
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "agents" / "chart_makers.json").exists()
    assert Path(manifest.trace_path).exists()
    assert Path(manifest.validation_report_path).exists()
    assert "trace.jsonl" in Path(manifest.trace_path).name
    trace_lines = Path(manifest.trace_path).read_text(encoding="utf-8").splitlines()
    assert any('"stage": "policy_validation"' in line for line in trace_lines)
    validation = json.loads(Path(manifest.validation_report_path).read_text(encoding="utf-8"))
    assert not any(item["action"] == "block" for item in validation)
    central_dir = Path(manifest.central_history_dir)
    assert central_dir.exists()
    assert (central_dir / "trace.jsonl").exists()
    assert (central_dir / "manifest.json").exists()
    assert (central_dir / "validation_report.json").exists()
    assert (central_dir / "agents" / "chart_makers.json").exists()
    assert (central_dir / "run_summary.json").exists()
    assert (history_root / "index.jsonl").exists()
    central_trace_lines = (central_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(central_trace_lines) == len(trace_lines)


def test_bar_chart_renderer_supports_grouped_categorical_breakdown() -> None:
    spec = ChartSpec(
        id="depression_social_interaction",
        title="Prevalence of Depression by Social Interaction Level",
        description="Show depression label across social interaction levels.",
        chart_type="bar",
        x="social_interaction_level",
        y=None,
        color="depression_label",
    )

    code = chart_code(spec)

    assert 'groupby([' in code
    assert 'color=\'depression_label\'' in code
    assert "barmode=" in code
    assert "group" in code


def test_bar_chart_renderer_supports_rate_aggregation() -> None:
    spec = ChartSpec(
        id="depression_social_interaction",
        title="Rate of Depression Label by Social Interaction Level",
        description="Show depression rate across social interaction levels.",
        chart_type="bar",
        x="social_interaction_level",
        y=None,
        color="depression_label",
        aggregation="rate",
        bar_mode="group",
        target_value="yes",
    )

    code = chart_code(spec)

    assert 'target_flag' in code
    assert 'mean().reset_index(name="rate")' in code
    assert '.0%' in code


def test_bar_chart_renderer_supports_count_coverage_with_value_column() -> None:
    spec = ChartSpec(
        id="dollar_coverage_by_source",
        title="Dollars by Source and State",
        description="Count records with non-null dollar values by source and state.",
        chart_type="bar",
        x="source",
        y="dollars",
        color="state",
        aggregation="count",
        bar_mode="group",
    )

    code = chart_code(spec)

    assert '.notna()' in code
    assert 'groupby([\'source\', \'state\']' in code
    assert '"count"' in code
    assert 'color=\'state\'' in code


def test_bar_chart_renderer_supports_segmented_rate_aggregation() -> None:
    spec = ChartSpec(
        id="depression_by_gender",
        title="Rate of Depression Label by Gender and Platform Usage",
        description="Show depression prevalence by gender and platform usage.",
        chart_type="bar",
        x="gender",
        y="depression_label",
        color="platform_usage",
        aggregation="rate",
        bar_mode="group",
        target_value="1",
    )

    code = chart_code(spec)

    assert "depression_label" in code
    assert "platform_usage" in code
    assert 'groupby([\'gender\', \'platform_usage\']' in code
    assert 'color=\'platform_usage\'' in code


def test_renderer_supports_violin_and_heatmap() -> None:
    violin = ChartSpec(
        id="stress_distribution",
        title="Distribution of Stress Level by Gender",
        description="Show stress spread by gender.",
        chart_type="violin",
        x="gender",
        y="stress_level",
    )
    heatmap = ChartSpec(
        id="platform_gender_heatmap",
        title="Platform Usage vs Gender",
        description="Show category concentration.",
        chart_type="heatmap",
        x="platform_usage",
        y="gender",
        aggregation="count",
    )

    violin_code = chart_code(violin)
    heatmap_code = chart_code(heatmap)

    assert "px.violin" in violin_code
    assert "px.density_heatmap" in heatmap_code


def test_heatmap_renderer_supports_numeric_sum_and_log_transform() -> None:
    heatmap = ChartSpec(
        id="state_year_pounds_heatmap",
        title="Total of Pounds across Year and State",
        description="Show volume concentration.",
        chart_type="heatmap",
        x="year",
        y="state",
        color="pounds",
        aggregation="sum",
        log_value_axis=True,
    )

    code = chart_code(heatmap)

    assert "math.log10" in code
    assert "pounds" in code
    assert "px.density_heatmap" in code


def test_bar_chart_renderer_supports_top_bottom_focus() -> None:
    spec = ChartSpec(
        id="top_bottom_country_happiness",
        title="Top and Bottom Countries by Average Happiness Score",
        description="Focused comparison.",
        chart_type="bar",
        x="country",
        y="happiness_score",
        aggregation="mean",
        orientation="h",
        sort_descending=True,
        limit_mode="top_bottom",
        limit_n=10,
    )

    code = chart_code(spec)

    assert "_limit_categories" in code
    assert "mode='top_bottom'" in code
    assert "n=10" in code
    assert "orientation='h'" in code


def test_sample_table_renderer_limits_embedded_rows() -> None:
    spec = TableSpec(
        id="dataset_explorer",
        title="Dataset Explorer",
        description="Interactive dataset view.",
        kind="sample",
        max_rows=50,
        focus_columns=["revenue", "region"],
    )

    code = table_code(spec)

    assert "nrows=50" in code


def test_scatter_renderer_downsamples_large_frames() -> None:
    spec = ChartSpec(
        id="revenue_vs_cost",
        title="Revenue vs Cost",
        description="Relationship chart.",
        chart_type="scatter",
        x="cost",
        y="revenue",
        color="region",
    )

    code = chart_code(spec)

    assert "_sample_plot_df" in code
    assert "px.scatter(plot_df" in code


def test_large_cleaned_dataset_skips_autoexecution(tmp_path: Path) -> None:
    large_csv = tmp_path / "large.csv"
    large_csv.write_bytes(b"x\n" + (b"a" * 1024 + b"\n") * 20_000)

    should_execute, reason = should_autoexecute_notebook(large_csv, row_count=20_000)

    assert should_execute is False
    assert reason is not None
    assert "auto-execution was skipped" in reason.lower()
