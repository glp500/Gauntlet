"""Tests for CLI model-profile overrides."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


_START_PATH = Path(__file__).resolve().parents[1] / "start.py"
_START_SPEC = importlib.util.spec_from_file_location("proto_gauntlet_start", _START_PATH)
assert _START_SPEC is not None
assert _START_SPEC.loader is not None
_START_MODULE = importlib.util.module_from_spec(_START_SPEC)
_START_SPEC.loader.exec_module(_START_MODULE)

_apply_cli_overrides = _START_MODULE._apply_cli_overrides
parse_args = _START_MODULE.parse_args


def test_parse_args_accepts_large_local_model_flag() -> None:
    """The CLI should accept the one-shot larger local model override."""
    args = parse_args(["--large-local-model"])

    assert args.large_local_model is True


def test_apply_cli_overrides_sets_default_ollama_model(monkeypatch) -> None:
    """The CLI should default local runs to the smaller Gemma profile."""
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    _apply_cli_overrides(argparse.Namespace(large_local_model=False))

    assert "OLLAMA_MODEL" in __import__("os").environ
    assert __import__("os").environ["OLLAMA_MODEL"] == "gemma4:e2b"


def test_apply_cli_overrides_sets_large_ollama_model(monkeypatch) -> None:
    """The CLI should switch to the larger Gemma profile when requested."""
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:e2b")

    _apply_cli_overrides(argparse.Namespace(large_local_model=True))

    assert __import__("os").environ["OLLAMA_MODEL"] == "gemma4:26b"
