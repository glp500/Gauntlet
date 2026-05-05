from pathlib import Path

import pandas as pd

from applesauce import agents
from applesauce.data import build_data_card, infer_and_clean, load_dataset
from applesauce.models import ChartOrchestration, ChartPlan, ChartSpec, ColumnProfile, DataCard, TablePlan, TableSpec
from applesauce.policy import validate_chart_specs


FIXTURE = Path(__file__).parent / "fixtures" / "mixed.csv"


def _card():
    raw = load_dataset(FIXTURE)
    cleaned, duplicates = infer_and_clean(raw)
    return build_data_card(FIXTURE, cleaned, duplicates)


def _wellness_card() -> DataCard:
    return DataCard(
        source_path="wellness.csv",
        row_count=1200,
        column_count=6,
        duplicate_rows_removed=0,
        missing_cells=0,
        missing_percent=0.0,
        columns=[
            ColumnProfile(name="age", dtype="int64", role="numeric", missing_count=0, missing_percent=0.0, unique_count=7, sample_values=["13", "14"]),
            ColumnProfile(name="gender", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=2, sample_values=["male", "female"]),
            ColumnProfile(name="platform_usage", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=3, sample_values=["Instagram", "TikTok"]),
            ColumnProfile(name="social_interaction_level", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=3, sample_values=["low", "medium"]),
            ColumnProfile(name="depression_label", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=2, sample_values=["yes", "no"]),
            ColumnProfile(name="daily_social_media_hours", dtype="float64", role="numeric", missing_count=0, missing_percent=0.0, unique_count=200, sample_values=["1.2", "4.5"]),
        ],
    )


def _trout_card() -> DataCard:
    return DataCard(
        source_path="trout.csv",
        row_count=695,
        column_count=10,
        duplicate_rows_removed=0,
        missing_cells=564,
        missing_percent=8.12,
        columns=[
            ColumnProfile(name="year", dtype="int64", role="numeric", missing_count=0, missing_percent=0.0, unique_count=72, sample_values=["2021", "2020"]),
            ColumnProfile(name="state", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=16, sample_values=["OREGON", "WASHINGTON"]),
            ColumnProfile(name="nmfs_name", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=5, sample_values=["TROUT, RAINBOW", "TROUT, BROOK"]),
            ColumnProfile(name="pounds", dtype="Int64", role="numeric", missing_count=54, missing_percent=7.77, unique_count=543, sample_values=["7055", "50706"]),
            ColumnProfile(name="metric_tons", dtype="float64", role="numeric", missing_count=54, missing_percent=7.77, unique_count=183, sample_values=["3.0", "23.0"]),
            ColumnProfile(name="dollars", dtype="Int64", role="numeric", missing_count=348, missing_percent=50.07, unique_count=345, sample_values=["11886", "34338"]),
            ColumnProfile(name="collection", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=2, sample_values=["Recreational", "Commercial"]),
            ColumnProfile(name="scientific_name", dtype="object", role="categorical", missing_count=108, missing_percent=15.54, unique_count=5, sample_values=["Oncorhynchus mykiss", "Salvelinus fontinalis"]),
            ColumnProfile(name="tsn", dtype="int64", role="numeric", missing_count=0, missing_percent=0.0, unique_count=5, sample_values=["161989", "161990"]),
            ColumnProfile(name="source", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=7, sample_values=["MRIP", "PACFIN"]),
        ],
        notes=["Missing values are retained for transparent analysis."],
    )


def _happiness_card() -> DataCard:
    return DataCard(
        source_path="happiness.csv",
        row_count=2363,
        column_count=4,
        duplicate_rows_removed=0,
        missing_cells=0,
        missing_percent=0.0,
        columns=[
            ColumnProfile(name="year", dtype="int64", role="numeric", missing_count=0, missing_percent=0.0, unique_count=20, sample_values=["2024", "2023"]),
            ColumnProfile(name="country", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=165, sample_values=["Finland", "Denmark"]),
            ColumnProfile(name="happiness_score", dtype="float64", role="numeric", missing_count=0, missing_percent=0.0, unique_count=800, sample_values=["7.8", "2.1"]),
            ColumnProfile(name="region", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=10, sample_values=["Western Europe", "South Asia"]),
        ],
    )


def test_offline_agents_produce_valid_contracts() -> None:
    card = _card()
    plan = agents.create_analysis_plan(card, "Explore revenue by segment")
    theme = agents.select_theme(plan)
    tables = agents.create_table_plan(card, plan)
    chart_plan = agents.orchestrate_charts(card, plan, theme)
    chart_specs = agents.build_chart_specs(chart_plan, card)
    layout = agents.create_layout_plan(plan, tables, chart_specs)

    assert plan.key_questions
    assert theme.name in {"executive", "technical"}
    assert tables.tables
    assert chart_specs
    assert layout.items[0].kind == "data_card"


def test_chart_specs_reference_existing_columns() -> None:
    card = _card()
    plan = agents.create_analysis_plan(card, "Explore revenue relationships")
    theme = agents.select_theme(plan)
    chart_specs = agents.build_chart_specs(agents.orchestrate_charts(card, plan, theme), card)
    columns = {column.name for column in card.columns}

    for chart in chart_specs:
        assert chart.x in columns
        assert chart.y is None or chart.y in columns
        assert chart.color is None or chart.color in columns


def test_invalid_chart_maker_output_is_repaired() -> None:
    card = _card()
    plan = ChartPlan(
        id="behavior_distribution",
        title="Behavior Distribution",
        goal="Show the behavior distribution.",
        chart_type="bar",
        columns=["customer_segment"],
        rationale="Categorical distribution.",
    )

    class BadClient:
        def parse(self, **kwargs):
            return ChartSpec(
                id="behavior_distribution",
                title="Behavior Distribution",
                description="Bad API output with invented melt columns.",
                chart_type="bar",
                x="variable",
                y="value",
            )

    spec = agents.make_chart_spec(plan, card, BadClient())  # type: ignore[arg-type]
    columns = {column.name for column in card.columns}

    assert spec.x in columns
    assert spec.y is None or spec.y in columns


def test_chart_orchestration_with_invented_columns_is_sanitized() -> None:
    card = _card()
    orchestration = ChartOrchestration(
        charts=[
            ChartPlan(
                id="behavior_distribution",
                title="Behavior Distribution",
                goal="Show the behavior distribution.",
                chart_type="bar",
                columns=["variable", "value"],
                rationale="Invalid but plausible model output.",
            )
        ]
    )
    sanitized = agents.sanitize_chart_orchestration(orchestration, card)
    columns = {column.name for column in card.columns}

    assert sanitized.charts[0].columns
    assert set(sanitized.charts[0].columns).issubset(columns)


def test_duplicate_tables_are_sanitized_into_unique_views() -> None:
    card = _card()
    raw_plan = TablePlan(
        tables=[
            TableSpec(id="one", title="Preview A", description="First preview.", kind="sample", focus_columns=["order_id", "revenue"]),
            TableSpec(id="two", title="Preview B", description="Second preview.", kind="sample", focus_columns=["customer_segment", "region"]),
        ]
    )

    sanitized = agents.sanitize_table_plan(raw_plan, card)

    assert len(sanitized.tables) == 1
    assert sanitized.tables[0].title == "Dataset Explorer"
    assert sanitized.tables[0].kind == "sample"


def test_duplicate_chart_specs_are_deduplicated() -> None:
    card = _card()
    orchestration = ChartOrchestration(
        charts=[
            ChartPlan(
                id="first_distribution",
                title="Revenue Distribution",
                goal="Inspect revenue distribution.",
                chart_type="histogram",
                columns=["revenue"],
                rationale="First pass.",
            ),
            ChartPlan(
                id="second_distribution",
                title="Revenue Histogram",
                goal="Inspect revenue distribution again.",
                chart_type="histogram",
                columns=["revenue"],
                rationale="Duplicate pass.",
            ),
        ]
    )

    specs = agents.build_chart_specs(orchestration, card)
    signatures = {(spec.chart_type, spec.x, spec.y, spec.color) for spec in specs}

    assert len(signatures) == len(specs)
    assert any(spec.x == "revenue" for spec in specs)


def test_layout_plan_deduplicates_repeated_refs() -> None:
    card = _card()
    analysis = agents.create_analysis_plan(card, "Explore revenue by segment")
    tables = agents.create_table_plan(card, analysis)
    charts = agents.build_chart_specs(ChartOrchestration(charts=agents.default_chart_plans(card)), card)
    raw_layout = agents.LayoutPlan(
        title="Notebook",
        subtitle="Test",
        items=[
            agents.LayoutItem(kind="data_card", ref="data_card", title="Data Card"),
            agents.LayoutItem(kind="table", ref=tables.tables[0].id, title=tables.tables[0].title),
            agents.LayoutItem(kind="table", ref=tables.tables[0].id, title="Duplicate Table"),
            agents.LayoutItem(kind="chart", ref=charts[0].id, title=charts[0].title),
            agents.LayoutItem(kind="chart", ref=charts[0].id, title="Duplicate Chart"),
        ],
    )

    sanitized = agents.sanitize_layout_plan(raw_layout, analysis, tables, charts)
    signatures = {(item.kind, item.ref) for item in sanitized.items}

    assert len(signatures) == len(sanitized.items)


def test_layout_plan_forces_table_before_charts() -> None:
    card = _card()
    analysis = agents.create_analysis_plan(card, "Explore revenue by segment")
    tables = agents.create_table_plan(card, analysis)
    charts = agents.build_chart_specs(ChartOrchestration(charts=agents.default_chart_plans(card)), card)
    raw_layout = agents.LayoutPlan(
        title="Notebook",
        subtitle="Test",
        items=[
            agents.LayoutItem(kind="data_card", ref="data_card", title="Data Card"),
            agents.LayoutItem(kind="chart", ref=charts[0].id, title=charts[0].title),
            agents.LayoutItem(kind="table", ref=tables.tables[0].id, title=tables.tables[0].title),
        ],
    )

    sanitized = agents.sanitize_layout_plan(raw_layout, analysis, tables, charts)

    assert sanitized.items[0].kind == "data_card"
    assert sanitized.items[1].kind == "table"
    assert all(item.kind == "chart" for item in sanitized.items[2:])


def test_table_plan_uses_columns_mentioned_in_title() -> None:
    card = _wellness_card()
    raw_plan = TablePlan(
        tables=[
            TableSpec(
                id="depression_summary",
                title="Depression Explorer",
                description="Show depression labels in the grid first.",
                kind="sample",
                focus_columns=["depression_label", "gender"],
            )
        ]
    )

    sanitized = agents.sanitize_table_plan(raw_plan, card)

    assert sanitized.tables[0].focus_columns[:2] == ["depression_label", "gender"]
    assert sanitized.tables[0].title == "Dataset Explorer"


def test_chart_spec_title_matches_displayed_dimensions() -> None:
    card = _wellness_card()
    plan = ChartPlan(
        id="age_gender_distribution",
        title="Distribution of Age and Gender",
        goal="Show age grouped by gender.",
        chart_type="histogram",
        columns=["age", "gender"],
        rationale="Age distribution should be segmented by gender.",
    )

    spec = agents.make_chart_spec(plan, card)

    assert spec.x == "age"
    assert spec.color == "gender"
    assert spec.title == "Histogram of Age by Gender"


def test_bar_chart_spec_retains_outcome_dimension() -> None:
    card = _wellness_card()
    plan = ChartPlan(
        id="depression_social_interaction",
        title="Prevalence of Depression by Social Interaction Level",
        goal="Show depression label across social interaction levels.",
        chart_type="bar",
        columns=["social_interaction_level", "depression_label"],
        rationale="The outcome label should appear on the chart.",
    )

    spec = agents.make_chart_spec(plan, card)

    assert spec.x == "social_interaction_level"
    assert spec.color == "depression_label"
    assert "Depression Label" in spec.title


def test_offline_defaults_expand_beyond_old_template_set() -> None:
    card = _wellness_card()
    chart_plan = agents.default_chart_plans(card)
    chart_types = {chart.chart_type for chart in chart_plan}
    aggregations = {chart.aggregation for chart in chart_plan}

    assert "violin" in chart_types or "heatmap" in chart_types
    assert "rate" in aggregations or "mean" in aggregations


def test_rate_chart_spec_keeps_target_value() -> None:
    card = _wellness_card()
    plan = ChartPlan(
        id="depression_by_platform",
        title="Depression Label by Platform Usage",
        goal="Compare depression prevalence across platforms.",
        chart_type="bar",
        columns=["platform_usage", "depression_label"],
        rationale="Use a prevalence view instead of raw counts.",
        aggregation="rate",
        bar_mode="group",
    )

    spec = agents.make_chart_spec(plan, card)

    assert spec.aggregation == "rate"
    assert spec.color == "depression_label"
    assert spec.target_value is not None


def test_numeric_binary_outcome_prefers_positive_class() -> None:
    card = DataCard(
        source_path="teen.csv",
        row_count=10,
        column_count=2,
        duplicate_rows_removed=0,
        missing_cells=0,
        missing_percent=0.0,
        columns=[
            ColumnProfile(name="platform_usage", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=2, sample_values=["Instagram", "TikTok"]),
            ColumnProfile(name="depression_label", dtype="int64", role="numeric", missing_count=0, missing_percent=0.0, unique_count=2, sample_values=["0", "0"]),
        ],
    )
    plan = ChartPlan(
        id="depression_rate",
        title="Depression by Platform Usage",
        goal="Compare depression prevalence across platforms.",
        chart_type="bar",
        columns=["platform_usage", "depression_label"],
        rationale="Use a prevalence view instead of raw counts.",
        aggregation="rate",
        bar_mode="group",
    )

    spec = agents.make_chart_spec(plan, card)

    assert spec.target_value == "1"


def test_heatmap_with_continuous_axes_is_downgraded() -> None:
    card = _wellness_card()
    plan = ChartPlan(
        id="hours_sleep_heatmap",
        title="Daily Social Media Hours vs Sleep Hours",
        goal="Compare two continuous lifestyle metrics.",
        chart_type="heatmap",
        columns=["daily_social_media_hours", "sleep_hours"],
        rationale="A dense count heatmap would be unreadable here.",
    )

    spec = agents.make_chart_spec(plan, card)

    assert spec.chart_type == "scatter"
    assert spec.x != spec.y


def test_box_plot_never_compares_a_variable_to_itself() -> None:
    card = _wellness_card()
    plan = ChartPlan(
        id="stress_distribution",
        title="Stress Level by Social Interaction Level",
        goal="Compare stress level across interaction groups.",
        chart_type="box",
        columns=["stress_level", "social_interaction_level"],
        rationale="Do not plot stress level against itself.",
    )

    spec = agents.make_chart_spec(plan, card)

    assert spec.chart_type in {"box", "violin", "bar", "histogram"}
    assert spec.y is None or spec.x != spec.y


def test_numeric_text_measure_is_not_used_as_breakdown() -> None:
    card = _trout_card()

    assert agents.is_reasonable_breakdown_column("pounds", card) is False


def test_redundant_unit_column_is_removed_from_chart_breakdown() -> None:
    card = _trout_card()
    plan = ChartPlan(
        id="metric_tons_by_year_and_pounds",
        title="Total of Metric Tons by Year and Pounds",
        goal="Show total metric tons by year.",
        chart_type="bar",
        columns=["year", "metric_tons", "pounds"],
        rationale="Broad overview, not a unit-conversion validation check.",
        aggregation="sum",
        bar_mode="group",
    )

    spec = agents.make_chart_spec(plan, card)

    assert spec.y == "metric_tons"
    assert spec.color != "pounds"
    assert "Pounds" not in spec.title


def test_temporal_sequence_column_is_not_treated_as_metric() -> None:
    card = _trout_card()

    assert agents.is_metric_for_chart("year", card) is False


def test_code_like_column_is_not_treated_as_metric() -> None:
    card = _trout_card()

    assert agents.is_metric_for_chart("tsn", card) is False


def test_skewed_bar_chart_is_refined_for_legibility() -> None:
    card = _trout_card()
    df = pd.DataFrame(
        {
            "nmfs_name": ["TROUT, RAINBOW", "TROUT, LAKE", "TROUT, BROOK", "TROUT, CUTTHROAT"],
            "metric_tons": [15000.0, 12000.0, 80.0, 10.0],
            "state": ["OREGON", "WASHINGTON", "ALASKA", "MAINE"],
        }
    )
    spec = ChartSpec(
        id="species_volume_by_state",
        title="Total of Metric Tons by Nmfs Name and State",
        description="Compare total volume by species and state.",
        chart_type="bar",
        x="nmfs_name",
        y="metric_tons",
        color="state",
        aggregation="sum",
        bar_mode="group",
    )

    refined = agents.refine_chart_specs_with_data([spec], df, card)[0]

    assert refined.orientation == "h"
    assert refined.log_value_axis is True


def test_skewed_multiseries_bar_is_converted_to_heatmap() -> None:
    card = _trout_card()
    df = pd.DataFrame(
        {
            "nmfs_name": ["TROUT, RAINBOW"] * 6 + ["TROUT, BROOK"] * 6,
            "state": ["OREGON", "WASHINGTON", "ALASKA", "MAINE", "NEW YORK", "PENNSYLVANIA"] * 2,
            "pounds": [1500000.0, 900000.0, 120000.0, 8000.0, 500.0, 50.0, 120.0, 60.0, 10.0, 5.0, 2.0, 1.0],
        }
    )
    spec = ChartSpec(
        id="trout_type_state_composition",
        title="Total of Pounds by State and Nmfs Name",
        description="Compare total landed pounds by state and trout type.",
        chart_type="bar",
        x="nmfs_name",
        y="pounds",
        color="state",
        aggregation="sum",
        bar_mode="stack",
    )

    refined = agents.refine_chart_specs_with_data([spec], df, card)[0]

    assert refined.chart_type == "heatmap"
    assert refined.x == "nmfs_name"
    assert refined.y == "state"
    assert refined.color == "pounds"
    assert refined.log_value_axis is True


def test_heatmap_with_categorical_color_and_sum_uses_numeric_measure() -> None:
    card = _trout_card()
    plan = ChartPlan(
        id="state_year_pounds_heatmap",
        title="State-year concentration of landed pounds",
        goal="Reveal concentrations across state-year combinations.",
        chart_type="heatmap",
        columns=["state", "year", "pounds"],
        rationale="Use a heatmap to show geographic-temporal volume concentration.",
        aggregation="sum",
    )
    bad_spec = ChartSpec(
        id="state_year_pounds_heatmap",
        title="Total of Collection across Year and State",
        description="Broken categorical aggregation.",
        chart_type="heatmap",
        x="year",
        y="state",
        color="collection",
        aggregation="sum",
    )

    repaired = agents.reconcile_chart_spec(bad_spec, plan, card)

    assert repaired.color == "pounds"
    assert repaired.aggregation == "sum"


def test_high_cardinality_heatmap_is_refined_to_focused_comparison() -> None:
    card = _happiness_card()
    rows = []
    for index in range(60):
        country = f"Country {index:02d}"
        base_score = 2.0 + index / 10
        rows.append({"country": country, "year": 2024, "happiness_score": base_score})
        rows.append({"country": country, "year": 2025, "happiness_score": base_score + 0.1})
    df = pd.DataFrame(rows)
    spec = ChartSpec(
        id="country_year_happiness_heatmap",
        title="Average of Happiness Score across Year and Country",
        description="Country-by-year heatmap.",
        chart_type="heatmap",
        x="year",
        y="country",
        color="happiness_score",
        aggregation="mean",
    )

    refined = agents.refine_chart_specs_with_data([spec], df, card)[0]

    assert refined.chart_type == "bar"
    assert refined.x == "country"
    assert refined.y == "happiness_score"
    assert refined.limit_mode == "top_bottom"
    assert refined.limit_n == 10
    assert refined.orientation == "h"
    assert "Top and Bottom Country" in refined.title


def test_policy_warns_about_unfocused_high_cardinality_heatmap() -> None:
    card = _happiness_card()
    spec = ChartSpec(
        id="country_year_happiness_heatmap",
        title="Average of Happiness Score across Year and Country",
        description="Country-by-year heatmap.",
        chart_type="heatmap",
        x="year",
        y="country",
        color="happiness_score",
        aggregation="mean",
    )

    decisions = validate_chart_specs([spec], card)

    assert any("too many categories" in decision.reason for decision in decisions)
