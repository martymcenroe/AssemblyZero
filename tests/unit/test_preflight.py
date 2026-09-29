import pytest
from assemblyzero.core.preflight import PreflightResult

class TestPreflightResult:
    """Tests for PreflightResult dataclass."""

    def test_dataclass_fields(self) -> None:
        """PreflightResult has all expected fields."""
        result = PreflightResult(
            passed=True,
            available_credentials=3,
            total_credentials=3,
            exhausted_names=[],
            model_reachable=True,
            warnings=[],
        )
        assert result.passed is True
        assert result.available_credentials == 3
        assert result.total_credentials == 3
        assert result.exhausted_names == []
        assert result.model_reachable is True
        assert result.warnings == []
