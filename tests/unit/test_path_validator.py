"""Tests for path security validation (Issue #289).

Tests validate_context_path, is_secret_file, check_file_size,
and load_context_files.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from assemblyzero.workflows.testing.path_validator import (
    check_file_size,
    is_secret_file,
    load_context_files,
    validate_context_path,
)


class TestIsSecretFile:
    """Test secret file pattern matching."""

    @pytest.mark.parametrize("path", [
        ".env",
        ".env.local",
        ".env.production",
        "credentials.json",
        "aws-credentials",
        "secret.yaml",
        "my-secret-config.json",
        "server.pem",
        "private.key",
        "id_rsa",
        "id_ed25519",
        "keystore.p12",
        "cert.pfx",
        "app.jks",
    ])
    def test_rejects_secret_files(self, path):
        assert is_secret_file(path) is True

    @pytest.mark.parametrize("path", [
        "main.py",
        "README.md",
        "config.yaml",
        "test_env.py",
        "utils/helpers.py",
        "docs/architecture.md",
    ])
    def test_allows_safe_files(self, path):
        assert is_secret_file(path) is False


class TestCheckFileSize:
    """Test file size limit checks."""

    def test_within_limit(self, tmp_path):
        f = tmp_path / "small.txt"
        f.write_text("hello" * 10)
        ok, error = check_file_size(f)
        assert ok is True
        assert error == ""

    def test_exceeds_limit(self, tmp_path):
        f = tmp_path / "large.txt"
        f.write_bytes(b"x" * 200_000)
        ok, error = check_file_size(f, limit=100_000)
        assert ok is False
        assert "too large" in error.lower()
        assert "200,000" in error

    def test_custom_limit(self, tmp_path):
        f = tmp_path / "medium.txt"
        f.write_bytes(b"x" * 500)
        ok, _ = check_file_size(f, limit=100)
        assert ok is False

    def test_nonexistent_file(self, tmp_path):
        ok, error = check_file_size(tmp_path / "missing.txt")
        assert ok is False
        assert "cannot stat" in error.lower()


class TestValidateContextPath:
    """Test full path validation pipeline."""

    def test_valid_file(self, tmp_path):
        f = tmp_path / "context.py"
        f.write_text("# valid context")
        valid, error = validate_context_path(str(f), tmp_path)
        assert valid is True
        assert error == ""

    def test_relative_path(self, tmp_path):
        f = tmp_path / "src" / "module.py"
        f.parent.mkdir()
        f.write_text("# module")
        valid, error = validate_context_path("src/module.py", tmp_path)
        assert valid is True

    def test_rejects_traversal(self, tmp_path):
        valid, error = validate_context_path("../../../etc/passwd", tmp_path)
        assert valid is False
        assert "traversal" in error.lower()

    def test_rejects_path_outside_root(self, tmp_path):
        # Create a file outside project root
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("secret")
        try:
            valid, error = validate_context_path(str(outside), tmp_path)
            assert valid is False
            assert "outside project root" in error.lower()
        finally:
            outside.unlink(missing_ok=True)

    def test_rejects_secret_file(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("SECRET=value")
        valid, error = validate_context_path(str(f), tmp_path)
        assert valid is False
        assert "secret" in error.lower()

    def test_rejects_credentials(self, tmp_path):
        f = tmp_path / "credentials.json"
        f.write_text("{}")
        valid, error = validate_context_path(str(f), tmp_path)
        assert valid is False
        assert "secret" in error.lower()

    def test_rejects_nonexistent(self, tmp_path):
        valid, error = validate_context_path("missing.py", tmp_path)
        assert valid is False
        assert "not found" in error.lower()

    def test_rejects_directory(self, tmp_path):
        d = tmp_path / "subdir"
        d.mkdir()
        valid, error = validate_context_path(str(d), tmp_path)
        assert valid is False
        assert "not a file" in error.lower()

    def test_rejects_oversized(self, tmp_path):
        f = tmp_path / "huge.py"
        f.write_bytes(b"x" * 200_000)
        valid, error = validate_context_path(str(f), tmp_path)
        assert valid is False
        assert "too large" in error.lower()


class TestLoadContextFiles:
    """Test context file loading and concatenation."""

    def test_loads_single_file(self, tmp_path):
        f = tmp_path / "context.py"
        f.write_text("# context code")
        content, errors = load_context_files([str(f)], tmp_path)
        assert "# context code" in content
        assert errors == []

    def test_loads_multiple_files(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.md"
        f1.write_text("# file a")
        f2.write_text("# file b")
        content, errors = load_context_files([str(f1), str(f2)], tmp_path)
        assert "# file a" in content
        assert "# file b" in content
        assert errors == []

    def test_skips_invalid_files(self, tmp_path):
        good = tmp_path / "good.py"
        good.write_text("# good")
        bad_path = str(tmp_path / "missing.py")
        content, errors = load_context_files([str(good), bad_path], tmp_path)
        assert "# good" in content
        assert len(errors) == 1
        assert "REJECTED" in errors[0]

    def test_rejects_all_invalid(self, tmp_path):
        content, errors = load_context_files(["missing.py"], tmp_path)
        assert content == ""
        assert len(errors) == 1

    def test_empty_list(self, tmp_path):
        content, errors = load_context_files([], tmp_path)
        assert content == ""
        assert errors == []
