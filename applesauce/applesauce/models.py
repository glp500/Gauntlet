from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UserRequest(BaseModel):
    dataset_path: Path
    spec: str = Field(min_length=1)
    output_dir: Path


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    role: Literal["numeric", "categorical", "datetime", "boolean", "text", "unknown"]
    missing_count: int
    missing_percent: float
    unique_count: int
    sample_values: list[str] = Field(default_factory=list)


class DataCard(BaseModel):
    source_path: str
    row_count: int
    column_count: int
    duplicate_rows_removed: int
    missing_cells: int
    missing_percent: float
    columns: list[ColumnProfile]
    notes: list[str] = Field(default_factory=list)


class AnalysisPlan(BaseModel):
    objective: str
    tone: Literal["executive", "playful", "calm", "technical", "editorial"]
    audience: str
    key_questions: list[str] = Field(min_length=1, max_length=8)
    recommended_tables: list[str] = Field(default_factory=list)
    chart_goals: list[str] = Field(default_factory=list)
    narrative: str


class ThemeChoice(BaseModel):
    name: Literal["executive", "playful", "calm", "technical", "editorial"]
    reason: str


class ThemePreset(BaseModel):
    name: str
    label: str
    palette: list[str]
    chart_palette: list[str]
    background: str
    foreground: str
    accent: str
    grid: str
    table_header_background: str
    table_header_foreground: str
    table_cell_background: str
    table_cell_background_alt: str
    plotly_template: str = "plotly_white"


class TableSpec(BaseModel):
    id: str
    title: str
    description: str
    kind: Literal["sample", "missingness", "numeric_summary", "categorical_summary"]
    max_rows: int = Field(default=20, ge=1, le=100)
    focus_columns: list[str] = Field(default_factory=list, max_length=32)


class TablePlan(BaseModel):
    tables: list[TableSpec]


class ChartPlan(BaseModel):
    id: str
    title: str
    goal: str
    chart_type: Literal["histogram", "bar", "scatter", "line", "box", "violin", "heatmap"]
    columns: list[str] = Field(min_length=1, max_length=4)
    rationale: str
    aggregation: Literal["count", "mean", "median", "sum", "rate"] | None = None
    bar_mode: Literal["group", "stack", "overlay"] | None = None


class ChartOrchestration(BaseModel):
    charts: list[ChartPlan] = Field(min_length=1, max_length=6)


class ChartSpec(BaseModel):
    id: str
    title: str
    description: str
    chart_type: Literal["histogram", "bar", "scatter", "line", "box", "violin", "heatmap"]
    x: str
    y: str | None = None
    color: str | None = None
    aggregation: Literal["count", "mean", "median", "sum", "rate"] | None = None
    bar_mode: Literal["group", "stack", "overlay"] | None = None
    target_value: str | None = None
    orientation: Literal["v", "h"] | None = None
    log_value_axis: bool = False
    sort_descending: bool = False
    limit_mode: Literal["top", "bottom", "top_bottom"] | None = None
    limit_n: int | None = Field(default=None, ge=1, le=50)

    @field_validator("id")
    @classmethod
    def id_must_be_identifierish(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("chart id cannot be blank")
        return cleaned.replace(" ", "_").lower()


class LayoutItem(BaseModel):
    kind: Literal["markdown", "data_card", "table", "chart"]
    ref: str
    title: str


class LayoutPlan(BaseModel):
    title: str
    subtitle: str
    items: list[LayoutItem]


class AgentArtifacts(BaseModel):
    analysis_plan: AnalysisPlan
    theme_choice: ThemeChoice
    table_plan: TablePlan
    chart_orchestration: ChartOrchestration
    chart_specs: list[ChartSpec]
    layout_plan: LayoutPlan


class RunManifest(BaseModel):
    request: UserRequest
    cleaned_data_path: str
    notebook_path: str
    data_card: DataCard
    artifacts: AgentArtifacts
    offline: bool
    model: str | None = None
    notebook_executed: bool = True
    runtime_notes: list[str] = Field(default_factory=list)
    trace_path: str | None = None
    validation_report_path: str | None = None
    cached_data_path: str | None = None
    central_history_dir: str | None = None


class ColumnRoles(BaseModel):
    numeric: list[str] = Field(default_factory=list)
    categorical: list[str] = Field(default_factory=list)
    datetime: list[str] = Field(default_factory=list)
    boolean: list[str] = Field(default_factory=list)
    text: list[str] = Field(default_factory=list)


class AgentStage(str, Enum):
    ANALYST = "data_analyst"
    THEME = "theme"
    TABLE = "table_creator"
    CHART_ORCHESTRATOR = "chart_orchestrator"
    CHART_MAKER = "chart_maker"
    LAYOUT = "layout"
