"""N4: Implement Code node for TDD Testing Workflow.

This module is a backward-compatibility shim. The implementation has been
split into focused modules under the `implementation/` package.

All public names are re-exported here so existing imports continue to work:
    from assemblyzero.workflows.testing.nodes.implement_code import implement_code
"""

from assemblyzero.workflows.testing.nodes.implementation import *  # noqa: F401, F403
from assemblyzero.workflows.testing.nodes.implementation import (  # noqa: F811
    implement_code,
    extract_code_block,
    validate_code_response,
    call_claude_for_file,
    select_model_for_file,
    ProgressReporter,
    ImplementationError,
    build_single_file_prompt,
    build_system_prompt,
    build_retry_prompt,
    build_diff_prompt,
    generate_file_with_retry,
    validate_files_to_modify,
    estimate_context_tokens,
    summarize_file_for_context,
    detect_summary_response,
    detect_truncation,
    compute_dynamic_timeout,
    is_large_file,
    select_generation_strategy,
    parse_diff_response,
    apply_diff_changes,
    build_implementation_prompt,
    parse_implementation_response,
    write_implementation_files,
    call_claude_headless,
    _mock_implement_code,
    _normalize_whitespace,
    _summarize_class,
    _summarize_function,
    MAX_FILE_RETRIES,
    CLI_TIMEOUT,
    LARGE_FILE_LINE_THRESHOLD,
    LARGE_FILE_BYTE_THRESHOLD,
    CODE_GEN_PROMPT_CAP,
    HAIKU_MODEL,
    SMALL_FILE_LINE_THRESHOLD,
)