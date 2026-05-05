from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import agents
from ..data import build_data_card, infer_and_clean, load_dataset
from ..history import central_run_dir, save_run_history
from ..models import AgentArtifacts, ChartOrchestration, ChartPlan, LayoutPlan, RunManifest, UserRequest
from ..notebook import execute_notebook, trust_notebook, write_notebook
from ..pipeline import should_autoexecute_notebook, write_json, write_parquet_cache
from ..policy import has_blocking_decisions, validate_chart_specs, validate_layout_plan
from ..themes import get_theme
from ..trace import RunTracer
from .client import OpenAICompatibleLocalClient
from .heuristics import (
    build_analysis_plan,
    build_layout_plan,
    build_table_plan,
    build_theme_choice,
    candidate_charts,
    candidate_questions,
    candidate_themes,
    compact_card_summary,
    filter_candidates_by_ids,
)
from .models import CandidateChart, OptionSelection, ThemeSelection, TitlePolish
from .prompts import chart_selection_prompt, layout_selection_prompt, question_selection_prompt, theme_selection_prompt, title_polish_prompt


@dataclass(frozen=True)
class LocalModelSettings:
    base_url: str
    model: str
    api_key: str = "local-not-needed"


def run_pipeline(*, dataset_path: Path, spec: str, output_dir: Path, settings: LocalModelSettings, client: OpenAICompatibleLocalClient | None = None) -> RunManifest:
    request = UserRequest(dataset_path=dataset_path, spec=spec, output_dir=output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    agents_dir = output_dir / "agents"
    agents_dir.mkdir(exist_ok=True)
    trace_path = output_dir / "trace.jsonl"
    tracer = RunTracer(trace_path)
    history_dir = central_run_dir(run_id=tracer.run_id, dataset_path=request.dataset_path)
    tracer.add_mirror(history_dir / "trace.jsonl")
    tracer.event(
        "run_it_yaself",
        "start",
        dataset_path=request.dataset_path,
        spec=request.spec,
        output_dir=request.output_dir,
        central_history_dir=history_dir,
        model=settings.model,
        base_url=settings.base_url,
    )

    local_client = client or OpenAICompatibleLocalClient(
        base_url=settings.base_url,
        model=settings.model,
        api_key=settings.api_key,
        tracer=tracer,
    )

    with tracer.stage("data_loading", dataset_path=request.dataset_path):
        raw_df = load_dataset(request.dataset_path)
        tracer.event("data_loading", "loaded", rows=len(raw_df), columns=list(raw_df.columns))

    with tracer.stage("data_cleaning"):
        cleaned_df, duplicates_removed = infer_and_clean(raw_df)
        tracer.event("data_cleaning", "cleaned", rows=len(cleaned_df), columns=list(cleaned_df.columns), duplicate_rows_removed=duplicates_removed)

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

    card_summary = compact_card_summary(data_card)

    with tracer.stage("data_analyst"):
        question_candidates = candidate_questions(data_card, request.spec)
        question_selection = _safe_select_options(
            client=local_client,
            stage="data_analyst",
            prompt=question_selection_prompt(
                spec=request.spec,
                card_summary=card_summary,
                candidates=[candidate.model_dump() for candidate in question_candidates],
            ),
            fallback_ids=[candidate.id for candidate in question_candidates[:4]],
        )
        selected_questions = [candidate for candidate in question_candidates if candidate.id in question_selection.selected_ids]
        analysis_plan = build_analysis_plan(spec=request.spec, selected_questions=selected_questions, fallback_questions=question_candidates)
        write_json(agents_dir / "data_analyst.json", {"selection": question_selection.model_dump(), "analysis_plan": analysis_plan.model_dump()})

    with tracer.stage("theme"):
        theme_candidates = candidate_themes(request.spec)
        theme_selection = _safe_select_theme(
            client=local_client,
            prompt=theme_selection_prompt(
                spec=request.spec,
                plan_summary={"objective": analysis_plan.objective, "tone": analysis_plan.tone, "key_questions": analysis_plan.key_questions},
                candidates=[candidate.model_dump() for candidate in theme_candidates],
            ),
        )
        theme_choice = build_theme_choice(selected_name=theme_selection.selected_name, candidates=theme_candidates)
        write_json(agents_dir / "theme.json", {"selection": theme_selection.model_dump(), "theme_choice": theme_choice.model_dump()})

    with tracer.stage("table_creator"):
        table_plan = build_table_plan(data_card)
        write_json(agents_dir / "table_creator.json", table_plan.model_dump())

    with tracer.stage("chart_orchestrator"):
        chart_candidates = candidate_charts(data_card, request.spec)
        chart_selection = _safe_select_options(
            client=local_client,
            stage="chart_orchestrator",
            prompt=chart_selection_prompt(
                spec=request.spec,
                card_summary=card_summary,
                candidates=[_compact_chart_candidate(candidate) for candidate in chart_candidates],
            ),
            fallback_ids=[candidate.id for candidate in chart_candidates[:4]],
        )
        selected_chart_candidates = filter_candidates_by_ids(chart_candidates, chart_selection.selected_ids) or chart_candidates[:4]
        chart_orchestration = ChartOrchestration(
            charts=[
                ChartPlan(
                    id=candidate.chart_spec.id,
                    title=candidate.chart_spec.title,
                    goal=candidate.chart_spec.description,
                    chart_type=candidate.chart_spec.chart_type,
                    columns=[candidate.chart_spec.x] + ([candidate.chart_spec.y] if candidate.chart_spec.y else []) + ([candidate.chart_spec.color] if candidate.chart_spec.color else []),
                    rationale=candidate.rationale,
                    aggregation=candidate.chart_spec.aggregation,
                    bar_mode=candidate.chart_spec.bar_mode,
                )
                for candidate in selected_chart_candidates
            ]
        )
        write_json(
            agents_dir / "chart_orchestrator.json",
            {
                "selection": chart_selection.model_dump(),
                "candidates": [_compact_chart_candidate(candidate) for candidate in chart_candidates],
                "chart_orchestration": chart_orchestration.model_dump(),
            },
        )

    with tracer.stage("chart_makers"):
        chart_specs = [candidate.chart_spec for candidate in selected_chart_candidates]
        before_refinement = [chart.model_dump() for chart in chart_specs]
        polished_specs: list = []
        for spec_model in chart_specs:
            polished = _polish_chart_title(client=local_client, spec_model=spec_model)
            polished_specs.append(polished)
        chart_specs = agents.refine_chart_specs_with_data(polished_specs, cleaned_df, data_card)
        after_refinement = [chart.model_dump() for chart in chart_specs]
        if before_refinement != after_refinement:
            tracer.event("chart_makers", "data_aware_refinement", before=before_refinement, after=after_refinement)
        write_json(agents_dir / "chart_makers.json", [chart.model_dump() for chart in chart_specs])

    with tracer.stage("layout"):
        ordered_chart_ids = _safe_select_options(
            client=local_client,
            stage="layout",
            prompt=layout_selection_prompt(
                spec=request.spec,
                chart_candidates=[{"id": spec.id, "title": spec.title, "description": spec.description} for spec in chart_specs],
            ),
            fallback_ids=[spec.id for spec in chart_specs],
        ).selected_ids
        layout_plan: LayoutPlan = build_layout_plan(
            analysis_plan=analysis_plan,
            table_plan=table_plan,
            chart_specs=chart_specs,
            ordered_chart_ids=ordered_chart_ids,
        )
        write_json(agents_dir / "layout.json", layout_plan.model_dump())

    validation_report_path = output_dir / "validation_report.json"
    with tracer.stage("policy_validation"):
        chart_decisions = validate_chart_specs(chart_specs, data_card)
        layout_decisions = validate_layout_plan(layout_plan, table_plan, chart_specs)
        policy_decisions = chart_decisions + layout_decisions
        write_json(validation_report_path, [decision.model_dump() for decision in policy_decisions])
        tracer.event("policy_validation", "decisions", decisions=[decision.model_dump() for decision in policy_decisions])
        if has_blocking_decisions(policy_decisions):
            repaired_specs = agents.refine_chart_specs_with_data(chart_specs, cleaned_df, data_card)
            repaired_decisions = validate_chart_specs(repaired_specs, data_card) + validate_layout_plan(layout_plan, table_plan, repaired_specs)
            if not has_blocking_decisions(repaired_decisions):
                chart_specs = repaired_specs
                write_json(validation_report_path, [decision.model_dump() for decision in repaired_decisions])
                tracer.event("policy_validation", "repair_pass_succeeded", decisions=[decision.model_dump() for decision in repaired_decisions])
            else:
                raise ValueError(f"Run it yaself mode could not repair policy violations. See {validation_report_path}.")

    notebook_path = output_dir / "exploration.ipynb"
    should_execute, runtime_note = should_autoexecute_notebook(cleaned_path, data_card.row_count)
    runtime_notes = [
        "Run it yaself mode uses deterministic candidates plus small-model selection, repair, and fallback guards."
    ]
    if runtime_note:
        runtime_notes.append(runtime_note)
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
        offline=False,
        model=f"run-it-yaself:{settings.model}",
        notebook_executed=notebook_executed,
        runtime_notes=runtime_notes,
        trace_path=str(trace_path),
        validation_report_path=str(validation_report_path),
        cached_data_path=str(cached_path) if cached_path else None,
        central_history_dir=str(history_dir),
    )
    write_json(output_dir / "manifest.json", manifest.model_dump())
    tracer.event("run_it_yaself", "end", manifest=manifest)
    save_run_history(
        run_dir=output_dir,
        destination=history_dir,
        run_id=tracer.run_id,
        manifest=manifest,
        extra={"mode": "run_it_yaself", "base_url": settings.base_url},
    )
    return manifest


def _safe_select_options(*, client: OpenAICompatibleLocalClient, stage: str, prompt: str, fallback_ids: list[str]) -> OptionSelection:
    try:
        selection = client.parse(stage=stage, user=prompt, output_model=OptionSelection)
    except Exception:
        return OptionSelection(selected_ids=fallback_ids, abstain=True, confidence="low", reason="Fell back to deterministic candidate ranking.")
    if selection.abstain or not selection.selected_ids:
        return OptionSelection(selected_ids=fallback_ids, abstain=True, confidence="low", reason=selection.reason or "Model abstained.")
    unique_ids = list(dict.fromkeys(selection.selected_ids))
    return OptionSelection(selected_ids=unique_ids[: max(1, len(fallback_ids))], abstain=False, confidence=selection.confidence, reason=selection.reason)


def _safe_select_theme(*, client: OpenAICompatibleLocalClient, prompt: str) -> ThemeSelection:
    try:
        selection = client.parse(stage="theme", user=prompt, output_model=ThemeSelection)
    except Exception:
        return ThemeSelection(abstain=True, confidence="low", reason="Fell back to deterministic theme choice.")
    if selection.abstain:
        return ThemeSelection(abstain=True, confidence=selection.confidence, reason=selection.reason)
    return selection


def _polish_chart_title(*, client: OpenAICompatibleLocalClient, spec_model):
    try:
        polish = client.parse(
            stage=f"chart_title_{spec_model.id}",
            user=title_polish_prompt(
                chart_summary={
                    "id": spec_model.id,
                    "title": spec_model.title,
                    "x": spec_model.x,
                    "y": spec_model.y,
                    "color": spec_model.color,
                    "aggregation": spec_model.aggregation,
                }
            ),
            output_model=TitlePolish,
        )
    except Exception:
        return spec_model
    if polish.abstain or not polish.title:
        return spec_model
    return spec_model.model_copy(update={"title": polish.title})


def _compact_chart_candidate(candidate: CandidateChart) -> dict[str, object]:
    spec_model = candidate.chart_spec
    return {
        "id": candidate.id,
        "title": candidate.title,
        "insight": candidate.insight,
        "rationale": candidate.rationale,
        "heuristic_score": round(candidate.heuristic_score, 3),
        "chart_type": spec_model.chart_type,
        "x": spec_model.x,
        "y": spec_model.y,
        "color": spec_model.color,
        "aggregation": spec_model.aggregation,
        "limit_mode": spec_model.limit_mode,
        "limit_n": spec_model.limit_n,
    }
