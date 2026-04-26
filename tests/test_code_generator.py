"""Prompt and parser regressions for local code generation contracts."""

from __future__ import annotations

import json

import pytest

from gauntlet.orchestrator.code_generator import (
    build_bundle_contract_prompts,
    parse_bundle_contract,
)


def test_build_bundle_contract_prompts_forbid_column_names() -> None:
    """The contract prompt should steer local models toward bundle keys, not schema columns."""
    _, user_prompt = build_bundle_contract_prompts(
        "Analyze the dataset and create one figure.",
    )

    assert "whole-table keys such as `sales_data`, `monthly_sales`, or `supplier_summary`" in user_prompt
    assert "Do not use CSV schema columns such as `YEAR`, `MONTH`, or `RETAIL SALES`" in user_prompt
    assert "Every non-figure contract name must be lowercase snake_case." in user_prompt


def test_parse_bundle_contract_rejects_column_style_keys() -> None:
    """Column names are not valid bundle keys for local file coordination."""
    response_text = json.dumps(
        {
            "loaded_keys": ["YEAR", "MONTH", "RETAIL SALES"],
            "processed_keys": ["YEAR", "MONTH", "RETAIL SALES"],
            "result_table_names": ["sales_summary"],
            "figure_file_names": ["sales_summary.png"],
        }
    )

    with pytest.raises(ValueError, match="lowercase snake_case names"):
        parse_bundle_contract(response_text)


def test_parse_bundle_contract_accepts_small_snake_case_contract() -> None:
    """A compact snake_case contract should pass unchanged."""
    response_text = json.dumps(
        {
            "loaded_keys": ["sales_data"],
            "processed_keys": ["monthly_sales"],
            "result_table_names": ["sales_summary"],
            "figure_file_names": ["sales_summary.png"],
        }
    )

    contract = parse_bundle_contract(response_text)

    assert contract == {
        "loaded_keys": ["sales_data"],
        "processed_keys": ["monthly_sales"],
        "result_table_names": ["sales_summary"],
        "figure_file_names": ["sales_summary.png"],
    }
