"""Write one summary artifact per run."""

from __future__ import annotations

import json
from typing import Any

from gauntlet.run_context import RunContext


def write_summary(context: RunContext, summary: dict[str, Any]) -> None:
    """Persist the run summary in the outputs folder."""
    context.summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
