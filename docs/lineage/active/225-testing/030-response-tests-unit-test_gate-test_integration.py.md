

```python
"""Integration tests for the full test-gate workflow.

Issue #225: Hard gate wrapper for skipped test enforcement.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.test_gate.models import SkippedTest

# Import the main entry point
import sys

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools import test_gate  # noqa: E402 (ensure package imports work)


# We need to be careful importing test-gate.py since it has a hyphen
# Instead, we test through the module's main function by importing directly

_GATE_SCRIPT = _PROJECT_ROOT / "tools" / "test-gate.py"


def _load_test_gate_main():
    """Dynamically load test-gate.py and return its main function."""
    spec = importlib.util.spec_from_file_location("test_gate_main", _GATE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


PYTEST_OUTPUT_NO_SKIPS = """\
tests/test_a.py::test_one PASSED
tests/test_a.py::test_two PASSED
===== 2 passed in 0.5s =====
"""

PYTEST_OUTPUT_WITH_SKIPS = """\
tests/test_a.py::test_one PASSED
tests/test_auth.py::test_oauth SKIPPED (External provider)
tests/test_utils.py::test_deprecated_helper SKIPPED (Deprecated)
===== 1 passed, 2 skipped in 0.5s =====
"""

PYTEST_OUTPUT_WITH_CRITICAL_SKIP = """\
tests/test_security.py::test_xss_prevention SKIPPED (TODO implement)
===== 1 skipped in 0.1s =====
"""

AUDIT_BLOCK_FOR_SKIPS = """\
<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_auth.py::test_oauth | VERIFIED | External provider | marty | |
| tests/test_utils.py::test_deprecated_* | EXPECTED | Deprecated | marty | |
<!-- END SKIPPED TEST AUDIT -->
"""


class TestIntegrationNoSkips:
    """T150: No skips scenario."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_no_skips_returns_pytest_exit_code(self, mock_run: MagicMock) -> None:
        """T150: Clean test run passes through exit code."""
        mock_run.return_value = (0, PYTEST_OUTPUT_NO_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 0


class TestIntegrationMissingAudit:
    """T100: Missing audit block."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_skips_without_audit_fails(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T100: Skips without audit block returns exit 1."""
        monkeypatch.chdir(tmp_path)  # No .skip-audit.md in tmp_path
        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 1


class TestIntegrationWithAudit:
    """T130: All audited scenario."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_all_audited_passes(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T130: All skips audited returns pytest exit code."""
        monkeypatch.chdir(tmp_path)
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(AUDIT_BLOCK_FOR_SKIPS)

        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 0


class TestIntegrationUnaudited:
    """T110: Unaudited test scenario."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_unaudited_test_fails(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T110: Unaudited skip returns exit 1."""
        monkeypatch.chdir(tmp_path)
        # Audit that only covers auth, not utils
        partial_audit = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_auth.py::test_oauth | VERIFIED | External provider | marty | |
<!-- END SKIPPED TEST AUDIT -->"""
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(partial_audit)

        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 1


class TestIntegrationUnverifiedCritical:
    """T120: Unverified critical test scenario."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_unverified_critical_fails(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T120: Critical test with UNVERIFIED status returns exit 1."""
        monkeypatch.chdir(tmp_path)
        audit = """<!-- SKIPPED TEST AUDIT -->
| Test | Status | Justification | Owner | Expires |
|------|--------|---------------|-------|---------|
| tests/test_security.py::test_xss_prevention | UNVERIFIED | Needs review | | |
<!-- END SKIPPED TEST AUDIT -->"""
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(audit)

        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_CRITICAL_SKIP, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 1


class TestIntegrationBypass:
    """T140: Bypass flag scenario."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_bypass_logs_and_passes(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """T140: --skip-gate-bypass logs warning and passes through."""
        monkeypatch.chdir(tmp_path)
        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/", "--skip-gate-bypass", "Emergency hotfix for #500"])
        assert result == 0
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "Emergency hotfix" in captured.err

    @patch("tools.test_gate.parser.run_pytest")
    def test_bypass_empty_reason_fails(
        self, mock_run: MagicMock, capsys: pytest.CaptureFixture
    ) -> None:
        """Bypass with empty string is rejected."""
        mock_run.return_value = (0, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/", "--skip-gate-bypass", ""])
        assert result == 2


class TestIntegrationCommonFlags:
    """T160: Common pytest flags work."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_common_flags_preserved(self, mock_run: MagicMock) -> None:
        """T160: Common flags are passed through to pytest."""
        mock_run.return_value = (0, PYTEST_OUTPUT_NO_SKIPS, "")
        main = _load_test_gate_main()

        # These flags should not be consumed by the gate
        result = main([
            "tests/unit/",
            "-v",
            "--tb=short",
            "--cov=assemblyzero",
            "-k", "test_something",
            "-m", "not integration",
        ])
        assert result == 0

        # Verify flags were passed to pytest
        call_args = mock_run.call_args[0][0]
        assert "-v" in call_args
        assert "--tb=short" in call_args
        assert "--cov=assemblyzero" in call_args
        assert "-k" in call_args
        assert "test_something" in call_args


class TestIntegrationExitCodePreservation:
    """T020: Exit code preservation."""

    @patch("tools.test_gate.parser.run_pytest")
    def test_pytest_failure_preserved_when_no_skips(self, mock_run: MagicMock) -> None:
        """T020: Pytest failure exit code preserved when no skips."""
        mock_run.return_value = (1, "FAILED tests/test_a.py::test_one\n", "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 1

    @patch("tools.test_gate.parser.run_pytest")
    def test_pytest_failure_preserved_when_gate_passes(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T020: Pytest failure preserved even when gate passes."""
        monkeypatch.chdir(tmp_path)
        audit_file = tmp_path / ".skip-audit.md"
        audit_file.write_text(AUDIT_BLOCK_FOR_SKIPS)

        # Pytest returns 1 (some tests failed), but skips are audited
        mock_run.return_value = (1, PYTEST_OUTPUT_WITH_SKIPS, "")
        main = _load_test_gate_main()
        result = main(["tests/"])
        assert result == 1  # pytest exit code, not gate's
```
