from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any

from pydantic import BaseModel


DEFAULT_HISTORY_DIR = Path("runs") / "_history"


def history_root() -> Path:
    configured = os.environ.get("APPLESAUCE_RUN_HISTORY_DIR")
    return Path(configured) if configured else DEFAULT_HISTORY_DIR


def safe_slug(value: str, *, max_length: int = 48) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return (cleaned or "run")[:max_length].strip("-") or "run"


def central_run_dir(*, run_id: str, dataset_path: Path, root: Path | None = None) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dataset_slug = safe_slug(dataset_path.stem)
    return (root or history_root()) / f"{timestamp}_{dataset_slug}_{run_id[:10]}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _copy_if_exists(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def save_run_history(
    *,
    run_dir: Path,
    destination: Path,
    run_id: str,
    manifest: BaseModel,
    extra: dict[str, Any] | None = None,
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    _copy_if_exists(run_dir / "trace.jsonl", destination / "trace.jsonl")
    _copy_if_exists(run_dir / "validation_report.json", destination / "validation_report.json")
    _copy_if_exists(run_dir / "manifest.json", destination / "manifest.json")
    _copy_if_exists(run_dir / "data_card.json", destination / "data_card.json")

    agents_dir = run_dir / "agents"
    if agents_dir.exists():
        target_agents_dir = destination / "agents"
        target_agents_dir.mkdir(parents=True, exist_ok=True)
        for artifact_path in agents_dir.glob("*.json"):
            _copy_if_exists(artifact_path, target_agents_dir / artifact_path.name)

    summary = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "local_run_dir": str(run_dir),
        "central_run_dir": str(destination),
        "manifest": _jsonable(manifest),
    }
    if extra:
        summary["extra"] = _jsonable(extra)
    (destination / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    index_path = destination.parent / "index.jsonl"
    index_record = {
        "run_id": run_id,
        "timestamp": summary["timestamp"],
        "local_run_dir": str(run_dir),
        "central_run_dir": str(destination),
        "dataset_path": str(manifest.request.dataset_path),  # type: ignore[attr-defined]
        "spec": str(manifest.request.spec),  # type: ignore[attr-defined]
        "offline": bool(manifest.offline),  # type: ignore[attr-defined]
        "model": getattr(manifest, "model", None),
        "notebook_executed": bool(getattr(manifest, "notebook_executed", False)),
    }
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(index_record, default=str) + "\n")
