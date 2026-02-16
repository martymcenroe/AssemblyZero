"""Tests for context trimming in implementation workflow.

Issue #373: Fix TDD workflow timeout by trimming accumulated context
and increasing CLI timeout.
"""

import pytest

from assemblyzero.workflows.testing.nodes.implement_code import (
    summarize_file_for_context,
    compute_dynamic_timeout,
    CLI_TIMEOUT,
)


# =============================================================================
# summarize_file_for_context()
# =============================================================================


class TestSummarizeFileForContext:
    """Tests for file context summarization."""

    def test_extracts_imports(self):
        """Imports should be preserved in summary."""
        code = '''"""Module docstring."""

import os
from pathlib import Path
from typing import TypedDict

def foo():
    """Do something."""
    x = 1
    y = 2
    return x + y
'''
        summary = summarize_file_for_context(code)
        assert "import os" in summary
        assert "from pathlib import Path" in summary
        assert "from typing import TypedDict" in summary

    def test_extracts_function_signatures(self):
        """Function signatures should appear in summary."""
        code = '''def analyze(filepath: str, max_size: int = 1000) -> list[str]:
    """Analyze a file for issues.

    Args:
        filepath: Path to file.
        max_size: Maximum file size.
    """
    content = open(filepath).read()
    results = []
    for line in content.split("\\n"):
        if len(line) > max_size:
            results.append(line)
    return results
'''
        summary = summarize_file_for_context(code)
        assert "def analyze(filepath: str, max_size: int = 1000) -> list[str]:" in summary
        assert "Analyze a file for issues." in summary
        # Implementation body should NOT be in summary
        assert "open(filepath).read()" not in summary

    def test_extracts_class_and_methods(self):
        """Class definitions and their method signatures should appear."""
        code = '''class MyProcessor:
    """Process things."""

    def __init__(self, config: dict):
        """Initialize processor."""
        self.config = config
        self.results = []

    def process(self, data: str) -> bool:
        """Process the data."""
        for item in data.split(","):
            self.results.append(item.strip())
        return True
'''
        summary = summarize_file_for_context(code)
        assert "class MyProcessor:" in summary
        assert "Process things." in summary
        assert "def __init__(self, config: dict):" in summary
        assert "def process(self, data: str) -> bool:" in summary
        # Method bodies should NOT be in summary
        assert "self.results.append" not in summary

    def test_preserves_module_docstring(self):
        """Module-level docstring should be preserved."""
        code = '''"""This is the module docstring.

It describes what the module does.
"""

import os

def foo():
    pass
'''
        summary = summarize_file_for_context(code)
        assert "This is the module docstring." in summary

    def test_preserves_constants(self):
        """Short module-level assignments (constants) should be preserved."""
        code = '''MAX_RETRIES = 3
DEFAULT_TIMEOUT = 300

def foo():
    pass
'''
        summary = summarize_file_for_context(code)
        assert "MAX_RETRIES = 3" in summary
        assert "DEFAULT_TIMEOUT = 300" in summary

    def test_dramatically_shorter_than_original(self):
        """Summary should be significantly smaller than the original."""
        # Simulate a realistic ~500 line file
        code = '"""Big module."""\n\nimport os\nfrom pathlib import Path\n\n'
        for i in range(20):
            code += f'def function_{i}(arg1: str, arg2: int = 0) -> bool:\n'
            code += f'    """Function {i} docstring."""\n'
            for j in range(20):
                code += f'    line_{j} = arg1 + str(arg2 + {j})\n'
            code += '    return True\n\n'

        summary = summarize_file_for_context(code)
        # Summary should be much smaller
        assert len(summary) < len(code) * 0.3  # Less than 30% of original

    def test_handles_syntax_error_gracefully(self):
        """Invalid Python should produce a truncated fallback, not crash."""
        code = "def broken(:\n    pass\nclass also broken{}"
        summary = summarize_file_for_context(code)
        assert len(summary) > 0
        assert "truncated" in summary.lower() or "syntax" in summary.lower()

    def test_handles_empty_file(self):
        """Empty file should produce empty-ish summary."""
        summary = summarize_file_for_context("")
        assert isinstance(summary, str)

    def test_handles_typeddict(self):
        """TypedDict class definitions should be captured."""
        code = '''from typing import TypedDict


class Config(TypedDict):
    """Configuration options."""
    name: str
    value: int
    enabled: bool
'''
        summary = summarize_file_for_context(code)
        assert "class Config(TypedDict):" in summary
        assert "from typing import TypedDict" in summary


# =============================================================================
# compute_dynamic_timeout()
# =============================================================================


class TestComputeDynamicTimeout:
    """Tests for dynamic timeout calculation."""

    def test_small_prompt_gets_base_timeout(self):
        """Short prompts should get close to the base 300s timeout."""
        timeout = compute_dynamic_timeout("short prompt")
        assert timeout == 300

    def test_large_prompt_gets_higher_timeout(self):
        """Large prompts should scale up the timeout."""
        # 88KB prompt (like the one that failed)
        large_prompt = "x" * 88000
        timeout = compute_dynamic_timeout(large_prompt)
        assert timeout > 300
        assert timeout == min(300 + 88, CLI_TIMEOUT)

    def test_timeout_capped_at_cli_timeout(self):
        """Timeout should never exceed CLI_TIMEOUT."""
        huge_prompt = "x" * 1_000_000
        timeout = compute_dynamic_timeout(huge_prompt)
        assert timeout == CLI_TIMEOUT

    def test_medium_prompt_scales_linearly(self):
        """50KB prompt should get ~350s timeout."""
        medium_prompt = "x" * 50000
        timeout = compute_dynamic_timeout(medium_prompt)
        assert timeout == 350


# =============================================================================
# CLI_TIMEOUT constant
# =============================================================================


class TestTimeoutConstants:
    """Verify timeout constants are set correctly."""

    def test_cli_timeout_is_600(self):
        """Issue #373: CLI_TIMEOUT should be 600s."""
        assert CLI_TIMEOUT == 600
