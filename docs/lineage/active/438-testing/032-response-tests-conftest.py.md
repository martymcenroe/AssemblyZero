```python
"""Pytest configuration for test suite."""

import os
import sys
from pathlib import Path

import pytest

# Ensure tools directory is importable
tools_dir = Path(__file__).parent.parent / "tools"
if str(tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(tools_dir.parent))


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )
    config.addinivalue_line(
        "markers",
        "e2e: End-to-end tests (deselect with '-m \"not e2e\"')",
    )
    config.addinivalue_line(
        "markers",
        "timeout(seconds): set a timeout for the test (requires pytest-timeout plugin)",
    )


@pytest.fixture
def mock_file_size(monkeypatch):
    """Factory fixture that patches os.path.getsize to return specified sizes for given paths.

    Usage:
        mock_file_size({"/path/to/file.log": 52_428_800})

    Files not in the map delegate to the real os.path.getsize.
    """
    _original_getsize = os.path.getsize

    def _mock(size_map: dict[str, int]) -> None:
        def _patched_getsize(path):
            str_path = str(path)
            if str_path in size_map:
                return size_map[str_path]
            return _original_getsize(str_path)

        monkeypatch.setattr("os.path.getsize", _patched_getsize)

    return _mock
```
