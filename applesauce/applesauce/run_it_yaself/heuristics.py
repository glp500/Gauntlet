from __future__ import annotations

from typing import Iterable

from ..models import AnalysisPlan, ChartSpec, DataCard, LayoutItem, LayoutPlan, TablePlan, TableSpec, ThemeChoice
from .models import CandidateChart, CandidateQuestion, CandidateTheme


def compact_card_summary(card: DataCard) -> dict[str, object]:
    return {
        "rows": card.row_count,
        "columns": card.column_count,
        "numeric": [column.name for column in card.columns if column.role == "numeric"][:8],
        "categorical": [column.name for column in card.columns if column.role in {"categorical", "boolean"}][:8],
        "datetime": [column.name for column in card.columns if column.role == "datetime"][:4],
        "notes": card.notes[:4],
    }


def candidate_questions(card: DataCard, spec: str) -> list[CandidateQuestion]:
    numeric = [column.name for column in card.columns if column.role == "numeric"]
    categorical = [column.name for column in card.columns if column.role in {"categorical", "boolean"}]
    datetime = [column.name for column in card.columns if column.role == "datetime"]
    candidates: list[CandidateQuestion] = []

    if numeric:
        candidates.append(CandidateQuestion(id="spread", text=f"Which numeric fields such as {numeric[0]} have the widest spread or strongest outliers?", priority=78, rationale="Numerical spread is almost always a useful first pass."))
    if categorical:
        candidates.append(CandidateQuestion(id="distribution", text=f"How are the main records distributed across {categorical[0]}?", priority=74, rationale="Category distribution gives a quick structural overview."))
    if len(numeric) >= 2:
        candidates.append(CandidateQuestion(id="relationship", text=f"What relationship, if any, exists between {numeric[0]} and {numeric[1]}?", priority=71, rationale="Pairwise metric relationships often reveal useful signal."))
    if numeric and categorical:
        candidates.append(CandidateQuestion(id="comparison", text=f"How does {numeric[0]} vary across {categorical[0]}?", priority=81, rationale="Crossing a metric with a category is usually high value."))
    if datetime and numeric:
        candidates.append(CandidateQuestion(id="trend", text=f"How does {numeric[0]} change over {datetime[0]}?", priority=80, rationale="Time trends are useful when a real time axis exists."))
    if len(categorical) >= 2:
        candidates.append(CandidateQuestion(id="category_cross", text=f"What patterns appear when comparing {categorical[0]} against {categorical[1]}?", priority=66, rationale="Two-way category structure can reveal segmentation or sparsity."))

    if not candidates:
        candidates.append(CandidateQuestion(id="overview", text=f"What are the most important structural patterns in this dataset for: {spec}?", priority=70, rationale="Safe fallback when typed structure is limited."))

    return candidates[:6]


def candidate_themes(spec: str) -> list[CandidateTheme]:
    lowered = spec.lower()
    return [
        CandidateTheme(name="technical", rationale="Best for careful, methodical analysis.", priority=85 if any(token in lowered for token in ["model", "technical", "stat", "analysis"]) else 72),
        CandidateTheme(name="calm", rationale="Best for readable, general-audience exploration.", priority=82),
        CandidateTheme(name="executive", rationale="Best for concise decision-oriented summaries.", priority=68),
        CandidateTheme(name="editorial", rationale="Best for more narrative framing.", priority=40),
        CandidateTheme(name="playful", rationale="Best for intentionally light tone.", priority=25),
    ]


def candidate_charts(card: DataCard, spec: str) -> list[CandidateChart]:
    numeric = [column for column in card.columns if column.role == "numeric"]
    categorical = [column for column in card.columns if column.role in {"categorical", "boolean"}]
    datetime = [column for column in card.columns if column.role == "datetime"]
    candidates: list[CandidateChart] = []

    def add(candidate: CandidateChart) -> None:
        if any(existing.chart_spec.id == candidate.chart_spec.id for existing in candidates):
            return
        candidates.append(candidate)

    if categorical:
        cat = categorical[0]
        add(
            CandidateChart(
                id="category_distribution",
                title=f"Distribution of {pretty(cat.name)}",
                insight=f"Show how records are distributed across {cat.name}.",
                rationale="A categorical distribution is a strong opening overview.",
                heuristic_score=_base_score(spec, cat.name, None) + 0.62,
                chart_spec=ChartSpec(
                    id="category_distribution",
                    title=f"Distribution of {pretty(cat.name)}",
                    description=f"Frequency view of {cat.name}.",
                    chart_type="bar",
                    x=cat.name,
                    aggregation="count",
                    orientation="h" if cat.unique_count > 10 else "v",
                    sort_descending=True,
                    limit_mode="top" if cat.unique_count > 20 else None,
                    limit_n=15 if cat.unique_count > 20 else None,
                ),
            )
        )

    if numeric:
        metric = numeric[0]
        add(
            CandidateChart(
                id="metric_distribution",
                title=f"Distribution of {pretty(metric.name)}",
                insight=f"Show the spread of {metric.name}.",
                rationale="A histogram is a stable baseline for the primary metric.",
                heuristic_score=_base_score(spec, metric.name, None) + 0.58,
                chart_spec=ChartSpec(
                    id="metric_distribution",
                    title=f"Distribution of {pretty(metric.name)}",
                    description=f"Distribution of {metric.name}.",
                    chart_type="histogram",
                    x=metric.name,
                ),
            )
        )

    if numeric and categorical:
        metric = numeric[0]
        cat = categorical[0]
        add(
            CandidateChart(
                id="metric_by_category",
                title=f"Average of {pretty(metric.name)} by {pretty(cat.name)}",
                insight=f"Compare {metric.name} across {cat.name}.",
                rationale="This is usually the most interpretable comparison chart.",
                heuristic_score=_base_score(spec, metric.name, cat.name) + 0.9,
                chart_spec=ChartSpec(
                    id="metric_by_category",
                    title=f"Average of {pretty(metric.name)} by {pretty(cat.name)}",
                    description=f"Compare mean {metric.name} across {cat.name}.",
                    chart_type="bar",
                    x=cat.name,
                    y=metric.name,
                    aggregation="mean",
                    orientation="h" if cat.unique_count > 8 else "v",
                    sort_descending=True,
                    limit_mode="top_bottom" if cat.unique_count > 30 else ("top" if cat.unique_count > 12 else None),
                    limit_n=10 if cat.unique_count > 30 else (12 if cat.unique_count > 12 else None),
                ),
            )
        )
        add(
            CandidateChart(
                id="metric_spread_by_category",
                title=f"Distribution of {pretty(metric.name)} by {pretty(cat.name)}",
                insight=f"Show spread and outliers in {metric.name} within each {cat.name} group.",
                rationale="Distribution plots are often more informative than means alone.",
                heuristic_score=_base_score(spec, metric.name, cat.name) + 0.73,
                chart_spec=ChartSpec(
                    id="metric_spread_by_category",
                    title=f"Distribution of {pretty(metric.name)} by {pretty(cat.name)}",
                    description=f"Distribution of {metric.name} grouped by {cat.name}.",
                    chart_type="violin",
                    x=cat.name,
                    y=metric.name,
                ),
            )
        )

    if len(numeric) >= 2:
        x_metric = numeric[0]
        y_metric = numeric[1]
        add(
            CandidateChart(
                id="metric_relationship",
                title=f"{pretty(y_metric.name)} vs {pretty(x_metric.name)}",
                insight=f"Inspect the relationship between {x_metric.name} and {y_metric.name}.",
                rationale="Scatterplots are useful when both axes are real measures.",
                heuristic_score=_base_score(spec, x_metric.name, y_metric.name) + 0.69,
                chart_spec=ChartSpec(
                    id="metric_relationship",
                    title=f"{pretty(y_metric.name)} vs {pretty(x_metric.name)}",
                    description=f"Relationship view between {x_metric.name} and {y_metric.name}.",
                    chart_type="scatter",
                    x=x_metric.name,
                    y=y_metric.name,
                ),
            )
        )

    if datetime and numeric:
        time_axis = datetime[0]
        metric = numeric[0]
        add(
            CandidateChart(
                id="metric_over_time",
                title=f"Average {pretty(metric.name)} over {pretty(time_axis.name)}",
                insight=f"Show how {metric.name} changes over {time_axis.name}.",
                rationale="Time series are high value when a real temporal axis exists.",
                heuristic_score=_base_score(spec, metric.name, time_axis.name) + 0.83,
                chart_spec=ChartSpec(
                    id="metric_over_time",
                    title=f"Average {pretty(metric.name)} over {pretty(time_axis.name)}",
                    description=f"Trend of {metric.name} over {time_axis.name}.",
                    chart_type="line",
                    x=time_axis.name,
                    y=metric.name,
                    aggregation="mean",
                ),
            )
        )

    if len(categorical) >= 2:
        first = categorical[0]
        second = categorical[1]
        if first.unique_count <= 20 and second.unique_count <= 20:
            add(
                CandidateChart(
                    id="category_cross_heatmap",
                    title=f"{pretty(first.name)} vs {pretty(second.name)}",
                    insight=f"Show concentration patterns across {first.name} and {second.name}.",
                    rationale="Low-cardinality category crossings can work well as heatmaps.",
                    heuristic_score=_base_score(spec, first.name, second.name) + 0.54,
                    chart_spec=ChartSpec(
                        id="category_cross_heatmap",
                        title=f"{pretty(first.name)} vs {pretty(second.name)}",
                        description=f"Category concentration across {first.name} and {second.name}.",
                        chart_type="heatmap",
                        x=first.name,
                        y=second.name,
                        aggregation="count",
                    ),
                )
            )

    ordered = sorted(candidates, key=lambda candidate: candidate.heuristic_score, reverse=True)
    return ordered[:8]


def build_analysis_plan(*, spec: str, selected_questions: list[CandidateQuestion], fallback_questions: list[CandidateQuestion]) -> AnalysisPlan:
    chosen = selected_questions or fallback_questions[:4]
    tone = "technical" if any(token in spec.lower() for token in ["model", "technical", "stat", "quality"]) else "calm"
    return AnalysisPlan(
        objective=f"Explore the dataset in response to: {spec}",
        tone=tone,  # type: ignore[arg-type]
        audience="Analyst using a smaller local model workflow",
        key_questions=[question.text for question in chosen[:5]],
        recommended_tables=["Dataset Explorer"],
        chart_goals=[question.text for question in chosen[:4]],
        narrative="This notebook uses a constrained local-model workflow: deterministic candidates are generated first, then a smaller model selects among safe options with repair and fallback guards.",
    )


def build_theme_choice(*, selected_name: str | None, candidates: list[CandidateTheme]) -> ThemeChoice:
    if selected_name:
        match = next((candidate for candidate in candidates if candidate.name == selected_name), None)
        if match:
            return ThemeChoice(name=match.name, reason=match.rationale)
    best = max(candidates, key=lambda candidate: candidate.priority)
    return ThemeChoice(name=best.name, reason=best.rationale)


def build_table_plan(card: DataCard) -> TablePlan:
    return TablePlan(
        tables=[
            TableSpec(
                id="dataset_explorer",
                title="Dataset Explorer",
                description="Interactive, paginated view of the cleaned dataset for direct exploration.",
                kind="sample",
                max_rows=50,
                focus_columns=[column.name for column in card.columns],
            )
        ]
    )


def build_layout_plan(*, analysis_plan: AnalysisPlan, table_plan: TablePlan, chart_specs: list[ChartSpec], ordered_chart_ids: list[str]) -> LayoutPlan:
    ordered_ids = [chart_id for chart_id in ordered_chart_ids if any(spec.id == chart_id for spec in chart_specs)]
    remaining = [spec.id for spec in chart_specs if spec.id not in ordered_ids]
    final_ids = ordered_ids + remaining
    items = [LayoutItem(kind="data_card", ref="data_card", title="Data Card")]
    items.extend(LayoutItem(kind="table", ref=table.id, title=table.title) for table in table_plan.tables)
    items.extend(LayoutItem(kind="chart", ref=chart_id, title=next(spec.title for spec in chart_specs if spec.id == chart_id)) for chart_id in final_ids)
    return LayoutPlan(
        title="Run it yaself Exploration Notebook",
        subtitle=analysis_plan.objective,
        items=items,
    )


def pretty(value: str) -> str:
    return value.replace("_", " ").title()


def _base_score(spec: str, left: str | None, right: str | None) -> float:
    lowered_spec = spec.lower()
    score = 0.25
    for column in [left, right]:
        if not column:
            continue
        tokens = column.replace("_", " ").lower().split()
        if any(token in lowered_spec for token in tokens):
            score += 0.18
    return min(score, 1.0)


def filter_candidates_by_ids(candidates: Iterable[CandidateChart], ids: list[str]) -> list[CandidateChart]:
    by_id = {candidate.id: candidate for candidate in candidates}
    return [by_id[candidate_id] for candidate_id in ids if candidate_id in by_id]
