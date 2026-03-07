"""Prompt construction for code generation.

Builds prompts for single-file generation, diff-based generation, and retries.
"""

from pathlib import Path

from assemblyzero.utils.file_type import get_file_type_info

from .context import summarize_file_for_context


# Issue #309: Maximum retry attempts per file
MAX_FILE_RETRIES = 2


def build_stable_system_prompt(
    lld_content: str,
    repo_structure: str = "",
    path_enforcement_section: str = "",
    test_content: str = "",
    context_content: str = "",
) -> str:
    """Build the stable system prompt that is identical across all files.

    Issue #643: Content that doesn't change per-file goes here so Anthropic's
    prompt caching can reuse it. The system prompt is sent once and cached;
    files 2+ read from cache at 10% cost.

    Args:
        lld_content: The full LLD specification.
        repo_structure: Repository directory tree for path grounding.
        path_enforcement_section: Allowed-paths prompt section.
        test_content: Test file content that must pass.
        context_content: Injected architectural context.

    Returns:
        System prompt string containing all stable content.
    """
    prompt = f"""You are a file generator. You will be given a file to implement from an LLD specification.

## LLD Specification

{lld_content}

"""

    if path_enforcement_section:
        prompt += path_enforcement_section + "\n"

    if repo_structure:
        prompt += f"""## Repository Structure

The actual directory layout of this repository:

```
{repo_structure}
```

Use these real paths — do NOT invent paths that don't exist.

"""

    if context_content:
        prompt += f"""## Additional Context

{context_content}

"""

    if test_content:
        prompt += f"""## Tests That Must Pass

```python
{test_content}
```

"""

    return prompt


def build_single_file_prompt(
    filepath: str,
    file_spec: dict,
    lld_content: str,
    completed_files: list[tuple[str, str]],
    repo_root: Path,
    test_content: str = "",
    previous_error: str = "",
    path_enforcement_section: str = "",
    context_content: str = "",
    repo_structure: str = "",
) -> str:
    """Build per-file user message prompt.

    Issue #643: Stable content (LLD, repo structure, path enforcement, tests,
    context) has been moved to build_stable_system_prompt(). This function now
    only builds per-file content. The old parameters are kept for backward
    compatibility but ignored when a system prompt is used.

    Issue #188: Added path_enforcement_section parameter to inject allowed paths.
    Issue #288: Added context_content parameter for injected architectural context.
    Issue #445: Added repo_structure parameter to ground Claude in actual layout.
    """

    change_type = file_spec.get("change_type", "Add")
    description = file_spec.get("description", "")

    prompt = f"""# Implementation Request: {filepath}

## Task

Write the complete contents of `{filepath}`.

Change type: {change_type}
Description: {description}

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

    # Issue #373: Include previously completed files with trimmed context.
    # Only the most recent file (N-1) gets full content for continuity.
    # All earlier files get signature-only summaries to reduce prompt size.
    if completed_files:
        prompt += "## Previously Implemented Files\n\n"
        prompt += "These files have already been implemented. Use them for imports and references:\n\n"
        for idx, (prev_path, prev_content) in enumerate(completed_files):
            is_most_recent = (idx == len(completed_files) - 1)
            if is_most_recent:
                # Most recent file: full content for continuity
                prompt += f"""### {prev_path} (full)

```python
{prev_content}
```

"""
            else:
                # Earlier files: signatures only to save context
                summary = summarize_file_for_context(prev_content)
                prompt += f"""### {prev_path} (signatures)

```python
{summary}
```

"""

    # Include previous error if this is a retry... wait, no retries!
    # Actually we might loop back from green phase failure, so include error context
    if previous_error:
        prompt += f"""## Previous Attempt Failed — Fix These Specific Errors

The previous implementation failed these tests:

```
{previous_error}
```

Read the error messages carefully and fix the root cause in your implementation.

"""

    # Issue #447: File-type-aware output format
    info = get_file_type_info(filepath)
    tag = info["language_tag"]
    descriptor = info["content_descriptor"]
    block_tag = tag if tag else ""

    prompt += f"""## Output Format

Output ONLY the file contents. No explanations, no markdown headers, just the {descriptor}.

```{block_tag}
# Your {descriptor} here
```

IMPORTANT:
- Output the COMPLETE file contents
- Do NOT output a summary or description
- Do NOT say "I've implemented..."
- Just output the {descriptor} in a single fenced code block
"""

    return prompt


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
