from pathlib import Path

from applesauce.cli import main
from applesauce.eval import run_eval


def test_eval_command_writes_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPLESAUCE_RUN_HISTORY_DIR", str(tmp_path / "history"))
    exit_code = main(["eval", "--out", str(tmp_path)])

    assert exit_code == 0
    report_path = tmp_path / "eval_report.json"
    assert report_path.exists()
    assert "passed" in report_path.read_text(encoding="utf-8")


def test_eval_include_large_checks_large_notebook_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPLESAUCE_RUN_HISTORY_DIR", str(tmp_path / "history"))
    report = run_eval(tmp_path, include_large=True)

    assert report["passed"] == report["total"]
    large_run = next(run for run in report["runs"] if run["name"] == "large")
    check_names = {check["name"] for check in large_run["checks"]}
    assert "large_run_skips_autoexecution" in check_names
    assert "large_notebook_stays_small" in check_names
