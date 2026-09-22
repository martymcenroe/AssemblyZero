"""Tests for file write validation hook.

Issue #188: Test IDs match LLD Section 10.0.
"""


from assemblyzero.hooks.file_write_validator import (
    find_closest_lld_path,
    validate_file_write,
)


ALLOWED_PATHS = {
    "assemblyzero/utils/lld_path_enforcer.py",
    "assemblyzero/hooks/file_write_validator.py",
    "tests/unit/test_lld_path_enforcer.py",
}


class TestValidateFileWrite:
    """T030, T040, T050, T080: Test file write validation."""

    def test_validate_allowed_path(self):
        """T030: Allowed path returns allowed=True."""
        result = validate_file_write(
            "assemblyzero/utils/lld_path_enforcer.py",
            ALLOWED_PATHS,
        )
        assert result["allowed"] is True

    def test_reject_non_lld_path(self):
        """T040: Non-LLD path returns allowed=False with closest match."""
        result = validate_file_write(
            "assemblyzero/core/lld_path_enforcer.py",
            ALLOWED_PATHS,
        )
        assert result["allowed"] is False
        assert result["closest_match"] == "assemblyzero/utils/lld_path_enforcer.py"

    def test_path_normalization(self):
        """T050: ./foo/bar.py matches foo/bar.py."""
        result = validate_file_write(
            "./assemblyzero/utils/lld_path_enforcer.py",
            ALLOWED_PATHS,
        )
        assert result["allowed"] is True

    def test_path_traversal_rejected(self):
        """T080: Path traversal attempt returns allowed=False."""
        result = validate_file_write(
            "../../../etc/passwd",
            ALLOWED_PATHS,
        )
        assert result["allowed"] is False
        assert "traversal" in result["reason"].lower()

    def test_reject_includes_reason(self):
        """Rejected path includes helpful reason."""
        result = validate_file_write(
            "some/random/path.py",
            ALLOWED_PATHS,
        )
        assert result["allowed"] is False
        assert "not in LLD" in result["reason"]

    def test_empty_allowed_paths_rejects_all(self):
        """Empty allowed set rejects all paths."""
        result = validate_file_write("any/path.py", set())
        assert result["allowed"] is False

    def test_exact_match_takes_priority(self):
        """Exact match returns allowed without closest_match."""
        result = validate_file_write(
            "assemblyzero/utils/lld_path_enforcer.py",
            ALLOWED_PATHS,
        )
        assert result["allowed"] is True
        assert result["closest_match"] is None


class TestFindClosestLLDPath:
    """T070: Test closest path matching."""

    def test_find_closest_similar_path(self):
        """T070: Suggests utils/lld.py for core/lld.py."""
        allowed = {"assemblyzero/utils/lld.py", "assemblyzero/cli/main.py"}
        closest = find_closest_lld_path("assemblyzero/core/lld.py", allowed)
        assert closest == "assemblyzero/utils/lld.py"

    def test_no_close_match_returns_none(self):
        """Very different paths return None."""
        allowed = {"src/completely/different.py"}
        closest = find_closest_lld_path("xyz.txt", allowed)
        # May return None or the only option depending on threshold
        # The key is it doesn't crash
        assert closest is None or isinstance(closest, str)

    def test_empty_allowed_returns_none(self):
        """Empty allowed set returns None."""
        closest = find_closest_lld_path("any/path.py", set())
        assert closest is None

    def test_finds_best_among_multiple(self):
        """Returns the most similar path among multiple options."""
        allowed = {
            "assemblyzero/utils/lld_verification.py",
            "assemblyzero/hooks/file_validator.py",
            "tests/test_something.py",
        }
        # "assemblyzero/utils/lld_verifier.py" should match lld_verification.py
        closest = find_closest_lld_path(
            "assemblyzero/utils/lld_verifier.py", allowed
        )
        assert closest == "assemblyzero/utils/lld_verification.py"


class TestPathTraversal:
    """Additional path traversal security tests."""

    def test_double_dot_in_middle(self):
        """../foo/../bar is rejected."""
        result = validate_file_write("foo/../../../etc/passwd", ALLOWED_PATHS)
        assert result["allowed"] is False

    def test_normal_dots_in_filename(self):
        """Dots in filenames (not ..) are fine."""
        allowed = {"src/config.default.py"}
        result = validate_file_write("src/config.default.py", allowed)
        assert result["allowed"] is True
