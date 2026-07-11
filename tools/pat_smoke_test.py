#!/usr/bin/env python3
"""Verify the encrypted classic PAT end-to-end. OPERATOR-RUN ONLY (#1745).

One read-only GET proves the whole chain: the gpg file decrypts (pinentry
surfacing is itself the zero-TTL agent-config check), the decrypted token
authenticates, it belongs to the expected account, it carries the `repo`
scope the fleet tooling needs, and its expiration is what the operator
chose. Built after a rotation "verification" step pointed at a tool that
never touches the classic PAT and therefore verified nothing.

Per the ADR-0216 threat model the OPERATOR runs this in their own shell —
never an agent (the decrypted token lives briefly in this process's heap).

Usage (from AssemblyZero, in Git Bash):
    poetry run python tools/pat_smoke_test.py

Exit 0 with PASS lines, or exit 1 with the specific failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session  # noqa: E402

EXPECTED_LOGIN = "martymcenroe"
REQUIRED_SCOPE = "repo"
API = "https://api.github.com/user"
HTTP_TIMEOUT_S = 30


def evaluate(status: int, login: str, scopes_header: str,
             expiration_header: str) -> tuple[bool, list[str]]:
    """Pure verdict: (ok, report lines). Unit-tested; no I/O."""
    lines: list[str] = []
    ok = True

    if status == 200:
        lines.append(f"PASS  token authenticates (HTTP {status})")
    else:
        lines.append(f"FAIL  HTTP {status} from GET /user -- token invalid, "
                     f"revoked, or malformed (re-check the encrypt step)")
        return False, lines

    if login == EXPECTED_LOGIN:
        lines.append(f"PASS  account: {login}")
    else:
        ok = False
        lines.append(f"FAIL  account is {login!r}, expected {EXPECTED_LOGIN!r} "
                     f"-- wrong token in the file?")

    scopes = [s.strip() for s in scopes_header.split(",") if s.strip()]
    if REQUIRED_SCOPE in scopes:
        lines.append(f"PASS  scopes: {', '.join(scopes)}")
    else:
        ok = False
        lines.append(f"FAIL  scope '{REQUIRED_SCOPE}' missing (has: "
                     f"{scopes_header or 'none'}) -- recreate the token with "
                     f"repo (full) checked")

    if expiration_header:
        lines.append(f"PASS  expires: {expiration_header} -- put it in the calendar")
    else:
        lines.append("NOTE  no expiration header (non-expiring token)")

    return ok, lines


def main() -> int:
    with classic_pat_session() as pat:
        resp = requests.get(
            API,
            headers={
                "Authorization": f"Bearer {pat}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=HTTP_TIMEOUT_S,
        )
    login = ""
    try:
        login = resp.json().get("login", "")
    except ValueError:
        pass
    ok, lines = evaluate(
        resp.status_code,
        login,
        resp.headers.get("X-OAuth-Scopes", ""),
        resp.headers.get("github-authentication-token-expiration", ""),
    )
    print("\n".join(lines))
    print("\nRESULT: " + ("PASS -- rotation verified" if ok else "FAIL -- see above"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
