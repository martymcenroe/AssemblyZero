"""Tests for the PyPI publishing scaffold added to new_repo.py (#1074).

Validates the constant templates and the post-poetry-init mutations in
isolation — without invoking the full create_python_project() flow,
which depends on a network-enabled `poetry init` + `poetry add` and
takes ~30s. The integration test (does `new_repo.py NewPkg`
actually work end-to-end) is a manual smoke test by convention.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Make tools/ importable. Mirrors the conftest pattern other AZ tests use.
_TOOLS = Path(__file__).resolve().parent.parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from new_repo import (  # noqa: E402
    _PACKAGE_INIT_BODY,
    _PACKAGE_MAIN_BODY,
    _PYPROJECT_PYPI_BLOCK,
    create_github_workflows,
)


# ---------------------------------------------------------------------------
# Template constants
# ---------------------------------------------------------------------------


def test_package_init_body_formats_with_module_name():
    """__init__.py template substitutes {module} into the docstring."""
    rendered = _PACKAGE_INIT_BODY.format(module="boostgauge")
    assert '"""boostgauge package."""' in rendered


def test_package_main_body_has_main_entry_point():
    """__main__.py template defines main() and the if __name__ block."""
    rendered = _PACKAGE_MAIN_BODY.format(module="boostgauge")
    assert "def main() -> int:" in rendered
    assert 'if __name__ == "__main__":' in rendered
    assert "raise SystemExit(main())" in rendered
    # docstring mentions both invocation forms
    assert "python -m boostgauge" in rendered
    assert "boostgauge CLI script" in rendered


def test_pyproject_pypi_block_has_required_sections():
    """The injected pyproject block contains [tool.poetry.scripts] + [urls]."""
    rendered = _PYPROJECT_PYPI_BLOCK.format(
        module="boostgauge",
        github_user_repo="martymcenroe/boostgauge",
    )
    assert "[tool.poetry.scripts]" in rendered
    assert 'boostgauge = "boostgauge.__main__:main"' in rendered
    assert "[tool.poetry.urls]" in rendered
    assert 'Homepage = "https://github.com/martymcenroe/boostgauge"' in rendered
    assert 'Source = "https://github.com/martymcenroe/boostgauge"' in rendered
    assert 'Issues = "https://github.com/martymcenroe/boostgauge/issues"' in rendered


def test_pyproject_pypi_block_handles_underscored_module():
    """Module names with underscores are preserved (Python identifiers)."""
    rendered = _PYPROJECT_PYPI_BLOCK.format(
        module="multi_word",
        github_user_repo="user/multi-word",
    )
    assert 'multi_word = "multi_word.__main__:main"' in rendered
    # The repo URL uses the hyphenated form (Poetry distribution name).
    assert "https://github.com/user/multi-word" in rendered


# ---------------------------------------------------------------------------
# create_github_workflows release.yml integration
# ---------------------------------------------------------------------------


def test_create_github_workflows_writes_release_yml_when_pypi_enabled(tmp_path: Path):
    """With enable_pypi=True (default), release.yml is deployed alongside auto-reviewer.yml."""
    create_github_workflows(tmp_path, enable_pypi=True)
    workflows = tmp_path / ".github" / "workflows"
    assert (workflows / "auto-reviewer.yml").exists()
    assert (workflows / "release.yml").exists()


def test_create_github_workflows_skips_release_yml_when_pypi_disabled(tmp_path: Path):
    """With enable_pypi=False, only auto-reviewer.yml is deployed."""
    create_github_workflows(tmp_path, enable_pypi=False)
    workflows = tmp_path / ".github" / "workflows"
    assert (workflows / "auto-reviewer.yml").exists()
    assert not (workflows / "release.yml").exists()


def test_release_yml_uses_oidc_trusted_publisher(tmp_path: Path):
    """release.yml has the OIDC permissions block — no PyPI token in secrets."""
    create_github_workflows(tmp_path, enable_pypi=True)
    content = (tmp_path / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "id-token: write" in content
    assert "environment: pypi" in content
    assert "pypa/gh-action-pypi-publish" in content
    # No tokens/passwords — the whole point of OIDC.
    assert "PYPI_TOKEN" not in content
    assert "PYPI_API_TOKEN" not in content
    assert "password:" not in content


def test_release_yml_triggers_on_semver_tag(tmp_path: Path):
    """release.yml fires on tags like v0.1.0, v1.2.3 — semver pattern."""
    create_github_workflows(tmp_path, enable_pypi=True)
    content = (tmp_path / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    # Should match the v*.*.* pattern
    assert re.search(r'tags:\s*\n\s*-\s*"v\*\.\*\.\*"', content), (
        "release.yml should trigger on tags matching v*.*.*"
    )


def test_release_yml_uses_lf_line_endings(tmp_path: Path):
    """release.yml is written with LF on Windows (matches AZ fleet convention)."""
    create_github_workflows(tmp_path, enable_pypi=True)
    raw = (tmp_path / ".github" / "workflows" / "release.yml").read_bytes()
    # No CRLF — Windows would default to CRLF unless newline="" is passed.
    assert b"\r\n" not in raw, "release.yml must use LF line endings"
