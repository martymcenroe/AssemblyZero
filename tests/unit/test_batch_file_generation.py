"""Tests for Issue #647: Batch small file generation.

Verifies:
- build_batch_file_prompt() produces correctly formatted multi-file prompt
- parse_batch_response() splits response by file markers
- parse_batch_response() handles missing files gracefully
- Batch of 3 small files produces 1 API call, not 3 (unit-level verification)
"""

import pytest

from assemblyzero.workflows.testing.nodes.implementation.prompts import (
    build_batch_file_prompt,
)
from assemblyzero.workflows.testing.nodes.implementation.parsers import (
    parse_batch_response,
)


# ---------------------------------------------------------------------------
# build_batch_file_prompt tests
# ---------------------------------------------------------------------------


class TestBuildBatchFilePrompt:
    """Verify batch prompt format."""

    def test_contains_all_file_markers(self):
        specs = [
            {"path": "src/a.py", "change_type": "Add", "description": "module a"},
            {"path": "src/b.py", "change_type": "Add", "description": "module b"},
        ]
        result = build_batch_file_prompt(specs)
        assert "=== FILE: src/a.py ===" in result
        assert "=== FILE: src/b.py ===" in result

    def test_contains_descriptions(self):
        specs = [
            {"path": "src/a.py", "change_type": "Add", "description": "handles auth"},
        ]
        result = build_batch_file_prompt(specs)
        assert "handles auth" in result

    def test_contains_output_format(self):
        specs = [
            {"path": "src/a.py", "change_type": "Add", "description": "foo"},
        ]
        result = build_batch_file_prompt(specs)
        assert "Output Format" in result
        assert "=== FILE:" in result

    def test_single_file_batch(self):
        specs = [
            {"path": "tests/conftest.py", "change_type": "Add", "description": "fixtures"},
        ]
        result = build_batch_file_prompt(specs)
        assert "=== FILE: tests/conftest.py ===" in result

    def test_five_file_batch(self):
        specs = [
            {"path": f"src/f{i}.py", "change_type": "Add", "description": f"file {i}"}
            for i in range(5)
        ]
        result = build_batch_file_prompt(specs)
        for i in range(5):
            assert f"=== FILE: src/f{i}.py ===" in result


# ---------------------------------------------------------------------------
# parse_batch_response tests
# ---------------------------------------------------------------------------


class TestParseBatchResponse:
    """Verify batch response parsing."""

    def test_parses_two_files(self):
        response = """=== FILE: src/a.py ===
```python
def hello():
    return "a"
```

=== FILE: src/b.py ===
```python
def world():
    return "b"
```
"""
        result = parse_batch_response(response, ["src/a.py", "src/b.py"])
        assert result["src/a.py"] is not None
        assert "hello" in result["src/a.py"]
        assert result["src/b.py"] is not None
        assert "world" in result["src/b.py"]

    def test_missing_file_returns_none(self):
        response = """=== FILE: src/a.py ===
```python
def hello():
    return "a"
```
"""
        result = parse_batch_response(response, ["src/a.py", "src/missing.py"])
        assert result["src/a.py"] is not None
        assert result["src/missing.py"] is None

    def test_empty_response_returns_all_none(self):
        result = parse_batch_response("", ["src/a.py", "src/b.py"])
        assert result["src/a.py"] is None
        assert result["src/b.py"] is None

    def test_malformed_code_block_returns_none(self):
        response = """=== FILE: src/a.py ===
This is not a code block, just text.
"""
        result = parse_batch_response(response, ["src/a.py"])
        assert result["src/a.py"] is None

    def test_three_files_parsed(self):
        response = """=== FILE: src/a.py ===
```python
a = 1
```

=== FILE: src/b.py ===
```python
b = 2
```

=== FILE: src/c.py ===
```python
c = 3
```
"""
        result = parse_batch_response(response, ["src/a.py", "src/b.py", "src/c.py"])
        assert all(v is not None for v in result.values())

    def test_unexpected_file_ignored(self):
        """Files not in expected_paths should not appear in results."""
        response = """=== FILE: src/a.py ===
```python
a = 1
```

=== FILE: src/unexpected.py ===
```python
x = 99
```
"""
        result = parse_batch_response(response, ["src/a.py"])
        assert "src/a.py" in result
        assert "src/unexpected.py" not in result

    def test_handles_preamble_text(self):
        """Text before the first marker should be ignored."""
        response = """Here are the implementations:

=== FILE: src/a.py ===
```python
a = 1
```
"""
        result = parse_batch_response(response, ["src/a.py"])
        assert result["src/a.py"] is not None
        assert "a = 1" in result["src/a.py"]
