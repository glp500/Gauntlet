"""Run the early Gauntlet sandbox pipeline against the configured local dataset."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "gauntlet-sandbox" / "gauntlet.yaml"

STEP_FUNCTIONS = {
    "data_loader": ("data_loader.py", "load_data"),
    "data_preprocessing": ("data_preprocessing.py", "preprocess"),
    "analysis": ("analysis.py", "analyze"),
    "train": ("train.py", "train_model"),
    "eval": ("eval.py", "evaluate"),
    "visualization": ("visualization.py", "create_visualizations"),
}

CORE_ARTIFACTS = [
    "run_manifest.json",
    "data_profile.json",
    "preprocessing_report.json",
    "analysis_summary.md",
    "model_metrics.json",
    "report.md",
]


def main() -> int:
    """Parse CLI arguments and run the configured sandbox pipeline."""
    parser = argparse.ArgumentParser(description="Run the Gauntlet sandbox pipeline.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the gauntlet sandbox manifest.",
    )
    args = parser.parse_args()

    return run_pipeline(Path(args.config))


def run_pipeline(config_path: Path) -> int:
    """Run the configured pipeline and return a process-style exit code."""
    resolved_config_path = config_path.resolve()
    created_at = _utc_now()
    run_id = _build_run_id(created_at)
    manifest_data: dict[str, Any] = {
        "run_id": run_id,
        "created_at": created_at,
        "config_path": str(resolved_config_path),
        "status": "running",
        "pipeline_steps": [],
        "artifacts": [],
        "errors": [],
    }

    outputs_dir: Path | None = None

    try:
        config = _load_config(resolved_config_path)
        sandbox_dir = resolved_config_path.parent
        outputs_dir = sandbox_dir / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)
        _clear_previous_outputs(outputs_dir)

        runtime_config = _build_runtime_config(config, resolved_config_path)
        manifest_data["prompt_file"] = runtime_config["resolved_paths"]["prompt_file"]
        manifest_data["dataset_path"] = runtime_config["resolved_paths"]["dataset_file"]
        manifest_data["pipeline_order"] = list(runtime_config["pipeline"]["steps"])

        step_outputs: dict[str, Any] = {}
        execution_state: dict[str, Any] = {}

        for step_name in runtime_config["pipeline"]["steps"]:
            step_output = _run_step(
                sandbox_dir=sandbox_dir,
                step_name=step_name,
                config=runtime_config,
                state=execution_state,
            )
            manifest_data["pipeline_steps"].append(
                {
                    "name": step_name,
                    "status": "completed",
                }
            )
            step_outputs[step_name] = step_output

        artifact_paths = _write_artifacts(outputs_dir, runtime_config, step_outputs)
        manifest_data["artifacts"] = artifact_paths
        manifest_data["status"] = "success"
        manifest_data["completed_at"] = _utc_now()
        _write_json(outputs_dir / "run_manifest.json", manifest_data)
        return 0
    except Exception as error:
        manifest_data["status"] = "failed"
        manifest_data["completed_at"] = _utc_now()
        manifest_data["errors"].append(
            {
                "message": str(error),
                "type": error.__class__.__name__,
                "traceback": traceback.format_exc(),
            }
        )
        if outputs_dir is not None:
            _write_json(outputs_dir / "run_manifest.json", manifest_data)
        print(f"Gauntlet sandbox run failed: {error}", file=sys.stderr)
        return 1


def _load_config(config_path: Path) -> dict[str, Any]:
    """Read the sandbox manifest from disk."""
    if not config_path.exists():
        raise FileNotFoundError(f"Sandbox config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}

    if not isinstance(loaded, dict):
        raise ValueError("Sandbox config must be a mapping at the top level.")

    return loaded


def _build_runtime_config(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    """Resolve relative file paths and prompt text for the current run."""
    sandbox_dir = config_path.parent
    input_config = config.get("input", {})
    prompt_path = (sandbox_dir / input_config["prompt_file"]).resolve()
    dataset_path = (sandbox_dir / input_config["data"]["path"]).resolve()

    if not prompt_path.exists():
        raise FileNotFoundError(f"Configured prompt file not found: {prompt_path}")

    prompt_text = prompt_path.read_text(encoding="utf-8")

    runtime_config = dict(config)
    runtime_config["resolved_paths"] = {
        "config_file": str(config_path),
        "prompt_file": str(prompt_path),
        "dataset_file": str(dataset_path),
        "outputs_dir": str((sandbox_dir / "outputs").resolve()),
    }
    runtime_config["prompt_text"] = prompt_text

    return runtime_config


def _run_step(
    sandbox_dir: Path,
    step_name: str,
    config: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Load the configured step module and execute the expected function."""
    if step_name not in STEP_FUNCTIONS:
        raise ValueError(f"Unsupported pipeline step: {step_name}")

    file_name, function_name = STEP_FUNCTIONS[step_name]
    module = _load_module(sandbox_dir / file_name, step_name)
    step_function = getattr(module, function_name)

    if step_name == "data_loader":
        output = step_function(config)
        state["loaded_data"] = output
        return output

    if step_name == "data_preprocessing":
        output = step_function(state["loaded_data"], config)
        state["preprocessed_data"] = output
        return output

    if step_name == "analysis":
        output = step_function(state["preprocessed_data"], config)
        state["analysis"] = output
        return output

    if step_name == "train":
        output = step_function(state["preprocessed_data"], config)
        state["model"] = output
        return output

    if step_name == "eval":
        output = step_function(state["model"], state["preprocessed_data"], config)
        state["evaluation"] = output
        return output

    output = step_function(
        state["preprocessed_data"],
        state["analysis"],
        state["evaluation"],
        config,
    )
    state["visualization"] = output
    return output


def _load_module(module_path: Path, module_name: str) -> Any:
    """Load a Python module from an explicit filesystem path."""
    if not module_path.exists():
        raise FileNotFoundError(f"Sandbox module not found: {module_path}")

    spec = importlib.util.spec_from_file_location(f"gauntlet_{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_artifacts(
    outputs_dir: Path,
    config: dict[str, Any],
    step_outputs: dict[str, Any],
) -> list[dict[str, str]]:
    """Write the core sandbox artifacts from the in-memory step outputs."""
    data_profile_path = outputs_dir / "data_profile.json"
    preprocessing_report_path = outputs_dir / "preprocessing_report.json"
    analysis_summary_path = outputs_dir / "analysis_summary.md"
    model_metrics_path = outputs_dir / "model_metrics.json"
    report_path = outputs_dir / "report.md"

    _write_json(data_profile_path, step_outputs["data_loader"]["profile"])
    _write_json(
        preprocessing_report_path,
        step_outputs["data_preprocessing"]["report"],
    )
    _write_text(
        analysis_summary_path,
        step_outputs["analysis"]["summary_markdown"],
    )
    _write_json(
        model_metrics_path,
        {
            "train": step_outputs["train"],
            "evaluation": step_outputs["eval"],
            "visualization": step_outputs["visualization"],
        },
    )
    _write_text(
        report_path,
        _build_report(config, step_outputs),
    )

    return [
        {"name": "data_profile", "path": str(data_profile_path)},
        {"name": "preprocessing_report", "path": str(preprocessing_report_path)},
        {"name": "analysis_summary", "path": str(analysis_summary_path)},
        {"name": "model_metrics", "path": str(model_metrics_path)},
        {"name": "report", "path": str(report_path)},
    ]


def _build_report(config: dict[str, Any], step_outputs: dict[str, Any]) -> str:
    """Build a short human-readable run report."""
    profile = step_outputs["data_loader"]["profile"]
    preprocessing_report = step_outputs["data_preprocessing"]["report"]
    dataset = profile["dataset"]

    lines = [
        "# Gauntlet Run Report",
        "",
        f"- Project: {config['project']['name']}",
        f"- Prompt file: `{config['resolved_paths']['prompt_file']}`",
        f"- Dataset file: `{dataset['path']}`",
        f"- Rows profiled: {dataset['row_count']}",
        f"- Columns profiled: {dataset['column_count']}",
        "",
        "## Preprocessing",
        f"- Status: {preprocessing_report['status']}",
        f"- Mode: {preprocessing_report['mode']}",
        "",
        "## Modeling",
        "- Training remains a placeholder in this slice.",
        "- Evaluation remains a placeholder in this slice.",
        "",
        "## Visualization",
        "- Figure generation remains a placeholder in this slice.",
        "- No figure files were written.",
    ]

    return "\n".join(lines) + "\n"


def _clear_previous_outputs(outputs_dir: Path) -> None:
    """Remove stale core artifacts so each run rewrites a clean output set."""
    for file_name in CORE_ARTIFACTS:
        artifact_path = outputs_dir / file_name
        if artifact_path.exists():
            artifact_path.unlink()


def _write_json(path: Path, payload: Any) -> None:
    """Write JSON with stable formatting for tests and review."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _write_text(path: Path, content: str) -> None:
    """Write a plain-text artifact."""
    with path.open("w", encoding="utf-8") as handle:
        handle.write(content)


def _utc_now() -> str:
    """Return a UTC timestamp for run metadata."""
    return datetime.now(UTC).isoformat()


def _build_run_id(created_at: str) -> str:
    """Create a readable run identifier from the current timestamp."""
    timestamp = created_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
    return f"run_{timestamp}"


if __name__ == "__main__":
    raise SystemExit(main())
