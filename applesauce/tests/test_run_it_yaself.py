from pathlib import Path

from applesauce.cli import main
from applesauce.models import ColumnProfile, DataCard
from applesauce.run_it_yaself.client import _extract_json
from applesauce.run_it_yaself.heuristics import candidate_charts
from applesauce.run_it_yaself.models import OptionSelection, ThemeSelection, TitlePolish
from applesauce.run_it_yaself.pipeline import LocalModelSettings, run_pipeline


FIXTURE = Path(__file__).parent / "fixtures" / "mixed.csv"


class FakeLocalClient:
    def parse(self, *, stage: str, user: str, output_model):
        if output_model is OptionSelection:
            if stage == "data_analyst":
                return OptionSelection(selected_ids=["comparison", "spread", "distribution"], confidence="medium", reason="Good coverage.")
            if stage == "chart_orchestrator":
                return OptionSelection(selected_ids=["metric_by_category", "metric_distribution", "category_distribution"], confidence="medium", reason="Diverse set.")
            if stage == "layout":
                return OptionSelection(selected_ids=["category_distribution", "metric_by_category", "metric_distribution"], confidence="medium", reason="Overview first.")
        if output_model is ThemeSelection:
            return ThemeSelection(selected_name="technical", confidence="high", reason="Best fit.")
        if output_model is TitlePolish:
            return TitlePolish(abstain=True, reason="Current title is fine.")
        raise AssertionError(f"Unexpected parse request: {stage} -> {output_model}")


def _high_card_card() -> DataCard:
    return DataCard(
        source_path="big.csv",
        row_count=4000,
        column_count=3,
        duplicate_rows_removed=0,
        missing_cells=0,
        missing_percent=0.0,
        columns=[
            ColumnProfile(name="country", dtype="object", role="categorical", missing_count=0, missing_percent=0.0, unique_count=120, sample_values=["A", "B"]),
            ColumnProfile(name="happiness_score", dtype="float64", role="numeric", missing_count=0, missing_percent=0.0, unique_count=600, sample_values=["7.1", "5.2"]),
            ColumnProfile(name="year", dtype="int64", role="numeric", missing_count=0, missing_percent=0.0, unique_count=20, sample_values=["2024", "2025"]),
        ],
    )


def test_run_it_yaself_menu_option_is_available(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPLESAUCE_RUN_HISTORY_DIR", str(tmp_path / "history"))
    answers = iter(["2"])

    class DummyManifest:
        notebook_path = str(tmp_path / "exploration.ipynb")

    monkeypatch.setattr("applesauce.cli.interactive_run_it_yaself", lambda input_func: DummyManifest())
    exit_code = main([], input_func=lambda prompt: next(answers))

    assert exit_code == 0


def test_high_cardinality_candidate_prefers_focused_bar() -> None:
    candidates = candidate_charts(_high_card_card(), "Show happiest and least happy countries")
    metric_by_category = next(candidate for candidate in candidates if candidate.id == "metric_by_category")

    assert metric_by_category.chart_spec.limit_mode == "top_bottom"
    assert metric_by_category.chart_spec.limit_n == 10
    assert metric_by_category.chart_spec.orientation == "h"


def test_local_pipeline_runs_with_fake_client(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPLESAUCE_RUN_HISTORY_DIR", str(tmp_path / "history"))
    manifest = run_pipeline(
        dataset_path=FIXTURE,
        spec="Explore revenue and region patterns with a small local model",
        output_dir=tmp_path,
        settings=LocalModelSettings(base_url="http://127.0.0.1:1234/v1", model="tiny-local"),
        client=FakeLocalClient(),  # type: ignore[arg-type]
    )

    assert Path(manifest.notebook_path).exists()
    assert Path(manifest.central_history_dir).exists()
    assert manifest.model == "run-it-yaself:tiny-local"
    assert any("Run it yaself mode" in note for note in manifest.runtime_notes)


def test_extract_json_handles_markdown_wrappers() -> None:
    wrapped = """```json\n{\"selected_ids\":[\"a\"],\"abstain\":false,\"confidence\":\"high\",\"reason\":\"ok\"}\n```"""

    extracted = _extract_json(wrapped)

    assert extracted.startswith("{")
    assert '"selected_ids"' in extracted
