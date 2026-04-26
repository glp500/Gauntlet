"""Review generated files before execution."""

from __future__ import annotations

import json


def build_review_prompts(
    code_bundle: dict[str, str],
    bundle_contract: dict[str, list[str]] | None = None,
) -> tuple[str, str]:
    """Build prompts that validate the generated bundle."""
    system_prompt = (
        "You review a constrained Python analysis bundle. "
        "Return JSON only with keys: status, summary, issues. "
        "status must be either 'approved' or 'blocked'. "
        "issues must be a list of objects with keys: category, message, blocking. "
        "Allowed categories are contract, dependency, sandbox, readability, other."
    )

    rendered_files = []
    for file_name, content in code_bundle.items():
        rendered_files.append(f"File: {file_name}\n{content}")

    contract_section = ""
    if bundle_contract is not None:
        contract_section = (
            "\nShared bundle contract:\n"
            f"{json.dumps(bundle_contract, indent=2)}\n"
        )

    user_prompt = (
        "Review the generated bundle for the following rules:\n"
        "- Only the expected file roles are present.\n"
        "- Required public functions exist with the exact names: load_data, preprocess, run_analysis, create_figures.\n"
        "- Dictionary keys passed from load_data to preprocess to run_analysis to create_figures stay consistent.\n"
        "- run_analysis returns only pandas DataFrames and does not mix in text or scalar values.\n"
        "- The bundle appears likely to write at least one result table and at least one figure for this task.\n"
        "- Code is readable and explicit.\n"
        "- Dependencies stay within pandas, matplotlib, and the standard library.\n"
        "- No network access or shell execution.\n"
        "- No hidden writes outside provided output paths.\n\n"
        + contract_section
        + "\n\n".join(rendered_files)
    )
    return system_prompt, user_prompt


def parse_review_response(response_text: str) -> dict[str, object]:
    """Parse and validate the review response."""
    payload = json.loads(response_text.strip())
    status = payload.get("status")
    issues = payload.get("issues", [])

    if status not in {"approved", "blocked"}:
        raise ValueError("Review response must include status='approved' or 'blocked'.")

    if not isinstance(issues, list):
        raise ValueError("Review response must include a list of issues.")

    summary = payload.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("Review response summary must be a string.")

    normalized_issues: list[dict[str, object]] = []
    for item in issues:
        if isinstance(item, str):
            normalized_issues.append(
                {
                    "category": "other",
                    "message": item,
                    "blocking": status == "blocked",
                }
            )
            continue

        if not isinstance(item, dict):
            raise ValueError("Each review issue must be either a string or an object.")

        category = item.get("category", "other")
        message = item.get("message")
        blocking = item.get("blocking", status == "blocked")

        if not isinstance(category, str):
            raise ValueError("Review issue category must be a string.")

        if not isinstance(message, str):
            raise ValueError("Review issue message must be a string.")

        if not isinstance(blocking, bool):
            raise ValueError("Review issue blocking flag must be a boolean.")

        normalized_issues.append(
            {
                "category": category.strip().lower() or "other",
                "message": message,
                "blocking": blocking,
            }
        )

    return {
        "status": status,
        "summary": summary,
        "issues": normalized_issues,
    }
