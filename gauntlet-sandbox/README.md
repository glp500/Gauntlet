# Gauntlet Sandbox

## Purpose

`gauntlet-sandbox/` is the first stable MVP target for Gauntlet.
It defines the data-science pipeline contract that later agent and runner work will
consume. The sandbox is intentionally small: it holds the six Python pipeline
modules, the project manifest, and the generated artifact directory.

## Current scope

This scaffold does not implement the runner yet.
It only defines the contract for future work:

- where the sandbox reads prompt and dataset inputs
- which pipeline steps exist
- which artifacts should be produced
- which runtime policies should govern execution

## Pipeline contract

The sandbox pipeline is split into six modules with one primary responsibility each:

```text
data_loader.py
  load_data(config) -> LoadedData

data_preprocessing.py
  preprocess(data, config) -> PreprocessedData

analysis.py
  analyze(data, config) -> AnalysisArtifacts

train.py
  train_model(data, config) -> ModelArtifacts

eval.py
  evaluate(model, data, config) -> EvaluationArtifacts

visualization.py
  create_visualizations(data, analysis, evaluation, config) -> FigureArtifacts
```

These modules are the first stable target for the MVP and should stay modular.
Future runner and agent work should build around this contract rather than replacing
it with a monolithic script.

## Manifest

`gauntlet.yaml` is the human-edited sandbox project config.
It defines:

- prompt and dataset input paths
- runtime and safety defaults
- the ordered pipeline step list
- baseline modeling defaults
- figure output settings

The future sandbox runner should read `gauntlet.yaml` and write execution results to
`outputs/`.

## Expected artifact layout

```text
gauntlet-sandbox/
  outputs/
    run_manifest.json
    data_profile.json
    preprocessing_report.json
    analysis_summary.md
    model_metrics.json
    figures/
      figure_001.json
      figure_001.svg
      figure_001.png
      figure_001.py
    report.md
```

Generated artifacts in `outputs/` are ignored by git, except for `.gitkeep`.

## Input contract

The forward-looking repository contract uses:

- `../input/prompt.md` as the canonical prompt file
- `../input/run_config.yaml` as the canonical run-specific config file
- `../input_data/` as the local dataset directory

Legacy `input/agent_task.md` and `input/agent_scaffold.md` are transitional files
and are not yet wired into the sandbox contract.

