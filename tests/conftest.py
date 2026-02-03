"""Pytest configuration for test suite."""

import sys
from pathlib import Path

# Ensure tools directory is importable
tools_dir = Path(__file__).parent.parent / "tools"
if str(tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(tools_dir.parent))


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (deselect with '-m \"not integration\"')"
    )