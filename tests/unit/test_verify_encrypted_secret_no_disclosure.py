"""verify_encrypted_secret.py never prints what it decrypted (#3278).

The tool's whole reason to exist is checking a blob without exposing it. Its
report used to print the first and last decrypted lines for every type, and a
token is one line, so a run printed the whole credential twice. The checks
below drive `main()`, which `tests/tools/test_verify_encrypted_secret.py` does
not, with `_decrypt` stood in, so no gpg runs and no real secret is involved.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / "tools" / "verify_encrypted_secret.py"

# Built at run time, and visibly not a credential.
SYNTHETIC_TOKEN = "ghp_" + "SYNTHETIC0TEST0VALUE0" * 2
PEM_BODY = "SYNTHETIC0PEM0BODY0LINE"
SYNTHETIC_PEM = "\n".join(
    ["-----BEGIN RSA PRIVATE KEY-----"]
    + [PEM_BODY + str(n).zfill(40) for n in range(28)]
    + ["-----END RSA PRIVATE KEY-----"]
) + "\n"


def _tool():
    spec = importlib.util.spec_from_file_location("verify_encrypted_secret_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(tmp_path, capsys, name, decrypted, *args):
    blob = tmp_path / name
    blob.write_bytes(b"ciphertext stand-in")
    tool = _tool()
    tool._decrypt = lambda path: decrypted
    code = tool.main([str(blob), *args])
    captured = capsys.readouterr()
    return code, captured.out + captured.err


def test_a_token_never_reaches_the_report(tmp_path, capsys):
    code, report = _run(tmp_path, capsys, "classic-pat.gpg", SYNTHETIC_TOKEN + "\n")
    assert SYNTHETIC_TOKEN not in report
    assert code == 0
    assert "VERDICT: VALID" in report


def test_a_token_in_a_blob_typed_as_text_never_reaches_the_report(tmp_path, capsys):
    _, report = _run(tmp_path, capsys, "notes.gpg", SYNTHETIC_TOKEN + "\n")
    assert SYNTHETIC_TOKEN not in report


def test_a_token_mislabelled_as_pem_never_reaches_the_report(tmp_path, capsys):
    """A filename decides the type, so `--type pem` must not be what makes a line safe."""
    code, report = _run(tmp_path, capsys, "cerberus-pem.gpg", SYNTHETIC_TOKEN + "\n")
    assert SYNTHETIC_TOKEN not in report
    assert code == 1


def test_a_multi_line_text_blob_shows_neither_end(tmp_path, capsys):
    first, last = "SYNTHETIC-first-line-value", "SYNTHETIC-last-line-value"
    _, report = _run(tmp_path, capsys, "notes.gpg", f"{first}\nmiddle\n{last}\n")
    assert first not in report
    assert last not in report


def test_a_valid_pem_reports_its_markers_without_its_body(tmp_path, capsys):
    code, report = _run(tmp_path, capsys, "cerberus-pem.gpg", SYNTHETIC_PEM)
    assert code == 0
    assert "has_begin_marker: True" in report
    assert "has_end_marker: True" in report
    assert PEM_BODY not in report


@pytest.mark.parametrize("field", ["Total bytes:", "Line count:"])
def test_the_structural_metadata_is_still_reported(tmp_path, capsys, field):
    _, report = _run(tmp_path, capsys, "classic-pat.gpg", SYNTHETIC_TOKEN + "\n")
    assert field in report
