"""Main implementation orchestrator — the LangGraph node and retry logic.

Contains implement_code() (the N4 node entry point) and supporting functions.
"""

import subprocess
from pathlib import Path
from typing import Any

from assemblyzero.core import retry_gate
from assemblyzero.core.llm_provider import get_cumulative_cost
from assemblyzero.core.retry_mode import is_regeneration
from assemblyzero.workflows.testing.nodes.implementation.edit_script_fix import (
    EDIT_SCRIPT_CODE_SYSTEM_PROMPT,
    EditScriptOutcome,
    apply_code_edit_script,
    build_code_edit_script_prompt,
    failures_for_file,
    response_is_a_regeneration,
    should_use_edit_script,
)
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
    parse_batch_response,
    validate_code_response,
)
from .prompts import (
    MAX_FILE_RETRIES,
    build_batch_file_prompt,
    build_retry_prompt,
    build_single_file_prompt,
    build_stable_system_prompt,
)
from .routing import HAIKU_MODEL, select_model_for_file

# Issue #644: Prompt size cap for code generation (chars)
CODE_GEN_PROMPT_CAP = 60_000

# Issue #647: Maximum files per batch call
BATCH_SIZE = 5


def try_edit_script_fix(
    filepath: str,
    existing_content: str,
    failure_context: str,
    model: str = "",
    system_prompt: str = "",
    audit_dir: Path | None = None,
    spec_excerpt: str = "",
) -> EditScriptOutcome:
    """One attempt to fix `filepath` with an edit script instead of a rewrite.

    Deliberately makes ONE call and never retries. A malformed edit script is
    not a transport failure, and the fallback -- full regeneration, with its
    own retry budget -- is right there. Retrying the patch first would spend
    twice to reach the same place, which is the habit #2423 exists to break.

    Any failure at any step returns an outcome whose `code` is None, and the
    caller regenerates.
    """
    scoped = failures_for_file(failure_context, filepath)
    prompt = build_code_edit_script_prompt(
        filepath=filepath,
        existing_content=existing_content,
        failure_context=scoped,
        spec_excerpt=spec_excerpt,
    )

    if audit_dir is not None and audit_dir.exists():
        save_audit_file(
            audit_dir, next_file_number(audit_dir),
            f"prompt-editscript-{filepath.replace('/', '-')}.md", prompt,
        )

    try:
        with ProgressReporter("Calling Claude (edit script)", interval=15):
            result = call_claude_for_file(
                prompt, file_path=filepath, model=model,
                # The stable system prompt describes whole-file output; a
                # patch engine needs the opposite instruction, and mixing them
                # is how a model ends up sending a file back.
                system_prompt=EDIT_SCRIPT_CODE_SYSTEM_PROMPT,
            )
    except Exception as exc:  # noqa: BLE001 - a patch attempt never costs the roll
        return EditScriptOutcome(None, failures=[f"edit-script call failed: {exc}"])

    if isinstance(result, tuple) and len(result) == 2:
        response, api_error_raw = result
    else:
        response, api_error_raw = result, ""
    if isinstance(api_error_raw, str) and api_error_raw:
        return EditScriptOutcome(None, failures=[f"API error: {api_error_raw}"])

    if audit_dir is not None and audit_dir.exists():
        save_audit_file(
            audit_dir, next_file_number(audit_dir),
            f"response-editscript-{filepath.replace('/', '-')}.md", response or "",
        )

    if response_is_a_regeneration(response or ""):
        return EditScriptOutcome(
            None, failures=["model returned a whole file instead of edit blocks"]
        )

    return apply_code_edit_script(response or "", existing_content)


def generate_file_with_retry(
    filepath: str,
    base_prompt: str,
    audit_dir: Path | None = None,
    max_retries: int = MAX_FILE_RETRIES,
    pruned_prompt: str = "",
    existing_content: str = "",
    estimated_line_count: int = 0,
    is_test_scaffold: bool = False,
    system_prompt: str = "",
    repo_root: Path | None = None,
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
        system_prompt: Stable system prompt for caching (Issue #643).

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
            # #2547: causal wording. The old line printed the PREVIOUS
            # attempt's error under the NEW attempt's number, so
            # "[RETRY 2/2] Validation failed: ..." followed by silence read
            # as an exhausted validator the pipeline ignored — a reading the
            # #2546/#2547 investigation spent real time refuting. The line
            # now says whose error it is and what happens next; the outcome
            # is always printed too ([SUCCESS] on recovery, the
            # ImplementationError halt on exhaustion — never a silent
            # proceed).
            print(
                f"        [RETRY {attempt_num}/{max_retries}] attempt "
                f"{attempt_num - 1} failed ({last_error[:80]}...) -- retrying"
            )
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
        # Issue #643: pass stable system prompt for caching
        result = call_claude_for_file(prompt, file_path=filepath, model=model, system_prompt=system_prompt)

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
            # #2423: classify the TRANSPORT failure before paying again. This
            # loop is where the 2026-08-15 cost came from, and it came doubled:
            # it sits INSIDE the orchestrator's stage-retry loop, so its
            # attempts multiply rather than add. Counted from
            # run-issue1-090001: 7 payments of ~602s, 70.2 minutes, zero
            # artifacts. A ceiling kill halts here on the first one.
            #
            # Content failures below (a summary, no code block) are NOT gated:
            # the model answered and answered wrongly, which a retry can
            # genuinely fix. Only the transport class is deterministic.
            decision = retry_gate.should_retry(
                retry_gate.classify_failure(api_error),
                attempts_made=attempt_num,
                max_attempts=max_retries,
            )
            if decision.retry:
                print(retry_gate.retry_spend_line(
                    filepath, attempts_made=attempt_num, budget=max_retries,
                    failure_class=decision.failure_class,
                    cumulative_cost=get_cumulative_cost(),
                ))
                continue
            print(retry_gate.halt_line(
                filepath, decision, get_cumulative_cost(),
            ))
            emit("workflow.halt_and_plan", repo="", metadata={"filepath": filepath, "reason": "max_retries_exceeded"})
            raise ImplementationError(
                filepath=filepath,
                # "API error after N attempts" is kept verbatim: two existing
                # tests pin that prefix, and it is the phrase a reader greps
                # for. The class and the reason are appended, not substituted.
                reason=(
                    f"API error after {attempt_num} attempts "
                    f"[{decision.failure_class}]: {api_error}. "
                    f"{decision.reason}"
                ),
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

        # Validate code mechanically (Issue #842: pass repo_root for import validation)
        validation_result = validate_code_response(
            code, filepath, existing_content,
            repo_root=str(repo_root) if repo_root else "",
        )

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


def came_from_base(repo_root: Path, filepath: str) -> bool:
    """Is this path TRACKED, i.e. inherited from the base branch? (#2032)

    The discriminator the skip-on-resume guard was missing. A pipeline worktree
    is cut from the integration branch, so a file present when a run starts is
    tracked and belongs to an earlier phase. A file a previous attempt of THIS
    run wrote is untracked, because nothing commits mid-stage.

    Same observation -- "the file is already there" -- with opposite correct
    responses: resume past our own half-written output, never past another
    phase's finished work.
    """
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", filepath],
        cwd=str(repo_root), capture_output=True, text=True,
    )
    return result.returncode == 0


def _should_skip_existing_file(
    change_type: str, target_path: Path, iteration_count: int,
    repo_root: Path | None = None, filepath: str = "",
    regenerate: bool = False,
) -> bool:
    """Issue #547 skip-on-resume, scoped by Issue #1842 to the first pass only.

    Retry iterations (iteration_count > 0) exist to REWRITE files with the
    test-failure feedback that build_single_file_prompt carries as
    previous_error. The unscoped guard skipped every already-on-disk Add file,
    so no retry ever called the model — N5 re-ran byte-identical files until
    the stagnation detector halted the run (hardening runs 8/10/11, boostgauge
    campaign 2026-07-28).

    #2032: a file that came from the BASE is never a resume. boostgauge #2
    skipped all five planned files -- #41 and #1 had landed them on the
    integration branch -- printed "5 files written" having written none, and
    died at pytest with nothing collected.
    """
    #1941: a clean-slate regeneration must not consult this path at all. The
    # whole point of regenerating is that the previous attempt's output is the
    # thing being discarded, so "it is already on disk" is not a reason to keep
    # it -- it is the reason to replace it.
    if regenerate:
        return False
    if iteration_count > 0:
        return False
    if repo_root is not None and filepath and came_from_base(repo_root, filepath):
        return False
    return (
        change_type.lower() == "add"
        and target_path.exists()
        and target_path.stat().st_size > 0
    )


def resolve_change_type(
    change_type: str, repo_root: Path, filepath: str, target_path: Path
) -> str:
    """An Add whose file the base already ships is really a Modify (#2032/#2033).

    The spec plans every file as Add because it is drafted against an empty tree
    rather than the base the worktree is cut from. Followed literally on a
    mid-arc phase that OVERWRITES an earlier phase: #2 would have replaced the
    telltale module #41 built instead of extending it.

    Coercing here makes the destructive case impossible while the plan is still
    wrong, and routes the file through the Modify prompt, which carries the
    current contents and asks for a change rather than a replacement.
    """
    if (
        change_type.lower() == "add"
        and target_path.exists()
        and came_from_base(repo_root, filepath)
    ):
        print(
            f"        Base already ships {filepath}; implementing as Modify so "
            f"the earlier phase's work is extended rather than replaced."
        )
        return "Modify"
    return change_type


def implement_code(state: TestingWorkflowState) -> dict[str, Any]:
    """N4: Generate implementation code file-by-file.

    Issue #272: File-by-file prompting with mechanical validation.
    """
    iteration_count = state.get("iteration_count", 0)
    # #1941: set when a stage retry classified the previous failure as
    # deterministic (or could not classify it). Discards that attempt's files
    # rather than resuming them, which is what made run11b's attempt 2 a
    # byte-identical replay of attempt 1.
    _regenerating = is_regeneration(state.get("retry_mode"))
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

    # Issue #643: Build stable system prompt ONCE before the file loop.
    # This content is identical for every file and will be cached by Anthropic.
    stable_system_prompt = build_stable_system_prompt(
        lld_content=lld_content,
        repo_structure=repo_structure,
        path_enforcement_section=path_enforcement_section,
        test_content=test_content,
        context_content=state.get("context_content", ""),
    )

    # Accumulated context
    completed_files: list[tuple[str, str]] = []
    written_paths: list[str] = []

    # Issue #647: Batch small Haiku-routed files to reduce API calls.
    # Partition files: batchable (Haiku-routed Add files that aren't fast-pathed)
    # vs regular (everything else).
    _trivial_extensions = (".json", ".yaml", ".yml", ".toml", ".txt", ".csv")
    _placeholder_names = {".gitkeep", ".gitignore_placeholder", ".keep"}
    batch_specs: list[dict] = []
    regular_specs: list[dict] = []

    for file_spec in files_to_modify:
        fp = file_spec["path"]
        ct = file_spec.get("change_type", "Add")
        fname = Path(fp).name
        desc = file_spec.get("description", "")
        target = repo_root / fp

        # Skip files that have fast paths (handled without Claude)
        is_fast_path = (
            ct.lower() == "delete"
            or fname in _placeholder_names
            or (
                (fname == "__init__.py" or fp.endswith(_trivial_extensions))
                and ct.lower() == "add"
                and len(desc) < 50
            )
            or (ct.lower() == "add" and target.exists() and target.stat().st_size > 0)
        )

        if is_fast_path:
            regular_specs.append(file_spec)
            continue

        # Only batch Add files routed to Haiku
        model = select_model_for_file(fp, file_spec.get("estimated_line_count", 0))
        if ct.lower() == "add" and model == HAIKU_MODEL:
            batch_specs.append(file_spec)
        else:
            regular_specs.append(file_spec)

    # Process batches
    batch_failed_specs: list[dict] = []
    if batch_specs:
        print(f"\n    [BATCH] {len(batch_specs)} small files eligible for batching")
        for batch_start in range(0, len(batch_specs), BATCH_SIZE):
            batch = batch_specs[batch_start:batch_start + BATCH_SIZE]
            batch_paths = [s["path"] for s in batch]
            print(f"    [BATCH] Processing {len(batch)} files: {', '.join(batch_paths)}")

            batch_prompt = build_batch_file_prompt(batch)

            with ProgressReporter("Batch generating", interval=15):
                response, api_error = call_claude_for_file(
                    prompt=batch_prompt,
                    file_path=batch_paths[0],
                    model=HAIKU_MODEL,
                    system_prompt=stable_system_prompt,
                )

            if api_error:
                print(f"    [BATCH] API error, falling back to individual: {api_error[:80]}")
                batch_failed_specs.extend(batch)
                continue

            parsed = parse_batch_response(response, batch_paths)

            for spec in batch:
                fp = spec["path"]
                code = parsed.get(fp)

                if code is None:
                    print(f"        [BATCH] Failed to parse {fp}, will retry individually")
                    batch_failed_specs.append(spec)
                    continue

                # Validate. #2547: repo_root travels here too — the batch
                # path used to omit it, which silently skipped import (and
                # now conftest-option) validation for every batch-written
                # file. run-issue331-235455's killing conftest was written
                # exactly this way, validated for syntax alone.
                valid, val_error = validate_code_response(
                    code, fp, repo_root=str(repo_root),
                )
                if not valid:
                    print(
                        f"        [BATCH] Validation failed for {fp}: "
                        f"{val_error} -- falling back to individual "
                        f"generation with retries"
                    )
                    batch_failed_specs.append(spec)
                    continue

                # Write file
                target_path = repo_root / fp
                target_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
                temp_path.write_text(code, encoding="utf-8")
                temp_path.replace(target_path)
                print(f"        Written (batch): {target_path}")
                completed_files.append((fp, code))
                written_paths.append(str(target_path))

    # Merge batch failures back into regular for individual processing
    if batch_failed_specs:
        print(f"    [BATCH] {len(batch_failed_specs)} files falling back to individual generation")
        regular_specs.extend(batch_failed_specs)

    # Replace files_to_modify with regular_specs for the main loop
    files_to_modify = regular_specs

    # #2064: symmetry-break for a repeated failing set. Tests and impl are both
    # regenerated from the same spec, so when they disagree, a deterministic
    # drafter reproduces the exact same failures every iteration -- six
    # boostgauge #2 runs repeated their counts to the digit. When N5 saw the
    # same set twice it froze the tests: they are the contract now (the passing
    # ones prove they run), and only the implementation may change.
    freeze_tests = bool(state.get("freeze_tests"))
    revision_error_context = (
        (test_failure_summary or e2e_failure_summary or green_phase_output)
        if iteration_count > 0 else ""
    )
    if freeze_tests and revision_error_context:
        revision_error_context = (
            "THE TESTS ARE A FROZEN CONTRACT. They will not be rewritten. "
            "Change the implementation so the tests pass exactly as written; "
            "read the failing assertions for the expected behavior.\n\n"
            + revision_error_context
        )
    if freeze_tests:
        print(
            "    [N4] tests are FROZEN this iteration (repeated failing set): "
            "rewriting implementation only, against the tests as written"
        )

    for i, file_spec in enumerate(files_to_modify):
        filepath = file_spec["path"]
        change_type = file_spec.get("change_type", "Add")

        if freeze_tests and filepath.replace("\\", "/").startswith("tests/"):
            target_path = repo_root / filepath
            if target_path.is_file():
                completed_files.append(
                    (filepath, target_path.read_text(encoding="utf-8"))
                )
                written_paths.append(str(target_path))
                print(
                    f"\n    [{i+1}/{len(files_to_modify)}] {filepath} — frozen "
                    f"(contract; not rewritten)"
                )
                continue

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
                print("        Deleted")
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
        if _should_skip_existing_file(
            change_type, target_path, iteration_count, repo_root, filepath,
            regenerate=_regenerating,
        ):
            existing_content = target_path.read_text(encoding="utf-8")
            print(f"        Skipped (already exists): {target_path}")
            completed_files.append((filepath, existing_content))
            written_paths.append(str(target_path))
            continue

        # #2032: the base already ships this file, so extend it rather than
        # overwriting an earlier phase. Must run AFTER the resume check, whose
        # subject is our own output, and BEFORE the validation below, which
        # reads change_type.
        change_type = resolve_change_type(
            change_type, repo_root, filepath, target_path
        )

        # #2644: the edit script's own view of the file, read AFTER the
        # resolution above.
        #
        # `existing_content` is read ~60 lines up, guarded by
        # `change_type.lower() == "modify"` -- and at that point change_type
        # still says whatever the LLD said. For a file the LLD calls "Add"
        # that the base already ships, it is "Add" there and "Modify" here, so
        # `existing_content` stays "" and `should_use_edit_script` sees an
        # empty file and declines. That is exactly the mid-arc case the edit
        # script exists for, and the case every Phase 2 run is in.
        #
        # Measured on run-issue331-092220: iteration 0 wrote stingray.py whole
        # in 67s; iteration 1, fixing 3 failing tests and a 3-point coverage
        # gap, ran the full-file path for 1200s and was killed
        # (ceiling_timeout). No `[EDIT-SCRIPT]` line appears anywhere in that
        # log -- the machinery #2407 landed two weeks earlier never engaged.
        #
        # Deliberately a SEPARATE name rather than repairing `existing_content`
        # in place. That value also reaches `validate_code_response`, where a
        # non-empty existing file activates #587's drastic-shrink gate; making
        # it non-empty here would add a refusal surface to the full-file path,
        # on the campaign's own route, as a side effect of a timeout fix.
        edit_script_content = existing_content
        if (
            not edit_script_content
            and change_type.lower() == "modify"
            and target_path.exists()
        ):
            try:
                edit_script_content = target_path.read_text(encoding="utf-8")
            except OSError as exc:
                # fail-open: an unreadable file leaves the edit script with
                # nothing to SEARCH, which is precisely the condition
                # `should_use_edit_script` declines on. Continuing lands on
                # the full-file path, which reads the file itself through the
                # prompt builder and will report its own failure -- so this is
                # never worse than the behaviour before #2644. Halting here
                # would turn a read hiccup into a dead stage.
                #
                # Audible on purpose: the silent version of this was what the
                # fail-open gate objected to, and an edit script that quietly
                # declines is exactly how run-issue331-092220 went unexplained.
                edit_script_content = ""
                print(
                    f"        [EDIT-SCRIPT] could not read {filepath} "
                    f"({exc}); falling through to the full-file path"
                )

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
            previous_error=revision_error_context,
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
            previous_error=revision_error_context,
            path_enforcement_section=path_enforcement_section,
            context_content=state.get("context_content", ""),
            repo_structure=repo_structure,
        )

        # Issue #644: Enforce prompt size cap — use pruned prompt if full exceeds cap
        if len(prompt) > CODE_GEN_PROMPT_CAP:
            print(f"        [PRUNE] Prompt {len(prompt):,} -> {len(pruned_prompt):,} chars (cap: {CODE_GEN_PROMPT_CAP:,})")
            prompt = pruned_prompt

        # #2407: a fix asks for EDITS, not a rebirth. Measured in
        # run-issue1-090001: stingray.py drafted from nothing in 15.9s, then
        # its fix calls ran 602s and were killed, three times -- a factor of
        # thirty-eight on the same file, because a regeneration re-derives
        # everything including the parts that already pass. The spec stage
        # learned this in #1528; this is the implementation stage inheriting
        # it. Any failure returns None and falls through to the full-file path
        # below, so this is never worse than the behavior it replaces.
        code = None
        if should_use_edit_script(
            change_type, edit_script_content, revision_error_context
        ):
            outcome = try_edit_script_fix(
                filepath=filepath,
                existing_content=edit_script_content,
                failure_context=revision_error_context,
                model=select_model_for_file(filepath, 0, False),
                system_prompt=stable_system_prompt,
                audit_dir=audit_dir if audit_dir.exists() else None,
            )
            print(f"        {outcome.describe()}")
            code = outcome.code

        if code is None:
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
                    system_prompt=stable_system_prompt,
                    repo_root=repo_root,
                )
            # Note: generate_file_with_retry raises ImplementationError on
            # failure, so if we get here, code is valid

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

    # Issue #460 replaced the scaffold with the implementer's test files. Since
    # #2316 the scaffold is the spec's own suite -- the contract -- and it
    # stays (#2709). One helper decides, so the rule has one home.
    issue_number = state.get("issue_number", 0)
    real_test_files = [
        p for p in written_paths
        if "/tests/" in p.replace("\\", "/")
        and Path(p).name.startswith("test_")
        and p.endswith(".py")
    ]
    test_files_after = merge_test_files(
        scaffold_path=repo_root / "tests" / f"test_issue_{issue_number}.py",
        scaffold_is_spec_suite=bool(
            (state.get("spec_test_suite") or {}).get("functions")
        ),
        real_test_files=real_test_files,
        prior_test_files=list(state.get("test_files", []) or []),
    )

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
        "test_files": test_files_after,
        "node_costs": node_costs,  # Issue #511
    }


def merge_test_files(
    scaffold_path: Path,
    scaffold_is_spec_suite: bool,
    real_test_files: list[str],
    prior_test_files: list[str],
) -> list[str]:
    """What the green phase runs after N4 (#2709).

    #460 deleted the scaffold and ran the implementer's test files instead,
    because the scaffold was ``assert False`` stubs no implementation could
    satisfy. #2316 changed what the scaffold is: the spec's own executable
    functions, emitted verbatim, verified by #2706/#2707 before the spec was
    approved. Measured on boostgauge run-issue4-172600: nine validated spec
    tests were unlinked one node after validation and the green phase graded
    three tests the implementer wrote for its own code -- the #2677 shape.

    So: when the scaffold carries the spec's suite it stays and runs FIRST;
    the implementer's files are additions after it. A stub scaffold (no spec
    functions) is still replaced, exactly as #460 intended. With no
    implementer test files at all, the prior list stands.
    """
    if not real_test_files:
        return list(prior_test_files)

    scaffold = str(scaffold_path)
    if scaffold_is_spec_suite and scaffold_path.exists():
        print(f"    Kept the spec's suite as the contract: {scaffold_path} (#2709)")
        return [scaffold] + [p for p in real_test_files if Path(p) != scaffold_path]

    if scaffold_path.exists():
        scaffold_path.unlink()
        print(f"    Deleted scaffold: {scaffold_path}")
    return list(real_test_files)


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