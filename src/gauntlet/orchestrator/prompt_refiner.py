"""Turn raw task input and CSV metadata into a structured analysis brief."""

from __future__ import annotations

import json

from gauntlet.io.input_loader import InputManifest


def build_refinement_prompts(manifest: InputManifest) -> tuple[str, str]:
    """Build the system and user prompts for brief refinement."""
    system_prompt = (
        "You are refining a CSV analysis request into a structured brief for a "
        "local code generation pipeline. Be concrete, cautious, and concise. "
        "Do not invent columns that are not visible in the manifest. "
        "Output markdown with the exact headings: "
        "'Task Objective', 'Input Dataset Summary', 'Assumptions From Schema', "
        "'Required Outputs', and 'Code Constraints'."
    )

    user_prompt = (
        "Turn the raw task and dataset manifest below into the structured brief.\n\n"
        f"Raw task:\n{manifest.task_text}\n\n"
        "Dataset manifest JSON:\n"
        f"{json.dumps(manifest.to_dict(), indent=2)}\n\n"
        "Code constraints:\n"
        "- Generated code may only implement data_loader.py, preprocessing.py, "
        "analysis.py, and figures.py.\n"
        "- Use pandas and matplotlib only.\n"
        "- No network access.\n"
        "- No shell commands.\n"
        "- Keep logic explicit and readable.\n"
    )
    return system_prompt, user_prompt
