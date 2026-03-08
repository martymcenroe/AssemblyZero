import sys
from pathlib import Path

def patch_file(path_str):
    path = Path(path_str)
    content = path.read_text(encoding='utf-8')

    # 1. Two-Strike Rule
    content = content.replace("MAX_FILE_RETRIES = 3", "MAX_FILE_RETRIES = 2")

    # 2. Update validate_code_response signature
    old_validate = '''def validate_code_response(code: str, filepath: str) -> tuple[bool, str]:
    """Mechanically validate code. No LLM judgment.

    Returns (valid, error_message).
    """
    if not code:'''

    new_validate = '''def validate_code_response(code: str, filepath: str, existing_content: str = "") -> tuple[bool, str]:
    """Mechanically validate code. No LLM judgment.

    Returns (valid, error_message).
    """
    if not code:'''
    content = content.replace(old_validate, new_validate)

    # 3. Inject Size Gate Logic
    old_validate_logic = '''        if not short_ok and len(lines) < 2:
            return False, f"Code too short ({len(lines)} lines)"

    # Python syntax validation'''

    new_validate_logic = '''        if not short_ok and len(lines) < 2:
            return False, f"Code too short ({len(lines)} lines)"

    # Issue #587: Mechanical File Size Safety Gate
    if existing_content:
        existing_lines = existing_content.strip().split("\\n")
        # Only apply check if existing file is non-trivial (>10 lines)
        if len(existing_lines) > 10:
            new_lines = len(lines)
            if new_lines < len(existing_lines) * 0.5:
                return False, f"Mechanical Size Gate: File shrank drastically from {len(existing_lines)} lines to {new_lines} lines. You must output the ENTIRE file without using placeholders."

    # Python syntax validation'''
    content = content.replace(old_validate_logic, new_validate_logic)

    # 4. Update generate_file_with_retry signature
    old_gen = '''def generate_file_with_retry(
    filepath: str,
    base_prompt: str,
    audit_dir: Path | None = None,
    max_retries: int = MAX_FILE_RETRIES,
) -> tuple[str, bool]:'''

    new_gen = '''def generate_file_with_retry(
    filepath: str,
    base_prompt: str,
    audit_dir: Path | None = None,
    max_retries: int = MAX_FILE_RETRIES,
    pruned_prompt: str = "",
    existing_content: str = "",
) -> tuple[str, bool]:'''
    content = content.replace(old_gen, new_gen)

    # 5. Update retry prompt call (Context Pruning)
    old_retry_call = '''        # Build retry prompt if this isn't the first attempt
        if attempt > 0:
            prompt = build_retry_prompt(base_prompt, last_error, attempt_num)'''

    new_retry_call = '''        # Build retry prompt if this isn't the first attempt
        if attempt > 0:
            prompt = build_retry_prompt(pruned_prompt or base_prompt, last_error, attempt_num)'''
    content = content.replace(old_retry_call, new_retry_call)

    # 6. Pass existing_content to validation
    old_val_call = '''        # Validate code mechanically
        valid, validation_error = validate_code_response(code, filepath)'''

    new_val_call = '''        # Validate code mechanically
        valid, validation_error = validate_code_response(code, filepath, existing_content)'''
    content = content.replace(old_val_call, new_val_call)

    # 7. Extract existing_content in the main loop
    old_impl_loop = '''    for i, file_spec in enumerate(files_to_modify):
        filepath = file_spec["path"]
        change_type = file_spec.get("change_type", "Add")

        print(f"\\n    [{i+1}/{len(files_to_modify)}] {filepath} ({change_type})...")'''

    new_impl_loop = '''    for i, file_spec in enumerate(files_to_modify):
        filepath = file_spec["path"]
        change_type = file_spec.get("change_type", "Add")
        
        existing_content = ""
        target_path = repo_root / filepath
        if change_type.lower() == "modify" and target_path.exists():
            try:
                existing_content = target_path.read_text(encoding="utf-8")
            except Exception:
                pass

        print(f"\\n    [{i+1}/{len(files_to_modify)}] {filepath} ({change_type})...")'''
    content = content.replace(old_impl_loop, new_impl_loop)

    # 8. Call with pruned prompt
    old_gen_call = '''        # Call Claude with retry logic (Issue #309)
        # Issue #267: Progress feedback during long API calls
        with ProgressReporter("Calling Claude", interval=15):
            code, success = generate_file_with_retry(
                filepath=filepath,
                base_prompt=prompt,
                audit_dir=audit_dir if audit_dir.exists() else None,
                max_retries=MAX_FILE_RETRIES,
            )'''

    new_gen_call = '''        # Issue #588: Pruned prompt for retries (no completed_files context)
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
            )'''
    content = content.replace(old_gen_call, new_gen_call)

    path.write_text(content, encoding='utf-8')
    print("Patch applied successfully.")

if __name__ == "__main__":
    patch_file(sys.argv[1])
