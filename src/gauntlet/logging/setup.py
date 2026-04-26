"""Configure readable file-backed logging for each run."""

from __future__ import annotations

import logging
from pathlib import Path

from gauntlet.run_context import RunContext


def _build_file_handler(path: Path) -> logging.FileHandler:
    """Create one UTF-8 file handler with a shared format."""
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    return handler


def _reset_logger(logger: logging.Logger, level: int) -> None:
    """Clear old handlers so repeated test runs stay readable."""
    logger.setLevel(level)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def configure_run_logging(context: RunContext) -> tuple[logging.Logger, logging.Logger]:
    """Return the pipeline and execution loggers for one run."""
    pipeline_logger = logging.getLogger("gauntlet.pipeline")
    execution_logger = logging.getLogger("gauntlet.execution")

    _reset_logger(pipeline_logger, logging.INFO)
    _reset_logger(execution_logger, logging.INFO)

    pipeline_logger.addHandler(_build_file_handler(context.logs_dir / "pipeline.log"))
    execution_logger.addHandler(_build_file_handler(context.logs_dir / "execution.log"))

    return pipeline_logger, execution_logger
