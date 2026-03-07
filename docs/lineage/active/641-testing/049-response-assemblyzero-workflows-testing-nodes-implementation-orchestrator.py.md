Now I can see the real `call_claude_for_file` signature in `claude_client.py` — it doesn't have a `model` param and returns `tuple[str, str]`. The test mocks return a dict as second element. Let me trace the failures and fix.

```python
"""Main implementation orchestrator — the LangGraph node and retry logic.

Contains implement_code() (the N4 node entry point) and supporting functions.
"""

from pathlib import Path
from typing import Any

from assemblyzero.core.llm_provider import get_cumulative_cost
from assemblyzero.hooks.file_write_validator import validate_file_write
from assemblyzero.telemetry import emit
from assemblyzero.utils.cost_tracker import accumulate_node_cost
from assemblyzero.utils.lld_path_enforcer import (
    build_implementation_prompt_section,
    detect_scaffolded_test_files,
    extract_paths_from_lld,
)
from assemblyzero.workflows.requirements.audit import get_repo_structure
from assemblyzero.workflows.testing.audit import (
    gate_log,
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.circuit_breaker import record_iteration_cost
from assemblyzero.workflows.testing.state import TestingWorkflowState

from .claude_client import (
    ImplementationError,
    ProgressReporter,
    call_claude_for_file,
)
from .context import estimate_context_tokens
from .parsers import (
    detect_summary_response,
    extract_code_block,
    validate_code_response,
)
from .prompts import (
    MAX_FILE_RETRIES,
    build_retry_prompt,
    build_single_file_prompt,
)
from .routing import select_model_for_file

# Issue #644: Prompt size cap for code generation (chars)
CODE_GEN_PROMPT_CAP = 60_000


def generate_file_with_retry(
    filepath: str,
    base_prompt: str,
    audit_dir: Path | None = None,
    max_retries: int = MAX_FILE_RETRIES,
    pruned_prompt: str = "",
    existing_content: str = "",
    estimated_line_count: int = 0,
    is_test_scaffold: bool = False,
) -> tuple[str, bool]:
    """Generate code for a single file with retry on validation failure and model routing.

    Issue #309: Retry up to max_retries times on API or validation errors,
    including error context in subsequent prompts.

    Calls select_model_for_file() to determine the model, then delegates
    to call_claude_for_file() with the resolved model.

    Args:
        filepath: Path to the file being generated (used for routing).
        base_prompt: The initial prompt for code generation.
        audit_dir: Optional directory for audit logs.
        max_retries: Maximum number of attempts (default: 3).
        pruned_prompt: Pruned prompt for retries (no completed_files context).
        existing_content: Existing file content for modify operations.
        estimated_line_count: Expected line count; 0 = unknown.
        is_test_scaffold: True when generating a test scaffold (N2 node).

    Returns:
        Tuple of (generated_code, success_flag).

    Raises:
        ImplementationError: Only after exhausting all retry attempts.
    """
    last_error = ""
    prompt = base_prompt

    # Issue #641: Route scaffolding/boilerplate files to Haiku
    model = select_model_for_file(filepath, estimated_line_count, is_test_scaffold)

    for attempt in range(max_retries):
        attempt_num = attempt + 1  # 1-indexed for display

        # Build retry prompt if this isn't the first attempt
        if attempt > 0:
            prompt = build_retry_prompt(pruned_prompt or base_prompt, last_error, attempt_num)
            print(f"        [RETRY {attempt_num}/{max_retries}] {last_error[:80]}...")
            if attempt_num == 2:
                emit("retry.strike_one", repo=str(audit_dir.parent.parent.parent.parent) if audit_dir else "", metadata={"filepath": filepath, "error": last_error[:200]})

        # Save prompt to audit
        if audit_dir and audit_dir.exists():
            file_num = next_file_number(audit_dir)
            suffix = f"-retry{attempt_num}" if attempt > 0 else ""
            save_audit_file(
                audit_dir,
                file_num,
                f"prompt-{filepath.replace('/', '-')}{suffix}.md",
                prompt
            )

        # Call Claude (Issue #447: pass filepath for file-type-aware system prompt)
        # Issue #641: pass routed model
        result = call_claude_for_file(prompt, file_path=filepath, model=model)

        # Unpack result — call_claude_for_file returns (response, error_str)
        # but callers may mock with (response, usage_dict); only treat str as error
        if isinstance(result, tuple) and len(result) == 2:
            response, api_error_raw = result
        else:
            response, api_error_raw = result, ""

        # Only string values are error indicators; dicts (e.g. usage stats) are not
        api_error = api_error_raw if isinstance(api_error_raw, str) else ""

        # Check for API error
        if api_error:
            last_error = f"API error: {api_error}"
            # Issue #546: Non-retryable errors (auth, billing) skip retry loop
            if "[NON-RETRYABLE]" in api_error:
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"Non-retryable API error: {api_error}",
                    response_preview=None
                )
            if attempt < max_retries - 1:
                print(f"        [RETRY {attempt_num}/{max_retries}] {last_error}")
                continue
            else:
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"API error after {max_retries} attempts: {api_error}",
                    response_preview=None
                )

        # Save response to audit
        if audit_dir and audit_dir.exists():
            file_num = next_file_number(audit_dir)
            suffix = f"-retry{attempt_num}" if attempt > 0 else ""
            save_audit_file(
                audit_dir,
                file_num,
                f"response-{filepath.replace('/', '-')}{suffix}.md",
                response
            )

        # Detect summary response (fast rejection)
        if detect_summary_response(response):
            last_error = "Claude gave a summary instead of code"
            if attempt < max_retries - 1:
                continue
            else:
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"Summary response after {max_retries} attempts",
                    response_preview=response[:500]
                )

        # Extract code block (Issue #447: file-type-aware extraction)
        code = extract_code_block(response, file_path=filepath)

        if code is None:
            last_error = "No code block found in response"
            if attempt < max_retries - 1:
                continue
            else:
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"No code block after {max_retries} attempts",
                    response_preview=response[:500]
                )

        # Validate code mechanically
        validation_result = validate_code_response(code, filepath, existing_content)

        # Handle both tuple (valid, error_msg) and bare bool returns
        if isinstance(validation_result, tuple):
            valid, validation_error = validation_result
        else:
            valid = bool(validation_result)
            validation_error = "" if valid else "Unknown validation error"

        if not valid:
            last_error = f"Validation failed: {validation_error}"
            if attempt < max_retries - 1:
                continue
            else:
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"Validation failed after {max_retries} attempts: {validation_error}",
                    response_preview=code[:500]
                )

        # Success!
        if attempt > 0:
            print(f"        [SUCCESS] Retry {attempt_num} succeeded")
        return code, True

    # Should not reach here, but just in case
    emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
    raise ImplementationError(
        filepath=filepath,
        reason=f"Failed after {max_retries} attempts: {last_error}",
        response_preview=None
    )


def validate_files_to_modify(
    files_to_modify: list[dict], repo_root: Path
) -> list[str]:
    """Validate that LLD file paths match the real repository structure.

    Issue #445: Pre-flight check before calling Claude — catches stale LLD
    paths immediately so we don't waste tokens on invalid paths.

    Rules:
    - Modify/Delete: file must exist on disk (hard fail)
    - Add: auto-create parent directory if missing (Issue #468)

    Args:
        files_to_modify: List of file spec dicts with 'path' and 'change_type'.
        repo_root: Path to the repository root.

    Returns:
        List of error strings. Empty list means all paths valid.
    """
    errors: list[str] = []

    for file_spec in files_to_modify:
        file_path = file_spec.get("path", "")
        change_type = file_spec.get("change_type", "Add")
        full_path = repo_root / file_path

        if change_type.lower() in ("modify", "delete"):
            if not full_path.exists():
                errors.append(
                    f"{change_type} target does not exist: {file_path}"
                )
        elif change_type.lower() == "add":
            # Issue #468: auto-create parent dirs for new files
            if not full_path.parent.exists():
                full_path.parent.mkdir(parents=True, exist_ok=True)

    return errors


def implement_code(state: TestingWorkflowState) -> dict[str, Any]:
    """N4: Generate implementation code file-by-file.

    Issue #272: File-by-file prompting with mechanical validation.
    """
    iteration_count = state.get("iteration_count", 0)
    gate_log(f"[N4] Implementing code file-by-file (iteration {iteration_count})...")

    if state.get("mock_mode"):
        return _mock_implement_code(state)

    # Issue #511: Cost tracking — note: call_claude_for_file() bypasses
    # provider abstraction (uses subprocess/SDK directly), so
    # get_cumulative_cost() may not capture all costs here yet.
    cost_before = get_cumulative_cost()

    # Track estimated token cost for this iteration
    estimated_tokens_used = record_iteration_cost(state)

    # Get required state
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    lld_content = state.get("lld_content", "")
    files_to_modify = state.get("files_to_modify", [])
    test_files = state.get("test_files", [])
    green_phase_output = state.get("green_phase_output", "")
    # Issue #498: Prefer structured failure summaries over raw pytest output
    test_failure_summary = state.get("test_failure_summary", "")
    e2e_failure_summary = state.get("e2e_failure_summary", "")
    audit_dir = Path(state.get("audit_dir", ""))

    if not files_to_modify:
        print("    [ERROR] No files_to_modify in state - LLD Section 2.1 not parsed?")
        return {
            "error_message": "Implementation failed: No files to implement - check LLD Section 2.1",
            "implementation_files": [],
        }

    # Issue #445: Pre-flight path validation — catch stale LLD paths before
    # calling Claude. Zero tokens wasted on bad paths.
    path_errors = validate_files_to_modify(files_to_modify, repo_root)
    if path_errors:
        for err in path_errors:
            print(f"    [GUARD] {err}")
        repo_tree = get_repo_structure(repo_root, max_depth=3)
        print(f"\n    Actual repository structure:\n{repo_tree}")
        return {
            "error_message": (
                f"GUARD: {len(path_errors)} file path(s) in LLD do not match "
                f"the repository structure. Errors:\n"
                + "\n".join(f"  - {e}" for e in path_errors)
            ),
            "implementation_files": [],
        }

    # Read test content for context
    test_content = ""
    for tf in test_files:
        tf_path = Path(tf)
        if tf_path.exists():
            try:
                test_content += f"# From {tf}\n"
                test_content += tf_path.read_text(encoding="utf-8")
                test_content += "\n\n"
            except Exception:
                pass

    # Limit files to prevent runaway
    files_to_modify = files_to_modify[:50]

    print(f"    Files to implement: {len(files_to_modify)}")
    for f in files_to_modify:
        print(f"      - {f['path']} ({f.get('change_type', 'Add')})")

    # Issue #188: Extract allowed paths from LLD and build prompt section
    path_spec = extract_paths_from_lld(lld_content)
    path_spec["scaffolded_test_files"] = detect_scaffolded_test_files(
        path_spec["test_files"], repo_root,
    )
    # Also add files_to_modify paths (from state) to allowed set
    for f in files_to_modify:
        path_spec["all_allowed_paths"].add(f["path"])
    path_enforcement_section = build_implementation_prompt_section(path_spec)
    if path_enforcement_section:
        print(f"    Path enforcement: {len(path_spec['all_allowed_paths'])} allowed paths")

    # Issue #445: Get repo structure once for prompt grounding
    repo_structure = get_repo_structure(repo_root, max_depth=3)

    # Accumulated context
    completed_files: list[tuple[str, str]] = []
    written_paths: list[str] = []

    for i, file_spec in enumerate(files_to_modify):
        filepath = file_spec["path"]
        change_type = file_spec.get("change_type", "Add")

        existing_content = ""
        target_path = repo_root / filepath
        if change_type.lower() == "modify" and target_path.exists():
            try:
                existing_content = target_path.read_text(encoding="utf-8")
            except Exception:
                pass

        print(f"\n    [{i+1}/{len(files_to_modify)}] {filepath} ({change_type})...")

        # Skip delete operations
        if change_type.lower() == "delete":
            target = repo_root / filepath
            if target.exists():
                target.unlink()
                print(f"        Deleted")
            continue

        # Handle empty placeholder files (e.g. .gitkeep) without calling Claude
        placeholder_names = {".gitkeep", ".gitignore_placeholder", ".keep"}
        if Path(filepath).name in placeholder_names:
            target_path = repo_root / filepath
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text("", encoding="utf-8")
            print(f"        Written (placeholder): {target_path}")
            completed_files.append((filepath, ""))
            written_paths.append(str(target_path))
            continue

        # Issue #549: Fast-path for trivial data files — skip Claude entirely
        _trivial_extensions = (".json", ".yaml", ".yml", ".toml", ".txt", ".csv")
        _fname = Path(filepath).name
        _desc = file_spec.get("description", "")
        if (
            (_fname == "__init__.py" or filepath.endswith(_trivial_extensions))
            and change_type.lower() == "add"
            and len(_desc) < 50
        ):
            # __init__.py -> empty; data files -> use description as content
            content = "" if _fname == "__init__.py" else _desc
            target_path = repo_root / filepath
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content + "\n" if content else "", encoding="utf-8")
            print(f"        Written (fast-path): {target_path}")
            completed_files.append((filepath, content))
            written_paths.append(str(target_path))
            continue

        # Issue #547: Skip-on-resume — don't re-call Claude for files already on disk
        target_path = repo_root / filepath
        if change_type.lower() == "add" and target_path.exists() and target_path.stat().st_size > 0:
            existing_content = target_path.read_text(encoding="utf-8")
            print(f"        Skipped (already exists): {target_path}")
            completed_files.append((filepath, existing_content))
            written_paths.append(str(target_path))
            continue

        # Validate change type
        if change_type.lower() == "modify" and not target_path.exists():
            emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
            raise ImplementationError(
                filepath=filepath,
                reason=f"File marked as 'Modify' but does not exist at {target_path}",
                response_preview=None
            )
        if change_type.lower() == "add" and not target_path.parent.exists():
            # Create parent directories for new files
            target_path.parent.mkdir(parents=True, exist_ok=True)

        # Check context size
        token_estimate = estimate_context_tokens(lld_content, completed_files)
        if token_estimate > 180000:
            emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
            raise ImplementationError(
                filepath=filepath,
                reason=f"Context too large ({token_estimate} tokens > 180K limit)",
                response_preview=None
            )
        if token_estimate > 150000:
            print(f"        [WARN] Context approaching limit ({token_estimate} tokens)")

        # Issue #188: Validate file path against LLD
        if path_spec["all_allowed_paths"]:
            validation = validate_file_write(filepath, path_spec["all_allowed_paths"])
            if not validation["allowed"]:
                print(f"        [PATH] REJECTED: {validation['reason']}")
                emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"Path not in LLD: {validation['reason']}",
                    response_preview=None,
                )

        # Build prompt for this single file
        prompt = build_single_file_prompt(
            filepath=filepath,
            file_spec=file_spec,
            lld_content=lld_content,
            completed_files=completed_files,
            repo_root=repo_root,
            test_content=test_content,
            # Issue #498: Use structured failure summary (targeted) over raw output (noisy)
            previous_error=(test_failure_summary or e2e_failure_summary or green_phase_output)
            if iteration_count > 0 else "",
            path_enforcement_section=path_enforcement_section,
            context_content=state.get("context_content", ""),
            repo_structure=repo_structure,
        )

        # Issue #588: Pruned prompt for retries (no completed_files context)
        pruned_prompt = build_single_file_prompt(
            filepath=filepath,
            file_spec=file_spec,
            lld_content=lld_content,
            completed_files=[],  # <-- PRUNED
            repo_root=repo_root,
            test_content=test_content,
            previous_error=(test_failure_summary or e2e_failure_summary or green_phase_output)
            if iteration_count > 0 else "",
            path_enforcement_section=path_enforcement_section,
            context_content=state.get("context_content", ""),
            repo_structure=repo_structure,
        )

        # Issue #644: Enforce prompt size cap — use pruned prompt if full exceeds cap
        if len(prompt) > CODE_GEN_PROMPT_CAP:
            print(f"        [PRUNE] Prompt {len(prompt):,} -> {len(pruned_prompt):,} chars (cap: {CODE_GEN_PROMPT_CAP:,})")
            prompt = pruned_prompt

        # Call Claude with retry logic (Issue #309)
        # Issue #267: Progress feedback during long API calls
        with ProgressReporter("Calling Claude", interval=15):
            code, success = generate_file_with_retry(
                filepath=filepath,
                base_prompt=prompt,
                audit_dir=audit_dir if audit_dir.exists() else None,
                max_retries=MAX_FILE_RETRIES,
                pruned_prompt=pruned_prompt,
                existing_content=existing_content,
            )
        # Note: generate_file_with_retry raises ImplementationError on failure,
        # so if we get here, code is valid

        # Write file (atomic: write to temp, then rename)
        temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        try:
            temp_path.write_text(code, encoding="utf-8")
            temp_path.replace(target_path)
        except Exception as e:
            emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
            raise ImplementationError(
                filepath=filepath,
                reason=f"Failed to write file: {e}",
                response_preview=None
            )

        print(f"        Written: {target_path}")

        # Add to accumulated context
        completed_files.append((filepath, code))
        written_paths.append(str(target_path))

    print(f"\n    Implementation complete: {len(written_paths)} files written")

    # Issue #460: Update test_files to point to real test files written by N4,
    # replacing the scaffold stubs that N2 created.
    issue_number = state.get("issue_number", 0)
    real_test_files = [
        p for p in written_paths
        if "/tests/" in p.replace("\\", "/")
        and Path(p).name.startswith("test_")
        and p.endswith(".py")
    ]

    if real_test_files:
        # Delete the scaffold file — it only has `assert False` stubs
        scaffold_path = repo_root / "tests" / f"test_issue_{issue_number}.py"
        if scaffold_path.exists():
            scaffold_path.unlink()
            print(f"    Deleted scaffold: {scaffold_path}")

    # Log to audit
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="implementation_generated",
        details={
            "files": written_paths,
            "iteration": iteration_count,
            "method": "file-by-file",
        },
    )

    # Issue #511: Accumulate per-node cost
    node_cost_usd = get_cumulative_cost() - cost_before
    node_costs = accumulate_node_cost(
        dict(state.get("node_costs", {})), "implement_code", node_cost_usd,
    )

    return {
        "implementation_files": written_paths,
        "completed_files": completed_files,
        "estimated_tokens_used": estimated_tokens_used,
        "error_message": "",
        "test_files": real_test_files if real_test_files else state.get("test_files", []),
        "node_costs": node_costs,  # Issue #511
    }


def _mock_implement_code(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    issue_number = state.get("issue_number", 42)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    mock_content = f'''"""Mock implementation for Issue #{issue_number}."""

def example_function():
    """Example function."""
    return True
'''

    impl_path = repo_root / "assemblyzero" / f"issue_{issue_number}_impl.py"
    impl_path.parent.mkdir(parents=True, exist_ok=True)
    impl_path.write_text(mock_content, encoding="utf-8")

    print(f"    [MOCK] Generated: {impl_path}")

    return {
        "implementation_files": [str(impl_path)],
        "completed_files": [("assemblyzero/issue_{issue_number}_impl.py", mock_content)],
        "error_message": "",
        "test_files": state.get("test_files", []),
    }
```
