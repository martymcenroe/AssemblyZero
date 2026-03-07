Here is the content for the file

## Output Format

Output ONLY the {descriptor} inside a single fenced code block.
- No explanation before or after
- No file path in the response
- No markdown headers inside the code block
- Complete, working code only

```{block_tag}
<complete file contents here>
```
"""

    return prompt


def build_retry_prompt(original_prompt: str, error_message: str, attempt_num: int, max_retries: int) -> str:
    """Append error feedback to original prompt for retry.

    Issue #309: Include specific error message so Claude can fix it.
    """
    return original_prompt + f"""

## Previous Attempt Failed (Attempt {attempt_num}/{max_retries + 1})

Your previous response had an error:

```
{error_message}
```

Please fix this issue and provide the corrected, complete file contents.
IMPORTANT: Output the ENTIRE file, not just the fix.
"""


# =============================================================================
# Claude API Interaction
# =============================================================================


def select_model_for_file(
    file_path: str,
    estimated_line_count: int = 0,
    is_test_scaffold: bool = False,
) -> str:
    """Return the model ID to use for generating the given file.

    Routing rules (evaluated in order):
      1. is_test_scaffold=True  -> HAIKU_MODEL
      2. basename is __init__.py or conftest.py -> HAIKU_MODEL
      3. estimated_line_count > 0 and < SMALL_FILE_LINE_THRESHOLD -> HAIKU_MODEL
      4. Otherwise -> configured default (Sonnet via CLAUDE_MODEL)

    Issue #641: Route scaffolding/boilerplate files to Haiku.

    Args:
        file_path: Relative or absolute path to the file being generated.
            Only the basename is used for filename-based routing rules.
        estimated_line_count: Expected line count of the generated file.
            Pass 0 (default) when unknown; 0 disables line-count routing.
            Negative values are treated as unknown (same as 0).
        is_test_scaffold: True when this file is being generated as a test
            scaffold by the N2 node; overrides all other routing rules.

    Returns:
        Model identifier string suitable for passing to the Anthropic client.
    """
    basename = Path(file_path).name

    if is_test_scaffold:
        logger.info(
            "Routing %s -> %s (reason: test scaffold)", file_path, HAIKU_MODEL
        )
        return HAIKU_MODEL

    if basename in {"__init__.py", "conftest.py"}:
        logger.info(
            "Routing %s -> %s (reason: boilerplate filename)", file_path, HAIKU_MODEL
        )
        return HAIKU_MODEL

    if estimated_line_count > 0 and estimated_line_count < SMALL_FILE_LINE_THRESHOLD:
        logger.info(
            "Routing %s -> %s (reason: small file, lines=%d)",
            file_path,
            HAIKU_MODEL,
            estimated_line_count,
        )
        return HAIKU_MODEL

    default_model = CLAUDE_MODEL
    logger.info("Routing %s -> %s (reason: default)", file_path, default_model)
    return default_model


def call_claude_for_file(prompt: str, file_path: str = "", model: str | None = None) -> tuple[str, str]:
    """Call Claude for a single file implementation.

    Issue #447: Added file_path parameter for file-type-aware system prompt.
    Issue #641: Added model parameter for routing to different models.

    Args:
        prompt: The full generation prompt.
        file_path: Path for file-type-aware system prompt.
        model: Override model; if None, uses CLAUDE_MODEL from config.

    Returns:
        Tuple of (response_text, stop_reason).
    """
    resolved_model = model if model is not None else CLAUDE_MODEL

    # Issue #447: Build system prompt based on file type
    info = get_file_type_info(file_path) if file_path else {}
    system_prompt_parts = [
        "You are a senior Python engineer implementing production code.",
        "Output ONLY the complete file contents inside a fenced code block.",
        "No explanations, no commentary, no markdown outside the code block.",
    ]

    if info.get("file_type"):
        system_prompt_parts.append(
            f"The file you are implementing is a {info['file_type']} file."
        )
    if info.get("guidelines"):
        system_prompt_parts.extend(info["guidelines"])

    system_prompt = "\n".join(system_prompt_parts)

    # Try SDK first, fall back to CLI
    try:
        return _call_claude_sdk(prompt, system_prompt, resolved_model)
    except Exception as e:
        print(f"    [WARN] SDK call failed ({e}), trying CLI fallback...", flush=True)
        try:
            return _call_claude_cli(prompt, resolved_model)
        except Exception as cli_e:
            raise RuntimeError(f"Both SDK and CLI failed. SDK: {e}, CLI: {cli_e}") from cli_e


def _call_claude_sdk(prompt: str, system_prompt: str, model: str = "") -> tuple[str, str]:
    """Call Claude via the Anthropic Python SDK.

    Issue #321: Increased timeout from 300s to 600s for large prompts.
    Issue #444: Cost tracking via get_cumulative_cost.
    Issue #447: Accepts system_prompt parameter for file-type-aware prompting.

    Args:
        prompt: The user prompt.
        system_prompt: System prompt for behavior guidance.
        model: Model to use. Defaults to CLAUDE_MODEL if empty.

    Returns:
        Tuple of (response_text, stop_reason).
    """
    import anthropic

    if not model:
        model = CLAUDE_MODEL

    max_tokens = 16384
    # Issue #373: Increase max_tokens for very large prompts (proportional)
    estimated_tokens = len(prompt) // 4
    if estimated_tokens > 8000:
        max_tokens = 32768

    # Emit start telemetry
    emit("llm.call_start", repo="", metadata={
        "model": model,
        "prompt_chars": len(prompt),
        "max_tokens": max_tokens,
        "caller": "implement_code",
    })

    client = anthropic.Anthropic(timeout=SDK_TIMEOUT)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
    except anthropic.APIStatusError as e:
        # Emit failure telemetry
        emit("llm.call_error", repo="", metadata={
            "model": model,
            "error": str(e),
            "caller": "implement_code",
        })
        raise

    # Extract response text and metadata
    response_text = response.content[0].text if response.content else ""
    stop_reason = response.stop_reason or "unknown"

    # Emit completion telemetry with usage
    input_tokens = getattr(response.usage, "input_tokens", 0) if response.usage else 0
    output_tokens = getattr(response.usage, "output_tokens", 0) if response.usage else 0

    emit("llm.call_complete", repo="", metadata={
        "model": model,
        "stop_reason": stop_reason,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "response_chars": len(response_text),
        "caller": "implement_code",
    })

    # Issue #444: Report cost from centralized tracker
    cost = get_cumulative_cost()
    if cost > 0:
        print(f"     Cumulative API cost: ${cost:.4f}", flush=True)

    return response_text, stop_reason


def _call_claude_cli(prompt: str, model: str = "") -> tuple[str, str]:
    """Call Claude via CLI subprocess.

    Issue #321: Scaled timeout for large prompts.

    Args:
        prompt: The full prompt.
        model: Model to use. Defaults to CLAUDE_MODEL if empty.

    Returns:
        Tuple of (response_text, stop_reason).
        stop_reason is always "end_turn" for CLI (no truncation detection).
    """
    claude_cmd = _find_claude_cli()
    if not claude_cmd:
        raise RuntimeError("Claude CLI not found")

    if not model:
        model = CLAUDE_MODEL

    # Issue #321: Scale timeout based on prompt size
    prompt_tokens = len(prompt) // 4
    timeout = CLI_TIMEOUT + (prompt_tokens // 1000) * 30

    try:
        result = run_command(
            [claude_cmd, "--print", "--model", model, "-p", prompt],
            timeout=timeout,
        )
        return result.stdout.strip(), "end_turn"
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Claude CLI timed out after {timeout}s")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Claude CLI error: {e.stderr[:200] if e.stderr else 'no stderr'}")


# =============================================================================
# File Generation with Retry
# =============================================================================


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
    """Generate code for a single file with retry on validation failure.

    Issue #309: Retry up to max_retries times on API or validation errors.
    Issue #641: Routes to appropriate model via select_model_for_file().
    """
    model = select_model_for_file(filepath, estimated_line_count, is_test_scaffold)

    last_error = ""
    active_prompt = base_prompt
    for attempt in range(max_retries + 1):
        if attempt > 0:
            # Issue #644: Use pruned prompt on retry if available
            retry_base = pruned_prompt if pruned_prompt else active_prompt
            active_prompt = build_retry_prompt(retry_base, last_error, attempt, max_retries)
            print(f"    ⟳ Retry {attempt}/{max_retries} for {filepath}", flush=True)

        try:
            with ProgressReporter(f"Generating {filepath} (attempt {attempt + 1})", interval=15):
                response_text, stop_reason = call_claude_for_file(active_prompt, filepath, model=model)
        except Exception as e:
            last_error = f"API call failed: {e}"
            print(f"     API error: {last_error}", flush=True)
            if attempt == max_retries:
                return "", False
            continue

        # Issue #324: Check for truncation
        if stop_reason == "max_tokens":
            last_error = "Response was truncated (hit max_tokens). Output the COMPLETE file."
            print(f"     Response truncated", flush=True)
            if attempt == max_retries:
                return "", False
            continue

        # Detect summary response
        if detect_summary_response(response_text):
            last_error = "You gave a summary instead of code. Output ONLY the complete file in a code block."
            print(f"     Summary detected", flush=True)
            if attempt == max_retries:
                return "", False
            continue

        # Extract code block
        code = extract_code_block(response_text, filepath)

        if code is None:
            last_error = "No code block found in response"
            print(f"     No code block", flush=True)

            # Save raw response for debugging
            if audit_dir:
                try:
                    raw_file = audit_dir / f"raw_response_{filepath.replace('/', '_')}_attempt{attempt}.txt"
                    raw_file.write_text(response_text[:5000], encoding="utf-8")
                except Exception:
                    pass

            if attempt == max_retries:
                return "", False
            continue

        # Validate
        valid, error_msg = validate_code_response(code, filepath, existing_content)

        if not valid:
            last_error = error_msg
            print(f"     Validation: {error_msg}", flush=True)

            if audit_dir:
                try:
                    val_file = audit_dir / f"validation_{filepath.replace('/', '_')}_attempt{attempt}.txt"
                    val_file.write_text(f"Error: {error_msg}\n\nCode:\n{code[:3000]}", encoding="utf-8")
                except Exception:
                    pass

            if attempt == max_retries:
                return "", False
            continue

        # Success!
        if attempt > 0:
            print(f"     Succeeded on attempt {attempt + 1}", flush=True)

        return code, True

    return "", False


# =============================================================================
# Context / Architectural Injection
# =============================================================================

def load_context_files(
    repo_root: Path,
    filepath: str,
    files_to_modify: list[dict],
) -> str:
    """Load context files from LLD specification.

    Issue #288: Injects architectural context (existing modules, patterns)
    into the generation prompt so Claude understands the codebase.

    Args:
        repo_root: Repository root path.
        filepath: Current file being generated.
        files_to_modify: List of file specs from LLD.

    Returns:
        Combined context content string.
    """
    context_parts = []

    # Find the spec for this file
    file_spec = None
    for spec in files_to_modify:
        if spec.get("path") == filepath:
            file_spec = spec
            break

    if not file_spec:
        return ""

    # Load context files specified in the LLD
    context_files = file_spec.get("context_files", [])
    for ctx_path in context_files:
        full_path = repo_root / ctx_path
        if full_path.exists():
            try:
                content = full_path.read_text(encoding="utf-8")
                context_parts.append(f"### {ctx_path}\n\n```python\n{content}\n```\n")
            except Exception:
                pass

    return "\n".join(context_parts)


# =============================================================================
# Main Node Entry Point
# =============================================================================


def implement_code(state: TestingWorkflowState) -> TestingWorkflowState:
    """N4: Implement code file-by-file with mechanical validation.

    Issue #272: Iterates through files_to_modify, calling Claude for each file.
    Issue #309: Retries up to MAX_FILE_RETRIES on validation failure.
    Issue #188: Validates writes against LLD-specified paths.

    Each file sees:
    - The full LLD specification
    - Previously completed files (for imports/references)
    - Its own test file content (if available)
    - Error feedback (if retry)

    Args:
        state: Current workflow state with files_to_modify and lld_content.

    Returns:
        Updated state with implemented_files populated.
    """
    repo_root = get_repo_root(state)
    files_to_modify = state.get("files_to_modify", [])
    lld_content = state.get("lld_content", "")

    if not files_to_modify:
        print("  [WARN] No files to implement", flush=True)
        state["implemented_files"] = []
        return state

    # Issue #188: Build path enforcement section
    allowed_paths = extract_paths_from_lld(lld_content)
    path_enforcement = build_implementation_prompt_section(allowed_paths)

    # Issue #445: Get repo structure for grounding
    repo_structure = get_repo_structure(str(repo_root), max_depth=3)

    # Issue #188: Detect scaffolded test files
    scaffolded_test_files = detect_scaffolded_test_files(repo_root, allowed_paths)

    # Track costs
    cost_before = get_cumulative_cost()

    # Track all results
    implemented_files: list[dict] = []
    completed_files: list[tuple[str, str]] = []  # (path, content) for accumulating context
    failed_files: list[str] = []
    file_models: dict[str, str] = {}  # Track which model was used for each file
    audit_dir = Path(state.get("audit_dir", "")) if state.get("audit_dir") else None

    total_files = len(files_to_modify)
    print(f"\n   Implementing {total_files} file(s)...\n", flush=True)

    for idx, file_spec in enumerate(files_to_modify, 1):
        filepath = file_spec.get("path", "")
        change_type = file_spec.get("change_type", "Add")
        description = file_spec.get("description", "")

        print(f"  [{idx}/{total_files}] {filepath} ({change_type})", flush=True)

        if not filepath:
            print(f"    [WARN] Empty filepath in file spec, skipping", flush=True)
            continue

        # Issue #188: Validate path against LLD
        if not validate_file_write(filepath, allowed_paths):
            msg = f"     Path not in LLD allowed paths: {filepath}"
            print(msg, flush=True)
            gate_log(state, f"PATH_REJECTED: {filepath}")
            failed_files.append(filepath)
            continue

        # Load existing content for Modify operations
        existing_content = ""
        if change_type.lower() == "modify":
            existing_path = repo_root / filepath
            if existing_path.exists():
                try:
                    existing_content = existing_path.read_text(encoding="utf-8")
                except Exception:
                    pass

        # Check for associated test file
        test_content = ""
        test_path = _find_test_for_file(filepath, files_to_modify, repo_root)
        if test_path:
            try:
                full_test_path = repo_root / test_path
                if full_test_path.exists():
                    test_content = full_test_path.read_text(encoding="utf-8")
            except Exception:
                pass

        # Issue #288: Load context files
        context_content = load_context_files(repo_root, filepath, files_to_modify)

        # Issue #324: Select generation strategy
        strategy = select_generation_strategy(change_type, existing_content)

        if strategy == "diff":
            # Diff-based generation for large files
            prompt = build_diff_prompt(lld_content, existing_content, test_content, filepath)
            print(f"     Using diff mode (large file: {len(existing_content)} bytes)", flush=True)

            try:
                with ProgressReporter(f"Generating diff for {filepath}", interval=15):
                    response_text, stop_reason = call_claude_for_file(prompt, filepath)
            except Exception as e:
                print(f"     Diff generation failed: {e}", flush=True)
                failed_files.append(filepath)
                continue

            # Parse and apply diff
            diff_result = parse_diff_response(response_text)
            if not diff_result["success"]:
                print(f"     Diff parse error: {diff_result['error']}", flush=True)
                failed_files.append(filepath)
                continue

            code, apply_errors = apply_diff_changes(existing_content, diff_result["changes"])
            if apply_errors:
                for err in apply_errors:
                    print(f"    [WARN] Diff apply: {err}", flush=True)
                # Still try to use the result if some changes applied

            # Validate the result
            valid, error_msg = validate_code_response(code, filepath, existing_content)
            if not valid:
                print(f"     Diff result invalid: {error_msg}", flush=True)
                # Fall back to standard mode
                strategy = "standard"
                print(f"    ↩ Falling back to standard mode", flush=True)

        if strategy == "standard":
            # Standard full-file generation
            prompt = build_single_file_prompt(
                filepath=filepath,
                file_spec=file_spec,
                lld_content=lld_content,
                completed_files=completed_files,
                repo_root=repo_root,
                test_content=test_content,
                path_enforcement_section=path_enforcement,
                context_content=context_content,
                repo_structure=repo_structure,
            )

            # Issue #644: Cap prompt size for code generation
            if len(prompt) > CODE_GEN_PROMPT_CAP:
                pruned = _prune_prompt(prompt, CODE_GEN_PROMPT_CAP)
                print(f"     Prompt pruned: {len(prompt)} -> {len(pruned)} chars", flush=True)
            else:
                pruned = ""

            # Determine if this is a scaffolded test file
            is_scaffold = filepath in scaffolded_test_files

            # Get estimated line count from file spec if available
            est_lines = file_spec.get("estimated_lines", 0)

            code, success = generate_file_with_retry(
                filepath=filepath,
                base_prompt=prompt,
                audit_dir=audit_dir,
                pruned_prompt=pruned,
                existing_content=existing_content,
                estimated_line_count=est_lines,
                is_test_scaffold=is_scaffold,
            )

            if not success:
                print(f"     FAILED after all retries", flush=True)
                failed_files.append(filepath)
                continue

        # Write the file
        target_path = repo_root / filepath
        target_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            target_path.write_text(code, encoding="utf-8")
            print(f"     Written: {filepath} ({len(code.splitlines())} lines)", flush=True)
        except Exception as e:
            print(f"     Write failed: {e}", flush=True)
            failed_files.append(filepath)
            continue

        # Track
        implemented_files.append({
            "path": filepath,
            "change_type": change_type,
            "lines": len(code.splitlines()),
        })
        completed_files.append((filepath, code))

    # Cost tracking
    cost_after = get_cumulative_cost()
    node_cost = cost_after - cost_before
    if node_cost > 0:
        accumulate_node_cost(state, "N4_implement", node_cost)
        record_iteration_cost(state, node_cost)

    # Summary
    print(f"\n   Implementation Summary:", flush=True)
    print(f"      Succeeded: {len(implemented_files)}/{total_files}", flush=True)
    if failed_files:
        print(f"      Failed: {len(failed_files)}", flush=True)
        for f in failed_files:
            print(f"       - {f}", flush=True)

    state["implemented_files"] = implemented_files
    state["failed_files"] = failed_files

    if failed_files and not implemented_files:
        state["implementation_failed"] = True

    return state


def _find_test_for_file(
    filepath: str,
    files_to_modify: list[dict],
    repo_root: Path,
) -> str | None:
    """Find associated test file for a source file.

    Looks for test files in the same batch and on disk.
    """
    # Convert source path to expected test path
    path = Path(filepath)

    # If this IS a test file, skip
    if path.name.startswith("test_"):
        return None

    # Look for test_<name>.py pattern
    test_name = f"test_{path.name}"

    # Check in files_to_modify first
    for spec in files_to_modify:
        spec_path = spec.get("path", "")
        if Path(spec_path).name == test_name:
            return spec_path

    # Check on disk in tests/ directory
    test_candidates = [
        f"tests/unit/{test_name}",
        f"tests/{test_name}",
        f"tests/integration/{test_name}",
    ]

    for candidate in test_candidates:
        if (repo_root / candidate).exists():
            return candidate

    return None


def _prune_prompt(prompt: str, cap: int) -> str:
    """Prune prompt to fit under cap by removing least-important sections.

    Issue #644: Reduces prompt size while preserving critical sections.
    Priority (highest to lowest):
    1. Task and LLD specification
    2. Tests that must pass
    3. Path enforcement
    4. Existing file contents
    5. Repository structure
    6. Previously implemented files (removed first)
    7. Additional context (removed first)
    """
    if len(prompt) <= cap:
        return prompt

    # Remove sections in order of least importance
    sections_to_remove = [
        "## Additional Context",
        "## Previously Implemented Files",
        "## Repository Structure",
    ]

    result = prompt
    for section_header in sections_to_remove:
        if len(result) <= cap:
            break
        result = _remove_section(result, section_header)

    # If still too long, truncate the LLD content
    if len(result) > cap:
        result = result[:cap] + "\n\n[TRUNCATED - prompt exceeded size limit]\n"

    return result


def _remove_section(prompt: str, section_header: str) -> str:
    """Remove a markdown section from the prompt."""
    start = prompt.find(section_header)
    if start == -1:
        return prompt

    # Find the next section header (## )
    next_section = prompt.find("\n## ", start + len(section_header))
    if next_section == -1:
        # Last section - remove to end
        return prompt[:start].rstrip() + "\n"
    else:
        return prompt[:start] + prompt[next_section + 1:]
```

## Instructions

Generate the complete updated file content for `assemblyzero/workflows/testing/nodes/implement_code.py`.

Apply all changes from the LLD specification:
- Add `HAIKU_MODEL` and `SMALL_FILE_LINE_THRESHOLD` constants; add `select_model_for_file()` routing function; update `call_claude_for_file()` to accept `model` param; update `generate_file_with_retry()` to call routing

The file content provided above is the CURRENT state of the file.
Compare the current state with the LLD requirements and make ONLY the changes that are still needed.
Do NOT duplicate changes that have already been applied.

Output the complete file with all necessary modifications applied.
