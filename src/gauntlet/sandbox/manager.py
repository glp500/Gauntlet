"""Create the per-run workspace and copy controlled files into it."""

from __future__ import annotations

import shutil

from gauntlet.config import Settings
from gauntlet.run_context import RunContext


def prepare_sandbox(
    context: RunContext,
    settings: Settings,
    generated_files: dict[str, str],
    *,
    attempt_number: int | None = None,
) -> None:
    """Copy the runtime template, inputs, and generated bundle into the run sandbox."""
    if not settings.sandbox_template_dir.exists():
        raise FileNotFoundError(
            f"Sandbox template folder does not exist: {settings.sandbox_template_dir}"
        )

    shutil.copytree(
        settings.sandbox_template_dir,
        context.sandbox_dir,
        dirs_exist_ok=True,
    )

    sandbox_input_dir = context.sandbox_dir / "inputs" / "data"
    sandbox_input_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(settings.input_task_path, context.sandbox_dir / "inputs" / "input.txt")

    for csv_path in sorted(settings.input_data_dir.glob("*.csv")):
        shutil.copy2(csv_path, sandbox_input_dir / csv_path.name)

    for file_name, content in generated_files.items():
        (context.sandbox_dir / file_name).write_text(content, encoding="utf-8")

    context.record_step(
        "prepare_sandbox",
        status="completed",
        attempt_number=attempt_number,
        details={"sandbox_dir": str(context.sandbox_dir)},
    )
