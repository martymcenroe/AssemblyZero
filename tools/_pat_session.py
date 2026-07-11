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

Module contract (what this code needs to exist and hold):
    - `~/.secrets/classic-pat.gpg` — a gpg symmetric-encrypted file whose
      decrypted content is the token on a single line (a trailing newline
      is tolerated and stripped).
    - gpg-agent passphrase caching DISABLED (`default-cache-ttl 0`,
      `max-cache-ttl 0` in ~/.gnupg/gpg-agent.conf, then
      `gpgconf --kill gpg-agent`). While a passphrase is cached, ANY
      same-user process can silently decrypt the file — TTL=0 forces
      every decrypt to surface pinentry, making a sibling's attempt
      visible. This is a hard precondition, not a tuning suggestion.

Creating and ROTATING that file is an operator procedure and is
deliberately not documented here — it lives in the operator's private
rotation runbook, alongside the token-scope, verification, revocation,
and residue-destruction steps.

REQUIRED operational rule:
    The user runs scripts that import this module, in their own Git Bash.
    NEVER let an agent (Claude Code, Codex, Gemini) invoke them via its
    Bash tool — the spawned Python process becomes the agent's child and
    its heap is theoretically readable by the agent for the seconds the
    PAT is in scope.
"""

from __future__ import annotations

import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_PAT_PATH: Path = Path.home() / ".secrets" / "classic-pat.gpg"
DEFAULT_CERBERUS_PEM_PATH: Path = Path.home() / ".secrets" / "cerberus-pem.gpg"
GPG_TIMEOUT_S: int = 180
MAX_GPG_ATTEMPTS: int = 5


@contextmanager
def classic_pat_session(
    pat_path: Path = DEFAULT_PAT_PATH,
) -> Iterator[str]:
    """Yield the gpg-decrypted classic PAT.

    Retries up to MAX_GPG_ATTEMPTS times on decrypt failure; pinentry
    re-prompts each time. Long passphrases entered without visual feedback
    (pinentry-w32 default) make mistypes common, so the loop is forgiving.
    Ctrl-C the host script to abort.

    Args:
        pat_path: Path to the gpg-encrypted PAT file.

    Yields:
        The decrypted PAT as a string. Lives only in this generator's scope.

    Raises:
        FileNotFoundError: If the encrypted PAT file does not exist.
            The error message includes the one-time-setup command.
        RuntimeError: After MAX_GPG_ATTEMPTS consecutive gpg failures.
            Carries gpg's last stderr so the caller can diagnose.
        subprocess.TimeoutExpired: If pinentry doesn't respond within
            GPG_TIMEOUT_S on a single attempt -- propagates rather than
            retrying, since a hung pinentry won't unhang.
    """
    if not pat_path.exists():
        raise FileNotFoundError(
            f"Classic PAT not found at {pat_path}.\n"
            f"One-time setup (copy your classic PAT to clipboard first, then):\n"
            f"  mkdir -p {pat_path.parent}\n"
            f"  cat /dev/clipboard | gpg -c -o {pat_path}\n"
            f"(macOS: pbpaste. Linux: xclip -selection clipboard -o.)"
        )

    last_stderr = ""
    for attempt in range(1, MAX_GPG_ATTEMPTS + 1):
        result = subprocess.run(
            ["gpg", "--quiet", "--decrypt", str(pat_path)],
            capture_output=True,
            text=True,
            timeout=GPG_TIMEOUT_S,
        )
        if result.returncode == 0:
            pat = result.stdout.strip()
            try:
                yield pat
            finally:
                del pat
            return
        last_stderr = result.stderr.strip()
        if attempt < MAX_GPG_ATTEMPTS:
            print(
                f"gpg decrypt failed (attempt {attempt}/{MAX_GPG_ATTEMPTS}): {last_stderr}",
                file=sys.stderr,
            )
            print(
                "Retrying -- pinentry will prompt again. (Ctrl-C to abort.)",
                file=sys.stderr,
            )

    raise RuntimeError(
        f"gpg decrypt failed after {MAX_GPG_ATTEMPTS} attempts. "
        f"Last error: {last_stderr}"
    )


@contextmanager
def cerberus_pem_session(
    pem_path: Path = DEFAULT_CERBERUS_PEM_PATH,
) -> Iterator[str]:
    """Yield the gpg-decrypted Cerberus App private-key PEM.

    Same threat model as classic_pat_session: the PEM lives at rest
    gpg-symmetric-encrypted (passphrase-gated), is decrypted only into
    this Python process's heap inside the context-manager scope, and
    never touches disk in plaintext form during script execution.

    Solves the multi-repo Cerberus deploy problem (#1254): the operator
    runs new_repo_setup.py once per repo against the SAME encrypted
    PEM, so a single browser-trip generates the key and a single
    browser-trip revokes it, regardless of how many repos are created.
    The plaintext PEM is deleted right after the one-time gpg-encrypt
    step and never reappears.

    One-time setup (operator, Save-As pattern — preferred per #1265):
        # 1. Browser: Generate a private key, then Save As ~/.secrets/cerberus.pem
        #    (NOT ~/Downloads/ — that path is often OneDrive-synced and the
        #    cloud-sync race can upload the plaintext before local rm fires).
        #    mkdir -p ~/.secrets first if the directory doesn't exist.
        # 2. Encrypt and delete plaintext (shell rm, NOT File Explorer):
        gpg -c -o ~/.secrets/cerberus-pem.gpg ~/.secrets/cerberus.pem
        rm ~/.secrets/cerberus.pem
        # 3. Clear-RecycleBin + browser download history (see runbook 0927
        #    "Hygiene surfaces" table for the full audit gate).

    Same operational rules apply as classic_pat_session:
        - gpg-agent default-cache-ttl 0 (silent sibling-decrypt attempts
          surface pinentry — see ADR-0216 and the classic_pat_session
          docstring above)
        - The OPERATOR runs the script that opens this context; an
          agent must never invoke it via its Bash tool

    Args:
        pem_path: Path to the gpg-encrypted Cerberus PEM file.

    Yields:
        The decrypted PEM as a string. Lives only in this generator's
        scope; the local binding is deleted on exit.

    Raises:
        FileNotFoundError: If the encrypted PEM file does not exist.
        RuntimeError: After MAX_GPG_ATTEMPTS consecutive gpg failures.
        subprocess.TimeoutExpired: Same hung-pinentry handling as
            classic_pat_session.

    Implementation note: the body intentionally duplicates
    classic_pat_session's structure rather than sharing a helper.
    Keeping the load-bearing PAT path untouched is worth ~30 lines of
    duplication.
    """
    if not pem_path.exists():
        raise FileNotFoundError(
            f"Cerberus PEM not found at {pem_path}.\n"
            f"One-time setup (after downloading the .pem from the Cerberus "
            f"App settings page):\n"
            f"  mkdir -p {pem_path.parent}\n"
            f"  cat ~/Downloads/cerberus.pem | gpg -c -o {pem_path}\n"
            f"  rm ~/Downloads/cerberus.pem"
        )

    last_stderr = ""
    for attempt in range(1, MAX_GPG_ATTEMPTS + 1):
        result = subprocess.run(
            ["gpg", "--quiet", "--decrypt", str(pem_path)],
            capture_output=True,
            text=True,
            timeout=GPG_TIMEOUT_S,
        )
        if result.returncode == 0:
            pem = result.stdout.strip()
            try:
                yield pem
            finally:
                del pem
            return
        last_stderr = result.stderr.strip()
        if attempt < MAX_GPG_ATTEMPTS:
            print(
                f"gpg decrypt failed (attempt {attempt}/{MAX_GPG_ATTEMPTS}): {last_stderr}",
                file=sys.stderr,
            )
            print(
                "Retrying -- pinentry will prompt again. (Ctrl-C to abort.)",
                file=sys.stderr,
            )

    raise RuntimeError(
        f"gpg decrypt of Cerberus PEM failed after {MAX_GPG_ATTEMPTS} attempts. "
        f"Last error: {last_stderr}"
    )
