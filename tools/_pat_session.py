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

REQUIRED gpg-agent.conf settings (~/.gnupg/gpg-agent.conf):
    default-cache-ttl 0
    max-cache-ttl 0

The original ADR-0216 marked passphrase caching as a "small risk" and
suggested shorter TTLs as a mitigation. That undersells it: while a
passphrase is cached, ANY same-user process can call `gpg --decrypt
classic-pat.gpg` and silently obtain the PAT — defeating the entire
"in-process only" guarantee. The fleet of co-resident Claude/Codex/Gemini
agents makes that a real, not theoretical, attack class. TTL=0 forces
every decrypt to surface pinentry, so a sibling's silent attempt is
visible to the user. Apply with `gpgconf --kill gpg-agent`.

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
