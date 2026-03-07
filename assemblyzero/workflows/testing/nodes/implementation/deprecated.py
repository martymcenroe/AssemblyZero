"""Deprecated batch-mode functions maintained for backward compatibility.

Issue #272: These maintain old API while new code uses file-by-file approach.
"""

import re
from pathlib import Path
from typing import Any

from assemblyzero.workflows.testing.audit import get_repo_root
from assemblyzero.workflows.testing.state import TestingWorkflowState

from .claude_client import call_claude_for_file


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

    # Issue #498: Use structured failure summary when available
    test_failure_summary = state.get("test_failure_summary", "")
    e2e_failure_summary = state.get("e2e_failure_summary", "")
    error_feedback = test_failure_summary or e2e_failure_summary or green_phase_output

    if iteration_count > 0 and error_feedback:
        prompt += f"""## Previous Test Run (FAILED)

```
{error_feedback}
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
