"""N4: Implement Code node for TDD Testing Workflow.

Uses Claude to generate implementation code that passes the tests.
This is a temporary bridge until #87 (Implementation Workflow) is complete.
"""

import os
import shutil
import subprocess
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
            # Use text output mode (default) - simpler and more reliable
            # --print (-p): non-interactive mode, prints response to stdout
            # --dangerously-skip-permissions: required for non-interactive file writes
            cmd = [
                claude_cli,
                "--print",
                "--dangerously-skip-permissions",
            ]

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
                stderr_preview = result.stderr[:200] if result.stderr else "no stderr"
                print(f"    [WARN] CLI exit code {result.returncode}: {stderr_preview}")
                print("    Falling back to Anthropic SDK...")
            else:
                print("    [WARN] CLI returned empty response, trying SDK...")

        except subprocess.TimeoutExpired:
            return "", "Claude CLI execution timed out (10 minutes)"
        except Exception as e:
            print(f"    [WARN] CLI error: {e}, trying SDK...")

    # Fall back to Anthropic SDK
    try:
        import anthropic

        client = anthropic.Anthropic()

        message = client.messages.create(
            model="claude-sonnet-4-20250514",  # Use Sonnet for implementation
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
    - ```python with # File: header
    - ```gitignore, ```markdown, etc. with # File: header
    - Plain ```python blocks (fallback)

    Args:
        response: Claude's response text.

    Returns:
        List of dicts with 'path' and 'content' keys.
    """
    import re

    files = []

    # Primary pattern: any code block with # File: header
    # Matches: ```python, ```gitignore, ```markdown, ```yaml, etc.
    # The # File: comment must be on the first line after the fence
    pattern = re.compile(
        r"```\w*\s*\n#\s*File:\s*([^\n\(]+)(?:\s*\([^\)]*\))?\s*\n(.*?)```",
        re.DOTALL,
    )

    for match in pattern.finditer(response):
        path = match.group(1).strip()
        content = match.group(2).strip()

        # Skip invalid paths
        if not path or path.startswith("("):
            continue

        files.append({"path": path, "content": content})

    # Fallback: look for python blocks without explicit # File: header
    if not files:
        code_pattern = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)
        for i, match in enumerate(code_pattern.finditer(response)):
            content = match.group(1).strip()
            # Try to infer filename from content
            if "def " in content or "class " in content:
                files.append({
                    "path": f"implementation_{i}.py",
                    "content": content,
                })

    return files


def write_implementation_files(
    files: list[dict],
    repo_root: Path,
) -> list[str]:
    """Write implementation files to disk.

    Args:
        files: List of file dicts with 'path' and 'content'.
        repo_root: Repository root path.

    Returns:
        List of written file paths.
    """
    written = []

    for file_info in files:
        path = file_info["path"]
        content = file_info["content"]

        # Make path absolute if relative
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = repo_root / path

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
        print("    Response preview:", response[:200])

        return {
            "error_message": "No implementation files extracted from Claude response",
            "file_counter": file_num,
        }

    print(f"    Extracted {len(files)} implementation file(s)")

    # Write files
    written_paths = write_implementation_files(files, repo_root)
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
