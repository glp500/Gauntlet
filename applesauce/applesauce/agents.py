from __future__ import annotations

import json
import math

import pandas as pd

from .data import roles_from_card
from .llm import OpenAIStructuredClient
from .models import (
    AgentStage,
    AnalysisPlan,
    ChartOrchestration,
    ChartPlan,
    ChartSpec,
    DataCard,
    LayoutItem,
    LayoutPlan,
    TablePlan,
    TableSpec,
    ThemeChoice,
)
from .themes import choose_theme


SYSTEM_PROMPT = (
    "You are one specialist in a data-science exploration harness. "
    "Return only the requested structured output. Prefer practical, reproducible analysis."
)


def _card_json(card: DataCard) -> str:
    return json.dumps(card.model_dump(), indent=2)


def _normalized_text(value: str) -> str:
    return "".join(character if character.isalnum() else " " for character in value.lower())


def _column_tokens(column_name: str) -> list[str]:
    return [token for token in _normalized_text(column_name).split() if token]


def mentioned_columns(text: str, valid_columns: list[str]) -> list[str]:
    normalized = _normalized_text(text)
    matches: list[str] = []
    for column in valid_columns:
        if column.replace("_", " ").lower() in normalized:
            matches.append(column)
    return matches


def column_role_map(card: DataCard) -> dict[str, str]:
    return {column.name: column.role for column in card.columns}


def column_profiles(card: DataCard) -> dict[str, object]:
    return {column.name: column for column in card.columns}


def get_profile(card: DataCard, column_name: str):
    return column_profiles(card).get(column_name)


def is_numeric_like_text(column_name: str | None, card: DataCard) -> bool:
    if not column_name:
        return False
    profile = get_profile(card, column_name)
    if profile is None or getattr(profile, "role", None) != "text":
        return False
    samples = [sample.strip() for sample in getattr(profile, "sample_values", []) if sample and sample.strip()]
    if not samples:
        return False
    numeric_count = 0
    for sample in samples:
        cleaned = sample.replace(",", "").replace("$", "").replace("%", "").strip()
        try:
            float(cleaned)
        except ValueError:
            continue
        numeric_count += 1
    return numeric_count / len(samples) >= 0.8


def generic_measure_family(column_name: str | None) -> str | None:
    if not column_name:
        return None
    tokens = set(_column_tokens(column_name))
    weight_tokens = {"pound", "pounds", "lb", "lbs", "ton", "tons", "metric", "kg", "kilogram", "kilograms"}
    currency_tokens = {"dollar", "dollars", "usd", "price", "cost", "value", "amount"}
    if tokens and tokens.issubset(weight_tokens):
        return "weight"
    if tokens and tokens.issubset(currency_tokens):
        return "currency"
    return None


def is_temporal_sequence_column(column_name: str | None) -> bool:
    if not column_name:
        return False
    tokens = set(_column_tokens(column_name))
    temporal_tokens = {"year", "month", "day", "week", "quarter", "date"}
    return bool(tokens) and tokens.issubset(temporal_tokens)


def forms_redundant_measure_pair(left: str | None, right: str | None) -> bool:
    if not left or not right or left == right:
        return False
    left_family = generic_measure_family(left)
    right_family = generic_measure_family(right)
    return left_family is not None and left_family == right_family


def is_outcome_like(column_name: str, card: DataCard) -> bool:
    profile = get_profile(card, column_name)
    if profile is None:
        return False
    lowered = column_name.lower()
    if any(token in lowered for token in ["label", "status", "target", "outcome", "depress", "risk", "flag", "churn"]):
        return True
    return getattr(profile, "role", None) == "boolean"


def is_discrete_for_chart(column_name: str | None, card: DataCard) -> bool:
    if not column_name:
        return False
    profile = get_profile(card, column_name)
    if profile is None:
        return False
    if is_numeric_like_text(column_name, card):
        return False
    if getattr(profile, "role", None) in {"categorical", "boolean", "text"}:
        return True
    lowered = column_name.lower()
    if any(token in lowered for token in ["label", "status", "segment", "group", "category", "gender", "platform", "region", "level"]):
        return True
    return getattr(profile, "unique_count", 999) <= 12


def is_reasonable_breakdown_column(column_name: str | None, card: DataCard) -> bool:
    if not is_discrete_for_chart(column_name, card):
        return False
    profile = get_profile(card, column_name or "")
    if profile is None:
        return False
    if getattr(profile, "role", None) not in {"categorical", "boolean", "text"}:
        return False
    if generic_measure_family(column_name) is not None:
        return False
    return getattr(profile, "unique_count", 999) <= 24


def is_metric_for_chart(column_name: str | None, card: DataCard) -> bool:
    if not column_name:
        return False
    profile = get_profile(card, column_name)
    if profile is None:
        return False
    if getattr(profile, "role", None) != "numeric":
        return False
    if is_temporal_sequence_column(column_name):
        return False
    if is_outcome_like(column_name, card):
        return False
    return not is_identifier_like(profile, max(card.row_count, 1))


def additional_metric_columns(card: DataCard, exclude: set[str]) -> list[str]:
    profiles = column_profiles(card)
    candidates = [column.name for column in card.columns if is_metric_for_chart(column.name, card) and column.name not in exclude]
    return prioritize_numeric_columns(candidates, profiles)


def additional_discrete_columns(card: DataCard, exclude: set[str]) -> list[str]:
    candidates = [column.name for column in card.columns if is_reasonable_breakdown_column(column.name, card) and column.name not in exclude]
    return prioritize_discrete_columns(candidates)


def create_analysis_plan(card: DataCard, spec: str, client: OpenAIStructuredClient | None = None) -> AnalysisPlan:
    if client:
        return client.parse(
            stage=AgentStage.ANALYST.value,
            system=SYSTEM_PROMPT,
            user=(
                "Create a concise data analysis plan for this dataset and user request.\n\n"
                f"User request:\n{spec}\n\nData card:\n{_card_json(card)}"
            ),
            output_model=AnalysisPlan,
        )

    roles = roles_from_card(card)
    questions = [
        "What are the strongest distribution patterns in the dataset?",
        "Where do missing values or duplicates affect interpretation?",
    ]
    if roles.numeric and roles.categorical:
        questions.append(f"How does {roles.numeric[0]} vary across {roles.categorical[0]}?")
    if len(roles.numeric) >= 2:
        questions.append(f"Are {roles.numeric[0]} and {roles.numeric[1]} related?")
    if roles.datetime:
        questions.append(f"How do key metrics change over {roles.datetime[0]}?")

    tone = "technical" if any(word in spec.lower() for word in ["model", "stat", "technical", "quality"]) else "executive"
    return AnalysisPlan(
        objective=f"Explore the dataset in response to: {spec}",
        tone=tone,  # type: ignore[arg-type]
        audience="Data stakeholders",
        key_questions=questions[:6],
        recommended_tables=["Dataset preview", "Missingness profile", "Numeric summary"],
        chart_goals=[
            "Show core numeric distributions",
            "Compare categorical groups",
            "Surface relationships between numeric fields",
        ],
        narrative="Start with data quality, then move into patterns that can guide deeper investigation.",
    )


def select_theme(plan: AnalysisPlan, client: OpenAIStructuredClient | None = None) -> ThemeChoice:
    if client:
        return client.parse(
            stage=AgentStage.THEME.value,
            system=SYSTEM_PROMPT,
            user=(
                "Choose exactly one theme name from: executive, playful, calm, technical, editorial. "
                "Match the tone and audience.\n\n"
                f"Analysis plan:\n{plan.model_dump_json(indent=2)}"
            ),
            output_model=ThemeChoice,
        )
    return choose_theme(plan)


def create_table_plan(card: DataCard, plan: AnalysisPlan, client: OpenAIStructuredClient | None = None) -> TablePlan:
    if client:
        table_plan = client.parse(
            stage=AgentStage.TABLE.value,
            system=SYSTEM_PROMPT,
            user=(
                "Create exactly one table spec for the notebook. "
                "Use kind=sample and make it a full interactive dataset explorer, not a summary table. "
                "Use focus_columns to choose the most useful display order, but keep it broad enough for real exploration.\n\n"
                f"Analysis plan:\n{plan.model_dump_json(indent=2)}\n\nData card:\n{_card_json(card)}"
            ),
            output_model=TablePlan,
        )
        return sanitize_table_plan(table_plan, card)
    return TablePlan(tables=default_table_specs(card))


def orchestrate_charts(card: DataCard, plan: AnalysisPlan, theme: ThemeChoice, client: OpenAIStructuredClient | None = None) -> ChartOrchestration:
    if client:
        orchestration = client.parse(
            stage=AgentStage.CHART_ORCHESTRATOR.value,
            system=SYSTEM_PROMPT,
            user=(
                "Create 2-5 declarative chart plans. Allowed chart_type values: "
                "histogram, bar, scatter, line, box, violin, heatmap. Use only columns that exist in the data card. "
                "Choose aggregation and bar_mode when helpful. Prefer charts that produce real insight, not generic defaults. "
                "Avoid repetitive scatterplots unless the relationship is especially important. "
                "Avoid using numeric-looking text fields or redundant unit columns as categorical breakdowns. "
                "Each chart must be unique and reveal a different insight; avoid repeating the same columns with minor title changes.\n\n"
                f"Theme: {theme.model_dump_json()}\n\nAnalysis plan:\n{plan.model_dump_json(indent=2)}\n\nData card:\n{_card_json(card)}"
            ),
            output_model=ChartOrchestration,
        )
        return sanitize_chart_orchestration(orchestration, card)
    return ChartOrchestration(charts=default_chart_plans(card))


def default_table_specs(card: DataCard) -> list[TableSpec]:
    return sanitize_table_plan(
        TablePlan(
            tables=[
                TableSpec(
                    id="dataset_explorer",
                    title="Dataset Explorer",
                    description="Interactive view of the cleaned dataset for direct inspection.",
                    kind="sample",
                    max_rows=50,
                    focus_columns=[column.name for column in card.columns],
                )
            ]
        ),
        card,
    ).tables


def sanitize_table_plan(table_plan: TablePlan, card: DataCard) -> TablePlan:
    valid_columns = {column.name for column in card.columns}
    ordered_columns = [column.name for column in card.columns]
    source = table_plan.tables[0] if table_plan.tables else TableSpec(
        id="dataset_explorer",
        title="Dataset Explorer",
        description="Interactive view of the cleaned dataset for direct inspection.",
        kind="sample",
        max_rows=50,
        focus_columns=ordered_columns,
    )
    mentioned = mentioned_columns(f"{source.title} {source.description}", ordered_columns)
    focus_columns = [column for column in source.focus_columns if column in valid_columns]
    if mentioned:
        focus_columns = list(dict.fromkeys(focus_columns + mentioned))
    if not focus_columns:
        focus_columns = ordered_columns
    return TablePlan(
        tables=[
            TableSpec(
                id="dataset_explorer",
                title="Dataset Explorer",
                description="Interactive, paginated view of the cleaned dataset for direct exploration.",
                kind="sample",
                max_rows=50,
                focus_columns=focus_columns,
            )
        ]
    )


def ensure_table_title(table: TableSpec, focus_columns: list[str]) -> str:
    return "Dataset Explorer"


def ensure_table_description(table: TableSpec, focus_columns: list[str]) -> str:
    return "Interactive, paginated view of the cleaned dataset for direct exploration."


def default_chart_plans(card: DataCard) -> list[ChartPlan]:
    profiles = column_profiles(card)
    numeric_columns = [column.name for column in card.columns if is_metric_for_chart(column.name, card)]
    discrete_columns = [column.name for column in card.columns if is_reasonable_breakdown_column(column.name, card)]
    outcome_columns = [column.name for column in card.columns if is_outcome_like(column.name, card)]
    metric_columns = prioritize_numeric_columns(numeric_columns, profiles)
    dimension_columns = prioritize_discrete_columns(discrete_columns)
    datetime_columns = [column.name for column in card.columns if column.role == "datetime"]

    charts: list[ChartPlan] = []

    if metric_columns:
        metric = metric_columns[0]
        histogram_metric = metric_columns[1] if len(metric_columns) > 1 else metric
        histogram_breakdown = dimension_columns[1] if len(dimension_columns) > 1 else (dimension_columns[0] if dimension_columns else None)
        if dimension_columns:
            dimension = dimension_columns[0]
            charts.append(
                ChartPlan(
                    id=f"{metric}_by_{dimension}",
                    title=f"{metric.replace('_', ' ').title()} by {dimension.replace('_', ' ').title()}",
                    goal="Compare the average metric across major groups.",
                    chart_type="bar",
                    columns=[dimension, metric],
                    rationale="Mean comparisons across groups are often more useful than raw scatterplots.",
                    aggregation="mean",
                    bar_mode="group",
                )
            )
            charts.append(
                ChartPlan(
                    id=f"{metric}_distribution_by_{dimension}",
                    title=f"Distribution of {metric.replace('_', ' ').title()} by {dimension.replace('_', ' ').title()}",
                    goal="Show spread and skew by group.",
                    chart_type="violin",
                    columns=[dimension, metric],
                    rationale="Distributional plots reveal more than a single summary statistic.",
                )
            )
        charts.append(
            ChartPlan(
                id=f"{histogram_metric}_distribution",
                title=f"Distribution of {histogram_metric.replace('_', ' ').title()}",
                goal="Understand the shape and concentration of a key metric.",
                chart_type="histogram",
                columns=[histogram_metric] + ([histogram_breakdown] if histogram_breakdown else []),
                rationale="A metric distribution is a strong first diagnostic when paired with a sensible breakdown.",
                bar_mode="overlay",
            )
        )

    if len(metric_columns) >= 2 and not forms_redundant_measure_pair(metric_columns[0], metric_columns[1]):
        if all(getattr(profiles[column], "unique_count", 0) > 12 for column in metric_columns[:2]):
            first_metric, second_metric = metric_columns[:2]
            charts.append(
                ChartPlan(
                    id=f"{second_metric}_vs_{first_metric}",
                    title=f"{second_metric.replace('_', ' ').title()} vs {first_metric.replace('_', ' ').title()}",
                    goal="Explore whether two important numeric variables move together.",
                    chart_type="scatter",
                    columns=[first_metric, second_metric] + ([dimension_columns[0]] if dimension_columns else []),
                    rationale="Use scatterplots selectively for potentially meaningful numeric relationships.",
                )
            )

    if datetime_columns and metric_columns:
        charts.append(
            ChartPlan(
                id=f"{metric_columns[0]}_over_time",
                title=f"{metric_columns[0].replace('_', ' ').title()} Over Time",
                goal="Show how the primary metric changes over time.",
                chart_type="line",
                columns=[datetime_columns[0], metric_columns[0]] + ([dimension_columns[0]] if dimension_columns else []),
                rationale="Temporal aggregation is useful when a time dimension exists.",
                aggregation="mean",
            )
        )

    if outcome_columns and dimension_columns:
        outcome = outcome_columns[0]
        dimension = next((column for column in dimension_columns if column != outcome), dimension_columns[0])
        charts.append(
            ChartPlan(
                id=f"{outcome}_by_{dimension}",
                title=f"{outcome.replace('_', ' ').title()} by {dimension.replace('_', ' ').title()}",
                goal="Compare outcome prevalence across meaningful groups.",
                chart_type="bar",
                columns=[dimension, outcome],
                rationale="Outcome prevalence by group is more useful than simple category counts.",
                aggregation="rate",
                bar_mode="group",
            )
        )

    if len(dimension_columns) >= 2 and all(getattr(profiles[column], "unique_count", 999) <= 10 for column in dimension_columns[:2]):
        heatmap_columns = dimension_columns[:2]
        if outcome_columns:
            heatmap_columns.append(outcome_columns[0])
        charts.append(
            ChartPlan(
                id=f"{dimension_columns[0]}_{dimension_columns[1]}_heatmap",
                title=f"{dimension_columns[0].replace('_', ' ').title()} vs {dimension_columns[1].replace('_', ' ').title()}",
                goal="Reveal concentration patterns between two categorical dimensions.",
                chart_type="heatmap",
                columns=heatmap_columns,
                rationale="Heatmaps make two-way categorical structure easier to scan than repeated bar charts.",
                aggregation="count" if not outcome_columns else "rate",
            )
        )

    if not charts:
        charts.append(
            ChartPlan(
                id="row_count",
                title="Rows by Index",
                goal="Provide a simple row index diagnostic.",
                chart_type="bar",
                columns=[card.columns[0].name],
                rationale="Fallback chart for sparse schemas.",
                aggregation="count",
                bar_mode="group",
            )
        )

    return dedupe_chart_plans(charts)[:5]


def is_identifier_like(column, row_count: int) -> bool:
    lowered = column.name.lower()
    if "id" in lowered or lowered in {"tsn", "code"}:
        return True
    if column.role in {"numeric", "categorical"} and column.unique_count >= max(int(row_count * 0.9), 20):
        return True
    return False


def prioritize_numeric_columns(columns: list[str], profiles: dict[str, object]) -> list[str]:
    def score(name: str) -> tuple[int, int]:
        profile = profiles[name]
        priority = 0
        lowered = name.lower()
        if any(token in lowered for token in ["score", "hours", "time", "cost", "revenue", "sales", "stress", "anxiety", "performance", "age", "metric", "ton"]):
            priority += 3
        if any(token in lowered for token in ["count", "index", "number", "id"]):
            priority -= 2
        return (priority, getattr(profile, "unique_count", 0))

    return sorted(columns, key=score, reverse=True)


def prioritize_discrete_columns(columns: list[str]) -> list[str]:
    def score(name: str) -> int:
        lowered = name.lower()
        priority = 0
        if any(token in lowered for token in ["label", "segment", "group", "category", "gender", "platform", "region", "status", "level", "collection", "source", "state"]):
            priority += 3
        if any(token in lowered for token in ["note", "comment", "text", "description"]):
            priority -= 2
        return priority

    return sorted(columns, key=score, reverse=True)


def dedupe_chart_plans(charts: list[ChartPlan]) -> list[ChartPlan]:
    seen: set[tuple[str, tuple[str, ...], str | None]] = set()
    unique: list[ChartPlan] = []
    for chart in charts:
        signature = (chart.chart_type, tuple(chart.columns), chart.aggregation)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(chart)
    return unique


def reconcile_chart_columns(chart: ChartPlan, card: DataCard) -> list[str]:
    valid_columns = [column.name for column in card.columns]
    from_text = mentioned_columns(f"{chart.title} {chart.goal} {chart.rationale}", valid_columns)
    combined = [column for column in chart.columns if column in valid_columns]
    if from_text:
        combined = list(dict.fromkeys(combined + from_text))
    if combined:
        return combined[:4]
    fallback = fallback_chart_spec(chart, card)
    columns = [fallback.x]
    if fallback.y:
        columns.append(fallback.y)
    if fallback.color:
        columns.append(fallback.color)
    return columns


def infer_target_value(column_name: str | None, card: DataCard) -> str | None:
    if not column_name:
        return None
    profile = next((column for column in card.columns if column.name == column_name), None)
    if profile is None:
        return None
    preferred = ["yes", "true", "high", "positive", "depressed", "1"]
    lowered = column_name.lower()
    if any(token in lowered for token in ["label", "status", "depress", "risk", "churn", "flag"]):
        if getattr(profile, "role", None) == "numeric" and getattr(profile, "unique_count", 999) <= 2:
            return "1"
        if getattr(profile, "role", None) == "boolean":
            return "True"
        for sample in profile.sample_values:
            if sample.strip().lower() in preferred:
                return sample
    return profile.sample_values[0] if profile.sample_values else None


def _pick_secondary_metric(candidates: list[str], primary: str | None) -> str | None:
    for candidate in candidates:
        if candidate != primary and not forms_redundant_measure_pair(candidate, primary):
            return candidate
    return next((candidate for candidate in candidates if candidate != primary), None)


def fallback_chart_spec(plan: ChartPlan, card: DataCard) -> ChartSpec:
    valid_columns = {column.name for column in card.columns}
    roles = roles_from_card(card)
    role_map = column_role_map(card)
    columns = [column for column in plan.columns if column in valid_columns]
    numeric_columns = [column for column in columns if role_map.get(column) == "numeric"]
    discrete_columns = [column for column in columns if is_reasonable_breakdown_column(column, card)]
    aggregation = plan.aggregation
    bar_mode = plan.bar_mode
    target_value = None

    if plan.chart_type == "scatter":
        candidates = numeric_columns + [column for column in roles.numeric if column not in numeric_columns]
        selected = [column for column in dict.fromkeys(candidates) if not forms_redundant_measure_pair(candidates[0] if candidates else None, column) or column == (candidates[0] if candidates else None)]
        if len(selected) < 2:
            selected = list(dict.fromkeys(candidates))
        chart_type = "scatter" if len(selected) >= 2 else "histogram"
        x = selected[0]
        y = selected[1] if chart_type == "scatter" else None
        color = discrete_columns[0] if discrete_columns else None
    elif plan.chart_type == "line":
        x = columns[0] if columns else (roles.datetime[0] if roles.datetime else card.columns[0].name)
        y = _pick_secondary_metric(numeric_columns, x) if numeric_columns else _pick_secondary_metric(roles.numeric, x)
        chart_type = "line" if y else "histogram"
        color = discrete_columns[0] if discrete_columns else None
        aggregation = aggregation or "mean"
    elif plan.chart_type in {"box", "violin"}:
        x = discrete_columns[0] if discrete_columns else (roles.categorical[0] if roles.categorical else card.columns[0].name)
        y = _pick_secondary_metric(numeric_columns, x) if numeric_columns else _pick_secondary_metric(roles.numeric, x)
        chart_type = plan.chart_type if y else "bar"
        color = discrete_columns[1] if len(discrete_columns) > 1 else None
    elif plan.chart_type == "heatmap":
        chart_type = "heatmap"
        x = discrete_columns[0] if discrete_columns else (columns[0] if columns else card.columns[0].name)
        y = discrete_columns[1] if len(discrete_columns) > 1 else (columns[1] if len(columns) > 1 else x)
        color = columns[2] if len(columns) > 2 and is_reasonable_breakdown_column(columns[2], card) and columns[2] not in {x, y} else None
        aggregation = aggregation or "count"
        if aggregation == "rate":
            target_value = infer_target_value(color or y, card)
    elif plan.chart_type == "bar":
        chart_type = "bar"
        x = columns[0] if columns else ((discrete_columns[0] if discrete_columns else None) or (roles.categorical[0] if roles.categorical else card.columns[0].name))
        y = _pick_secondary_metric(numeric_columns, x)
        color = discrete_columns[1] if len(discrete_columns) > 1 else (discrete_columns[0] if discrete_columns and discrete_columns[0] != x else None)
        aggregation = aggregation or ("mean" if y else "count")
        bar_mode = bar_mode or "group"
        if aggregation == "rate":
            target_value = infer_target_value(color or y, card)
    else:
        chart_type = "histogram"
        x = numeric_columns[0] if numeric_columns else (columns[0] if columns else (roles.numeric[0] if roles.numeric else card.columns[0].name))
        y = None
        color = discrete_columns[0] if discrete_columns else None
        bar_mode = bar_mode or "overlay"

    return ChartSpec(
        id=plan.id,
        title=plan.title,
        description=plan.goal,
        chart_type=chart_type,  # type: ignore[arg-type]
        x=x,
        y=y,
        color=color,
        aggregation=aggregation,
        bar_mode=bar_mode,
        target_value=target_value,
    )


def sanitize_chart_orchestration(orchestration: ChartOrchestration, card: DataCard) -> ChartOrchestration:
    sanitized: list[ChartPlan] = []
    seen: set[tuple[str, tuple[str, ...], str | None]] = set()

    for chart in orchestration.charts:
        columns = reconcile_chart_columns(chart, card)
        if not columns:
            fallback = fallback_chart_spec(chart, card)
            columns = [fallback.x] + ([fallback.y] if fallback.y else []) + ([fallback.color] if fallback.color else [])
            chart_type = fallback.chart_type
            title = fallback.title
            goal = fallback.description
            aggregation = fallback.aggregation
            bar_mode = fallback.bar_mode
        else:
            chart_type = chart.chart_type
            title = chart.title
            goal = chart.goal
            aggregation = chart.aggregation
            bar_mode = chart.bar_mode

        signature = (chart_type, tuple(columns), aggregation)
        if signature in seen:
            continue
        seen.add(signature)
        sanitized.append(
            chart.model_copy(
                update={
                    "columns": columns,
                    "chart_type": chart_type,
                    "title": title,
                    "goal": goal,
                    "aggregation": aggregation,
                    "bar_mode": bar_mode,
                }
            )
        )

    for default in default_chart_plans(card):
        signature = (default.chart_type, tuple(default.columns), default.aggregation)
        if signature not in seen:
            seen.add(signature)
            sanitized.append(default)

    return ChartOrchestration(charts=sanitized[:5])


def make_chart_spec(plan: ChartPlan, card: DataCard, client: OpenAIStructuredClient | None = None) -> ChartSpec:
    valid_columns = {column.name for column in card.columns}
    if client:
        spec = client.parse(
            stage=AgentStage.CHART_MAKER.value,
            system=SYSTEM_PROMPT,
            user=(
                "Convert this chart plan into one declarative chart spec. "
                "Use only the provided columns and keep the chart_type unchanged. "
                "Do not use numeric-looking text fields or redundant unit columns as categorical breakdowns. "
                "Use aggregation, bar_mode, target_value, limit_mode, and limit_n when they materially improve the insight. "
                "If a categorical axis would contain too many values to read, prefer a focused top, bottom, or top_bottom view.\n\n"
                f"Valid columns: {sorted(valid_columns)}\n\nChart plan:\n{plan.model_dump_json(indent=2)}"
            ),
            output_model=ChartSpec,
        )
    else:
        spec = fallback_chart_spec(plan, card)

    referenced = {spec.x, spec.y, spec.color} - {None}
    if referenced - valid_columns:
        spec = fallback_chart_spec(plan, card)
    return reconcile_chart_spec(spec, plan, card)


def build_chart_specs(orchestration: ChartOrchestration, card: DataCard, client: OpenAIStructuredClient | None = None) -> list[ChartSpec]:
    unique_specs: list[ChartSpec] = []
    seen: set[tuple[str, str, str | None, str | None, str | None, str | None, str | None]] = set()

    for plan in sanitize_chart_orchestration(orchestration, card).charts:
        spec = make_chart_spec(plan, card, client)
        signature = (spec.chart_type, spec.x, spec.y, spec.color, spec.aggregation, spec.bar_mode, spec.target_value)
        if signature in seen:
            fallback = fallback_chart_spec(plan, card)
            signature = (fallback.chart_type, fallback.x, fallback.y, fallback.color, fallback.aggregation, fallback.bar_mode, fallback.target_value)
            spec = fallback
        if signature in seen:
            continue
        seen.add(signature)
        unique_specs.append(spec)

    return unique_specs


def _aggregated_series_for_bar(spec: ChartSpec, df: pd.DataFrame) -> pd.Series | None:
    if spec.chart_type != "bar":
        return None
    if spec.x not in df.columns:
        return None
    if spec.aggregation == "rate":
        outcome_column = spec.y or spec.color
        if outcome_column is None or outcome_column not in df.columns:
            return None
        plot_df = df[[spec.x, outcome_column]].dropna().copy()
        if plot_df.empty:
            return None
        target_value = spec.target_value
        if target_value is None:
            target_value = infer_target_value(outcome_column, build_data_card_from_dataframe(df))
        plot_df["_value"] = (plot_df[outcome_column].astype("string") == str(target_value)).astype(int)
        return plot_df.groupby(spec.x, dropna=False)["_value"].mean()
    if spec.aggregation == "count":
        value_column = spec.y if spec.y and spec.y in df.columns else None
        plot_df = df[[spec.x] + ([value_column] if value_column else [])].copy()
        if value_column:
            plot_df = plot_df[plot_df[value_column].notna()]
        return plot_df.groupby(spec.x, dropna=False).size()
    if spec.y and spec.y in df.columns and pd.api.types.is_numeric_dtype(df[spec.y]):
        plot_df = df[[spec.x, spec.y]].dropna().copy()
        if plot_df.empty:
            return None
        if spec.aggregation in {"mean", "median", "sum"}:
            return plot_df.groupby(spec.x, dropna=False)[spec.y].agg(spec.aggregation)
        return plot_df.groupby(spec.x, dropna=False)[spec.y].mean()
    return None


def _skew_ratio(series: pd.Series | None) -> float | None:
    if series is None or series.empty:
        return None
    positive = series[series > 0]
    if positive.empty:
        return None
    minimum = float(positive.min())
    maximum = float(positive.max())
    if minimum <= 0:
        return None
    return maximum / minimum


def build_data_card_from_dataframe(df: pd.DataFrame) -> DataCard:
    from .data import build_data_card
    from pathlib import Path

    return build_data_card(Path("in_memory.csv"), df, 0)


def refine_chart_specs_with_data(chart_specs: list[ChartSpec], df: pd.DataFrame, card: DataCard) -> list[ChartSpec]:
    refined: list[ChartSpec] = []
    for spec in chart_specs:
        current = spec
        if spec.chart_type == "bar":
            current = refine_bar_chart_with_data(spec, df, card)
        elif spec.chart_type == "heatmap":
            current = refine_heatmap_chart_with_data(spec, df, card)
        refined.append(current)
    return refined


def refine_heatmap_chart_with_data(spec: ChartSpec, df: pd.DataFrame, card: DataCard) -> ChartSpec:
    if spec.x not in df.columns or not spec.y or spec.y not in df.columns:
        return spec

    color = spec.color
    high_cardinality_axes = [
        axis for axis in [spec.x, spec.y]
        if axis in df.columns and int(df[axis].nunique(dropna=True)) > 30
    ]
    if not high_cardinality_axes:
        return spec

    value_column = color if color and color in df.columns and pd.api.types.is_numeric_dtype(df[color]) else None
    if spec.aggregation not in {"mean", "median", "sum"} or value_column is None:
        return spec

    focus_axis = max(high_cardinality_axes, key=lambda axis: int(df[axis].nunique(dropna=True)))
    grouped = df[[focus_axis, value_column]].dropna().groupby(focus_axis, dropna=False)[value_column].agg(spec.aggregation)
    if grouped.empty:
        return spec

    pretty_axis = focus_axis.replace("_", " ").title()
    pretty_value = value_column.replace("_", " ").title()
    pretty_agg = {"mean": "Average", "median": "Median", "sum": "Total"}[spec.aggregation]
    description = (
        f"Focused top-and-bottom view of {pretty_axis.lower()} because the original heatmap would require "
        f"showing {int(df[focus_axis].nunique(dropna=True)):,} categories."
    )
    return spec.model_copy(
        update={
            "chart_type": "bar",
            "x": focus_axis,
            "y": value_column,
            "color": None,
            "aggregation": spec.aggregation,
            "bar_mode": "group",
            "orientation": "h",
            "log_value_axis": False,
            "sort_descending": True,
            "limit_mode": "top_bottom",
            "limit_n": 10,
            "title": f"Top and Bottom {pretty_axis} by {pretty_agg} {pretty_value}",
            "description": description,
        }
    )


def refine_bar_chart_with_data(spec: ChartSpec, df: pd.DataFrame, card: DataCard) -> ChartSpec:
    color = spec.color
    orientation = spec.orientation
    log_value_axis = spec.log_value_axis
    sort_descending = spec.sort_descending

    if color and color in df.columns:
        color_unique = int(df[color].nunique(dropna=True))
        if color_unique > 8:
            color = None

    aggregated = _aggregated_series_for_bar(spec.model_copy(update={"color": color}), df)
    skew = _skew_ratio(aggregated)
    category_count = int(aggregated.shape[0]) if aggregated is not None else 0
    color_count = int(df[color].nunique(dropna=True)) if color and color in df.columns else 0

    if (
        color
        and spec.y
        and spec.aggregation in {"count", "sum", "mean", "median"}
        and color_count >= 5
        and skew is not None
        and skew >= 20
        and 2 <= category_count <= 30
    ):
        title = build_chart_title("heatmap", spec.x, color, spec.y, spec.aggregation)
        return spec.model_copy(
            update={
                "chart_type": "heatmap",
                "y": color,
                "color": spec.y,
                "orientation": None,
                "log_value_axis": True,
                "sort_descending": False,
                "title": title,
            }
        )

    if skew is not None and skew >= 15:
        log_value_axis = True
        sort_descending = True
        if category_count <= 25:
            orientation = "h"

    if category_count > 12 and orientation is None:
        orientation = "h"
        sort_descending = True

    title = build_chart_title(spec.chart_type, spec.x, spec.y, color, spec.aggregation)
    return spec.model_copy(
        update={
            "color": color,
            "orientation": orientation,
            "log_value_axis": log_value_axis,
            "sort_descending": sort_descending,
            "limit_mode": spec.limit_mode,
            "limit_n": spec.limit_n,
            "title": title,
        }
    )


def _first_nonredundant_metric(candidates: list[str], anchor: str | None) -> str | None:
    for candidate in candidates:
        if candidate != anchor and not forms_redundant_measure_pair(candidate, anchor):
            return candidate
    return next((candidate for candidate in candidates if candidate != anchor), None)


def reconcile_chart_spec(spec: ChartSpec, plan: ChartPlan, card: DataCard) -> ChartSpec:
    plan_columns = [column for column in reconcile_chart_columns(plan, card) if column != spec.x]
    used = [spec.x]
    valid_names = {column.name for column in card.columns}
    x = spec.x if spec.x in valid_names else card.columns[0].name
    y = spec.y if spec.y in valid_names else None
    color = spec.color if spec.color in valid_names else None
    aggregation = spec.aggregation or plan.aggregation
    bar_mode = spec.bar_mode or plan.bar_mode
    target_value = spec.target_value

    if y:
        used.append(y)
    if color:
        used.append(color)

    remaining = [column for column in plan_columns if column not in used]
    numeric_remaining = [column for column in remaining if is_metric_for_chart(column, card)]
    discrete_remaining = [column for column in remaining if is_reasonable_breakdown_column(column, card)]
    fallback_metrics = additional_metric_columns(card, set(used))
    fallback_discretes = additional_discrete_columns(card, set(used))

    if color and (
        color == x
        or color == y
        or
        not is_reasonable_breakdown_column(color, card)
        or forms_redundant_measure_pair(color, x)
        or forms_redundant_measure_pair(color, y)
    ):
        color = next((column for column in discrete_remaining + fallback_discretes if not forms_redundant_measure_pair(column, x) and not forms_redundant_measure_pair(column, y)), None)

    if y and forms_redundant_measure_pair(x, y):
        replacement_y = _first_nonredundant_metric(numeric_remaining + fallback_metrics, x)
        if replacement_y:
            y = replacement_y
        else:
            spec = spec.model_copy(update={"chart_type": "histogram"})
            y = None
            color = color if color and is_reasonable_breakdown_column(color, card) else None

    if spec.chart_type == "histogram":
        if color is None and discrete_remaining:
            color = discrete_remaining[0]
        if color is not None and not is_reasonable_breakdown_column(color, card):
            color = discrete_remaining[0] if discrete_remaining else None
        aggregation = None
        bar_mode = bar_mode or "overlay"
    elif spec.chart_type == "bar":
        if not (aggregation == "rate" and color and is_outcome_like(color, card)):
            if y is None and numeric_remaining:
                y = _first_nonredundant_metric(numeric_remaining, x)
            elif y is None and fallback_metrics:
                y = _first_nonredundant_metric(fallback_metrics, x)
        if color is None:
            if discrete_remaining:
                color = discrete_remaining[0]
            elif fallback_discretes:
                color = fallback_discretes[0]
            elif y is not None and is_reasonable_breakdown_column(y, card):
                color = y
                y = None
        if y and is_outcome_like(y, card) and aggregation in {None, "mean"}:
            aggregation = "rate"
        if aggregation is None:
            aggregation = "mean" if y and is_metric_for_chart(y, card) else "count"
        bar_mode = bar_mode or "group"
        if aggregation == "rate":
            target_value = target_value or infer_target_value(color or y, card)
    elif spec.chart_type == "scatter":
        if y is None and numeric_remaining:
            y = _first_nonredundant_metric(numeric_remaining, x)
        elif y is None and fallback_metrics:
            y = _first_nonredundant_metric(fallback_metrics, x)
        if y == x:
            alternative = _first_nonredundant_metric(numeric_remaining + fallback_metrics, x)
            if alternative:
                y = alternative
            else:
                spec = spec.model_copy(update={"chart_type": "histogram"})
                y = None
        if color is None and discrete_remaining:
            color = discrete_remaining[0]
        elif color is not None and not is_reasonable_breakdown_column(color, card):
            color = discrete_remaining[0] if discrete_remaining else None
        if not is_metric_for_chart(x, card) or (y is not None and not is_metric_for_chart(y, card)):
            if is_discrete_for_chart(x, card) and y and is_metric_for_chart(y, card):
                spec = spec.model_copy(update={"chart_type": "violin"})
            elif y and is_discrete_for_chart(y, card) and is_metric_for_chart(x, card):
                old_x = x
                spec = spec.model_copy(update={"chart_type": "violin", "x": y})
                x = y
                y = old_x
            else:
                spec = spec.model_copy(update={"chart_type": "histogram"})
                y = None
                color = color if color and is_reasonable_breakdown_column(color, card) else None
        aggregation = None
    elif spec.chart_type == "line":
        profile = get_profile(card, x)
        if profile is None or getattr(profile, "role", None) != "datetime":
            datetime_candidate = next((column.name for column in card.columns if column.role == "datetime" and column.name not in used), None)
            if datetime_candidate:
                if y is None and is_metric_for_chart(x, card):
                    y = x
                x = datetime_candidate
            else:
                spec = spec.model_copy(update={"chart_type": "bar"})
        if y is None and numeric_remaining:
            y = _first_nonredundant_metric(numeric_remaining, x)
        elif y is None and fallback_metrics:
            y = _first_nonredundant_metric(fallback_metrics, x)
        if color is None and discrete_remaining:
            color = discrete_remaining[0]
        elif color is not None and not is_reasonable_breakdown_column(color, card):
            color = discrete_remaining[0] if discrete_remaining else None
        aggregation = aggregation or "mean"
    elif spec.chart_type in {"box", "violin"}:
        if x == y and color and is_reasonable_breakdown_column(color, card):
            x = color
            color = None
        if y is None and numeric_remaining:
            y = _first_nonredundant_metric(numeric_remaining, x)
        elif y is None and fallback_metrics:
            y = _first_nonredundant_metric(fallback_metrics, x)
        if color is None and discrete_remaining:
            color = discrete_remaining[0]
        elif color is not None and not is_reasonable_breakdown_column(color, card):
            color = discrete_remaining[0] if discrete_remaining else None
        if not is_discrete_for_chart(x, card):
            replacement_x = next((column for column in discrete_remaining + fallback_discretes if column != y), None)
            if replacement_x:
                x = replacement_x
                if color == replacement_x:
                    color = None
        if y == x or y is None or not is_metric_for_chart(y, card):
            replacement_y = _first_nonredundant_metric(numeric_remaining + fallback_metrics, x)
            if replacement_y:
                y = replacement_y
            else:
                spec = spec.model_copy(update={"chart_type": "histogram"})
                y = None
                color = color if color and is_reasonable_breakdown_column(color, card) else None
        aggregation = None
    elif spec.chart_type == "heatmap":
        if aggregation in {"mean", "median", "sum"}:
            if color is None or not is_metric_for_chart(color, card):
                replacement_color = _first_nonredundant_metric(numeric_remaining + fallback_metrics, x)
                if replacement_color and replacement_color != y:
                    color = replacement_color
                else:
                    aggregation = "count"
                    color = None
        if y is None:
            if discrete_remaining:
                y = discrete_remaining[0]
            elif fallback_discretes:
                y = fallback_discretes[0]
            elif numeric_remaining:
                y = _first_nonredundant_metric(numeric_remaining, x)
        if y == x:
            if is_metric_for_chart(x, card):
                alternatives = numeric_remaining + fallback_metrics + discrete_remaining + fallback_discretes
            else:
                alternatives = discrete_remaining + fallback_discretes + numeric_remaining + fallback_metrics
            alternative = next((column for column in alternatives if column != x), None)
            if alternative:
                y = alternative
        if color is None and len(discrete_remaining) >= 2:
            color = discrete_remaining[1]
        x_discrete = is_discrete_for_chart(x, card)
        y_discrete = is_discrete_for_chart(y, card)
        x_metric = is_metric_for_chart(x, card)
        y_metric = is_metric_for_chart(y, card)
        if x_metric and y_metric:
            spec = spec.model_copy(update={"chart_type": "scatter"})
            color = color if color and is_reasonable_breakdown_column(color, card) else None
            aggregation = None
        elif (x_discrete and y_metric) or (x_metric and y_discrete):
            if x_metric and y_discrete:
                old_x = x
                x = y  # type: ignore[assignment]
                y = old_x
            spec = spec.model_copy(update={"chart_type": "violin"})
            color = color if color and is_reasonable_breakdown_column(color, card) else None
            aggregation = None
        else:
            aggregation = aggregation or "count"
            if aggregation == "rate":
                target_value = target_value or infer_target_value(color or y, card)

    title = build_chart_title(spec.chart_type, x, y, color, aggregation)
    return spec.model_copy(
        update={
            "x": x,
            "y": y,
            "color": color,
            "title": title,
            "aggregation": aggregation,
            "bar_mode": bar_mode,
            "target_value": target_value,
        }
    )


def build_chart_title(chart_type: str, x: str, y: str | None, color: str | None, aggregation: str | None) -> str:
    pretty_x = x.replace("_", " ").title()
    pretty_y = y.replace("_", " ").title() if y else None
    pretty_color = color.replace("_", " ").title() if color else None
    pretty_agg = {
        "count": "Count",
        "mean": "Average",
        "median": "Median",
        "sum": "Total",
        "rate": "Rate",
    }.get(aggregation or "", "")

    if chart_type == "histogram":
        return f"Histogram of {pretty_x} by {pretty_color}" if pretty_color else f"Distribution of {pretty_x}"
    if chart_type == "bar":
        if pretty_y and pretty_color:
            if aggregation in {"mean", "median", "sum", "rate"}:
                return f"{pretty_agg} of {pretty_y} by {pretty_x} and {pretty_color}"
            return f"{pretty_y} by {pretty_x} and {pretty_color}"
        if pretty_y:
            if aggregation in {"mean", "median", "sum", "rate"}:
                return f"{pretty_agg} of {pretty_y} by {pretty_x}"
            return f"{pretty_y} by {pretty_x}"
        if pretty_color:
            return f"Distribution of {pretty_x} by {pretty_color}"
        return f"Count of {pretty_x}"
    if chart_type == "scatter":
        return f"{pretty_y} vs {pretty_x}" + (f" by {pretty_color}" if pretty_color else "") if pretty_y else f"Relationship with {pretty_x}"
    if chart_type == "line":
        prefix = f"{pretty_agg} " if pretty_agg and pretty_y else ""
        return f"{prefix}{pretty_y} over {pretty_x}" + (f" by {pretty_color}" if pretty_color else "") if pretty_y else f"Trend over {pretty_x}"
    if chart_type in {"box", "violin"}:
        return f"Distribution of {pretty_y} by {pretty_x}" + (f" and {pretty_color}" if pretty_color else "") if pretty_y else f"Distribution by {pretty_x}"
    if chart_type == "heatmap":
        if aggregation in {"mean", "median", "sum", "rate"} and pretty_y and pretty_color:
            return f"{pretty_agg} of {pretty_color} across {pretty_x} and {pretty_y}"
        return f"{pretty_x} vs {pretty_y}" if pretty_y else f"Heatmap of {pretty_x}"
    return f"Chart of {pretty_x}"


def create_layout_plan(
    plan: AnalysisPlan,
    table_plan: TablePlan,
    chart_specs: list[ChartSpec],
    client: OpenAIStructuredClient | None = None,
) -> LayoutPlan:
    if client:
        layout_plan = client.parse(
            stage=AgentStage.LAYOUT.value,
            system=SYSTEM_PROMPT,
            user=(
                "Create the final notebook layout. Include a data_card item, selected tables, and selected charts. "
                "Item refs must match table/chart ids or 'data_card'. Each item must be unique; do not repeat the same ref twice.\n\n"
                f"Analysis plan:\n{plan.model_dump_json(indent=2)}\n\n"
                f"Tables:\n{table_plan.model_dump_json(indent=2)}\n\n"
                f"Charts:\n{json.dumps([chart.model_dump() for chart in chart_specs], indent=2)}"
            ),
            output_model=LayoutPlan,
        )
        return sanitize_layout_plan(layout_plan, plan, table_plan, chart_specs)

    items = [LayoutItem(kind="data_card", ref="data_card", title="Data Card")]
    items.extend(LayoutItem(kind="table", ref=table.id, title=table.title) for table in table_plan.tables[:2])
    items.extend(LayoutItem(kind="chart", ref=chart.id, title=chart.title) for chart in chart_specs)
    items.extend(LayoutItem(kind="table", ref=table.id, title=table.title) for table in table_plan.tables[2:])
    return sanitize_layout_plan(
        LayoutPlan(title="Data Exploration Notebook", subtitle=plan.objective, items=items),
        plan,
        table_plan,
        chart_specs,
    )


def sanitize_layout_plan(
    layout_plan: LayoutPlan,
    plan: AnalysisPlan,
    table_plan: TablePlan,
    chart_specs: list[ChartSpec],
) -> LayoutPlan:
    valid_refs = {"data_card"}
    valid_refs.update(table.id for table in table_plan.tables)
    valid_refs.update(chart.id for chart in chart_specs)
    seen: set[tuple[str, str]] = set()
    items: list[LayoutItem] = []

    for item in layout_plan.items:
        signature = (item.kind, item.ref)
        if item.ref not in valid_refs or signature in seen:
            continue
        seen.add(signature)
        items.append(item)

    normalized_by_signature = {(item.kind, item.ref): item for item in items}
    ordered_items: list[LayoutItem] = []

    ordered_items.append(
        normalized_by_signature.get(
            ("data_card", "data_card"),
            LayoutItem(kind="data_card", ref="data_card", title="Data Card"),
        )
    )

    for table in table_plan.tables:
        signature = ("table", table.id)
        ordered_items.append(
            normalized_by_signature.get(
                signature,
                LayoutItem(kind="table", ref=table.id, title=table.title),
            )
        )

    for chart in chart_specs:
        signature = ("chart", chart.id)
        ordered_items.append(
            normalized_by_signature.get(
                signature,
                LayoutItem(kind="chart", ref=chart.id, title=chart.title),
            )
        )

    return LayoutPlan(
        title=layout_plan.title or "Data Exploration Notebook",
        subtitle=layout_plan.subtitle or plan.objective,
        items=ordered_items,
    )
