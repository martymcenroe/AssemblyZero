"""Implementation code generation package.

Split from implement_code.py (1814 lines) into focused modules.
Re-exports all public names for backward compatibility.
"""

# --- parsers.py ---
from .parsers import (
    apply_diff_changes,
    detect_summary_response,
    detect_truncation,
    extract_code_block,
    parse_diff_response,
    validate_code_response,
    _normalize_whitespace,
)

# --- context.py ---
from .context import (
    LARGE_FILE_BYTE_THRESHOLD,
    LARGE_FILE_LINE_THRESHOLD,
    estimate_context_tokens,
    is_large_file,
    select_generation_strategy,
    summarize_file_for_context,
    _summarize_class,
    _summarize_function,
)

# --- prompts.py ---
from .prompts import (
    MAX_FILE_RETRIES,
    build_diff_prompt,
    build_retry_prompt,
    build_single_file_prompt,
    build_stable_system_prompt,
)

# --- claude_client.py ---
from .claude_client import (
    CLI_TIMEOUT,
    SDK_TIMEOUT,
    ImplementationError,
    ProgressReporter,
    build_system_prompt,
    call_claude_for_file,
    compute_dynamic_timeout,
    _find_claude_cli,
)

# --- orchestrator.py ---
from .orchestrator import (
    CODE_GEN_PROMPT_CAP,
    generate_file_with_retry,
    implement_code,
    validate_files_to_modify,
    _mock_implement_code,
)

# --- routing.py ---
from .routing import (
    select_model_for_file,
    HAIKU_MODEL,
    SMALL_FILE_LINE_THRESHOLD,
)

# --- deprecated.py ---
from .deprecated import (
    build_implementation_prompt,
    call_claude_headless,
    parse_implementation_response,
    write_implementation_files,
)

__all__ = [
    # parsers
    "apply_diff_changes",
    "detect_summary_response",
    "detect_truncation",
    "extract_code_block",
    "parse_diff_response",
    "validate_code_response",
    "_normalize_whitespace",
    # context
    "LARGE_FILE_BYTE_THRESHOLD",
    "LARGE_FILE_LINE_THRESHOLD",
    "estimate_context_tokens",
    "is_large_file",
    "select_generation_strategy",
    "summarize_file_for_context",
    "_summarize_class",
    "_summarize_function",
    # prompts
    "MAX_FILE_RETRIES",
    "build_diff_prompt",
    "build_retry_prompt",
    "build_single_file_prompt",
    "build_stable_system_prompt",
    # claude_client
    "CLI_TIMEOUT",
    "SDK_TIMEOUT",
    "ImplementationError",
    "ProgressReporter",
    "build_system_prompt",
    "call_claude_for_file",
    "compute_dynamic_timeout",
    "_find_claude_cli",
    # orchestrator
    "CODE_GEN_PROMPT_CAP",
    "generate_file_with_retry",
    "implement_code",
    "validate_files_to_modify",
    "_mock_implement_code",
    # routing
    "select_model_for_file",
    "HAIKU_MODEL",
    "SMALL_FILE_LINE_THRESHOLD",
    # deprecated
    "build_implementation_prompt",
    "call_claude_headless",
    "parse_implementation_response",
    "write_implementation_files",
]