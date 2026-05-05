from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from .models import ChartSpec, DataCard, LayoutPlan, TablePlan


PolicyAction = Literal["allow", "warn", "repair", "block"]


@dataclass(frozen=True)
class PolicyDecision:
    stage: str
    subject: str
    action: PolicyAction
    reason: str

    def model_dump(self) -> dict[str, str]:
        return asdict(self)


def _profile(card: DataCard, column: str | None):
    if not column:
        return None
    return next((profile for profile in card.columns if profile.name == column), None)


def _is_numeric(card: DataCard, column: str | None) -> bool:
    profile = _profile(card, column)
    return bool(profile and profile.role == "numeric")


def _is_categoricalish(card: DataCard, column: str | None) -> bool:
    profile = _profile(card, column)
    return bool(profile and profile.role in {"categorical", "boolean", "text"})


def _is_datetime(card: DataCard, column: str | None) -> bool:
    profile = _profile(card, column)
    return bool(profile and profile.role == "datetime")


def validate_chart_specs(chart_specs: list[ChartSpec], card: DataCard) -> list[PolicyDecision]:
    valid_columns = {column.name for column in card.columns}
    decisions: list[PolicyDecision] = []
    seen: set[tuple[str, str, str | None, str | None, str | None]] = set()

    for spec in chart_specs:
        referenced = {spec.x, spec.y, spec.color} - {None}
        missing = sorted(referenced - valid_columns)
        if missing:
            decisions.append(
                PolicyDecision("chart_specs", spec.id, "block", f"references unknown columns: {', '.join(missing)}")
            )
            continue

        signature = (spec.chart_type, spec.x, spec.y, spec.color, spec.aggregation)
        if signature in seen:
            decisions.append(PolicyDecision("chart_specs", spec.id, "warn", "duplicates another chart signature"))
        seen.add(signature)

        if spec.y and spec.x == spec.y:
            decisions.append(PolicyDecision("chart_specs", spec.id, "block", "plots a column against itself"))

        if spec.chart_type == "scatter" and spec.y and not (_is_numeric(card, spec.x) and _is_numeric(card, spec.y)):
            decisions.append(PolicyDecision("chart_specs", spec.id, "warn", "relationship chart has non-numeric axes"))

        if spec.chart_type == "line" and spec.y and not ((_is_numeric(card, spec.x) or _is_datetime(card, spec.x)) and _is_numeric(card, spec.y)):
            decisions.append(PolicyDecision("chart_specs", spec.id, "warn", "line chart has an invalid time or value axis"))

        if spec.chart_type in {"box", "violin"} and spec.y and not _is_numeric(card, spec.y):
            decisions.append(PolicyDecision("chart_specs", spec.id, "warn", "distribution chart has a non-numeric measure"))

        if spec.chart_type == "heatmap" and spec.aggregation in {"mean", "median", "sum"} and not _is_numeric(card, spec.color):
            decisions.append(PolicyDecision("chart_specs", spec.id, "block", "numeric heatmap aggregation lacks a numeric value field"))

        if spec.chart_type == "heatmap":
            high_cardinality_axes = [
                axis for axis in [spec.x, spec.y]
                if _profile(card, axis) and _profile(card, axis).unique_count > 30
            ]
            if high_cardinality_axes:
                decisions.append(
                    PolicyDecision(
                        "chart_specs",
                        spec.id,
                        "warn",
                        f"heatmap axis has too many categories to label clearly: {', '.join(high_cardinality_axes)}",
                    )
                )

        if spec.color and _profile(card, spec.color) and _profile(card, spec.color).unique_count > 50:
            decisions.append(PolicyDecision("chart_specs", spec.id, "warn", "color encoding has high cardinality"))

        if spec.chart_type == "bar" and spec.color and not _is_categoricalish(card, spec.color):
            decisions.append(PolicyDecision("chart_specs", spec.id, "warn", "bar color field is not categorical"))

    if not chart_specs:
        decisions.append(PolicyDecision("chart_specs", "all", "block", "no chart specs were produced"))
    return decisions


def validate_layout_plan(layout_plan: LayoutPlan, table_plan: TablePlan, chart_specs: list[ChartSpec]) -> list[PolicyDecision]:
    decisions: list[PolicyDecision] = []
    chart_refs = {chart.id for chart in chart_specs}
    table_refs = {table.id for table in table_plan.tables}
    item_signatures = [(item.kind, item.ref) for item in layout_plan.items]

    if not layout_plan.items or layout_plan.items[0].kind != "data_card":
        decisions.append(PolicyDecision("layout", "order", "warn", "data card is not first"))

    first_table_index = next((index for index, item in enumerate(layout_plan.items) if item.kind == "table"), None)
    first_chart_index = next((index for index, item in enumerate(layout_plan.items) if item.kind == "chart"), None)
    if first_table_index is None:
        decisions.append(PolicyDecision("layout", "dataset_explorer", "block", "dataset explorer table is missing"))
    elif first_chart_index is not None and first_table_index > first_chart_index:
        decisions.append(PolicyDecision("layout", "order", "repair", "dataset explorer should appear before charts"))

    if len(set(item_signatures)) != len(item_signatures):
        decisions.append(PolicyDecision("layout", "items", "warn", "layout contains duplicate refs"))

    for item in layout_plan.items:
        if item.kind == "chart" and item.ref not in chart_refs:
            decisions.append(PolicyDecision("layout", item.ref, "block", "chart ref does not exist"))
        if item.kind == "table" and item.ref not in table_refs:
            decisions.append(PolicyDecision("layout", item.ref, "block", "table ref does not exist"))

    return decisions


def has_blocking_decisions(decisions: list[PolicyDecision]) -> bool:
    return any(decision.action == "block" for decision in decisions)
