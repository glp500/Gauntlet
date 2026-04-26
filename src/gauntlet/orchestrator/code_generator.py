"""Generate and validate the fixed sandbox code bundle."""

from __future__ import annotations

import json
from typing import Any


ALLOWED_GENERATED_FILES = (
    "data_loader.py",
    "preprocessing.py",
    "analysis.py",
    "figures.py",
)
_REQUIRED_FUNCTION_NAMES = {
    "data_loader.py": "load_data",
    "preprocessing.py": "preprocess",
    "analysis.py": "run_analysis",
    "figures.py": "create_figures",
}
_FILE_ROLE_CONTRACTS = {
    "data_loader.py": (
        "Load CSV-like inputs from the provided input directory and return "
        "`dict[str, pd.DataFrame]`. This file is the only place that should touch input paths."
    ),
    "preprocessing.py": (
        "Transform the provided `data` dictionary and return another "
        "`dict[str, pd.DataFrame]`. Do not load files, run analysis, or create plots."
    ),
    "analysis.py": (
        "Consume the preprocessed `data` dictionary and return "
        "`dict[str, pd.DataFrame]` analysis results. Do not load files, do not call plotting, "
        "and do not orchestrate the other generated modules."
    ),
    "figures.py": (
        "Consume `data`, `results`, and `output_dir`, save figure files into the provided output "
        "directory, and return `list[str]` paths. Do not load files or run the pipeline."
    ),
}
_GLOBAL_NEGATIVE_RULES = [
    "Do not import data_loader, preprocessing, analysis, or figures.",
    "Do not add `if __name__ == \"__main__\"` blocks.",
    "Do not add print-driven pipeline orchestration.",
    "Do not include example code, demo code, or test code in the file.",
    "Do not use `plt.show()`.",
]
_FILE_SPECIFIC_NEGATIVE_RULES = {
    "data_loader.py": [
        "Do not preprocess data, run analysis, or create figures here.",
    ],
    "preprocessing.py": [
        "Do not read from file paths or touch the output directory here.",
    ],
    "analysis.py": [
        "Do not accept file paths as the main analysis input.",
        "Do not call `load_data`, `preprocess`, or `create_figures` here.",
        "Do not reference sibling generated modules here.",
    ],
    "figures.py": [
        "Do not call `run_analysis` or orchestrate the pipeline here.",
        "Close figures after saving them.",
    ],
}


def build_codegen_prompts(
    analysis_brief: str,
    *,
    prior_bundle: dict[str, str] | None = None,
    repair_brief: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build the prompts that request the constrained code bundle."""
    system_prompt = (
        "You write readable Python analysis code for a constrained local sandbox. "
        "Return one JSON object only, with exactly these keys: "
        "data_loader.py, preprocessing.py, analysis.py, figures.py. "
        "Each value must be the full file contents as a string. "
        "Do not include markdown fences, commentary, or extra keys. "
        "Each file must expose the exact required public function name for its role."
    )

    repair_section = ""
    if prior_bundle is not None and repair_brief is not None:
        repair_section = (
            "\nRepair mode:\n"
            "You are repairing a previously generated bundle. Keep compliant code stable and "
            "fix only the concrete issues listed below.\n\n"
            "Repair brief JSON:\n"
            f"{json.dumps(repair_brief, indent=2)}\n\n"
            "Previous bundle JSON:\n"
            f"{json.dumps(prior_bundle, indent=2)}\n"
        )

    user_prompt = (
        "Generate the sandbox code bundle described by the analysis brief below.\n\n"
        f"{analysis_brief}\n\n"
        "Hard rules:\n"
        "- data_loader.py must define `load_data(input_dir: str) -> dict[str, pd.DataFrame]`.\n"
        "- preprocessing.py must define `preprocess(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]`.\n"
        "- analysis.py must define `run_analysis(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]`.\n"
        "- figures.py must define `create_figures(data: dict[str, pd.DataFrame], results: dict[str, pd.DataFrame], output_dir: str) -> list[str]`.\n"
        "- The runtime imports those exact function names, so do not rename them.\n"
        "- Use pandas and matplotlib.\n"
        "- Keep code explicit and readable.\n"
        "- Add comments only where logic is not obvious.\n"
        + repair_section
    )
    return system_prompt, user_prompt


def build_single_file_codegen_prompts(
    analysis_brief: str,
    *,
    file_name: str,
    generated_so_far: dict[str, str],
    prior_bundle: dict[str, str] | None = None,
    repair_brief: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build a smaller prompt that generates one file at a time."""
    required_function_name = _REQUIRED_FUNCTION_NAMES[file_name]

    system_prompt = (
        "You write exactly one readable Python file for a constrained local sandbox. "
        f"Return only the full contents of {file_name}. "
        "Do not return JSON, markdown fences, or commentary. "
        f"The file must expose the required public function `{required_function_name}`."
    )

    repair_section = ""
    if repair_brief is not None:
        repair_section = _build_file_repair_section(file_name, repair_brief)

    previous_file_section = ""
    if prior_bundle is not None and file_name in prior_bundle:
        previous_file_section = (
            f"\nPrevious version of {file_name}:\n"
            f"{prior_bundle[file_name]}\n"
        )

    existing_files_section = _build_generated_context_section(file_name, generated_so_far)
    negative_rules = _GLOBAL_NEGATIVE_RULES + _FILE_SPECIFIC_NEGATIVE_RULES[file_name]
    negative_rules_section = "\n".join(f"- {rule}" for rule in negative_rules)

    user_prompt = (
        f"Generate only {file_name} for the sandbox bundle described below.\n\n"
        f"{analysis_brief}\n\n"
        f"Role contract for {file_name}:\n"
        f"- Required public function: `{required_function_name}`.\n"
        f"- {_FILE_ROLE_CONTRACTS[file_name]}\n\n"
        "Bundle rules:\n"
        "- The final bundle must contain exactly data_loader.py, preprocessing.py, analysis.py, and figures.py.\n"
        "- Use only pandas, matplotlib, and the Python standard library.\n"
        "- Keep code explicit and readable.\n"
        "- Add comments only where logic is not obvious.\n"
        "- No network access.\n"
        "- No shell commands.\n"
        "- Do not write files outside the provided output directory.\n\n"
        "Negative rules:\n"
        f"{negative_rules_section}\n"
        + existing_files_section
        + repair_section
        + previous_file_section
    )
    return system_prompt, user_prompt


def parse_generated_bundle(response_text: str) -> dict[str, str]:
    """Parse the model response and enforce the exact file contract."""
    payload = _strip_markdown_fence(response_text)
    data = json.loads(payload)

    if not isinstance(data, dict):
        raise ValueError("Generated code response must be a JSON object.")

    actual_keys = set(data.keys())
    expected_keys = set(ALLOWED_GENERATED_FILES)

    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ValueError(
            f"Generated bundle keys must match the allowed file set. Missing={missing}, extra={extra}"
        )

    bundle: dict[str, str] = {}
    for file_name in ALLOWED_GENERATED_FILES:
        file_content = data[file_name]
        if not isinstance(file_content, str) or not file_content.strip():
            raise ValueError(f"Generated file {file_name} must contain non-empty text.")
        bundle[file_name] = file_content

    return bundle


def parse_generated_file(response_text: str) -> str:
    """Parse one generated file and enforce that it contains code text."""
    payload = _strip_markdown_fence(response_text).strip()
    if not payload:
        raise ValueError("Generated file response must contain non-empty text.")

    return payload


def _strip_markdown_fence(text: str) -> str:
    """Remove a single outer JSON code fence when a model adds one."""
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _build_generated_context_section(
    file_name: str,
    generated_so_far: dict[str, str],
) -> str:
    """Summarize already-generated files without pasting their full broken contents."""
    if not generated_so_far:
        return ""

    lines = ["", "Files already generated for this attempt:", ""]
    for existing_file_name in generated_so_far:
        if existing_file_name == file_name:
            continue
        lines.append(
            f"- {existing_file_name}: function `{_REQUIRED_FUNCTION_NAMES[existing_file_name]}`. "
            f"{_FILE_ROLE_CONTRACTS[existing_file_name]}"
        )
    lines.append("")
    return "\n".join(lines)


def _build_file_repair_section(file_name: str, repair_brief: dict[str, Any]) -> str:
    """Render only the repair details that matter for the current file."""
    file_issues = repair_brief.get("file_issues", {})
    current_file_issues = file_issues.get(file_name, [])
    file_guidance = repair_brief.get("file_guidance", {})
    current_guidance = file_guidance.get(file_name, [])

    shared_lines = [
        "",
        "Repair guidance for this file:",
        f"- Prior failure stage: {repair_brief.get('failure_stage', 'unknown')}.",
    ]

    if current_file_issues:
        shared_lines.append("- Fix these concrete issues from the previous attempt:")
        shared_lines.extend(f"  - {issue}" for issue in current_file_issues)

    if current_guidance:
        shared_lines.append("- Follow this targeted guidance:")
        shared_lines.extend(f"  - {item}" for item in current_guidance)

    general_issues = repair_brief.get("issues", [])
    if general_issues and not current_file_issues:
        shared_lines.append("- Previous attempt issues:")
        shared_lines.extend(f"  - {issue}" for issue in general_issues)

    shared_lines.append("")
    return "\n".join(shared_lines)
