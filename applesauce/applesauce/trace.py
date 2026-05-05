from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid
from typing import Any, Iterator

from pydantic import BaseModel


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


class RunTracer:
    def __init__(self, path: Path, *, enabled: bool = True) -> None:
        self.path = path
        self.enabled = enabled
        self.run_id = uuid.uuid4().hex
        self.mirror_paths: list[Path] = []
        if self.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def add_mirror(self, path: Path) -> None:
        if not self.enabled:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        existing_trace = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        path.write_text(existing_trace, encoding="utf-8")
        self.mirror_paths.append(path)

    def event(self, stage: str, event: str, **payload: Any) -> None:
        if not self.enabled:
            return
        record = {
            "run_id": self.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "event": event,
            "payload": _jsonable(payload),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            line = json.dumps(record, default=str) + "\n"
            handle.write(line)
        for mirror_path in self.mirror_paths:
            with mirror_path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    @contextmanager
    def stage(self, stage: str, **payload: Any) -> Iterator[None]:
        start = time.perf_counter()
        self.event(stage, "start", **payload)
        try:
            yield
        except Exception as exc:
            self.event(
                stage,
                "error",
                error_type=type(exc).__name__,
                message=str(exc),
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            raise
        self.event(stage, "end", duration_ms=round((time.perf_counter() - start) * 1000, 2))
