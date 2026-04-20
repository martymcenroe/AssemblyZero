"""In-process classic PAT decryption.

Issue #959.

The classic Personal Access Token (admin-scope) is required for fleet-wide
operations like updating branch protection. Earlier patterns exposed it via
either `gh auth` storage or the child process's environment block, both of
which are readable by other same-user processes.

This module decrypts the PAT inside the calling Python process and yields
it as a local heap variable inside a context-manager scope. Callers are
expected to consume it via `requests` (Authorization: Bearer header)
directly — never set os.environ, never pass via subprocess argv, never log.

When the `with` block exits, the local binding is deleted. Python strings
are immutable so the bytes may persist in the heap until garbage collection;
the primary protection is process scope (the OS reclaims the address space
when the script exits, well before any neighbor agent could observe it).

One-time setup (user):
    mkdir -p ~/.secrets
    # Copy the classic PAT to clipboard, then:
    cat /dev/clipboard | gpg -c -o ~/.secrets/classic-pat.gpg

(macOS: substitute `pbpaste`. Linux: `xclip -selection clipboard -o`.)

The clipboard pattern keeps the secret out of shell history and out of
the process argv table — the previous `echo '<pat>' | gpg ...` form
exposed the secret in both places.
"""

from __future__ import annotations

import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_PAT_PATH: Path = Path.home() / ".secrets" / "classic-pat.gpg"
GPG_TIMEOUT_S: int = 30


@contextmanager
def classic_pat_session(
    pat_path: Path = DEFAULT_PAT_PATH,
) -> Iterator[str]:
    """Yield the gpg-decrypted classic PAT.

    Args:
        pat_path: Path to the gpg-encrypted PAT file.

    Yields:
        The decrypted PAT as a string. Lives only in this generator's scope.

    Raises:
        FileNotFoundError: If the encrypted PAT file does not exist.
            The error message includes the one-time-setup command.
        RuntimeError: If gpg decrypt returns non-zero. Carries gpg's stderr
            so the caller can diagnose passphrase / permission / key issues.
    """
    if not pat_path.exists():
        raise FileNotFoundError(
            f"Classic PAT not found at {pat_path}.\n"
            f"One-time setup (copy your classic PAT to clipboard first, then):\n"
            f"  mkdir -p {pat_path.parent}\n"
            f"  cat /dev/clipboard | gpg -c -o {pat_path}\n"
            f"(macOS: pbpaste. Linux: xclip -selection clipboard -o.)"
        )

    result = subprocess.run(
        ["gpg", "--quiet", "--decrypt", str(pat_path)],
        capture_output=True,
        text=True,
        timeout=GPG_TIMEOUT_S,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gpg decrypt failed: {result.stderr.strip()}")

    pat = result.stdout.strip()
    try:
        yield pat
    finally:
        del pat
