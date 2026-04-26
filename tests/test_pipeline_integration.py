"""Integration-style tests for the retry-aware pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from gauntlet.config import Settings
from gauntlet.llm.base import LLMBackendError
from gauntlet.llm.base import LLMResponse
from gauntlet.orchestrator.pipeline import build_pipeline
from gauntlet.run_context import RunContext
from gauntlet.sandbox.executor import execute_sandbox


def _seed_project(root: Path) -> None:
    (root / "inputs" / "data").mkdir(parents=True)
    (root / "outputs" / "latest").mkdir(parents=True)
    (root / "workspace_runs").mkdir(parents=True)
    (root / "sandbox_template").mkdir(parents=True)

    (root / "inputs" / "input.txt").write_text(
        "Analyze the sales data and summarize revenue.",
        encoding="utf-8",
    )
    (root / "inputs" / "data" / "sample.csv").write_text(
        "region,revenue\nNorth,10\nSouth,20\n",
        encoding="utf-8",
    )
    (root / "sandbox_template" / "run_analysis.py").write_text(
        (Path(__file__).resolve().parents[1] / "sandbox_template" / "run_analysis.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    (root / "sandbox_template" / "requirements.txt").write_text(
        "pandas\nmatplotlib\n",
        encoding="utf-8",
    )


@dataclass
class SequenceBackend:
    """Backend that returns a fixed sequence of responses."""

    responses: list[LLMResponse | Exception]
    backend_name: str = "openai"
    model: str = "mock-model"
    prompt_log: list[dict[str, str | None]] = field(default_factory=list)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: str | None = None,
    ) -> LLMResponse:
        self.prompt_log.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_format": response_format,
            }
        )
        if not self.responses:
            raise AssertionError("No mock responses left for this backend.")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def is_available(self) -> bool:
        return True


def _review_response(
    *,
    status: str,
    issues: list[dict[str, object]] | list[str],
    summary: str = "Review completed.",
) -> LLMResponse:
    return LLMResponse(
        content=json.dumps(
            {
                "status": status,
                "summary": summary,
                "issues": issues,
            }
        ),
        model="mock-openai",
        backend="openai",
        usage=None,
        raw_response={"id": "review"},
    )


def _local_file_response(file_content: str, backend_name: str) -> LLMResponse:
    """Build one local-backend file response in the format the pipeline expects."""
    raw_response: dict[str, object] = {}
    if backend_name == "llama_cpp":
        raw_response = {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": file_content},
                }
            ]
        }

    return LLMResponse(
        content=file_content,
        model=f"mock-{backend_name}",
        backend=backend_name,
        usage=None,
        raw_response=raw_response,
    )


def _local_contract() -> dict[str, list[str]]:
    """Return a coherent shared contract for the local file-by-file path."""
    return {
        "loaded_keys": ["sample"],
        "processed_keys": ["sample"],
        "result_table_names": ["revenue_by_region"],
        "figure_file_names": ["revenue_by_region.png"],
    }


def _valid_codegen_response() -> str:
    return json.dumps(_valid_codegen_bundle())


def _valid_codegen_bundle() -> dict[str, str]:
    bundle = {
        "data_loader.py": (
            '"""Load CSV inputs for the sandbox run."""\n\n'
            "from __future__ import annotations\n\n"
            "from pathlib import Path\n\n"
            "import pandas as pd\n\n"
            "def load_data(input_dir: str) -> dict[str, pd.DataFrame]:\n"
            '    """Load every CSV in the provided input directory."""\n'
            "    data: dict[str, pd.DataFrame] = {}\n"
            "    for csv_path in sorted(Path(input_dir).glob('*.csv')):\n"
            "        data[csv_path.stem] = pd.read_csv(csv_path)\n"
            "    return data\n"
        ),
        "preprocessing.py": (
            '"""Preprocess the loaded input data."""\n\n'
            "from __future__ import annotations\n\n"
            "import pandas as pd\n\n"
            "def preprocess(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
            '    """Return cleaned data frames without side effects."""\n'
            "    return data\n"
        ),
        "analysis.py": (
            '"""Compute analysis outputs for the sandbox run."""\n\n'
            "from __future__ import annotations\n\n"
            "import pandas as pd\n\n"
            "def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
            '    """Aggregate revenue by region for the sample dataset."""\n'
            "    frame = data['sample']\n"
            "    summary = frame.groupby('region', as_index=False)['revenue'].sum()\n"
            "    return {'revenue_by_region': summary}\n"
        ),
        "figures.py": (
            '"""Create figures from processed data and analysis outputs."""\n\n'
            "from __future__ import annotations\n\n"
            "from pathlib import Path\n\n"
            "import matplotlib.pyplot as plt\n"
            "import pandas as pd\n\n"
            "def create_figures(\n"
            "    data: dict[str, pd.DataFrame],\n"
            "    results: dict[str, pd.DataFrame],\n"
            "    output_dir: str,\n"
            ") -> list[str]:\n"
            '    """Write one bar chart and return the saved path."""\n'
            "    figure_dir = Path(output_dir)\n"
            "    figure_dir.mkdir(parents=True, exist_ok=True)\n"
            "    frame = results['revenue_by_region']\n"
            "    fig, ax = plt.subplots(figsize=(6, 4))\n"
            "    ax.bar(frame['region'], frame['revenue'])\n"
            "    ax.set_title('Revenue by Region')\n"
            "    ax.set_ylabel('Revenue')\n"
            "    destination = figure_dir / 'revenue_by_region.png'\n"
            "    fig.tight_layout()\n"
            "    fig.savefig(destination)\n"
            "    plt.close(fig)\n"
            "    return [str(destination)]\n"
        ),
    }
    return bundle


def _invalid_runtime_codegen_response() -> str:
    bundle = _valid_codegen_bundle()
    bundle["analysis.py"] = (
        '"""Compute analysis outputs for the sandbox run."""\n\n'
        "from __future__ import annotations\n\n"
        "import pandas as pd\n\n"
        "def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
        "    frame = data['missing_dataset']\n"
        "    return {'revenue_by_region': frame}\n"
    )
    return json.dumps(bundle)


def _missing_function_codegen_response() -> str:
    bundle = _valid_codegen_bundle()
    bundle["analysis.py"] = (
        '"""Broken analysis module."""\n\n'
        "from __future__ import annotations\n\n"
        "import pandas as pd\n\n"
        "def summarize_dataset(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
        "    return {}\n"
    )
    return json.dumps(bundle)


def _invalid_local_analysis_file() -> str:
    """Return the orchestrator-style analysis module seen in the failed local run."""
    return (
        '"""Coordinate the full sales analysis workflow."""\n\n'
        "from __future__ import annotations\n\n"
        "import pandas as pd\n\n"
        "import data_loader\n"
        "import figures\n"
        "import preprocessing\n\n"
        "def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
        "    loaded = data_loader.load_data('sample.csv')\n"
        "    prepared = preprocessing.preprocess(loaded)\n"
        "    figures.create_figures(prepared, {}, 'outputs')\n"
        "    return prepared\n\n"
        "if __name__ == '__main__':\n"
        "    run_analysis({})\n"
    )


def _invalid_result_type_codegen_response() -> str:
    """Return a bundle where run_analysis mixes text into the result dictionary."""
    bundle = _valid_codegen_bundle()
    bundle["analysis.py"] = (
        '"""Broken analysis module."""\n\n'
        "from __future__ import annotations\n\n"
        "import pandas as pd\n\n"
        "def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, object]:\n"
        "    frame = data['sample']\n"
        "    summary = frame.groupby('region', as_index=False)['revenue'].sum()\n"
        "    return {\n"
        "        'revenue_by_region': summary,\n"
        "        'text_summary': 'North and South were present.',\n"
        "    }\n"
    )
    return json.dumps(bundle)


def _key_drift_local_bundle() -> dict[str, str]:
    """Return a valid-but-incoherent local bundle with mismatched cross-file keys."""
    bundle = _valid_codegen_bundle()
    bundle["data_loader.py"] = (
        '"""Load CSV inputs for the sandbox run."""\n\n'
        "from __future__ import annotations\n\n"
        "from pathlib import Path\n\n"
        "import pandas as pd\n\n"
        "def load_data(input_dir: str) -> dict[str, pd.DataFrame]:\n"
        "    frame = pd.read_csv(Path(input_dir) / 'sample.csv')\n"
        "    return {'sales_data': frame}\n"
    )
    bundle["preprocessing.py"] = (
        '"""Preprocess the loaded input data."""\n\n'
        "from __future__ import annotations\n\n"
        "import pandas as pd\n\n"
        "def preprocess(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
        "    frame = data['sales_data'].copy()\n"
        "    return {'monthly_summary': frame}\n"
    )
    bundle["analysis.py"] = (
        '"""Compute analysis outputs for the sandbox run."""\n\n'
        "from __future__ import annotations\n\n"
        "import pandas as pd\n\n"
        "def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
        "    if 'sales_data' not in data:\n"
        "        return {}\n"
        "    frame = data['sales_data']\n"
        "    summary = frame.groupby('region', as_index=False)['revenue'].sum()\n"
        "    return {'revenue_by_region': summary}\n"
    )
    bundle["figures.py"] = (
        '"""Create figures from processed data and analysis outputs."""\n\n'
        "from __future__ import annotations\n\n"
        "import matplotlib.pyplot as plt\n"
        "import pandas as pd\n\n"
        "def create_figures(\n"
        "    data: dict[str, pd.DataFrame],\n"
        "    results: dict[str, pd.DataFrame],\n"
        "    output_dir: str,\n"
        ") -> list[str]:\n"
        "    if 'sales' not in data:\n"
        "        return []\n"
        "    frame = results['revenue_by_region']\n"
        "    fig, ax = plt.subplots(figsize=(6, 4))\n"
        "    ax.bar(frame['region'], frame['revenue'])\n"
        "    return []\n"
    )
    return bundle


def test_pipeline_completes_happy_path_with_mock_backend(tmp_path: Path) -> None:
    """The full vertical slice should run end-to-end with mocked model responses."""
    _seed_project(tmp_path)
    settings = Settings.from_env(project_root=tmp_path)

    backend = SequenceBackend(
        responses=[
            LLMResponse(
                content=(
                    "## Task Objective\nSummarize revenue by region.\n\n"
                    "## Input Dataset Summary\nOne CSV with region and revenue.\n\n"
                    "## Assumptions From Schema\nRevenue is numeric.\n\n"
                    "## Required Outputs\nA result table and one figure.\n\n"
                    "## Code Constraints\nUse pandas and matplotlib only.\n"
                ),
                model="mock-openai",
                backend="openai",
                usage=None,
                raw_response={"id": "refine"},
            ),
            LLMResponse(
                content=_valid_codegen_response(),
                model="mock-openai",
                backend="openai",
                usage=None,
                raw_response={"id": "codegen"},
            ),
            _review_response(status="approved", issues=[]),
        ]
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=backend,
        ollama_backend=backend,
        llama_cpp_backend=backend,
    )
    summary = pipeline.run()

    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 1
    assert summary["results"] == ["outputs/results/revenue_by_region.csv"]
    assert summary["figures"] == ["outputs/figures/revenue_by_region.png"]
    assert (settings.latest_output_dir / "results" / "revenue_by_region.csv").exists()
    assert (settings.latest_output_dir / "figures" / "revenue_by_region.png").exists()


def test_pipeline_ignores_hallucinated_review_contract_failures(tmp_path: Path) -> None:
    """Review-only contract or sandbox concerns should stay advisory when static checks pass."""
    _seed_project(tmp_path)
    settings = Settings.from_env(project_root=tmp_path)

    backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-openai", "openai", None, {}),
            LLMResponse(_valid_codegen_response(), "mock-openai", "openai", None, {}),
            _review_response(
                status="blocked",
                summary="These are advisory-only concerns.",
                issues=[
                    {
                        "category": "contract",
                        "message": "Missing required public function load_data in the expected module layout.",
                        "blocking": True,
                    },
                    {
                        "category": "sandbox",
                        "message": "create_figures writes output files and should be checked carefully.",
                        "blocking": True,
                    },
                ],
            ),
        ]
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=backend,
        ollama_backend=backend,
        llama_cpp_backend=backend,
    )
    summary = pipeline.run()

    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 1


def test_pipeline_repairs_after_static_validation_failure(tmp_path: Path) -> None:
    """A broken first bundle should trigger a second code generation attempt."""
    _seed_project(tmp_path)
    settings = Settings.from_env(project_root=tmp_path)

    backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-openai", "openai", None, {}),
            LLMResponse(_missing_function_codegen_response(), "mock-openai", "openai", None, {}),
            LLMResponse(_valid_codegen_response(), "mock-openai", "openai", None, {}),
            _review_response(status="approved", issues=[]),
        ]
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=backend,
        ollama_backend=backend,
        llama_cpp_backend=backend,
    )
    summary = pipeline.run()

    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 2
    assert summary["attempts"][0]["stage"] == "static_validation"
    assert (tmp_path / "workspace_runs" / summary["run_id"] / "responses" / "repair_brief_attempt_02.json").exists()


def test_pipeline_repairs_after_execution_failure(tmp_path: Path) -> None:
    """A runtime failure should feed into a second repaired attempt."""
    _seed_project(tmp_path)
    settings = Settings.from_env(project_root=tmp_path)

    backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-openai", "openai", None, {}),
            LLMResponse(_invalid_runtime_codegen_response(), "mock-openai", "openai", None, {}),
            LLMResponse(_valid_codegen_response(), "mock-openai", "openai", None, {}),
            _review_response(status="approved", issues=[]),
        ]
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=backend,
        ollama_backend=backend,
        llama_cpp_backend=backend,
    )
    summary = pipeline.run()

    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 2
    assert summary["attempts"][0]["stage"] == "semantic_validation"

    repair_brief_path = (
        tmp_path / "workspace_runs" / summary["run_id"] / "responses" / "repair_brief_attempt_02.json"
    )
    repair_brief = json.loads(repair_brief_path.read_text(encoding="utf-8"))
    assert repair_brief["failure_stage"] == "semantic_validation"
    assert "semantic_validation_result" in repair_brief


def test_pipeline_fails_immediately_without_openai_key(tmp_path: Path) -> None:
    """Missing infrastructure config should stop before the codegen loop starts."""
    _seed_project(tmp_path)
    settings = Settings.from_env(project_root=tmp_path)
    pipeline = build_pipeline(settings=settings)

    summary = pipeline.run()

    assert summary["status"] == "failed"
    assert summary["attempt_count"] == 0
    assert summary["attempts"] == []
    assert "OPENAI_API_KEY" in (summary["failure_reason"] or "")


def test_pipeline_runs_without_openai_key_when_all_steps_use_ollama(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A fully Ollama-routed pipeline should not require OpenAI credentials."""
    _seed_project(tmp_path)
    monkeypatch.setenv("GENERATION_BACKEND", "ollama")
    monkeypatch.setenv("REVIEW_BACKEND", "ollama")
    settings = Settings.from_env(project_root=tmp_path)
    bundle = _valid_codegen_bundle()

    ollama_backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-ollama", "ollama", None, {}),
            _local_file_response(json.dumps(_local_contract()), "ollama"),
            _local_file_response(bundle["data_loader.py"], "ollama"),
            _local_file_response(bundle["preprocessing.py"], "ollama"),
            _local_file_response(bundle["analysis.py"], "ollama"),
            _local_file_response(bundle["figures.py"], "ollama"),
            LLMResponse(
                content=json.dumps(
                    {
                        "status": "approved",
                        "summary": "Review completed.",
                        "issues": [],
                    }
                ),
                model="mock-ollama",
                backend="ollama",
                usage=None,
                raw_response={"id": "review"},
            ),
        ],
        backend_name="ollama",
        model="mock-ollama",
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=SequenceBackend(responses=[]),
        ollama_backend=ollama_backend,
        llama_cpp_backend=SequenceBackend(responses=[]),
    )
    summary = pipeline.run()

    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 1


def test_pipeline_stops_after_max_attempt_exhaustion(tmp_path: Path) -> None:
    """Retryable failures should stop once the configured attempt budget is exhausted."""
    _seed_project(tmp_path)
    settings = Settings.from_env(project_root=tmp_path)
    settings.max_codegen_attempts = 2

    backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-openai", "openai", None, {}),
            LLMResponse(_missing_function_codegen_response(), "mock-openai", "openai", None, {}),
            LLMResponse(_missing_function_codegen_response(), "mock-openai", "openai", None, {}),
        ]
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=backend,
        ollama_backend=backend,
        llama_cpp_backend=backend,
    )
    summary = pipeline.run()

    assert summary["status"] == "failed"
    assert summary["attempt_count"] == 2
    assert len(summary["attempts"]) == 2
    assert "after 2 attempts" in (summary["failure_reason"] or "")


def test_pipeline_fails_when_ollama_review_is_requested_but_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Review routing should still surface unavailable Ollama as non-retryable infrastructure failure."""
    _seed_project(tmp_path)
    monkeypatch.setenv("REVIEW_BACKEND", "ollama")
    settings = Settings.from_env(project_root=tmp_path)

    class UnavailableBackend(SequenceBackend):
        def is_available(self) -> bool:
            return False

    openai_backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-openai", "openai", None, {}),
            LLMResponse(_valid_codegen_response(), "mock-openai", "openai", None, {}),
        ]
    )
    ollama_backend = UnavailableBackend(responses=[])

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=openai_backend,
        ollama_backend=ollama_backend,
        llama_cpp_backend=SequenceBackend(responses=[]),
    )
    summary = pipeline.run()

    assert summary["status"] == "failed"
    assert summary["attempt_count"] == 0
    assert "unavailable" in (summary["failure_reason"] or "")


def test_pipeline_runs_without_openai_key_when_all_steps_use_llama_cpp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A fully llama.cpp-routed pipeline should not require OpenAI credentials."""
    _seed_project(tmp_path)
    monkeypatch.setenv("GENERATION_BACKEND", "llama_cpp")
    monkeypatch.setenv("REVIEW_BACKEND", "llama_cpp")
    settings = Settings.from_env(project_root=tmp_path)
    bundle = _valid_codegen_bundle()

    llama_cpp_backend = SequenceBackend(
        responses=[
            _local_file_response("brief", "llama_cpp"),
            _local_file_response(json.dumps(_local_contract()), "llama_cpp"),
            _local_file_response(bundle["data_loader.py"], "llama_cpp"),
            _local_file_response(bundle["preprocessing.py"], "llama_cpp"),
            _local_file_response(bundle["analysis.py"], "llama_cpp"),
            _local_file_response(bundle["figures.py"], "llama_cpp"),
            LLMResponse(
                content=json.dumps(
                    {
                        "status": "approved",
                        "summary": "Review completed.",
                        "issues": [],
                    }
                ),
                model="mock-llama.cpp",
                backend="llama_cpp",
                usage=None,
                raw_response={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": json.dumps(
                                    {
                                        "status": "approved",
                                        "summary": "Review completed.",
                                        "issues": [],
                                    }
                                )
                            },
                        }
                    ]
                },
            ),
        ],
        backend_name="llama_cpp",
        model="mock-llama.cpp",
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=SequenceBackend(responses=[]),
        ollama_backend=SequenceBackend(responses=[]),
        llama_cpp_backend=llama_cpp_backend,
    )
    summary = pipeline.run()

    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 1


def test_pipeline_records_distinct_local_retry_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A local retry path should distinguish static validation from backend transport failure."""
    _seed_project(tmp_path)
    monkeypatch.setenv("GENERATION_BACKEND", "ollama")
    settings = Settings.from_env(project_root=tmp_path)
    settings.max_codegen_attempts = 2
    bundle = _valid_codegen_bundle()
    bundle["analysis.py"] = (
        '"""Broken analysis module."""\n\n'
        "from __future__ import annotations\n\n"
        "import pandas as pd\n\n"
        "def summarize_dataset(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
        "    return {}\n"
    )

    backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-ollama", "ollama", None, {}),
            _local_file_response(json.dumps(_local_contract()), "ollama"),
            _local_file_response(bundle["data_loader.py"], "ollama"),
            _local_file_response(bundle["preprocessing.py"], "ollama"),
            _local_file_response(bundle["analysis.py"], "ollama"),
            _local_file_response(bundle["figures.py"], "ollama"),
            LLMBackendError(
                backend="ollama",
                model="mock-ollama",
                message="Ollama request failed: Connection reset by peer",
                request_details={"error_type": "ConnectionError"},
            ),
        ],
        backend_name="ollama",
        model="mock-ollama",
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=SequenceBackend(responses=[]),
        ollama_backend=backend,
        llama_cpp_backend=SequenceBackend(responses=[]),
    )
    summary = pipeline.run()

    assert summary["status"] == "failed"
    assert summary["attempt_count"] == 2
    assert summary["attempts"][0]["stage"] == "static_validation"
    assert summary["attempts"][1]["stage"] == "backend_request"


def test_pipeline_retries_on_incomplete_local_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An incomplete local response should be recorded as retryable instead of silently stalling."""
    _seed_project(tmp_path)
    monkeypatch.setenv("GENERATION_BACKEND", "ollama")
    monkeypatch.setenv("REVIEW_BACKEND", "ollama")
    settings = Settings.from_env(project_root=tmp_path)
    settings.max_codegen_attempts = 2
    bundle = _valid_codegen_bundle()

    backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-ollama", "ollama", None, {}),
            _local_file_response(json.dumps(_local_contract()), "ollama"),
            LLMResponse(
                json.dumps(_local_contract()),
                "mock-ollama",
                "ollama",
                None,
                {"done": False},
            ),
            _local_file_response(json.dumps(_local_contract()), "ollama"),
            _local_file_response(bundle["data_loader.py"], "ollama"),
            _local_file_response(bundle["preprocessing.py"], "ollama"),
            _local_file_response(bundle["analysis.py"], "ollama"),
            _local_file_response(bundle["figures.py"], "ollama"),
            LLMResponse(
                content=json.dumps(
                    {
                        "status": "approved",
                        "summary": "Review completed.",
                        "issues": [],
                    }
                ),
                model="mock-ollama",
                backend="ollama",
                usage=None,
                raw_response={},
            ),
        ],
        backend_name="ollama",
        model="mock-ollama",
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=SequenceBackend(responses=[]),
        ollama_backend=backend,
        llama_cpp_backend=SequenceBackend(responses=[]),
    )
    summary = pipeline.run()

    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 2
    assert summary["attempts"][0]["stage"] == "backend_request"


def test_local_repair_brief_targets_analysis_contract_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A local retry should call out sibling imports and narrow the repair prompt to the current file."""
    _seed_project(tmp_path)
    monkeypatch.setenv("GENERATION_BACKEND", "ollama")
    monkeypatch.setenv("REVIEW_BACKEND", "ollama")
    settings = Settings.from_env(project_root=tmp_path)
    bundle = _valid_codegen_bundle()

    attempt_one_bundle = dict(bundle)
    attempt_one_bundle["analysis.py"] = _invalid_local_analysis_file()

    ollama_backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-ollama", "ollama", None, {}),
            _local_file_response(json.dumps(_local_contract()), "ollama"),
            _local_file_response(attempt_one_bundle["data_loader.py"], "ollama"),
            _local_file_response(attempt_one_bundle["preprocessing.py"], "ollama"),
            _local_file_response(attempt_one_bundle["analysis.py"], "ollama"),
            _local_file_response(attempt_one_bundle["figures.py"], "ollama"),
            _local_file_response(json.dumps(_local_contract()), "ollama"),
            _local_file_response(bundle["data_loader.py"], "ollama"),
            _local_file_response(bundle["preprocessing.py"], "ollama"),
            _local_file_response(bundle["analysis.py"], "ollama"),
            _local_file_response(bundle["figures.py"], "ollama"),
            LLMResponse(
                content=json.dumps(
                    {
                        "status": "approved",
                        "summary": "Review completed.",
                        "issues": [],
                    }
                ),
                model="mock-ollama",
                backend="ollama",
                usage=None,
                raw_response={},
            ),
        ],
        backend_name="ollama",
        model="mock-ollama",
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=SequenceBackend(responses=[]),
        ollama_backend=ollama_backend,
        llama_cpp_backend=SequenceBackend(responses=[]),
    )
    summary = pipeline.run()

    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 2

    repair_brief_path = (
        tmp_path / "workspace_runs" / summary["run_id"] / "responses" / "repair_brief_attempt_02.json"
    )
    repair_brief = json.loads(repair_brief_path.read_text(encoding="utf-8"))
    analysis_issues = repair_brief["file_issues"]["analysis.py"]
    assert any("data_loader" in issue for issue in analysis_issues)
    assert any("preprocessing" in issue for issue in analysis_issues)
    assert any("figures" in issue for issue in analysis_issues)
    assert any(
        "run_analysis is not the pipeline entrypoint" in entry
        for entry in repair_brief["file_guidance"]["analysis.py"]
    )

    prompt_path = (
        tmp_path / "workspace_runs" / summary["run_id"] / "prompts" / "codegen_attempt_02__analysis.py.txt"
    )
    prompt_text = prompt_path.read_text(encoding="utf-8")
    assert "Previous bundle JSON" not in prompt_text
    assert "for csv_path in sorted(Path(input_dir).glob(" not in prompt_text
    assert "run_analysis.py is the only pipeline orchestrator." in prompt_text
    assert "The runtime imports the generated modules instead of executing them as scripts." in prompt_text
    assert (
        "`load_data(input_dir)`, `preprocess(data)`, `run_analysis(processed_data)`" in prompt_text
    )
    assert "Shared bundle contract:" in prompt_text
    assert "load_data must return keys: sample." in prompt_text
    assert "run_analysis must return result tables: revenue_by_region." in prompt_text
    assert "Role contract for analysis.py" in prompt_text
    assert "Do not import data_loader, preprocessing, analysis, or figures." in prompt_text
    assert "The `data` argument already contains preprocessed in-memory pandas DataFrames." in prompt_text
    assert "Do not add try/except blocks that orchestrate the pipeline here." in prompt_text
    assert "Do not print progress updates or pipeline banners here." in prompt_text


def test_pipeline_repairs_after_local_key_drift_semantic_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A local bundle with cross-file key drift should fail semantic validation and retry."""
    _seed_project(tmp_path)
    monkeypatch.setenv("GENERATION_BACKEND", "ollama")
    monkeypatch.setenv("REVIEW_BACKEND", "ollama")
    settings = Settings.from_env(project_root=tmp_path)
    valid_bundle = _valid_codegen_bundle()
    drifting_bundle = _key_drift_local_bundle()

    ollama_backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-ollama", "ollama", None, {}),
            _local_file_response(
                json.dumps(
                    {
                        "loaded_keys": ["sales_data"],
                        "processed_keys": ["sales_data"],
                        "result_table_names": ["revenue_by_region"],
                        "figure_file_names": ["revenue_by_region.png"],
                    }
                ),
                "ollama",
            ),
            _local_file_response(drifting_bundle["data_loader.py"], "ollama"),
            _local_file_response(drifting_bundle["preprocessing.py"], "ollama"),
            _local_file_response(drifting_bundle["analysis.py"], "ollama"),
            _local_file_response(drifting_bundle["figures.py"], "ollama"),
            _local_file_response(json.dumps(_local_contract()), "ollama"),
            _local_file_response(valid_bundle["data_loader.py"], "ollama"),
            _local_file_response(valid_bundle["preprocessing.py"], "ollama"),
            _local_file_response(valid_bundle["analysis.py"], "ollama"),
            _local_file_response(valid_bundle["figures.py"], "ollama"),
            LLMResponse(
                content=json.dumps(
                    {
                        "status": "approved",
                        "summary": "Review completed.",
                        "issues": [],
                    }
                ),
                model="mock-ollama",
                backend="ollama",
                usage=None,
                raw_response={},
            ),
        ],
        backend_name="ollama",
        model="mock-ollama",
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=SequenceBackend(responses=[]),
        ollama_backend=ollama_backend,
        llama_cpp_backend=SequenceBackend(responses=[]),
    )
    summary = pipeline.run()

    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 2
    assert summary["attempts"][0]["stage"] == "semantic_validation"

    repair_brief_path = (
        tmp_path / "workspace_runs" / summary["run_id"] / "responses" / "repair_brief_attempt_02.json"
    )
    repair_brief = json.loads(repair_brief_path.read_text(encoding="utf-8"))
    assert repair_brief["failure_stage"] == "semantic_validation"
    assert "semantic_validation_result" in repair_brief
    assert repair_brief["semantic_validation_result"]["loaded_keys"] == ["sales_data"]
    assert repair_brief["semantic_validation_result"]["processed_keys"] == ["monthly_summary"]
    assert any(
        "preprocess must preserve or intentionally transform dictionary keys" in entry
        for entry in repair_brief["file_guidance"]["preprocessing.py"]
    )


def test_pipeline_retries_when_local_contract_uses_column_names(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A column-style local contract should fail before file generation and retry cleanly."""
    _seed_project(tmp_path)
    monkeypatch.setenv("GENERATION_BACKEND", "ollama")
    monkeypatch.setenv("REVIEW_BACKEND", "ollama")
    settings = Settings.from_env(project_root=tmp_path)
    valid_bundle = _valid_codegen_bundle()

    ollama_backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-ollama", "ollama", None, {}),
            _local_file_response(
                json.dumps(
                    {
                        "loaded_keys": ["YEAR", "MONTH", "RETAIL SALES"],
                        "processed_keys": ["YEAR", "MONTH", "RETAIL SALES"],
                        "result_table_names": ["sales_summary"],
                        "figure_file_names": ["sales_summary.png"],
                    }
                ),
                "ollama",
            ),
            _local_file_response(json.dumps(_local_contract()), "ollama"),
            _local_file_response(valid_bundle["data_loader.py"], "ollama"),
            _local_file_response(valid_bundle["preprocessing.py"], "ollama"),
            _local_file_response(valid_bundle["analysis.py"], "ollama"),
            _local_file_response(valid_bundle["figures.py"], "ollama"),
            LLMResponse(
                content=json.dumps(
                    {
                        "status": "approved",
                        "summary": "Review completed.",
                        "issues": [],
                    }
                ),
                model="mock-ollama",
                backend="ollama",
                usage=None,
                raw_response={},
            ),
        ],
        backend_name="ollama",
        model="mock-ollama",
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=SequenceBackend(responses=[]),
        ollama_backend=ollama_backend,
        llama_cpp_backend=SequenceBackend(responses=[]),
    )
    summary = pipeline.run()

    assert summary["status"] == "completed"
    assert summary["attempt_count"] == 2
    assert summary["attempts"][0]["stage"] == "semantic_validation"
    assert "lowercase snake_case names" in summary["attempts"][0]["failure_reason"]


def test_pipeline_fails_when_analysis_returns_non_dataframe_values(tmp_path: Path) -> None:
    """Semantic validation should reject mixed-type analysis outputs before execution success."""
    _seed_project(tmp_path)
    settings = Settings.from_env(project_root=tmp_path)
    settings.max_codegen_attempts = 1

    backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-openai", "openai", None, {}),
            LLMResponse(_invalid_result_type_codegen_response(), "mock-openai", "openai", None, {}),
        ]
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=backend,
        ollama_backend=backend,
        llama_cpp_backend=backend,
    )
    summary = pipeline.run()

    assert summary["status"] == "failed"
    assert summary["attempt_count"] == 1
    assert summary["attempts"][0]["stage"] == "semantic_validation"
    assert "non-DataFrame values" in (summary["failure_reason"] or "")


def test_pipeline_retries_when_execution_finishes_without_required_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An exit code of zero is not enough when the run writes no results or figures."""
    _seed_project(tmp_path)
    settings = Settings.from_env(project_root=tmp_path)
    settings.max_codegen_attempts = 1

    backend = SequenceBackend(
        responses=[
            LLMResponse("brief", "mock-openai", "openai", None, {}),
            LLMResponse(_valid_codegen_response(), "mock-openai", "openai", None, {}),
            _review_response(status="approved", issues=[]),
        ]
    )

    monkeypatch.setattr(
        "gauntlet.orchestrator.pipeline.collect_artifacts",
        lambda context, settings: {"results": [], "figures": []},
    )

    pipeline = build_pipeline(
        settings=settings,
        openai_backend=backend,
        ollama_backend=backend,
        llama_cpp_backend=backend,
    )
    summary = pipeline.run()

    assert summary["status"] == "failed"
    assert summary["attempt_count"] == 1
    assert summary["attempts"][0]["stage"] == "execution"
    assert "produced no result tables" in (summary["failure_reason"] or "")


def test_executor_times_out(tmp_path: Path) -> None:
    """Long-running sandbox code should stop with a clear timeout result."""
    settings = Settings.from_env(project_root=tmp_path)
    context = RunContext.create(settings)
    (context.sandbox_dir / "run_analysis.py").write_text(
        "import time\n\ntime.sleep(5)\n",
        encoding="utf-8",
    )

    class LoggerStub:
        def info(self, message: str, *args: object) -> None:
            return None

        def error(self, message: str, *args: object) -> None:
            return None

    result = execute_sandbox(
        context=context,
        timeout_seconds=1,
        logger=LoggerStub(),
    )

    assert result["status"] == "failed"
    assert "timed out" in str(result["failure_reason"])
