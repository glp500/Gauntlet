from __future__ import annotations

import json
from pathlib import Path

from . import agents
from .data import build_data_card, infer_and_clean, load_dataset
from .history import central_run_dir, save_run_history
from .llm import OpenAIStructuredClient
from .models import AgentArtifacts, RunManifest, UserRequest
from .notebook import execute_notebook, trust_notebook, write_notebook
from .policy import has_blocking_decisions, validate_chart_specs, validate_layout_plan
from .themes import get_theme
from .trace import RunTracer

MAX_AUTOEXECUTE_ROWS = 20_000
MAX_AUTOEXECUTE_DATA_MB = 15.0


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def write_parquet_cache(cleaned_df, output_dir: Path) -> tuple[Path | None, str | None]:
    cache_path = output_dir / "cleaned_data.parquet"
    try:
        cleaned_df.to_parquet(cache_path, index=False)
    except Exception as exc:
        return None, f"Parquet cache was skipped because pandas could not write it: {type(exc).__name__}: {exc}"
    return cache_path, None


def should_autoexecute_notebook(cleaned_data_path: Path, row_count: int) -> tuple[bool, str | None]:
    size_mb = cleaned_data_path.stat().st_size / (1024 * 1024)
    reasons: list[str] = []
    if row_count > MAX_AUTOEXECUTE_ROWS:
        reasons.append(f"{row_count:,} rows exceeds the auto-execution limit of {MAX_AUTOEXECUTE_ROWS:,} rows")
    if size_mb > MAX_AUTOEXECUTE_DATA_MB:
        reasons.append(f"{size_mb:.1f} MB exceeds the auto-execution limit of {MAX_AUTOEXECUTE_DATA_MB:.1f} MB")
    if reasons:
        return (
            False,
            "Notebook auto-execution was skipped because "
            + " and ".join(reasons)
            + ". Embedded outputs can make large notebooks unstable in VS Code; open the notebook and run cells manually if needed.",
        )
    return True, None


def run_pipeline(*, dataset_path: Path, spec: str, output_dir: Path, offline: bool = False, model: str | None = None) -> RunManifest:
    request = UserRequest(dataset_path=dataset_path, spec=spec, output_dir=output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    agents_dir = output_dir / "agents"
    agents_dir.mkdir(exist_ok=True)
    trace_path = output_dir / "trace.jsonl"
    tracer = RunTracer(trace_path)
    history_dir = central_run_dir(run_id=tracer.run_id, dataset_path=request.dataset_path)
    tracer.add_mirror(history_dir / "trace.jsonl")
    tracer.event(
        "run",
        "start",
        dataset_path=request.dataset_path,
        spec=request.spec,
        output_dir=request.output_dir,
        central_history_dir=history_dir,
        offline=offline,
        model=model,
    )

    client = None if offline else OpenAIStructuredClient(model=model, tracer=tracer)
    with tracer.stage("data_loading", dataset_path=request.dataset_path):
        raw_df = load_dataset(request.dataset_path)
        tracer.event("data_loading", "loaded", rows=len(raw_df), columns=list(raw_df.columns))

    with tracer.stage("data_cleaning"):
        cleaned_df, duplicates_removed = infer_and_clean(raw_df)
        tracer.event(
            "data_cleaning",
            "cleaned",
            rows=len(cleaned_df),
            columns=list(cleaned_df.columns),
            duplicate_rows_removed=duplicates_removed,
        )

    cleaned_path = output_dir / "cleaned_data.csv"
    with tracer.stage("data_artifacts"):
        cleaned_df.to_csv(cleaned_path, index=False)
        cached_path, cache_note = write_parquet_cache(cleaned_df, output_dir)
        if cached_path:
            tracer.event("data_artifacts", "parquet_cache_written", path=cached_path)
        if cache_note:
            tracer.event("data_artifacts", "parquet_cache_skipped", reason=cache_note)

    with tracer.stage("data_card"):
        data_card = build_data_card(request.dataset_path, cleaned_df, duplicates_removed)
        write_json(output_dir / "data_card.json", data_card.model_dump())
        tracer.event("data_card", "profiled", rows=data_card.row_count, columns=data_card.column_count)

    with tracer.stage("data_analyst"):
        analysis_plan = agents.create_analysis_plan(data_card, request.spec, client)
        write_json(agents_dir / "data_analyst.json", analysis_plan.model_dump())

    with tracer.stage("theme"):
        theme_choice = agents.select_theme(analysis_plan, client)
        write_json(agents_dir / "theme.json", theme_choice.model_dump())

    with tracer.stage("table_creator"):
        table_plan = agents.create_table_plan(data_card, analysis_plan, client)
        write_json(agents_dir / "table_creator.json", table_plan.model_dump())

    with tracer.stage("chart_orchestrator"):
        chart_orchestration = agents.orchestrate_charts(data_card, analysis_plan, theme_choice, client)
        write_json(agents_dir / "chart_orchestrator.json", chart_orchestration.model_dump())

    with tracer.stage("chart_makers"):
        chart_specs = agents.build_chart_specs(chart_orchestration, data_card, client)
        before_refinement = [chart.model_dump() for chart in chart_specs]
        chart_specs = agents.refine_chart_specs_with_data(chart_specs, cleaned_df, data_card)
        after_refinement = [chart.model_dump() for chart in chart_specs]
        if before_refinement != after_refinement:
            tracer.event("chart_makers", "data_aware_refinement", before=before_refinement, after=after_refinement)
        write_json(agents_dir / "chart_makers.json", [chart.model_dump() for chart in chart_specs])

    with tracer.stage("layout"):
        layout_plan = agents.create_layout_plan(analysis_plan, table_plan, chart_specs, client)
        write_json(agents_dir / "layout.json", layout_plan.model_dump())

    validation_report_path = output_dir / "validation_report.json"
    with tracer.stage("policy_validation"):
        chart_decisions = validate_chart_specs(chart_specs, data_card)
        layout_decisions = validate_layout_plan(layout_plan, table_plan, chart_specs)
        policy_decisions = chart_decisions + layout_decisions
        write_json(validation_report_path, [decision.model_dump() for decision in policy_decisions])
        tracer.event("policy_validation", "decisions", decisions=[decision.model_dump() for decision in policy_decisions])
        if has_blocking_decisions(policy_decisions):
            raise ValueError(f"Policy validation blocked notebook generation. See {validation_report_path}.")

    notebook_path = output_dir / "exploration.ipynb"
    should_execute, runtime_note = should_autoexecute_notebook(cleaned_path, data_card.row_count)
    runtime_notes = [runtime_note] if runtime_note else []
    if cache_note:
        runtime_notes.append(cache_note)
    notebook_data_path = cached_path or cleaned_path
    with tracer.stage("notebook_write", notebook_data_path=notebook_data_path):
        write_notebook(
            path=notebook_path,
            cleaned_data_path=notebook_data_path,
            data_card=data_card,
            analysis_plan=analysis_plan,
            theme=get_theme(theme_choice),
            table_plan=table_plan,
            chart_specs=chart_specs,
            layout_plan=layout_plan,
            runtime_notes=runtime_notes,
        )

    notebook_executed = False
    if should_execute:
        with tracer.stage("notebook_execute"):
            execute_notebook(notebook_path)
            trust_notebook(notebook_path)
            notebook_executed = True
    else:
        tracer.event("notebook_execute", "skipped", reason=runtime_note)

    artifacts = AgentArtifacts(
        analysis_plan=analysis_plan,
        theme_choice=theme_choice,
        table_plan=table_plan,
        chart_orchestration=chart_orchestration,
        chart_specs=chart_specs,
        layout_plan=layout_plan,
    )
    manifest = RunManifest(
        request=request,
        cleaned_data_path=str(cleaned_path),
        notebook_path=str(notebook_path),
        data_card=data_card,
        artifacts=artifacts,
        offline=offline,
        model=None if offline else (model or getattr(client, "model", None)),
        notebook_executed=notebook_executed,
        runtime_notes=runtime_notes,
        trace_path=str(trace_path),
        validation_report_path=str(validation_report_path),
        cached_data_path=str(cached_path) if cached_path else None,
        central_history_dir=str(history_dir),
    )
    write_json(output_dir / "manifest.json", manifest.model_dump())
    tracer.event("run", "end", manifest=manifest)
    save_run_history(
        run_dir=output_dir,
        destination=history_dir,
        run_id=tracer.run_id,
        manifest=manifest,
        extra={"trace_path": trace_path, "validation_report_path": validation_report_path},
    )
    return manifest
