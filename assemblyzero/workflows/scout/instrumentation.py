"""Tracing and instrumentation for Scout workflow.

Configures LangSmith/file logging for observability.
"""

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def setup_tracing(
    project_name: str = "scout-workflow",
    enable_langsmith: bool = True,
    log_to_file: bool = True,
    log_dir: Path | None = None,
) -> dict[str, Any]:
    """Configure tracing for the Scout workflow.

    Args:
        project_name: LangSmith project name.
        enable_langsmith: Whether to enable LangSmith tracing.
        log_to_file: Whether to log to local file.
        log_dir: Directory for log files.

    Returns:
        Configuration dict with callbacks and settings.
    """
    callbacks = []
    config = {
        "project_name": project_name,
        "langsmith_enabled": False,
        "file_logging_enabled": False,
        "callbacks": callbacks,
    }

    # LangSmith setup
    if enable_langsmith:
        langsmith_key = os.environ.get("LANGSMITH_API_KEY")
        if langsmith_key:
            try:
                os.environ["LANGCHAIN_TRACING_V2"] = "true"
                os.environ["LANGCHAIN_PROJECT"] = project_name
                config["langsmith_enabled"] = True
                logger.info(f"LangSmith tracing enabled for project: {project_name}")
            except Exception as e:
                logger.warning(f"Failed to enable LangSmith: {e}")
        else:
            logger.debug("LangSmith API key not found, skipping LangSmith setup")

    # File logging setup
    if log_to_file:
        if log_dir is None:
            log_dir = Path.home() / ".assemblyzero" / "logs" / "scout"

        log_dir.mkdir(parents=True, exist_ok=True)

        # Configure file handler
        file_handler = logging.FileHandler(
            log_dir / "scout-workflow.log",
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

        # Add to root logger for this module
        logging.getLogger("assemblyzero.workflows.scout").addHandler(file_handler)
        config["file_logging_enabled"] = True
        config["log_file"] = str(log_dir / "scout-workflow.log")

        logger.info(f"File logging enabled: {config['log_file']}")

    return config


def log_node_execution(
    node_name: str,
    input_state: dict[str, Any],
    output_state: dict[str, Any],
    duration_ms: float,
) -> None:
    """Log node execution for debugging.

    Args:
        node_name: Name of the executed node.
        input_state: State before execution.
        output_state: State after execution.
        duration_ms: Execution duration in milliseconds.
    """
    logger.info(
        f"Node '{node_name}' executed in {duration_ms:.2f}ms "
        f"(input keys: {list(input_state.keys())}, "
        f"output keys: {list(output_state.keys())})"
    )

    # Log any errors
    if output_state.get("errors"):
        logger.error(f"Node '{node_name}' errors: {output_state['errors']}")


def log_api_call(
    service: str,
    operation: str,
    duration_ms: float,
    success: bool,
    details: dict[str, Any] | None = None,
) -> None:
    """Log external API calls.

    Args:
        service: Service name (e.g., "github", "gemini").
        operation: Operation performed.
        duration_ms: Call duration in milliseconds.
        success: Whether the call succeeded.
        details: Optional additional details.
    """
    status = "SUCCESS" if success else "FAILED"
    logger.info(
        f"API Call [{service}] {operation}: {status} ({duration_ms:.2f}ms)"
    )
    if details:
        logger.debug(f"API Call details: {details}")
