"""N4: Implement Code node for TDD Testing Workflow.

Uses Claude to generate implementation code that passes the tests.
This is a temporary bridge until #87 (Implementation Workflow) is complete.
"""

import os
import random
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from agentos.workflows.testing.audit import (
    get_repo_root,
    log_workflow_execution,
    next_file_number,
    save_audit_file,
)
from agentos.workflows.testing.state import TestingWorkflowState


def _find_claude_cli() -> str | None:
    """Find the Claude CLI executable.

    Returns:
        Path to Claude CLI if found, None otherwise.
    """
    # Try which/where first
    cli = shutil.which("claude")
    if cli:
        return cli

    # Try common Windows locations
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


# Retry configuration for rate limits
_RETRY_MAX_ATTEMPTS = 5
_RETRY_BASE_DELAY = 1.0  # seconds
_RETRY_MAX_DELAY = 60.0  # seconds
_RETRY_JITTER_FACTOR = 0.2  # ±20%


def _is_rate_limit_error(stderr: str) -> bool:
    """Check if the error is a rate limit (429).

    Args:
        stderr: The stderr output from subprocess.

    Returns:
        True if this appears to be a rate limit error.
    """
    stderr_lower = stderr.lower()
    return (
        "429" in stderr_lower
        or "rate limit" in stderr_lower
        or "too many requests" in stderr_lower
    )


def _calculate_retry_backoff(attempt: int) -> float:
    """Calculate exponential backoff with jitter.

    Args:
        attempt: The current attempt number (0-indexed).

    Returns:
        The delay in seconds before the next retry.
    """
    delay = min(_RETRY_BASE_DELAY * (2**attempt), _RETRY_MAX_DELAY)
    jitter = delay * _RETRY_JITTER_FACTOR * (2 * random.random() - 1)
    return delay + jitter


def build_implementation_prompt(state: TestingWorkflowState) -> str:
    """Build the prompt for Claude to generate implementation.

    Args:
        state: Current workflow state.

    Returns:
        Implementation prompt.
    """
    issue_number = state.get("issue_number", 0)
    lld_content = state.get("lld_content", "")
    test_files = state.get("test_files", [])
    test_scenarios = state.get("test_scenarios", [])
    iteration_count = state.get("iteration_count", 0)
    green_phase_output = state.get("green_phase_output", "")
    files_to_modify = state.get("files_to_modify", [])
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else None

    prompt = f"""# Implementation Request

## Context

You are implementing code for Issue #{issue_number} using TDD.
This is iteration {iteration_count} of the implementation.

## Requirements

The tests have been scaffolded and need implementation code to pass.

### LLD Summary

{lld_content[:2000]}{"..." if len(lld_content) > 2000 else ""}

### Test Scenarios

"""
    for scenario in test_scenarios:
        prompt += f"""- **{scenario.get("name")}**: {scenario.get("description", "")}
  - Requirement: {scenario.get("requirement_ref", "N/A")}
  - Type: {scenario.get("test_type", "unit")}

"""

    # Read test file content
    for tf in test_files:
        if Path(tf).exists():
            content = Path(tf).read_text(encoding="utf-8")
            prompt += f"""### Test File: {tf}

```python
{content}
```

"""

    # Include source files that need to be modified (from LLD Section 2.1)
    if files_to_modify and repo_root:
        prompt += "### Source Files to Modify\n\n"
        prompt += "These are the existing files you need to modify:\n\n"
        for file_info in files_to_modify:
            file_path = repo_root / file_info["path"]
            change_type = file_info.get("change_type", "Modify")
            if change_type.lower() == "modify" and file_path.exists():
                try:
                    source_content = file_path.read_text(encoding="utf-8")
                    prompt += f"""#### {file_info['path']} ({change_type})

{file_info.get('description', '')}

```python
{source_content}
```

"""
                except Exception:
                    prompt += f"#### {file_info['path']} - (could not read file)\n\n"
            elif change_type.lower() == "add":
                prompt += f"#### {file_info['path']} (NEW FILE)\n\n"
                prompt += f"{file_info.get('description', '')}\n\n"

    # Include previous failure output if iteration > 0
    if iteration_count > 0 and green_phase_output:
        prompt += f"""### Previous Test Run (FAILED)

The previous implementation attempt failed. Here's the test output:

```
{green_phase_output[-2000:]}
```

Please fix the issues and provide updated implementation.

"""

    prompt += """## Instructions

1. Generate implementation code that makes all tests pass
2. Follow the patterns established in the codebase
3. Ensure proper error handling
4. Add type hints where appropriate
5. Keep the implementation minimal - only what's needed to pass tests

## Output Format (CRITICAL - MUST FOLLOW EXACTLY)

For EACH file you need to create or modify, provide a code block with this EXACT format:

```python
# File: path/to/implementation.py

def function_name():
    ...
```

**Rules:**
- The `# File: path/to/file` comment MUST be the FIRST line inside the code block
- Use the language-appropriate code fence (```python, ```gitignore, ```yaml, etc.)
- Path must be relative to repository root (e.g., `src/module/file.py`)
- Do NOT include "(append)" or other annotations in the path
- Provide complete file contents, not patches or diffs

**Example for .gitignore:**
```gitignore
# File: .gitignore

# Existing patterns...
*.pyc
__pycache__/

# New pattern
.agentos/
```

If multiple files are needed, provide each in a separate code block with its own `# File:` header.
"""

    return prompt


def call_claude_headless(prompt: str) -> tuple[str, str]:
    """Call Claude via subprocess in headless mode, with SDK fallback.

    Args:
        prompt: The prompt to send to Claude.

    Returns:
        Tuple of (response_text, error_message).
    """
    # First try CLI
    claude_cli = _find_claude_cli()

    if claude_cli:
        try:
            # System prompt to enforce strict output format
            system_prompt = """You are a code generator. You MUST output code in EXACTLY this format:

For EACH file, output a fenced code block where the FIRST LINE inside the block is a # File: comment:

```python
# File: path/to/file.py

def example():
    pass
```

CRITICAL RULES:
1. The `# File: path` comment MUST be the FIRST line inside the code block
2. Use the appropriate language fence (```python, ```yaml, ```gitignore, etc.)
3. Output ONLY code blocks - no explanations, no summaries, no markdown headers
4. Each file gets its own code block with its own # File: header
5. Paths are relative to repo root (e.g., src/module/file.py)

DO NOT:
- Add explanatory text before or after code blocks
- Use markdown headers like "### 1. filename"
- Skip the # File: comment
- Combine multiple files in one block"""

            # Use text output mode (default) - simpler and more reliable
            # --print (-p): non-interactive mode, prints response to stdout
            # --dangerously-skip-permissions: required for non-interactive file writes
            # --system-prompt: enforce strict output format
            # --model opus: use Claude Opus for reliable implementation
            cmd = [
                claude_cli,
                "--print",
                "--dangerously-skip-permissions",
                "--model", "opus",
                "--system-prompt", system_prompt,
            ]

            # Retry loop for rate limits
            last_rate_limit_error = None
            for attempt in range(_RETRY_MAX_ATTEMPTS):
                result = subprocess.run(
                    cmd,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=600,  # 10 minute timeout for complex implementations
                )

                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout, ""
                elif result.returncode != 0:
                    # Check if rate limited - retry with backoff
                    if _is_rate_limit_error(result.stderr or ""):
                        delay = _calculate_retry_backoff(attempt)
                        print(
                            f"    [WARN] Rate limited, retrying in {delay:.1f}s "
                            f"(attempt {attempt + 1}/{_RETRY_MAX_ATTEMPTS})"
                        )
                        time.sleep(delay)
                        last_rate_limit_error = result.stderr
                        continue

                    # Non-rate-limit error - don't retry
                    stderr_preview = result.stderr[:200] if result.stderr else "no stderr"
                    print(f"    [WARN] CLI exit code {result.returncode}: {stderr_preview}")
                    print("    Falling back to Anthropic SDK...")
                    break
                else:
                    print("    [WARN] CLI returned empty response, trying SDK...")
                    break
            else:
                # Exhausted retries due to rate limiting
                print(f"    [WARN] Rate limited after {_RETRY_MAX_ATTEMPTS} retries, trying SDK...")
                if last_rate_limit_error:
                    print(f"    Last error: {last_rate_limit_error[:100]}")

        except subprocess.TimeoutExpired:
            return "", "Claude CLI execution timed out (10 minutes)"
        except Exception as e:
            print(f"    [WARN] CLI error: {e}, trying SDK...")

    # Fall back to Anthropic SDK
    try:
        import anthropic

        client = anthropic.Anthropic()

        message = client.messages.create(
            model="claude-opus-4-20250514",  # Use Opus for reliable implementation
            max_tokens=8192,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extract text from response
        response_text = ""
        for block in message.content:
            if hasattr(block, "text"):
                response_text += block.text

        return response_text, ""

    except ImportError:
        return "", "Neither Claude CLI nor Anthropic SDK available"
    except Exception as e:
        return "", f"Anthropic SDK error: {e}"


def parse_implementation_response(response: str) -> list[dict]:
    """Parse Claude's response to extract implementation files.

    Handles multiple code block formats:
    - ```python with # File: header (preferred)
    - ```gitignore, ```markdown, etc. with # File: header
    - Markdown header followed by code block (e.g., ### 1. `path`)
    - Plain ```python blocks (fallback)

    Args:
        response: Claude's response text.

    Returns:
        List of dicts with 'path' and 'content' keys.
    """
    import re

    files = []
    seen_paths = set()

    # Pattern 1 (preferred): code block with # File: header on first line
    # Matches: ```python\n# File: path\n...```
    pattern1 = re.compile(
        r"```(\w*)\s*\n#\s*File:\s*([^\n\(]+)(?:\s*\([^\)]*\))?\s*\n(.*?)```",
        re.DOTALL,
    )

    for match in pattern1.finditer(response):
        path = match.group(2).strip()
        content = match.group(3).strip()

        if not path or path.startswith("(") or path in seen_paths:
            continue

        files.append({"path": path, "content": content})
        seen_paths.add(path)

    # Pattern 2: markdown header with backtick filename, followed by code block
    # Matches: ### 1. `path/to/file.py`\n```python\n...```
    # Also handles: **`path/to/file.py`**\n```python\n...```
    if not files:
        pattern2 = re.compile(
            r"(?:#{1,4}\s*\d*\.?\s*)?[`*]+([^`*\n]+)[`*]+\s*\n+```(\w*)\s*\n(.*?)```",
            re.DOTALL,
        )

        for match in pattern2.finditer(response):
            path = match.group(1).strip()
            content = match.group(3).strip()

            # Clean up path (remove leading/trailing punctuation)
            path = path.strip("`*: ")

            if not path or path in seen_paths:
                continue

            # Validate it looks like a file path
            if "/" in path or path.endswith((".py", ".md", ".yaml", ".yml", ".json", ".txt", ".gitignore")):
                files.append({"path": path, "content": content})
                seen_paths.add(path)

    # Pattern 3: code block with path in a comment at start (various styles)
    # Matches: ```python\n# path/to/file.py\n...``` or ```python\n// path/to/file.js\n...```
    if not files:
        pattern3 = re.compile(
            r"```(\w+)\s*\n(?:#|//)\s*([^\n]+\.(?:py|js|ts|yaml|yml|json|md|txt))\s*\n(.*?)```",
            re.DOTALL,
        )

        for match in pattern3.finditer(response):
            path = match.group(2).strip()
            content = match.group(3).strip()

            if not path or path in seen_paths:
                continue

            files.append({"path": path, "content": content})
            seen_paths.add(path)

    # Pattern 4 (fallback): any code block, try to extract path from first line or infer
    if not files:
        pattern4 = re.compile(r"```(\w*)\s*\n(.*?)```", re.DOTALL)

        for i, match in enumerate(pattern4.finditer(response)):
            lang = match.group(1) or "python"
            content = match.group(2).strip()

            # Skip empty or very short blocks
            if not content or len(content) < 20:
                continue

            # Try to find a path-like first line
            first_line = content.split("\n")[0].strip()
            path = None

            # Check if first line is a file path comment
            if first_line.startswith(("#", "//", "<!--")):
                potential_path = first_line.lstrip("#/<!- ").rstrip(" ->")
                if "/" in potential_path or "." in potential_path:
                    path = potential_path
                    content = "\n".join(content.split("\n")[1:]).strip()

            # If no path found but has Python code, generate a name
            if not path and lang == "python" and ("def " in content or "class " in content):
                path = f"implementation_{i}.py"

            if path and path not in seen_paths:
                files.append({"path": path, "content": content})
                seen_paths.add(path)

    return files


def write_implementation_files(
    files: list[dict],
    repo_root: Path,
    test_files: list[str] | None = None,
) -> list[str]:
    """Write implementation files to disk.

    Args:
        files: List of file dicts with 'path' and 'content'.
        repo_root: Repository root path.
        test_files: List of test file paths to protect from overwrite.

    Returns:
        List of written file paths.
    """
    written = []

    # Build set of protected test file paths
    protected_paths = set()
    if test_files:
        for tf in test_files:
            protected_paths.add(str(Path(tf).resolve()))

    for file_info in files:
        path = file_info["path"]
        content = file_info["content"]

        # Make path absolute if relative
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = repo_root / path

        # SAFETY: Never overwrite test files
        resolved_path = str(file_path.resolve())
        if resolved_path in protected_paths:
            print(f"    [WARN] Skipping write to protected test file: {path}")
            continue

        # SAFETY: Never write to tests/ directory during implementation
        path_str = str(file_path)
        if "/tests/" in path_str or "\\tests\\" in path_str or path_str.startswith("tests"):
            print(f"    [WARN] Skipping write to tests/ directory: {path}")
            continue

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        file_path.write_text(content, encoding="utf-8")
        written.append(str(file_path))

    return written


def implement_code(state: TestingWorkflowState) -> dict[str, Any]:
    """N4: Generate implementation code using Claude.

    Args:
        state: Current workflow state.

    Returns:
        State updates with implementation files.
    """
    iteration_count = state.get("iteration_count", 0)
    print(f"\n[N4] Generating implementation (iteration {iteration_count})...")

    # Check for mock mode
    if state.get("mock_mode"):
        return _mock_implement_code(state)

    # Get repo root
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    # Build prompt
    prompt = build_implementation_prompt(state)

    # Save prompt to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "implementation-prompt.md", prompt)
    else:
        file_num = state.get("file_counter", 0)

    print("    Calling Claude for implementation...")

    # Call Claude
    response, error = call_claude_headless(prompt)

    if error:
        print(f"    [ERROR] {error}")
        return {
            "error_message": f"Implementation failed: {error}",
            "file_counter": file_num,
        }

    # Save response to audit trail
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "implementation-response.md", response)

    # Parse response
    files = parse_implementation_response(response)

    if not files:
        print("    [WARN] No implementation files extracted from response")
        print("    Response length:", len(response))
        # Sanitize for Windows console (remove non-ASCII)
        sanitized = response.encode("ascii", errors="replace").decode("ascii")
        print("    Response preview (first 500 chars):")
        print("    " + sanitized[:500].replace("\n", "\n    "))
        print("    ...")
        print("    Response preview (last 500 chars):")
        print("    " + sanitized[-500:].replace("\n", "\n    "))

        # Save full response for debugging
        if audit_dir.exists():
            file_num = next_file_number(audit_dir)
            save_audit_file(audit_dir, file_num, "failed-response-full.md", response)
            print(f"    Full response saved to audit trail")

        return {
            "error_message": "No implementation files extracted from Claude response",
            "file_counter": file_num,
        }

    print(f"    Extracted {len(files)} implementation file(s)")

    # Write files (protect test files from accidental overwrite)
    test_files = state.get("test_files", [])
    written_paths = write_implementation_files(files, repo_root, test_files)
    print(f"    Written: {', '.join(written_paths)}")

    # Save implementation to audit trail
    if audit_dir.exists():
        for i, file_info in enumerate(files):
            file_num = next_file_number(audit_dir)
            content = f"# File: {file_info['path']}\n\n```python\n{file_info['content']}\n```"
            save_audit_file(audit_dir, file_num, f"implementation-{i}.md", content)

    # Log implementation
    log_workflow_execution(
        target_repo=repo_root,
        issue_number=state.get("issue_number", 0),
        workflow_type="testing",
        event="implementation_generated",
        details={
            "files": written_paths,
            "iteration": iteration_count,
        },
    )

    return {
        "implementation_files": written_paths,
        "file_counter": file_num,
        "error_message": "",
    }


def _mock_implement_code(state: TestingWorkflowState) -> dict[str, Any]:
    """Mock implementation for testing."""
    issue_number = state.get("issue_number", 42)
    iteration_count = state.get("iteration_count", 0)
    repo_root_str = state.get("repo_root", "")
    repo_root = Path(repo_root_str) if repo_root_str else get_repo_root()

    # Generate mock implementation
    mock_content = f'''"""Implementation for Issue #{issue_number}."""


def login(username: str, password: str) -> dict:
    """Handle user login.

    Args:
        username: User's username.
        password: User's password.

    Returns:
        Dict with success status and session info.
    """
    if not username or not password:
        return {{"success": False, "error": "Invalid credentials"}}

    # Mock successful login
    return {{"success": True, "session_id": "mock-session-123"}}


def validate_input(data: str) -> bool:
    """Validate input data.

    Args:
        data: Input string to validate.

    Returns:
        True if valid, False otherwise.
    """
    if not data or len(data) < 1:
        return False
    return True


def log_error(message: str) -> None:
    """Log an error message.

    Args:
        message: Error message to log.
    """
    # Mock implementation
    print(f"ERROR: {{message}}")
'''

    # Write to file
    impl_path = repo_root / "agentos" / f"issue_{issue_number}_impl.py"
    impl_path.parent.mkdir(parents=True, exist_ok=True)
    impl_path.write_text(mock_content, encoding="utf-8")

    # Save to audit trail
    audit_dir = Path(state.get("audit_dir", ""))
    if audit_dir.exists():
        file_num = next_file_number(audit_dir)
        save_audit_file(audit_dir, file_num, "implementation.py", mock_content)
    else:
        file_num = state.get("file_counter", 0)

    print(f"    [MOCK] Generated implementation: {impl_path}")

    return {
        "implementation_files": [str(impl_path)],
        "file_counter": file_num,
        "error_message": "",
    }
