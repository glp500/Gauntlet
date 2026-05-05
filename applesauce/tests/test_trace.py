from pathlib import Path

import pytest

from applesauce.trace import RunTracer


def test_trace_mirror_receives_failure_events(tmp_path: Path) -> None:
    trace_path = tmp_path / "local" / "trace.jsonl"
    mirror_path = tmp_path / "history" / "trace.jsonl"
    tracer = RunTracer(trace_path)
    tracer.add_mirror(mirror_path)

    with pytest.raises(RuntimeError):
        with tracer.stage("boom"):
            raise RuntimeError("synthetic failure")

    local_lines = trace_path.read_text(encoding="utf-8").splitlines()
    mirror_lines = mirror_path.read_text(encoding="utf-8").splitlines()

    assert mirror_lines == local_lines
    assert any('"event": "error"' in line for line in mirror_lines)
