#!/usr/bin/env python3
"""Give the pr-sentinel Worker Cerberus's App ID and private key (#3663).

OPERATOR-RUN, in your own Git Bash, never through an agent's Bash tool: the
key is decrypted into this process's heap (cerberus_pem_session, ADR-0216's
threat model) and an agent's child process is the agent's.

    # from the AssemblyZero checkout
    poetry run python tools/cerberus_worker_key.py

It sets the Cerberus App ID (3079970; not confidential), decrypts ~/.secrets/cerberus-pem.gpg (pinentry asks for the
passphrase), converts the PEM to base64 PKCS#8, the form the Worker's WebCrypto
import takes, and pipes each value to `wrangler secret put` on stdin. The key
never reaches argv, the environment, a file, or the screen. It ends by listing
the Worker's secret NAMES, never values.

Surfaces touched (ADR-0227 audit gate): the gpg-encrypted file (read only),
this process's heap (deleted on exit), one stdin pipe per value to wrangler,
and the Worker's encrypted secret store. No clipboard, no shell history (the
value is never typed), no disk.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import cerberus_pem_session  # noqa: E402

SENTINEL = Path(__file__).resolve().parents[1] / "sentinel"


# Not secret: an App ID only identifies the App; the private key is what signs.
# The operator confirmed the value on 2026-09-27. The fleet ID registry is a
# separate issue; until it lands, the value lives here.
CERBERUS_APP_ID = "3079970"


def run(args: list[str], value: str | None = None) -> subprocess.CompletedProcess[str]:
    # wrangler prints emoji; Windows' default cp1252 decode crashed the reader
    # thread on the first run (2026-09-27), so decode as UTF-8 explicitly.
    return subprocess.run(
        args, input=value, text=True, encoding="utf-8", errors="replace",
        cwd=SENTINEL, capture_output=True,
    )


def put(npx: str, name: str, value: str) -> None:
    r = run([npx, "wrangler", "secret", "put", name], value)
    if r.returncode != 0:
        # wrangler's stderr names the secret and the error, never the value.
        sys.exit(f"FAILED: wrangler secret put {name}: {r.stderr.strip()[-400:]}")
    print(f"OK: {name} set")


def main() -> int:
    npx = shutil.which("npx")
    if not npx:
        sys.exit("FAILED: npx not found on PATH")
    with cerberus_pem_session(reason="pr-sentinel Worker, Cerberus approval (#3663)") as pem:
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        pkcs8 = key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        b64 = base64.b64encode(pkcs8).decode()
        del key, pkcs8
        put(npx, "CERBERUS_PRIVATE_KEY_B64", b64)
        del b64
    put(npx, "CERBERUS_APP_ID", CERBERUS_APP_ID)
    r = run([npx, "wrangler", "secret", "list"])
    names = [ln.split('"name":')[1].split('"')[1] for ln in r.stdout.splitlines() if '"name":' in ln]
    print("Worker secrets now:", ", ".join(names) if names else r.stdout.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
