"""Tests for generated bundle policy checks."""

from __future__ import annotations

import pytest

from gauntlet.sandbox.file_policy import (
    validate_generated_bundle,
    validate_runtime_contract,
)


def _valid_bundle() -> dict[str, str]:
    return {
        "data_loader.py": "import pandas as pd\n\ndef load_data(input_dir: str) -> dict[str, pd.DataFrame]:\n    return {}\n",
        "preprocessing.py": "def preprocess(data: dict[str, object]) -> dict[str, object]:\n    return data\n",
        "analysis.py": "import pandas as pd\n\ndef run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n    return {}\n",
        "figures.py": "def create_figures(data, results, output_dir: str) -> list[str]:\n    return []\n",
    }


def test_validate_generated_bundle_accepts_simple_valid_bundle() -> None:
    """The basic four-file contract should pass policy validation."""
    validate_generated_bundle(_valid_bundle())


def test_validate_generated_bundle_rejects_forbidden_import() -> None:
    """Network-capable dependencies should be blocked."""
    bundle = _valid_bundle()
    bundle["analysis.py"] = "import requests\n\ndef run_analysis(data):\n    return {}\n"

    with pytest.raises(ValueError, match="banned import"):
        validate_generated_bundle(bundle)


def test_validate_generated_bundle_rejects_extra_file() -> None:
    """Only the fixed generated file set is allowed."""
    bundle = _valid_bundle()
    bundle["extra.py"] = "print('nope')\n"

    with pytest.raises(ValueError, match="allowed file set"):
        validate_generated_bundle(bundle)


def test_validate_generated_bundle_rejects_sibling_module_imports() -> None:
    """Generated files must stay isolated instead of importing each other."""
    bundle = _valid_bundle()
    bundle["analysis.py"] = (
        "import pandas as pd\n"
        "import data_loader\n\n"
        "def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
        "    return {}\n"
    )

    with pytest.raises(ValueError, match="sibling generated module import `data_loader` is not allowed"):
        validate_generated_bundle(bundle)


def test_validate_generated_bundle_rejects_analysis_file_loading() -> None:
    """The analysis role must consume in-memory data instead of loading files."""
    bundle = _valid_bundle()
    bundle["analysis.py"] = (
        "import pandas as pd\n\n"
        "def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
        "    other = load_data('sample.csv')\n"
        "    return other\n"
    )

    with pytest.raises(ValueError, match="analysis.py must not load files or call `load_data`"):
        validate_generated_bundle(bundle)


def test_validate_generated_bundle_rejects_figures_show_calls() -> None:
    """Figure generation must save outputs instead of blocking on interactive display."""
    bundle = _valid_bundle()
    bundle["figures.py"] = (
        "import matplotlib.pyplot as plt\n\n"
        "def create_figures(data, results, output_dir: str) -> list[str]:\n"
        "    plt.show()\n"
        "    return []\n"
    )

    with pytest.raises(ValueError, match="figures.py must save figures and return paths instead of calling `plt.show`"):
        validate_generated_bundle(bundle)


def test_validate_generated_bundle_rejects_main_blocks() -> None:
    """Generated modules should expose functions only, not standalone entrypoints."""
    bundle = _valid_bundle()
    bundle["analysis.py"] = (
        "import pandas as pd\n\n"
        "def run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
        "    return {}\n\n"
        "if __name__ == '__main__':\n"
        "    run_analysis({})\n"
    )

    with pytest.raises(ValueError, match="must not contain `if __name__ == \"__main__\"` blocks"):
        validate_generated_bundle(bundle)


def test_validate_generated_bundle_rejects_missing_required_function() -> None:
    """Each generated module must expose the runtime contract function name."""
    bundle = _valid_bundle()
    bundle["analysis.py"] = (
        "import pandas as pd\n\n"
        "def summarize_dataset(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:\n"
        "    return {}\n"
    )

    with pytest.raises(ValueError, match="missing required function `run_analysis`"):
        validate_runtime_contract(bundle)
