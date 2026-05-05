from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

from .models import AnalysisPlan, ChartSpec, DataCard, LayoutPlan, TablePlan, TableSpec, ThemePreset


def hidden_code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source,
    }


def markdown_cell(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def data_card_markdown(card: DataCard) -> str:
    lines = [
        "## Data Card",
        "",
        f"- Rows: **{card.row_count:,}**",
        f"- Columns: **{card.column_count:,}**",
        f"- Missing cells: **{card.missing_cells:,} ({card.missing_percent:.2f}%)**",
        f"- Duplicate rows removed: **{card.duplicate_rows_removed:,}**",
    ]
    if card.notes:
        lines.extend(["", "### Cleaning Notes", *[f"- {note}" for note in card.notes]])
    lines.extend(["", "### Column Profile", "", "| Column | Role | Type | Missing | Unique |", "|---|---:|---:|---:|---:|"])
    for column in card.columns:
        lines.append(
            f"| `{column.name}` | {column.role} | `{column.dtype}` | "
            f"{column.missing_count:,} ({column.missing_percent:.2f}%) | {column.unique_count:,} |"
        )
    return "\n".join(lines)


def setup_code(cleaned_data_path: Path, notebook_path: Path, theme: ThemePreset, row_count: int) -> str:
    relative = os.path.relpath(cleaned_data_path, notebook_path.parent).replace("\\", "/")
    return f"""
from pathlib import Path
from numbers import Integral, Real
import math
import uuid

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from IPython.display import HTML, display

DATA_PATH = Path({relative!r})
DATASET_ROW_COUNT = {row_count}

THEME = {json.dumps(theme.model_dump(), indent=2)}
PALETTE = THEME["chart_palette"]
MAX_PLOT_ROWS = 2500 if DATASET_ROW_COUNT >= 50000 else 5000

def _unique_columns(columns):
    if not columns:
        return None
    ordered = []
    for column in columns:
        if column and column not in ordered:
            ordered.append(column)
    return ordered or None

def _load_df(columns=None, nrows=None):
    usecols = _unique_columns(columns)
    if DATA_PATH.suffix.lower() == ".parquet":
        frame = pd.read_parquet(DATA_PATH, columns=usecols)
        return frame.head(nrows) if nrows is not None else frame
    return pd.read_csv(DATA_PATH, usecols=usecols, nrows=nrows)

def _format_scalar(value):
    if pd.isna(value):
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, Integral):
        return f"{{int(value):,}}"
    if isinstance(value, Real):
        rounded = round(float(value), 3)
        return f"{{rounded:,.3f}}".rstrip("0").rstrip(".")
    text = str(value)
    return text if len(text) <= 42 else text[:39] + "..."

def _prepare_table_df(table_df):
    preview = table_df.copy()
    for column in preview.columns:
        series = preview[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            preview[column] = pd.to_datetime(series, errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
        else:
            preview[column] = series.map(_format_scalar)
    return preview

def _sample_plot_df(plot_df, max_rows=MAX_PLOT_ROWS, stratify_by=None):
    if len(plot_df) <= max_rows:
        return plot_df
    if stratify_by and stratify_by in plot_df.columns:
        groups = plot_df[stratify_by].astype("string").fillna("<missing>")
        group_count = max(int(groups.nunique(dropna=False)), 1)
        per_group = max(max_rows // group_count, 1)
        sampled_parts = []
        staged = plot_df.assign(_sample_group=groups)
        for _, frame in staged.groupby("_sample_group", dropna=False):
            sampled_parts.append(frame.sample(n=min(len(frame), per_group), random_state=42))
        sampled = pd.concat(sampled_parts, ignore_index=True).drop(columns="_sample_group", errors="ignore")
        if len(sampled) > max_rows:
            sampled = sampled.sample(n=max_rows, random_state=42)
        return sampled.reset_index(drop=True)
    return plot_df.sample(n=max_rows, random_state=42).sort_index().reset_index(drop=True)

def _limit_categories(plot_df, value_column, mode=None, n=None):
    if not mode or not n or value_column not in plot_df.columns or plot_df.empty:
        return plot_df
    ranked = plot_df.dropna(subset=[value_column]).copy()
    if ranked.empty:
        return plot_df
    n = max(int(n), 1)
    if mode == "top":
        return ranked.nlargest(n, value_column).reset_index(drop=True)
    if mode == "bottom":
        return ranked.nsmallest(n, value_column).reset_index(drop=True)
    if mode == "top_bottom":
        focused = pd.concat([ranked.nsmallest(n, value_column), ranked.nlargest(n, value_column)])
        return focused.drop_duplicates().sort_values(value_column, ascending=True).reset_index(drop=True)
    return plot_df

def _table_column_widths(preview):
    widths = []
    for column in preview.columns:
        lengths = [len(str(column))]
        lengths.extend(len(str(value)) for value in preview[column].tolist())
        widths.append(min(max(max(lengths) * 9, 110), 320))
    return widths

def _display_plotly_table(table_df, title):
    preview = _prepare_table_df(table_df)
    columnwidth = _table_column_widths(preview)
    row_fill = [
        [THEME["table_cell_background"] if row_index % 2 == 0 else THEME["table_cell_background_alt"] for _ in preview.columns]
        for row_index in range(len(preview))
    ]
    fig = go.Figure(
        data=[
            go.Table(
                columnwidth=columnwidth,
                header=dict(
                    values=list(preview.columns),
                    fill_color=THEME["table_header_background"],
                    align="left",
                    font=dict(color=THEME["table_header_foreground"], size=12),
                    height=34,
                ),
                cells=dict(
                    values=[preview[column].tolist() for column in preview.columns],
                    fill_color=row_fill,
                    align="left",
                    font=dict(color=THEME["foreground"], size=11),
                    height=30,
                ),
            )
        ]
    )
    fig.update_layout(
        title=title,
        paper_bgcolor=THEME["background"],
        font=dict(color=THEME["foreground"]),
        width=max(960, min(sum(columnwidth) + 80, 1600)),
        height=min(220 + len(preview) * 28, 900),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    fig.show()

def _display_data_grid(table_df, title):
    preview = _prepare_table_df(table_df)
    table_id = "applesauce-grid-" + uuid.uuid4().hex
    html_table = preview.to_html(index=False, table_id=table_id, classes="display compact nowrap applesauce-grid", border=0)
    styles = '''
    <style>
      .applesauce-grid-shell {{
        background: #2f2f2f;
        border: 1px solid #4a4a4a;
        border-radius: 16px;
        padding: 16px;
        color: #f5f5f5;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
      }}
      .applesauce-grid-viewport {{
        max-height: 460px;
        overflow: auto;
        border-radius: 12px;
      }}
      .applesauce-grid-title {{
        font-size: 1.1rem;
        font-weight: 600;
        color: #f8fafc;
        margin: 0 0 12px 0;
      }}
      table.applesauce-grid.dataTable,
      table.applesauce-grid.dataTable thead th,
      table.applesauce-grid.dataTable tbody td {{
        color: #f8fafc !important;
      }}
      table.applesauce-grid.dataTable thead th {{
        background: #363636 !important;
        border-bottom: 1px solid #525252 !important;
        font-weight: 700;
      }}
      table.applesauce-grid.dataTable tbody tr,
      table.applesauce-grid.dataTable tbody td {{
        background: #2f2f2f !important;
        border-color: #4a4a4a !important;
      }}
      table.applesauce-grid.dataTable tbody tr:hover td {{
        background: #3a3a3a !important;
      }}
      div.dt-container .dt-length,
      div.dt-container .dt-search,
      div.dt-container .dt-info,
      div.dt-container .dt-paging {{
        color: #e5e7eb !important;
      }}
      div.dt-container .dt-input,
      div.dt-container .dt-paging-button {{
        background: #363636 !important;
        color: #f8fafc !important;
        border: 1px solid #525252 !important;
        border-radius: 8px;
      }}
      div.dt-container .dt-paging-button.current {{
        background: #4f46e5 !important;
        border-color: #4f46e5 !important;
      }}
      div.dt-container .dt-scroll-head,
      div.dt-container .dt-scroll-body {{
        border-color: #4a4a4a !important;
      }}
    </style>
    '''
    script = '''
    <script>
      (function() {{
        const ensureReady = () => {{
          if (window.jQuery && window.jQuery.fn && window.jQuery.fn.DataTable) {{
            const selector = '#__TABLE_ID__';
            if (!window.jQuery.fn.dataTable.isDataTable(selector)) {{
              window.jQuery(selector).DataTable({{
                paging: true,
                pageLength: 50,
                lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
                deferRender: true,
                scrollX: true,
                autoWidth: false,
                order: [],
                searching: true,
                info: true
              }});
            }}
          }} else {{
            setTimeout(ensureReady, 120);
          }}
        }};
        ensureReady();
      }})();
    </script>
    '''
    script = script.replace("__TABLE_ID__", table_id)
    cdn = '''
    <link rel="stylesheet" href="https://cdn.datatables.net/2.0.8/css/dataTables.dataTables.min.css">
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://cdn.datatables.net/2.0.8/js/dataTables.min.js"></script>
    '''
    shell = '<div class="applesauce-grid-shell"><div class="applesauce-grid-title">' + str(title) + '</div><div class="applesauce-grid-viewport">' + html_table + '</div></div>'
    display(HTML(styles + cdn + shell + script))
""".strip()


def table_code(spec: TableSpec) -> str:
    title = spec.title
    focus_columns = spec.focus_columns
    columns_expr = repr(focus_columns)
    if spec.kind == "sample":
        body = f"""
selected_columns = _unique_columns({columns_expr})
table_df = _load_df(selected_columns, nrows={spec.max_rows})
""".strip()
    elif spec.kind == "missingness":
        body = f"""
selected_columns = _unique_columns({columns_expr})
focus_df = _load_df(selected_columns)
table_df = pd.DataFrame({{
    "column": focus_df.columns,
    "missing_count": [int(focus_df[column].isna().sum()) for column in focus_df.columns],
    "missing_percent": [round(float(focus_df[column].isna().mean() * 100), 2) for column in focus_df.columns],
    "dtype": [str(focus_df[column].dtype) for column in focus_df.columns],
}}).sort_values(["missing_count", "column"], ascending=[False, True])
""".strip()
    elif spec.kind == "numeric_summary":
        body = f"""
selected_columns = _unique_columns({columns_expr})
focus_df = _load_df(selected_columns)
numeric_columns = [column for column in (selected_columns or focus_df.columns.tolist()) if column in focus_df.columns and pd.api.types.is_numeric_dtype(focus_df[column])]
if not numeric_columns:
    numeric_columns = focus_df.select_dtypes(include="number").columns.tolist()
table_df = focus_df[numeric_columns].describe().transpose().reset_index().rename(columns={{"index": "column"}}) if numeric_columns else pd.DataFrame({{"note": ["No numeric columns detected."]}})
""".strip()
    elif spec.kind == "categorical_summary":
        body = f"""
selected_columns = _unique_columns({columns_expr})
focus_df = _load_df(selected_columns)
category_columns = []
for column in (selected_columns or focus_df.columns.tolist()):
    if not pd.api.types.is_numeric_dtype(focus_df[column]) or pd.api.types.is_bool_dtype(focus_df[column]):
        category_columns.append(column)
if not category_columns:
    category_columns = focus_df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
parts = []
for column in category_columns:
    counts = focus_df[column].astype("string").fillna("<missing>").value_counts().head(5).reset_index()
    counts.columns = ["value", "count"]
    counts.insert(0, "column", column)
    parts.append(counts)
table_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame({{"note": ["No categorical columns detected."]}})
""".strip()
    else:
        body = f'table_df = _load_df(nrows={spec.max_rows})'
    render = "_display_data_grid" if spec.kind == "sample" else "_display_plotly_table"
    return f'{body}\n{render}(table_df, {title!r})'


def chart_code(spec: ChartSpec) -> str:
    x = spec.x
    y = spec.y
    color = spec.color
    title = spec.title
    aggregation = spec.aggregation
    bar_mode = spec.bar_mode or "group"
    target_value = spec.target_value
    orientation = spec.orientation or "v"
    log_value_axis = spec.log_value_axis
    sort_descending = spec.sort_descending
    limit_mode = spec.limit_mode
    limit_n = spec.limit_n
    color_arg = f", color={color!r}" if color else ""
    horizontal = orientation == "h"

    def limit_line(value_field: str) -> str:
        if limit_mode and limit_n:
            return f"plot_df = _limit_categories(plot_df, {value_field!r}, mode={limit_mode!r}, n={limit_n!r})"
        return ""

    def bar_axis_expr(value_field: str) -> tuple[str, str]:
        return (repr(value_field), repr(x)) if horizontal else (repr(x), repr(value_field))

    common = """
fig.update_layout(
    title={title!r},
    template=THEME["plotly_template"],
    colorway=PALETTE,
    paper_bgcolor=THEME["background"],
    plot_bgcolor=THEME["background"],
    font=dict(color=THEME["foreground"]),
    legend=dict(bgcolor=THEME["background"]),
)
fig.update_xaxes(gridcolor=THEME["grid"], zerolinecolor=THEME["grid"])
fig.update_yaxes(gridcolor=THEME["grid"], zerolinecolor=THEME["grid"])
fig.show()
""".strip()

    if spec.chart_type == "histogram":
        histogram_columns = [x] + ([color] if color else [])
        body = f"""
plot_df = _load_df({histogram_columns!r}).dropna(subset=[{x!r}]).copy()
plot_df = _sample_plot_df(plot_df, stratify_by={color!r})
fig = px.histogram(plot_df, x={x!r}{color_arg}, color_discrete_sequence=PALETTE, barmode={bar_mode!r})
""".strip()
    elif spec.chart_type == "bar":
        if aggregation == "rate":
            target_expr = repr(str(target_value)) if target_value is not None else "None"
            outcome_column = y or color
            group_columns = [x] + ([color] if y and color else [])
            outcome_columns = [x] + ([y] if y else []) + ([color] if color else [])
            group_columns_expr = repr(group_columns)
            bar_x_expr, bar_y_expr = bar_axis_expr("rate")
            body = f"""
plot_df = _load_df({outcome_columns!r}).dropna().copy()
plot_df[{x!r}] = plot_df[{x!r}].astype("string").fillna("<missing>")
{"plot_df[" + repr(color) + "] = plot_df[" + repr(color) + "].astype(\"string\").fillna(\"<missing>\")" if color and y else ""}
target_value = {target_expr}
if target_value is None:
    target_value = plot_df[{outcome_column!r}].astype("string").mode().iloc[0]
plot_df["target_flag"] = (plot_df[{outcome_column!r}].astype("string") == target_value).astype(int)
plot_df = plot_df.groupby({group_columns_expr}, dropna=False)["target_flag"].mean().reset_index(name="rate")
{"plot_df = plot_df.sort_values('rate', ascending=False)" if sort_descending else ""}
{limit_line("rate")}
fig = px.bar(plot_df, x={bar_x_expr}, y={bar_y_expr}{color_arg if y and color else ""}, barmode={bar_mode!r}, color_discrete_sequence=PALETTE, orientation={orientation!r})
{"fig.update_xaxes(tickformat='.0%')" if horizontal else "fig.update_yaxes(tickformat='.0%')"}
""".strip()
        elif aggregation == "count":
            grouping_columns = [x] + ([color] if color else [])
            value_columns = list(dict.fromkeys(grouping_columns + ([y] if y else [])))
            group_columns_expr = repr(grouping_columns)
            bar_x_expr, bar_y_expr = bar_axis_expr("count")
            body = f"""
plot_df = _load_df({value_columns!r}).copy()
plot_df[{x!r}] = plot_df[{x!r}].astype("string").fillna("<missing>")
{"plot_df[" + repr(color) + "] = plot_df[" + repr(color) + "].astype(\"string\").fillna(\"<missing>\")" if color else ""}
{"plot_df = plot_df[plot_df[" + repr(y) + "].notna()].copy()" if y else ""}
plot_df = plot_df.groupby({group_columns_expr}, dropna=False).size().reset_index(name="count")
{"plot_df = plot_df.sort_values('count', ascending=False)" if sort_descending else ""}
{limit_line("count")}
fig = px.bar(plot_df, x={bar_x_expr}, y={bar_y_expr}{color_arg if color else ""}, barmode={bar_mode!r}, color_discrete_sequence=PALETTE, orientation={orientation!r})
""".strip()
        elif y and aggregation in {"mean", "median", "sum"}:
            agg_name = aggregation
            bar_x_expr, bar_y_expr = bar_axis_expr(y)
            body = f"""
plot_df = _load_df([{x!r}, {y!r}] + ([{color!r}] if {color is not None} else [])).dropna().copy()
group_columns = [{x!r}] + ([{color!r}] if {color is not None} else [])
plot_df = plot_df.groupby(group_columns, dropna=False)[{y!r}].agg({agg_name!r}).reset_index()
{"plot_df = plot_df.sort_values(" + repr(y) + ", ascending=False)" if sort_descending else ""}
{limit_line(y)}
fig = px.bar(plot_df, x={bar_x_expr}, y={bar_y_expr}{color_arg}, barmode={bar_mode!r}, color_discrete_sequence=PALETTE, orientation={orientation!r})
""".strip()
        elif y and color:
            bar_x_expr, bar_y_expr = bar_axis_expr(y)
            count_x_expr, count_y_expr = bar_axis_expr("count")
            body = f"""
plot_df = _load_df([{x!r}, {y!r}, {color!r}]).dropna().copy()
if pd.api.types.is_numeric_dtype(plot_df[{y!r}]):
    plot_df = plot_df.groupby([{x!r}, {color!r}], dropna=False)[{y!r}].mean().reset_index()
    {"plot_df = plot_df.sort_values(" + repr(y) + ", ascending=False)" if sort_descending else ""}
    {limit_line(y)}
    fig = px.bar(plot_df, x={bar_x_expr}, y={bar_y_expr}, color={color!r}, barmode={bar_mode!r}, color_discrete_sequence=PALETTE, orientation={orientation!r})
else:
    plot_df[{x!r}] = plot_df[{x!r}].astype("string").fillna("<missing>")
    plot_df[{y!r}] = plot_df[{y!r}].astype("string").fillna("<missing>")
    plot_df[{color!r}] = plot_df[{color!r}].astype("string").fillna("<missing>")
    plot_df = plot_df.groupby([{x!r}, {y!r}, {color!r}], dropna=False).size().reset_index(name="count")
    {"plot_df = plot_df.sort_values('count', ascending=False)" if sort_descending else ""}
    {limit_line("count")}
    fig = px.bar(plot_df, x={count_x_expr}, y={count_y_expr}, color={color!r}, pattern_shape={y!r}, barmode={bar_mode!r}, color_discrete_sequence=PALETTE, orientation={orientation!r})
""".strip()
        elif y and aggregation in {"mean", "median", "sum"}:
            agg_name = aggregation
            bar_x_expr, bar_y_expr = bar_axis_expr(y)
            body = f"""
plot_df = _load_df([{x!r}, {y!r}]).dropna().copy()
plot_df = plot_df.groupby({x!r}, dropna=False)[{y!r}].agg({agg_name!r}).reset_index()
{"plot_df = plot_df.sort_values(" + repr(y) + ", ascending=False)" if sort_descending else ""}
{limit_line(y)}
fig = px.bar(plot_df, x={bar_x_expr}, y={bar_y_expr}, color_discrete_sequence=PALETTE, orientation={orientation!r})
""".strip()
        elif y:
            bar_x_expr, bar_y_expr = bar_axis_expr(y)
            count_x_expr, count_y_expr = bar_axis_expr("count")
            body = f"""
plot_df = _load_df([{x!r}, {y!r}]).dropna().copy()
if pd.api.types.is_numeric_dtype(plot_df[{y!r}]):
    plot_df = plot_df.groupby({x!r}, dropna=False)[{y!r}].mean().reset_index()
    {"plot_df = plot_df.sort_values(" + repr(y) + ", ascending=False)" if sort_descending else ""}
    {limit_line(y)}
    fig = px.bar(plot_df, x={bar_x_expr}, y={bar_y_expr}, color_discrete_sequence=PALETTE, orientation={orientation!r})
else:
    plot_df[{x!r}] = plot_df[{x!r}].astype("string").fillna("<missing>")
    plot_df[{y!r}] = plot_df[{y!r}].astype("string").fillna("<missing>")
    plot_df = plot_df.groupby([{x!r}, {y!r}], dropna=False).size().reset_index(name="count")
    {"plot_df = plot_df.sort_values('count', ascending=False)" if sort_descending else ""}
    {limit_line("count")}
    fig = px.bar(plot_df, x={count_x_expr}, y={count_y_expr}, color={y!r}, barmode={bar_mode!r}, color_discrete_sequence=PALETTE, orientation={orientation!r})
""".strip()
        elif color:
            count_x_expr, count_y_expr = bar_axis_expr("count")
            body = f"""
plot_df = _load_df([{x!r}, {color!r}]).dropna().copy()
plot_df[{x!r}] = plot_df[{x!r}].astype("string").fillna("<missing>")
plot_df[{color!r}] = plot_df[{color!r}].astype("string").fillna("<missing>")
plot_df = plot_df.groupby([{x!r}, {color!r}], dropna=False).size().reset_index(name="count")
{"plot_df = plot_df.sort_values('count', ascending=False)" if sort_descending else ""}
{limit_line("count")}
fig = px.bar(plot_df, x={count_x_expr}, y={count_y_expr}, color={color!r}, barmode={bar_mode!r}, color_discrete_sequence=PALETTE, orientation={orientation!r})
""".strip()
        else:
            count_x_expr, count_y_expr = bar_axis_expr("count")
            body = f"""
plot_df = _load_df([{x!r}])[{x!r}].astype("string").fillna("<missing>").value_counts().head(20).rename_axis({x!r}).reset_index(name="count")
{"plot_df = plot_df.sort_values('count', ascending=False)" if sort_descending else ""}
{limit_line("count")}
fig = px.bar(plot_df, x={count_x_expr}, y={count_y_expr}, color_discrete_sequence=PALETTE, orientation={orientation!r})
""".strip()
    elif spec.chart_type == "scatter" and y:
        scatter_columns = [x, y] + ([color] if color else [])
        body = f"""
plot_df = _load_df({scatter_columns!r}).dropna().copy()
plot_df = _sample_plot_df(plot_df, stratify_by={color!r})
fig = px.scatter(plot_df, x={x!r}, y={y!r}{color_arg}, color_discrete_sequence=PALETTE)
""".strip()
    elif spec.chart_type == "line" and y:
        if aggregation in {"mean", "median", "sum"}:
            agg_name = aggregation
            body = f"""
plot_columns = [{x!r}, {y!r}] + ([{color!r}] if {color is not None} else [])
plot_df = _load_df(plot_columns).dropna().copy()
plot_df[{x!r}] = pd.to_datetime(plot_df[{x!r}], errors="coerce")
plot_df = plot_df.dropna().sort_values({x!r})
if {color is not None}:
    plot_df[{color!r}] = plot_df[{color!r}].astype("string").fillna("<missing>")
    plot_df = plot_df.groupby([pd.Grouper(key={x!r}, freq="D"), {color!r}], dropna=False)[{y!r}].agg({agg_name!r}).reset_index()
    fig = px.line(plot_df, x={x!r}, y={y!r}, color={color!r}, color_discrete_sequence=PALETTE)
else:
    plot_df = plot_df.groupby(pd.Grouper(key={x!r}, freq="D"))[{y!r}].agg({agg_name!r}).reset_index()
    fig = px.line(plot_df, x={x!r}, y={y!r}, color_discrete_sequence=PALETTE)
""".strip()
        else:
            body = f"""
plot_columns = [{x!r}, {y!r}] + ([{color!r}] if {color is not None} else [])
plot_df = _load_df(plot_columns).dropna().copy()
plot_df[{x!r}] = pd.to_datetime(plot_df[{x!r}], errors="coerce")
plot_df = plot_df.dropna().sort_values({x!r})
if {color is not None}:
    plot_df[{color!r}] = plot_df[{color!r}].astype("string").fillna("<missing>")
    plot_df = plot_df.groupby([pd.Grouper(key={x!r}, freq="D"), {color!r}], dropna=False)[{y!r}].mean().reset_index()
    fig = px.line(plot_df, x={x!r}, y={y!r}, color={color!r}, color_discrete_sequence=PALETTE)
else:
    plot_df = plot_df.groupby(pd.Grouper(key={x!r}, freq="D"))[{y!r}].mean().reset_index()
    fig = px.line(plot_df, x={x!r}, y={y!r}, color_discrete_sequence=PALETTE)
""".strip()
    elif spec.chart_type == "box" and y:
        box_columns = [x, y] + ([color] if color else [])
        body = f"""
plot_df = _load_df({box_columns!r}).dropna().copy()
plot_df = _sample_plot_df(plot_df, stratify_by={x!r})
fig = px.box(plot_df, x={x!r}, y={y!r}{color_arg}, color_discrete_sequence=PALETTE)
""".strip()
    elif spec.chart_type == "violin" and y:
        violin_columns = [x, y] + ([color] if color else [])
        body = f"""
plot_df = _load_df({violin_columns!r}).dropna().copy()
plot_df = _sample_plot_df(plot_df, stratify_by={x!r})
fig = px.violin(plot_df, x={x!r}, y={y!r}{color_arg}, box=True, points="outliers", color_discrete_sequence=PALETTE)
""".strip()
    elif spec.chart_type == "heatmap" and y:
        if aggregation == "rate" and color:
            target_expr = repr(target_value) if target_value is not None else "None"
            body = f"""
plot_df = _load_df([{x!r}, {y!r}, {color!r}]).dropna().copy()
plot_df[{x!r}] = plot_df[{x!r}].astype("string").fillna("<missing>")
plot_df[{y!r}] = plot_df[{y!r}].astype("string").fillna("<missing>")
plot_df[{color!r}] = plot_df[{color!r}].astype("string").fillna("<missing>")
target_value = {target_expr}
if target_value is None:
    target_value = plot_df[{color!r}].mode().iloc[0]
plot_df["target_flag"] = (plot_df[{color!r}] == target_value).astype(int)
plot_df = plot_df.groupby([{x!r}, {y!r}], dropna=False)["target_flag"].mean().reset_index(name="rate")
{"plot_df['_z_plot'] = plot_df['rate'].clip(lower=1e-9).map(lambda value: math.log10(value) if value > 0 else -9)" if log_value_axis else ""}
fig = px.density_heatmap(plot_df, x={x!r}, y={y!r}, z={"'_z_plot'" if log_value_axis else '"rate"'}, histfunc="avg", text_auto=".0%")
fig.update_coloraxes(colorbar_tickformat=".0%")
""".strip()
        elif aggregation in {"mean", "median", "sum"} and color:
            agg_name = aggregation
            body = f"""
plot_df = _load_df([{x!r}, {y!r}, {color!r}]).dropna().copy()
plot_df = plot_df.groupby([{x!r}, {y!r}], dropna=False)[{color!r}].agg({agg_name!r}).reset_index()
{"plot_df['_z_plot'] = plot_df[" + repr(color) + "].clip(lower=1).map(lambda value: math.log10(value) if value > 0 else 0)" if log_value_axis else ""}
fig = px.density_heatmap(plot_df, x={x!r}, y={y!r}, z={"'_z_plot'" if log_value_axis else repr(color)}, histfunc="avg", text_auto=True)
""".strip()
        else:
            body = f"""
plot_df = _load_df([{x!r}, {y!r}]).dropna().copy()
plot_df[{x!r}] = plot_df[{x!r}].astype("string").fillna("<missing>")
plot_df[{y!r}] = plot_df[{y!r}].astype("string").fillna("<missing>")
plot_df = plot_df.groupby([{x!r}, {y!r}], dropna=False).size().reset_index(name="count")
fig = px.density_heatmap(plot_df, x={x!r}, y={y!r}, z="count", histfunc="sum", text_auto=True)
""".strip()
    else:
        body = f'fig = px.histogram(df, x={x!r}{color_arg}, color_discrete_sequence=PALETTE, barmode={bar_mode!r})'
    axis_updates = ""
    if spec.chart_type == "bar" and log_value_axis:
        axis_updates = 'fig.update_xaxes(type="log")' if orientation == "h" else 'fig.update_yaxes(type="log")'
    return f"{body}\n{axis_updates}\n{common.format(title=title)}"


def write_notebook(
    *,
    path: Path,
    cleaned_data_path: Path,
    data_card: DataCard,
    analysis_plan: AnalysisPlan,
    theme: ThemePreset,
    table_plan: TablePlan,
    chart_specs: list[ChartSpec],
    layout_plan: LayoutPlan,
    runtime_notes: list[str] | None = None,
) -> None:
    tables = {table.id: table for table in table_plan.tables}
    charts = {chart.id: chart for chart in chart_specs}
    cells: list[dict] = [
        markdown_cell(f"# {layout_plan.title}\n\n{layout_plan.subtitle}\n\n**Theme:** {theme.label}"),
        markdown_cell(f"## Analysis Plan\n\n{analysis_plan.narrative}\n\n" + "\n".join(f"- {question}" for question in analysis_plan.key_questions)),
        hidden_code_cell(setup_code(cleaned_data_path, path, theme, data_card.row_count)),
    ]
    if runtime_notes:
        cells.insert(1, markdown_cell("## Runtime Notes\n\n" + "\n".join(f"- {note}" for note in runtime_notes)))

    for item in layout_plan.items:
        if item.kind == "data_card":
            cells.append(markdown_cell(data_card_markdown(data_card)))
        elif item.kind == "table" and item.ref in tables:
            table = tables[item.ref]
            cells.append(markdown_cell(f"## {table.title}\n\n{table.description}"))
            cells.append(hidden_code_cell(table_code(table)))
        elif item.kind == "chart" and item.ref in charts:
            chart = charts[item.ref]
            cells.append(markdown_cell(f"## {chart.title}\n\n{chart.description}"))
            cells.append(hidden_code_cell(chart_code(chart)))

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(notebook, indent=2), encoding="utf-8")


def execute_notebook(path: Path, timeout_seconds: int = 600) -> bool:
    jupyter = shutil.which("jupyter")
    if not jupyter:
        return False
    subprocess.run(
        [
            jupyter,
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            "--inplace",
            path.name,
            f"--ExecutePreprocessor.timeout={timeout_seconds}",
            "--ExecutePreprocessor.kernel_name=python3",
        ],
        cwd=path.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    return True


def trust_notebook(path: Path) -> bool:
    jupyter = shutil.which("jupyter")
    if not jupyter:
        return False
    subprocess.run(
        [jupyter, "trust", path.name],
        cwd=path.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    return True
