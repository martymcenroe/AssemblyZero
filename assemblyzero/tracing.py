"""LangSmith tracing configuration for all workflows.

Issue #120: Configure LangSmith project for tracing.

Tracing is enabled when LANGSMITH_API_KEY is set in the environment.
When enabled, all LangGraph workflows send traces to the "AssemblyZero"
project in LangSmith.

To enable: set LANGSMITH_API_KEY in your environment.
To disable: unset LANGSMITH_API_KEY (or don't set it).
"""

import os


DEFAULT_PROJECT = "AssemblyZero"


def configure_langsmith(project_name: str = DEFAULT_PROJECT) -> bool:
    """Configure LangSmith tracing if API key is available.

    Sets LANGCHAIN_TRACING_V2 and LANGCHAIN_PROJECT environment variables
    when LANGSMITH_API_KEY is present. Does nothing if the key is missing.

    Args:
        project_name: LangSmith project name (default: "AssemblyZero").

    Returns:
        True if tracing was enabled, False otherwise.
    """
    api_key = os.environ.get("LANGSMITH_API_KEY", "")
    if not api_key:
        # No key — disable tracing to avoid auth errors
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return False

    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = project_name
    return True
