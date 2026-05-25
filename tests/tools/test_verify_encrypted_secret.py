"""Unit tests for tools/verify_encrypted_secret.py.

Tests the type-detection + checker functions against fixture content.
Does NOT invoke gpg (decryption is the script's I/O boundary; we test the
content-classification logic that runs after decrypt).

Issue: martymcenroe/AssemblyZero#1272
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(_TOOLS))

from verify_encrypted_secret import (  # noqa: E402
    check_pat,
    check_pem,
    check_text,
    infer_type,
)


_VALID_PEM_LINES = [
    "-----BEGIN RSA PRIVATE KEY-----",
] + [
    "A" * 64 for _ in range(25)
] + [
    "-----END RSA PRIVATE KEY-----",
]
VALID_PEM = "\n".join(_VALID_PEM_LINES) + "\n"

VALID_PKCS8_PEM_LINES = [
    "-----BEGIN PRIVATE KEY-----",
] + ["B" * 64 for _ in range(25)] + [
    "-----END PRIVATE KEY-----",
]
VALID_PKCS8_PEM = "\n".join(VALID_PKCS8_PEM_LINES) + "\n"

INVALID_PEM_NO_HEADERS = "just some random text\nwith multiple lines\n"

INVALID_PEM_TOO_SHORT = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "AAAA\n"
    "-----END RSA PRIVATE KEY-----\n"
)

VALID_CLASSIC_PAT = "0123456789abcdef" * 2 + "01234567"  # 40 chars
assert len(VALID_CLASSIC_PAT) == 40

VALID_FINEGRAINED_PAT = "github_pat_" + "A" * 60  # 71 chars

INVALID_PAT_WRONG_CHARS = "this is not a real token, has spaces and uppercase"
INVALID_PAT_MULTILINE = "ghp_AAAA1234567890ABCDEFGHIJ_klmnopqrstuvwxyz\nextra line"


class TestInferType:
    def test_pem_in_name(self):
        assert infer_type(Path("/x/cerberus-pem.gpg")) == "pem"
        assert infer_type(Path("/x/PEM-blob.gpg")) == "pem"

    def test_pat_in_name(self):
        assert infer_type(Path("/x/classic-pat.gpg")) == "pat"
        assert infer_type(Path("/x/PAT.gpg")) == "pat"

    def test_pem_wins_over_pat(self):
        assert infer_type(Path("/x/pem-and-pat.gpg")) == "pem"

    def test_fallback_text(self):
        assert infer_type(Path("/x/secret.gpg")) == "text"
        assert infer_type(Path("/x/notes.gpg")) == "text"


class TestCheckPem:
    def test_valid_rsa_pkcs1(self):
        ok, details = check_pem(VALID_PEM)
        assert ok, f"valid PEM rejected: {details}"
        assert details["has_begin_marker"]
        assert details["has_end_marker"]
        assert details["size_in_typical_range"]
        assert details["line_count_in_typical_range"]

    def test_valid_pkcs8(self):
        ok, _ = check_pem(VALID_PKCS8_PEM)
        assert ok

    def test_no_headers_rejected(self):
        ok, details = check_pem(INVALID_PEM_NO_HEADERS)
        assert not ok
        assert not details["has_begin_marker"]
        assert not details["has_end_marker"]

    def test_too_short_rejected(self):
        ok, details = check_pem(INVALID_PEM_TOO_SHORT)
        assert not ok
        assert details["has_begin_marker"]
        assert details["has_end_marker"]
        assert not details["size_in_typical_range"]

    def test_empty_rejected(self):
        ok, _ = check_pem("")
        assert not ok


class TestCheckPat:
    def test_classic_pat_valid(self):
        ok, details = check_pat(VALID_CLASSIC_PAT)
        assert ok
        assert details["is_single_line"]
        assert details["matches_classic_pat_pattern"]
        assert details["char_count"] == 40

    def test_classic_pat_with_trailing_newline(self):
        ok, _ = check_pat(VALID_CLASSIC_PAT + "\n")
        assert ok

    def test_finegrained_pat_valid(self):
        ok, details = check_pat(VALID_FINEGRAINED_PAT)
        assert ok
        assert details["matches_finegrained_pat_pattern"]

    def test_wrong_chars_rejected(self):
        ok, _ = check_pat(INVALID_PAT_WRONG_CHARS)
        assert not ok

    def test_multiline_rejected(self):
        ok, details = check_pat(INVALID_PAT_MULTILINE)
        assert not ok
        assert not details["is_single_line"]

    def test_empty_rejected(self):
        ok, _ = check_pat("")
        assert not ok


class TestCheckText:
    def test_nonempty_valid(self):
        ok, details = check_text("any content")
        assert ok
        assert details["non_empty"]

    def test_empty_rejected(self):
        ok, details = check_text("")
        assert not ok
        assert not details["non_empty"]
