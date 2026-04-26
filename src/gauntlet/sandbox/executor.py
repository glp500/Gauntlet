"""Execute the fixed sandbox runtime in a subprocess."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from logging import Logger

from gauntlet.run_context import RunContext


def execute_sandbox(
    *,
    context: RunContext,
    timeout_seconds: int,
    logger: Logger,
    attempt_number: int | None = None,
) -> dict[str, object]:
    """Run `run_analysis.py` and capture execution metadata."""
    command = [sys.executable, "run_analysis.py"]
    start_time = time.perf_counter()

    try:
        completed = subprocess.run(
            command,
            cwd=context.sandbox_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        duration_seconds = time.perf_counter() - start_time
        logger.error("Sandbox timed out after %.2f seconds", duration_seconds)
        context.record_step(
            "execute_sandbox",
            status="failed",
            attempt_number=attempt_number,
            details={"duration_seconds": round(duration_seconds, 3), "timeout": True},
        )
        return {
            "status": "failed",
            "duration_seconds": round(duration_seconds, 3),
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "failure_reason": f"Sandbox execution timed out after {timeout_seconds} seconds.",
        }

    duration_seconds = time.perf_counter() - start_time
    logger.info("Sandbox exit code: %s", completed.returncode)
    if completed.stdout:
        logger.info("Sandbox stdout:\n%s", completed.stdout)
    if completed.stderr:
        logger.info("Sandbox stderr:\n%s", completed.stderr)

    status = "completed" if completed.returncode == 0 else "failed"
    failure_reason = None
    if status != "completed":
        failure_reason = f"Sandbox execution failed with exit code {completed.returncode}."
        stderr_lines = [line.strip() for line in completed.stderr.splitlines() if line.strip()]
        if stderr_lines:
            failure_reason = f"{failure_reason} {stderr_lines[-1]}"

    context.record_step(
        "execute_sandbox",
        status=status,
        attempt_number=attempt_number,
        details={
            "duration_seconds": round(duration_seconds, 3),
            "exit_code": completed.returncode,
        },
    )
    return {
        "status": status,
        "duration_seconds": round(duration_seconds, 3),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "failure_reason": failure_reason,
    }


def execute_semantic_smoke_check(
    *,
    context: RunContext,
    bundle_contract: dict[str, list[str]] | None,
    logger: Logger,
    attempt_number: int | None = None,
) -> dict[str, object]:
    """Run a deterministic semantic check against the generated bundle."""
    command = [sys.executable, "-c", _SMOKE_CHECK_SCRIPT]
    env = os.environ.copy()
    env["GAUNTLET_BUNDLE_CONTRACT"] = json.dumps(bundle_contract or {})
    start_time = time.perf_counter()

    completed = subprocess.run(
        command,
        cwd=context.sandbox_dir,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    duration_seconds = time.perf_counter() - start_time
    logger.info("Semantic smoke check exit code: %s", completed.returncode)
    if completed.stdout:
        logger.info("Semantic smoke check stdout:\n%s", completed.stdout)
    if completed.stderr:
        logger.info("Semantic smoke check stderr:\n%s", completed.stderr)

    raw_stdout = completed.stdout.strip()
    if not raw_stdout:
        payload = {
            "status": "failed",
            "failure_reason": _build_smoke_failure_reason(completed.returncode, completed.stderr),
            "raw_stdout": completed.stdout,
            "raw_stderr": completed.stderr,
        }
    else:
        try:
            payload = json.loads(raw_stdout)
        except json.JSONDecodeError:
            payload = {
                "status": "failed",
                "failure_reason": "Semantic smoke check returned unparseable output.",
                "raw_stdout": completed.stdout,
                "raw_stderr": completed.stderr,
            }

    if completed.returncode != 0 and payload.get("status") != "failed":
        payload = {
            "status": "failed",
            "failure_reason": _build_smoke_failure_reason(completed.returncode, completed.stderr),
            "raw_stdout": completed.stdout,
            "raw_stderr": completed.stderr,
        }

    if completed.returncode != 0:
        payload["status"] = "failed"
        payload["failure_reason"] = payload.get("failure_reason") or _build_smoke_failure_reason(
            completed.returncode,
            completed.stderr,
        )
        payload.setdefault("raw_stdout", completed.stdout)
        payload.setdefault("raw_stderr", completed.stderr)

    context.record_step(
        "semantic_smoke_check",
        status=str(payload.get("status", "failed")),
        attempt_number=attempt_number,
        details={
            "duration_seconds": round(duration_seconds, 3),
            "loaded_keys": payload.get("loaded_keys", []),
            "processed_keys": payload.get("processed_keys", []),
            "result_table_names": payload.get("result_table_names", []),
            "figure_file_names": payload.get("figure_file_names", []),
        },
    )
    payload["duration_seconds"] = round(duration_seconds, 3)
    return payload


def _build_smoke_failure_reason(exit_code: int, stderr: str) -> str:
    """Create a concise failure reason from a semantic smoke subprocess crash."""
    reason = f"Semantic smoke check failed with exit code {exit_code}."
    stderr_lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    if stderr_lines:
        reason = f"{reason} {stderr_lines[-1]}"
    return reason


_SMOKE_CHECK_SCRIPT = r"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import pandas as pd

from analysis import run_analysis
from data_loader import load_data
from figures import create_figures
from preprocessing import preprocess


def _normalize_contract(raw_contract: object) -> dict[str, list[str]]:
    if not isinstance(raw_contract, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for key in (
        "loaded_keys",
        "processed_keys",
        "result_table_names",
        "figure_file_names",
    ):
        raw_value = raw_contract.get(key, [])
        if not isinstance(raw_value, list):
            normalized[key] = []
            continue
        normalized[key] = [str(item).strip() for item in raw_value if str(item).strip()]
    return normalized


def _assert_expected_keys(
    actual_keys: list[str],
    expected_keys: list[str],
    label: str,
) -> None:
    if not expected_keys:
        return
    if set(actual_keys) != set(expected_keys):
        raise ValueError(
            f"{label} keys did not match the shared contract. "
            f"Expected={expected_keys}, actual={actual_keys}."
        )


def _resolve_reported_path(raw_path: str, sandbox_dir: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (sandbox_dir / path).resolve()


payload: dict[str, object] = {
    "status": "completed",
    "loaded_keys": [],
    "processed_keys": [],
    "result_table_names": [],
    "result_value_types": {},
    "figure_paths": [],
    "figure_file_names": [],
}

try:
    sandbox_dir = Path.cwd()
    input_dir = sandbox_dir / "inputs" / "data"
    smoke_output_dir = sandbox_dir / "_semantic_smoke_outputs"
    smoke_output_dir.mkdir(parents=True, exist_ok=True)
    contract = _normalize_contract(json.loads(os.environ.get("GAUNTLET_BUNDLE_CONTRACT", "{}")))

    loaded_data = load_data(str(input_dir))
    if not isinstance(loaded_data, dict):
        raise TypeError("load_data must return a dictionary.")

    loaded_keys = sorted(str(key) for key in loaded_data.keys())
    payload["loaded_keys"] = loaded_keys
    _assert_expected_keys(loaded_keys, contract.get("loaded_keys", []), "load_data")

    processed_data = preprocess(loaded_data)
    if not isinstance(processed_data, dict):
        raise TypeError("preprocess must return a dictionary.")

    processed_keys = sorted(str(key) for key in processed_data.keys())
    payload["processed_keys"] = processed_keys
    _assert_expected_keys(processed_keys, contract.get("processed_keys", []), "preprocess")

    analysis_results = run_analysis(processed_data)
    if not isinstance(analysis_results, dict):
        raise TypeError("run_analysis must return a dictionary.")

    result_value_types = {
        str(name): type(value).__name__
        for name, value in analysis_results.items()
    }
    payload["result_value_types"] = result_value_types

    invalid_result_keys = [
        str(name)
        for name, value in analysis_results.items()
        if not isinstance(value, pd.DataFrame)
    ]
    if invalid_result_keys:
        raise TypeError(
            "run_analysis returned non-DataFrame values for keys: "
            + ", ".join(invalid_result_keys)
        )

    result_table_names = sorted(str(name) for name in analysis_results.keys())
    payload["result_table_names"] = result_table_names
    if not result_table_names:
        raise ValueError("run_analysis returned no result tables.")
    _assert_expected_keys(
        result_table_names,
        contract.get("result_table_names", []),
        "run_analysis",
    )

    figure_paths = create_figures(processed_data, analysis_results, str(smoke_output_dir))
    if not isinstance(figure_paths, list):
        raise TypeError("create_figures must return a list of file paths.")
    if not figure_paths:
        raise ValueError("create_figures returned no figure paths.")

    normalized_figure_paths = [str(path) for path in figure_paths]
    payload["figure_paths"] = normalized_figure_paths
    figure_file_names = sorted(Path(path).name for path in normalized_figure_paths)
    payload["figure_file_names"] = figure_file_names
    _assert_expected_keys(
        figure_file_names,
        contract.get("figure_file_names", []),
        "create_figures",
    )

    for raw_path in normalized_figure_paths:
        resolved_path = _resolve_reported_path(raw_path, sandbox_dir)
        if not resolved_path.exists():
            raise FileNotFoundError(
                f"create_figures reported a figure path that does not exist: {raw_path}"
            )
except Exception as exc:
    payload["status"] = "failed"
    payload["failure_reason"] = str(exc)
    payload["traceback"] = traceback.format_exc()

print(json.dumps(payload))
"""
