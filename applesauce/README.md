# Applesauce

Applesauce is a local agent harness for data science exploration. It accepts a dataset and a short natural-language spec, runs the pipeline described in `agentFlow.png`, and writes a Jupyter notebook plus traceable run artifacts.

## Quick Start

```powershell
python -m pip install -e ".[dev]"
$env:OPENAI_API_KEY = "sk-..."
python -m applesauce
```

Choose `1. Create exploration notebook`, then enter the dataset path and specifications inside the CLI.
By default, the interactive CLI uses offline mode (`Y/n`) so you can test the harness without API calls. If you answer `n`, the CLI shows a numbered OpenAI model menu.
If no API key is available yet, Applesauce asks for it once and stores it in your user config file. On Windows, that is usually `%APPDATA%\applesauce\config.json`. The `OPENAI_API_KEY` environment variable still takes priority when set.
The CLI also includes `2. Run it yaself mode`, which uses a completely separate small-local-model pipeline under `applesauce/run_it_yaself/`.

For deterministic local testing without OpenAI calls:

```powershell
python -m applesauce run --data tests/fixtures/mixed.csv --spec "Explore revenue quality" --out runs/demo --offline
```

For a local model exposed through an OpenAI-compatible endpoint such as LM Studio, Ollama, or vLLM:

```powershell
python -m applesauce run-it-yaself --data tests/fixtures/mixed.csv --spec "Explore revenue quality" --out runs/demo-local --base-url http://127.0.0.1:1234/v1 --model your-local-model
```

The final notebook is written to `runs/demo/exploration.ipynb`. Supporting artifacts, including the cleaned dataset, agent outputs, trace log, validation report, and manifest are written beside it.
Run observability artifacts are also copied into the centralized history store at `runs/_history` by default. Set `APPLESAUCE_RUN_HISTORY_DIR` to use a different location.

For the local reliability eval suite:

```powershell
python -m applesauce eval --out runs/evals --include-large
```

The eval command runs golden offline datasets, checks notebook validity, chart uniqueness, layout ordering, trace generation, validation results, and large-file notebook stability.

## Pipeline

1. User input
2. Data cleaning
3. Data card
4. Data analyst
5. Theme selection
6. Table creation
7. Chart orchestration
8. Chart makers
9. Layout
10. Notebook UI

OpenAI-backed stages use structured Pydantic outputs. Chart and table rendering stays declarative: agents choose what should be shown, and trusted local templates generate the notebook code.

`Run it yaself` mode is intentionally separate. It is designed for weaker local models and uses:

- deterministic candidate generation instead of open-ended planning
- smaller prompts with compact dataset summaries
- model selection from vetted question, theme, chart, and layout options
- retry-and-repair JSON parsing for schema failures
- explicit abstain-and-fallback behavior when the local model is unsure

## Reliability Artifacts

Each run writes:

- `trace.jsonl`: stage-by-stage run events, timings, model calls, validation decisions, and runtime choices.
- `validation_report.json`: explicit policy decisions for chart specs and layout.
- `manifest.json`: final run summary with notebook execution status, runtime notes, trace path, validation path, and cached data path.
- `cleaned_data.parquet`: optional columnar cache when Parquet support is installed; notebooks use it for faster column-level loading.

Applesauce also snapshots each run's trace, manifest, validation report, data card, and agent JSON outputs into `runs/_history/<timestamp>_<dataset>_<run_id>/`. A compact `runs/_history/index.jsonl` is appended for later optimization and regression analysis.

Large datasets skip notebook auto-execution by default to avoid oversized embedded outputs in VS Code. Notebook cells load only the columns they need.
