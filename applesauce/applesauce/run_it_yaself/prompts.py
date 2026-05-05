from __future__ import annotations

import json
from typing import Any


SMALL_MODEL_SYSTEM_PROMPT = (
    "You are a careful assistant working inside 'Run it yaself' mode for a local model. "
    "Be conservative. Prefer choosing from provided options instead of inventing new structure. "
    "If the options are weak or the evidence is thin, abstain instead of guessing. "
    "Return valid JSON only."
)


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def question_selection_prompt(*, spec: str, card_summary: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    return (
        "Choose the most useful analysis questions for this dataset.\n"
        "Select 3 to 5 question ids. Prefer questions that are directly supported by the columns.\n"
        "Abstain if the candidate list does not match the dataset.\n\n"
        f"User spec: {spec}\n"
        f"Dataset summary: {compact_json(card_summary)}\n"
        f"Question candidates: {compact_json(candidates)}"
    )


def theme_selection_prompt(*, spec: str, plan_summary: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    return (
        "Choose one notebook theme from the provided candidates.\n"
        "Prefer calm or technical styles unless the user clearly wants something more playful.\n"
        "Abstain if no theme fits.\n\n"
        f"User spec: {spec}\n"
        f"Analysis summary: {compact_json(plan_summary)}\n"
        f"Theme candidates: {compact_json(candidates)}"
    )


def chart_selection_prompt(*, spec: str, card_summary: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    return (
        "Choose 3 to 5 chart ids from the vetted chart candidates.\n"
        "Rules:\n"
        "- Prefer charts with different insights, not minor variations.\n"
        "- Avoid illegible high-cardinality views.\n"
        "- Prefer focused comparisons over giant category dumps.\n"
        "- Abstain if all options are poor.\n\n"
        f"User spec: {spec}\n"
        f"Dataset summary: {compact_json(card_summary)}\n"
        f"Chart candidates: {compact_json(candidates)}"
    )


def layout_selection_prompt(*, spec: str, chart_candidates: list[dict[str, Any]]) -> str:
    return (
        "Order the chosen charts for a readable notebook story.\n"
        "Return the ordered chart ids only. Start with broad overview charts, then comparisons, then relationships.\n"
        "Abstain if the order is unclear.\n\n"
        f"User spec: {spec}\n"
        f"Chosen charts: {compact_json(chart_candidates)}"
    )


def title_polish_prompt(*, chart_summary: dict[str, Any]) -> str:
    return (
        "Polish this chart title if needed. Keep it short, literal, and faithful to the actual plotted fields.\n"
        "If the title is already good, abstain.\n\n"
        f"Chart summary: {compact_json(chart_summary)}"
    )


def repair_prompt(*, stage: str, schema: dict[str, Any], previous_output: str, validation_error: str) -> str:
    return (
        f"Your previous JSON for stage '{stage}' was invalid.\n"
        "Return corrected JSON only.\n\n"
        f"Required schema: {compact_json(schema)}\n"
        f"Validation error: {validation_error}\n"
        f"Previous output: {previous_output}"
    )
