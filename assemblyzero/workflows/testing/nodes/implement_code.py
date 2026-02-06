"""N4: Implement Code node for TDD Testing Workflow.

Issue #272: File-by-file prompting with mechanical validation.
Issue #309: Add retry logic on validation failure (up to 3 attempts).

Key changes from original:
- Iterate through files_to_modify one at a time (not batch)
- Accumulate context: each file sees LLD + previously completed files
- Mechanical validation: code block exists, not empty, parses
- RETRY on validation failure: up to 3 attempts with error feedback
- WE control the file path, not Claude
"""

import ast
import os
import re
import random
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import (
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.state import TestingWorkflowState


# Issue #309: Maximum retry attempts per file
MAX_FILE_RETRIES = 3

# Issue #324: Large file thresholds for diff-based generation
LARGE_FILE_LINE_THRESHOLD = 500  # Lines
LARGE_FILE_BYTE_THRESHOLD = 15000  # Bytes (~15KB)

# Issue #321: Timeout constants
CLI_TIMEOUT = 300  # 5 minutes for CLI subprocess
SDK_TIMEOUT = 300  # 5 minutes for SDK API call


class ImplementationError(Exception):
    """Raised when implementation fails mechanically.

    Graph runner should catch this and exit non-zero.
    """
    def __init__(self, filepath: str, reason: str, response_preview: str | None = None):
        self.filepath = filepath
        self.reason = reason
        self.response_preview = response_preview
        super().__init__(f"FATAL: Failed to implement {filepath}: {reason}")


def _find_claude_cli() -> str | None:
    """Find the Claude CLI executable."""
    cli = shutil.which("claude")
    if cli:
        return cli

    npm_paths = [
        Path.home() / "AppData" / "Roaming" / "npm" / "claude.cmd",
        Path.home() / "AppData" / "Roaming" / "npm" / "claude",
        Path.home() / ".npm-global" / "bin" / "claude",
        Path("/c/Users") / os.environ.get("USERNAME", "") / "AppData" / "Roaming" / "npm" / "claude.cmd",
    ]

    for path in npm_paths:
        if path.exists():
            return str(path)

    return None


# =============================================================================
# Mechanical Validation (no LLM judgment)
# =============================================================================

def extract_code_block(response: str) -> str | None:
    """Extract code block content from response.

    Returns the content of the first code block, or None if no valid block found.
    Does NOT trust any file path Claude puts in the response.
    """
    # Pattern: ```language\n...content...```
    pattern = re.compile(r"```\w*\s*\n(.*?)```", re.DOTALL)

    for match in pattern.finditer(response):
        content = match.group(1).strip()

        # Skip empty blocks
        if not content:
            continue

        # If first line is a # File: comment, strip it (we don't trust it)
        lines = content.split("\n")
        if lines[0].strip().startswith("# File:"):
            content = "\n".join(lines[1:]).strip()

        # Must have actual content
        if content and len(content) > 10:
            return content

    return None


def validate_code_response(code: str, filepath: str) -> tuple[bool, str]:
    """Mechanically validate code. No LLM judgment.

    Returns (valid, error_message).
    """
    if not code:
        return False, "Code is empty"

    if not code.strip():
        return False, "Code is only whitespace"

    # Minimum line threshold (5 lines for non-trivial files)
    lines = code.strip().split("\n")
    if len(lines) < 5:
        # Allow short files for __init__.py or simple configs
        if not filepath.endswith("__init__.py") and len(lines) < 2:
            return False, f"Code too short ({len(lines)} lines)"

    # Python syntax validation
    if filepath.endswith(".py"):
        try:
            ast.parse(code)
        except SyntaxError as e:
            return False, f"Python syntax error: {e}"

    return True, ""


def detect_summary_response(response: str) -> bool:
    """Detect if Claude gave a summary instead of code.

    Fast rejection before trying to parse.
    """
    blacklist = [
        "here's a summary",
        "here is a summary",
        "i've created",
        "i have created",
        "i've implemented",
        "i have implemented",
        "summary of",
        "the following files",
    ]

    response_lower = response.lower()[:500]  # Only check start

    for phrase in blacklist:
        if phrase in response_lower:
            # Check if there's also a code block (might be legit)
            if "```" not in response[:1000]:
                return True

    return False


def estimate_context_tokens(lld_content: str, completed_files: list[tuple[str, str]]) -> int:
    """Estimate token count for context.

    Uses simple heuristic: ~4 chars per token.
    """
    total_chars = len(lld_content)
    for filepath, content in completed_files:
        total_chars += len(filepath) + len(content) + 50  # 50 for formatting

    return total_chars // 4


# =============================================================================
# Issue #324: Diff-Based Generation for Large Files
# =============================================================================


def is_large_file(content: str) -> bool:
    """Check if file content exceeds size thresholds.

    Issue #324: Large files (500+ lines OR 15KB+) should use diff mode
    instead of full file regeneration.

    Args:
        content: The file content to check.

    Returns:
        True if file exceeds either threshold.
    """
    if not content:
        return False

    # Check line count (500+ lines = large)
    line_count = len(content.split("\n"))
    if line_count > LARGE_FILE_LINE_THRESHOLD:
        return True

    # Check byte size (15KB+ = large)
    byte_count = len(content.encode("utf-8"))
    if byte_count > LARGE_FILE_BYTE_THRESHOLD:
        return True

    return False


def select_generation_strategy(change_type: str, existing_content: str | None) -> str:
    """Select code generation strategy based on change type and file size.

    Issue #324: Use diff mode for large file modifications.

    Args:
        change_type: "Add", "Modify", or "Delete".
        existing_content: Current file content (None for new files).

    Returns:
        "standard" or "diff".
    """
    # Add and Delete always use standard mode
    if change_type.lower() in ("add", "delete"):
        return "standard"

    # Modify: check file size
    if existing_content and is_large_file(existing_content):
        return "diff"

    return "standard"


def build_diff_prompt(
    lld_content: str,
    existing_content: str,
    test_content: str,
    file_path: str,
) -> str:
    """Build prompt requesting FIND/REPLACE diff format.

    Issue #324: For large files, request targeted changes instead of
    full file regeneration.

    Args:
        lld_content: The LLD specification.
        existing_content: Current file content.
        test_content: Test code that must pass.
        file_path: Path to the file being modified.

    Returns:
        Prompt string for diff-based generation.
    """
    prompt = f"""# Modification Request: {file_path}

## Task

Modify the existing file using FIND/REPLACE blocks. Do NOT output the entire file.

## LLD Specification

{lld_content}

## Current File Content

```python
{existing_content}
```

"""

    if test_content:
        prompt += f"""## Tests That Must Pass

```python
{test_content}
```

"""

    prompt += """## Output Format

Output ONLY the changes using this FIND/REPLACE format:

### CHANGE 1: Brief description of what this change does
FIND:
```python
exact code to find
```

REPLACE WITH:
```python
replacement code
```

### CHANGE 2: Next change description
FIND:
```python
...
```

REPLACE WITH:
```python
...
```

CRITICAL RULES:
1. Do NOT output the entire file - only the FIND/REPLACE blocks
2. Each FIND block must match EXACTLY in the current file
3. Include enough context in FIND to be unambiguous (unique match)
4. Number your changes: CHANGE 1, CHANGE 2, etc.
5. Describe what each change does in the header
"""

    return prompt


def parse_diff_response(response: str) -> dict:
    """Parse FIND/REPLACE diff response from Claude.

    Issue #324: Extract change blocks from diff-format response.

    Args:
        response: Claude's response with FIND/REPLACE blocks.

    Returns:
        Dict with keys:
        - success: bool
        - error: str | None
        - changes: list[dict] with keys: description, find_block, replace_block
    """
    changes = []

    # Pattern to match CHANGE headers
    # Matches: ### CHANGE N: description
    change_pattern = re.compile(
        r"###\s*CHANGE\s*\d+\s*:\s*(.+?)(?=\n)",
        re.IGNORECASE
    )

    # Pattern to match FIND/REPLACE blocks
    # FIND: ```...``` REPLACE WITH: ```...```
    find_replace_pattern = re.compile(
        r"FIND:\s*```\w*\s*\n(.*?)```\s*\n+REPLACE\s+WITH:\s*```\w*\s*\n(.*?)```",
        re.DOTALL | re.IGNORECASE
    )

    # Split response into change sections
    sections = re.split(r"(###\s*CHANGE\s*\d+\s*:)", response, flags=re.IGNORECASE)

    # Process pairs: (header_marker, content)
    i = 1  # Skip text before first CHANGE
    while i < len(sections) - 1:
        header_marker = sections[i]  # "### CHANGE N:"
        content = sections[i + 1] if i + 1 < len(sections) else ""

        # Extract description from the content (first line after header)
        desc_match = re.match(r"\s*(.+?)(?=\n)", content)
        description = desc_match.group(1).strip() if desc_match else "Unknown change"

        # Find the FIND/REPLACE block in this section
        fr_match = find_replace_pattern.search(content)

        if not fr_match:
            return {
                "success": False,
                "error": f"CHANGE missing REPLACE WITH section: {description[:50]}",
                "changes": [],
            }

        find_block = fr_match.group(1).strip()
        replace_block = fr_match.group(2).strip()

        changes.append({
            "description": description,
            "find_block": find_block,
            "replace_block": replace_block,
        })

        i += 2

    if not changes:
        return {
            "success": False,
            "error": "No FIND/REPLACE changes found in response",
            "changes": [],
        }

    return {
        "success": True,
        "error": None,
        "changes": changes,
    }


def apply_diff_changes(
    content: str,
    changes: list[dict],
) -> tuple[str, list[str]]:
    """Apply FIND/REPLACE changes to file content.

    Issue #324: Apply each change sequentially, with error detection.

    Args:
        content: Original file content.
        changes: List of change dicts with find_block/replace_block.

    Returns:
        Tuple of (modified_content, error_list).
    """
    errors = []
    result = content

    for change in changes:
        find_block = change.get("find_block", "")
        replace_block = change.get("replace_block", "")
        description = change.get("description", "")

        if not find_block:
            errors.append(f"Empty FIND block for change: {description}")
            continue

        # Count occurrences
        count = result.count(find_block)

        if count == 0:
            # Try whitespace-normalized matching
            normalized_result = _normalize_whitespace(result)
            normalized_find = _normalize_whitespace(find_block)

            if normalized_find in normalized_result:
                # Found with normalization - but we can't reliably replace
                # so we report a whitespace-specific error
                errors.append(
                    f"FIND block has whitespace mismatch for: {description[:50]}. "
                    f"Exact match not found but similar code exists."
                )
            else:
                errors.append(f"FIND block not found in file: {description[:50]}")
            continue

        if count > 1:
            errors.append(
                f"Ambiguous FIND block (matches {count} locations): {description[:50]}"
            )
            continue

        # Single match - safe to replace
        result = result.replace(find_block, replace_block, 1)

    return result, errors


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace for fuzzy matching.

    Collapses multiple spaces and normalizes indentation.
    """
    # Replace tabs with spaces
    text = text.replace("\t", "    ")
    # Collapse multiple spaces (but preserve newlines)
    lines = text.split("\n")
    normalized_lines = []
    for line in lines:
        # Strip trailing whitespace, normalize internal spaces
        line = line.rstrip()
        normalized_lines.append(line)
    return "\n".join(normalized_lines)


def detect_truncation(response: object) -> bool:
    """Detect if response was truncated due to max_tokens.

    Issue #324: Check stop_reason to detect truncation.

    Args:
        response: Claude API response object with stop_reason attribute.

    Returns:
        True if response was truncated.
    """
    stop_reason = getattr(response, "stop_reason", None)
    return stop_reason == "max_tokens"


# =============================================================================
# Prompt Building
# =============================================================================

def build_single_file_prompt(
    filepath: str,
    file_spec: dict,
    lld_content: str,
    completed_files: list[tuple[str, str]],
    repo_root: Path,
    test_content: str = "",
    previous_error: str = "",
) -> str:
    """Build prompt for a single file with accumulated context."""

    change_type = file_spec.get("change_type", "Add")
    description = file_spec.get("description", "")

    prompt = f"""# Implementation Request: {filepath}

## Task

Write the complete contents of `{filepath}`.

Change type: {change_type}
Description: {description}

## LLD Specification

{lld_content}

"""

    # Include existing file content if modifying
    if change_type.lower() == "modify":
        existing_path = repo_root / filepath
        if existing_path.exists():
            try:
                existing_content = existing_path.read_text(encoding="utf-8")
                prompt += f"""## Existing File Contents

The file currently contains:

```python
{existing_content}
```

Modify this file according to the LLD specification.

"""
            except Exception:
                pass

    # Include test content if available
    if test_content:
        prompt += f"""## Tests That Must Pass

```python
{test_content}
```

"""

    # Include previously completed files (accumulated context)
    if completed_files:
        prompt += "## Previously Implemented Files\n\n"
        prompt += "These files have already been implemented. Use them for imports and references:\n\n"
        for prev_path, prev_content in completed_files:
            prompt += f"""### {prev_path}

```python
{prev_content}
```

"""

    # Include previous error if this is a retry... wait, no retries!
    # Actually we might loop back from green phase failure, so include error context
    if previous_error:
        prompt += f"""## Previous Attempt Failed

The previous implementation had this error:

```
{previous_error}
```

Fix the issue in your implementation.

"""

    prompt += """## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the code.

```python
# Your implementation here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the code in a single code block
"""

    return prompt


# =============================================================================
# Claude API Call
# =============================================================================

def call_claude_for_file(prompt: str) -> tuple[str, str]:
    """Call Claude for a single file implementation.

    Returns (response, error).
    NO RETRIES - if it fails, it fails.
    """
    claude_cli = _find_claude_cli()

    if claude_cli:
        try:
            system_prompt = """You are a code generator. Output ONLY code.

RULES:
1. Output a single code block with the complete file contents
2. No explanations before or after the code
3. No summaries
4. No "I've implemented..." statements
5. Just the code in a ```python block

If you output anything other than a code block, the build will fail."""

            cmd = [
                claude_cli,
                "--print",
                "--dangerously-skip-permissions",
                "--model", "opus",  # Opus 4.5 for code quality
                "--system-prompt", system_prompt,
            ]

            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=CLI_TIMEOUT,  # Issue #321: Use constant
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout, ""
            else:
                stderr = result.stderr[:200] if result.stderr else "no stderr"
                # Fall through to SDK
                print(f"    [WARN] CLI failed (exit {result.returncode}): {stderr}")

        except subprocess.TimeoutExpired:
            return "", f"CLI timeout after {CLI_TIMEOUT}s waiting for response"
        except Exception as e:
            print(f"    [WARN] CLI error: {e}")

    # Fallback to SDK
    try:
        import anthropic
        import httpx

        # Issue #321: Add timeout to SDK client
        client = anthropic.Anthropic(
            timeout=httpx.Timeout(SDK_TIMEOUT, connect=30.0)
        )

        message = client.messages.create(
            model="claude-opus-4-5-20250514",
            max_tokens=32768,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = ""
        for block in message.content:
            if hasattr(block, "text"):
                response_text += block.text

        return response_text, ""

    except ImportError:
        return "", "Neither Claude CLI nor Anthropic SDK available"
    except httpx.TimeoutException:
        return "", f"SDK timeout after {SDK_TIMEOUT}s waiting for response"
    except TimeoutError:
        return "", f"SDK timeout after {SDK_TIMEOUT}s waiting for response"
    except Exception as e:
        return "", f"SDK error: {e}"


# =============================================================================
# Issue #309: Retry Logic
# =============================================================================


def build_retry_prompt(base_prompt: str, validation_error: str, attempt: int) -> str:
    """Augment the base prompt with error context from previous attempt.

    Issue #309: Include validation error to help Claude self-correct.

    Args:
        base_prompt: The original prompt for this file.
        validation_error: Error message from the failed attempt.
        attempt: Current attempt number (1-indexed for display).

    Returns:
        Modified prompt with error feedback section.
    """
    error_section = f"""

## Previous Attempt Failed (Attempt {attempt}/{MAX_FILE_RETRIES})

Your previous response had an error:

```
{validation_error}
```

Please fix this issue and provide the corrected, complete file contents.
IMPORTANT: Output the ENTIRE file, not just the fix.
"""

    # Insert error section before the Output Format section
    if "## Output Format" in base_prompt:
        parts = base_prompt.split("## Output Format")
        return parts[0] + error_section + "\n## Output Format" + parts[1]
    else:
        return base_prompt + error_section


def generate_file_with_retry(
    filepath: str,
    base_prompt: str,
    audit_dir: Path | None = None,
    max_retries: int = MAX_FILE_RETRIES,
) -> tuple[str, bool]:
    """Generate code for a single file with retry on validation failure.

    Issue #309: Retry up to max_retries times on API or validation errors,
    including error context in subsequent prompts.

    Args:
        filepath: Path to the file being generated.
        base_prompt: The initial prompt for code generation.
        audit_dir: Optional directory for audit logs.
        max_retries: Maximum number of attempts (default: 3).

    Returns:
        Tuple of (generated_code, success_flag).

    Raises:
        ImplementationError: Only after exhausting all retry attempts.
    """
    last_error = ""
    prompt = base_prompt

    for attempt in range(max_retries):
        attempt_num = attempt + 1  # 1-indexed for display

        # Build retry prompt if this isn't the first attempt
        if attempt > 0:
            prompt = build_retry_prompt(base_prompt, last_error, attempt_num)
            print(f"        [RETRY {attempt_num}/{max_retries}] {last_error[:80]}...")

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

        # Call Claude
        response, api_error = call_claude_for_file(prompt)

        # Check for API error
        if api_error:
            last_error = f"API error: {api_error}"
            if attempt < max_retries - 1:
                print(f"        [RETRY {attempt_num}/{max_retries}] {last_error}")
                continue
            else:
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
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"Summary response after {max_retries} attempts",
                    response_preview=response[:500]
                )

        # Extract code block
        code = extract_code_block(response)

        if code is None:
            last_error = "No code block found in response"
            if attempt < max_retries - 1:
                continue
            else:
                raise ImplementationError(
                    filepath=filepath,
                    reason=f"No code block after {max_retries} attempts",
                    response_preview=response[:500]
                )

        # Validate code mechanically
        valid, validation_error = validate_code_response(code, filepath)

        if not valid:
            last_error = f"Validation failed: {validation_error}"
            if attempt < max_retries - 1:
                continue
            else:
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
    raise ImplementationError(
        filepath=filepath,
        reason=f"Failed after {max_retries} attempts: {last_error}",
        response_preview=None
    )


# =============================================================================
# Main Implementation Loop
# =============================================================================

def implement_code(state: TestingWorkflowState) -> dict[str, Any]:
    """N4: Generate implementation code file-by-file.

    Issue #272: File-by-file prompting with mechanical validation.
    """
    iteration_count = state.get("iteration_count", 0)
    print(f"\n[N4] Implementing code file-by-file (iteration {iteration_count})...")

    if state.get("mock_mode"):
        return _mock_implement_code(state)

    # Get required state
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    lld_content = state.get("lld_content", "")
    files_to_modify = state.get("files_to_modify", [])
    test_files = state.get("test_files", [])
    green_phase_output = state.get("green_phase_output", "")
    audit_dir = Path(state.get("audit_dir", ""))

    if not files_to_modify:
        print("    [ERROR] No files_to_modify in state - LLD Section 2.1 not parsed?")
        return {
            "error_message": "Implementation failed: No files to implement - check LLD Section 2.1",
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

    # Accumulated context
    completed_files: list[tuple[str, str]] = []
    written_paths: list[str] = []

    for i, file_spec in enumerate(files_to_modify):
        filepath = file_spec["path"]
        change_type = file_spec.get("change_type", "Add")

        print(f"\n    [{i+1}/{len(files_to_modify)}] {filepath} ({change_type})...")

        # Skip delete operations
        if change_type.lower() == "delete":
            target = repo_root / filepath
            if target.exists():
                target.unlink()
                print(f"        Deleted")
            continue

        # Validate change type
        target_path = repo_root / filepath
        if change_type.lower() == "modify" and not target_path.exists():
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
            raise ImplementationError(
                filepath=filepath,
                reason=f"Context too large ({token_estimate} tokens > 180K limit)",
                response_preview=None
            )
        if token_estimate > 150000:
            print(f"        [WARN] Context approaching limit ({token_estimate} tokens)")

        # Build prompt for this single file
        prompt = build_single_file_prompt(
            filepath=filepath,
            file_spec=file_spec,
            lld_content=lld_content,
            completed_files=completed_files,
            repo_root=repo_root,
            test_content=test_content,
            previous_error=green_phase_output if iteration_count > 0 else "",
        )

        # Call Claude with retry logic (Issue #309)
        print(f"        Calling Claude...")
        code, success = generate_file_with_retry(
            filepath=filepath,
            base_prompt=prompt,
            audit_dir=audit_dir if audit_dir.exists() else None,
            max_retries=MAX_FILE_RETRIES,
        )
        # Note: generate_file_with_retry raises ImplementationError on failure,
        # so if we get here, code is valid

        # Write file (atomic: write to temp, then rename)
        temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        try:
            temp_path.write_text(code, encoding="utf-8")
            temp_path.replace(target_path)
        except Exception as e:
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

    return {
        "implementation_files": written_paths,
        "completed_files": completed_files,
        "error_message": "",
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
    }


# =============================================================================
# Backward Compatibility Layer (for tests)
# Issue #272: These maintain old API while new code uses file-by-file approach
# =============================================================================

def build_implementation_prompt(state: TestingWorkflowState) -> str:
    """DEPRECATED: Build batch implementation prompt from state.

    Maintained for backward compatibility with existing tests.
    New code should use build_single_file_prompt() for file-by-file prompting.
    """
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()
    lld_content = state.get("lld_content", "")
    test_files = state.get("test_files", [])
    files_to_modify = state.get("files_to_modify", [])
    iteration_count = state.get("iteration_count", 0)
    green_phase_output = state.get("green_phase_output", "")
    issue_number = state.get("issue_number", 0)
    test_scenarios = state.get("test_scenarios", [])

    prompt = f"""# Implementation Request for Issue #{issue_number}

## LLD Specification

{lld_content}

"""

    # Include test scenarios
    if test_scenarios:
        prompt += "## Test Scenarios\n\n"
        for scenario in test_scenarios:
            name = scenario.get("name", "")
            description = scenario.get("description", "")
            requirement_ref = scenario.get("requirement_ref", "")
            prompt += f"- **{name}** ({requirement_ref}): {description}\n"
        prompt += "\n"

    # Read test file content
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

    if test_content:
        prompt += f"""## Tests That Must Pass

```python
{test_content}
```

"""

    if files_to_modify:
        prompt += "## Source Files to Modify\n\n"
        for f in files_to_modify:
            path = f.get("path", "")
            change_type = f.get("change_type", "Add")
            description = f.get("description", "")

            if change_type.lower() == "add":
                prompt += f"### NEW FILE: `{path}`\n{description}\n\n"
            else:
                prompt += f"### MODIFY: `{path}`\n{description}\n\n"
                # Include existing content for Modify
                existing_path = repo_root / path
                if existing_path.exists():
                    try:
                        existing = existing_path.read_text(encoding="utf-8")
                        prompt += f"Current content:\n```python\n{existing}\n```\n\n"
                    except Exception:
                        pass

    if iteration_count > 0 and green_phase_output:
        prompt += f"""## Previous Test Run (FAILED)

```
{green_phase_output}
```

Fix the issues and regenerate the implementation.

"""

    prompt += """## Output Format

Output each file with a header comment:

```python
# File: path/to/file.py
...code...
```

Output ALL files needed for the implementation.
"""

    return prompt


def parse_implementation_response(response: str) -> list[dict[str, str]]:
    """DEPRECATED: Parse multi-file response into list of {path, content} dicts.

    Maintained for backward compatibility with existing tests.
    New code uses extract_code_block() which returns just the code content
    since we control the file path.
    """
    files: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    # Pattern 1: # File: path/to/file.py followed by code
    pattern1 = re.compile(
        r"```(?:\w*)\s*\n#\s*File:\s*([^\n]+)\n(.*?)```",
        re.DOTALL
    )

    for match in pattern1.finditer(response):
        path = match.group(1).strip()
        content = match.group(2).strip()
        if path and content and path not in seen_paths:
            files.append({"path": path, "content": content})
            seen_paths.add(path)

    if files:
        return files

    # Pattern 2: ### (optional number.) path/to/file.py followed by code block
    # Handles: ### src/module.py, ### 1. `src/module.py`, **`src/module.py`**
    pattern2 = re.compile(
        r"(?:###\s+(?:\d+\.\s+)?`?([^`\n]+?)`?|\*\*`([^`\n]+?)`\*\*)\s*\n+```(?:\w*)\s*\n(.*?)```",
        re.DOTALL
    )

    for match in pattern2.finditer(response):
        # Group 1 is from ### format, Group 2 is from **` format
        path = (match.group(1) or match.group(2) or "").strip()
        content = match.group(3).strip()
        if path and content and path not in seen_paths:
            files.append({"path": path, "content": content})
            seen_paths.add(path)

    if files:
        return files

    # Pattern 3: Any code block with path in first line comment
    pattern3 = re.compile(r"```(?:\w*)\s*\n(.*?)```", re.DOTALL)

    file_counter = 1
    for match in pattern3.finditer(response):
        content = match.group(1).strip()
        if not content:
            continue

        # Check if first line is a path comment
        lines = content.split("\n")
        first_line = lines[0].strip()

        path = None
        if first_line.startswith("# ") and ("/" in first_line or first_line.endswith(".py")):
            # Could be "# path/to/file.py" or "# File: path/to/file.py"
            path_part = first_line[2:].strip()
            if path_part.startswith("File:"):
                path_part = path_part[5:].strip()
            if "/" in path_part or path_part.endswith(".py") or path_part.startswith("."):
                path = path_part
                content = "\n".join(lines[1:]).strip()

        if not path:
            # Generate a name
            path = f"implementation_{file_counter}.py"
            file_counter += 1

        if content and path not in seen_paths:
            files.append({"path": path, "content": content})
            seen_paths.add(path)

    return files


def write_implementation_files(
    files: list[dict[str, str]],
    repo_root: Path,
    test_files: list[str] | None = None,
) -> list[str]:
    """DEPRECATED: Write parsed files to disk.

    Maintained for backward compatibility with existing tests.
    New code writes files directly in the main implement_code() loop
    using atomic writes (temp file + rename).
    """
    written = []
    test_files = test_files or []

    for file_info in files:
        path = file_info.get("path", "")
        content = file_info.get("content", "")

        if not path or not content:
            continue

        # Skip test files (protected)
        if any(tf.endswith(path) or path in tf for tf in test_files):
            continue

        # Skip anything in tests/ directory
        if path.startswith("tests/") or "/tests/" in path:
            continue

        target = repo_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(str(target))

    return written


def call_claude_headless(
    prompt: str,
    system_prompt: str | None = None,
) -> tuple[str, str]:
    """DEPRECATED: Call Claude CLI with optional system prompt.

    Maintained for backward compatibility with existing tests.
    Alias for call_claude_for_file() which has the same signature
    (minus system_prompt handling).
    """
    # The new function doesn't take system_prompt as argument,
    # but the system prompt is hardcoded in call_claude_for_file()
    # For tests that pass system_prompt, we ignore it since the
    # real implementation uses a fixed system prompt anyway.
    return call_claude_for_file(prompt)
