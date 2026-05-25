"""Verify a gpg-encrypted secret blob without exposing key material.

Decrypts in-process (single pinentry prompt), then reports structural
metadata only -- byte count, line count, first/last lines, type-specific
checks. The decrypted content never reaches stdout/stderr and never lands
on disk. Follows the same threat-model posture as
``tools/_pat_session.py`` (ADR-0216).

Supported types:
    pem  -- PEM-encoded private key (RSA, EC, generic)
    pat  -- single-line PAT / token (classic or fine-grained)
    text -- generic text blob (just metadata, no semantic checks)

Type is auto-detected from the filename if ``--type`` is not given:
    "*pem*" -> pem
    "*pat*" -> pat
    else    -> text

Exit codes:
    0  verdict is VALID for the chosen type
    1  verdict is INVALID (one or more type checks failed)
    2  file not found / decrypt failed / argparse error

Usage:
    poetry run python tools/verify_encrypted_secret.py PATH [--type TYPE]

Issue: martymcenroe/AssemblyZero#1272
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

GPG_TIMEOUT_S = 180

# RSA-2048 PEMs land around 1700 bytes; RSA-4096 around 3300. A generous
# 1500-4000 range catches both with margin for line-ending variance.
PEM_TYPICAL_BYTES = (1500, 4000)
PEM_TYPICAL_LINES = (20, 60)

# Classic PAT: 40-char lowercase hex. Fine-grained: "ghp_" or "github_pat_"
# prefix followed by 36+ alphanumerics/underscores. Both should be a
# single line; total length 40-100.
PAT_CLASSIC = re.compile(r"^[a-f0-9]{40}$")
PAT_FINEGRAINED = re.compile(r"^(ghp_|github_pat_)[A-Za-z0-9_]{36,}$")
PAT_BYTE_RANGE = (40, 100)


def _decrypt(path: Path) -> str:
    """Decrypt the gpg blob in-process. Single pinentry prompt.

    Exits with code 2 if decrypt fails -- caller never gets ciphertext.
    """
    result = subprocess.run(
        ["gpg", "--quiet", "--decrypt", str(path)],
        capture_output=True,
        text=True,
        timeout=GPG_TIMEOUT_S,
        check=False,
    )
    if result.returncode != 0:
        print(f"ERROR: gpg decrypt failed: {result.stderr.strip()}",
              file=sys.stderr)
        sys.exit(2)
    return result.stdout


def infer_type(path: Path) -> str:
    """Auto-detect the secret type from the filename."""
    name = path.name.lower()
    if "pem" in name:
        return "pem"
    if "pat" in name:
        return "pat"
    return "text"


def check_pem(content: str) -> tuple[bool, dict]:
    """Check the decrypted content looks like a PEM private key."""
    lines = content.splitlines()
    has_begin = any("BEGIN" in l and "PRIVATE KEY" in l for l in lines)
    has_end = any("END" in l and "PRIVATE KEY" in l for l in lines)
    size_ok = PEM_TYPICAL_BYTES[0] <= len(content) <= PEM_TYPICAL_BYTES[1]
    lines_ok = PEM_TYPICAL_LINES[0] <= len(lines) <= PEM_TYPICAL_LINES[1]
    return (
        has_begin and has_end and size_ok and lines_ok,
        {
            "has_begin_marker": has_begin,
            "has_end_marker": has_end,
            "size_in_typical_range": size_ok,
            "line_count_in_typical_range": lines_ok,
        },
    )


def check_pat(content: str) -> tuple[bool, dict]:
    """Check the decrypted content looks like a GitHub PAT."""
    stripped = content.strip()
    lines = stripped.splitlines()
    is_single_line = len(lines) == 1
    classic = bool(PAT_CLASSIC.fullmatch(stripped))
    fine_grained = bool(PAT_FINEGRAINED.fullmatch(stripped))
    size_ok = PAT_BYTE_RANGE[0] <= len(stripped) <= PAT_BYTE_RANGE[1]
    return (
        is_single_line and (classic or fine_grained) and size_ok,
        {
            "is_single_line": is_single_line,
            "char_count": len(stripped),
            "matches_classic_pat_pattern": classic,
            "matches_finegrained_pat_pattern": fine_grained,
        },
    )


def check_text(content: str) -> tuple[bool, dict]:
    """Generic check: non-empty."""
    return (
        len(content) > 0,
        {"non_empty": len(content) > 0},
    )


CHECKERS = {
    "pem": check_pem,
    "pat": check_pat,
    "text": check_text,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a gpg-encrypted secret blob without exposing key material. "
            "Decrypts in-process, reports metadata + type-specific checks, "
            "never prints the decrypted content."
        ),
    )
    parser.add_argument(
        "path",
        help="Path to the gpg-encrypted file (e.g. ~/.secrets/cerberus-pem.gpg)",
    )
    parser.add_argument(
        "--type",
        choices=list(CHECKERS),
        default=None,
        help="Secret type. Auto-detected from filename if omitted: "
             "'*pem*' -> pem, '*pat*' -> pat, else text.",
    )
    args = parser.parse_args(argv)

    path = Path(args.path).expanduser()
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2

    secret_type = args.type or infer_type(path)

    print(f"File:         {path}")
    print(f"Type:         {secret_type}")
    print()

    content = _decrypt(path)
    lines = content.splitlines()

    print(f"Total bytes:  {len(content)}")
    print(f"Line count:   {len(lines)}")
    print(f"First line:   {lines[0] if lines else '(empty)'}")
    print(f"Last line:    {lines[-1] if lines else '(empty)'}")
    print()

    ok, details = CHECKERS[secret_type](content)
    print(f"Type-specific checks ({secret_type}):")
    for k, v in details.items():
        print(f"  {k}: {v}")
    print()

    if ok:
        print("VERDICT: VALID")
        return 0
    print("VERDICT: INVALID -- one or more checks failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
