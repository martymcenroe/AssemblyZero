"""Update martymcenroe/Clio repository metadata via the classic-PAT pattern.

Closes AssemblyZero #1214. Closes Clio #90 on first successful run.

Why this script exists
----------------------
The fine-grained PAT used by day-to-day agent sessions deliberately lacks
the scope required to PATCH a repo's settings (description, homepage,
topics). Per ADR-0216 we acquire the classic PAT in-process via
``classic_pat_session()`` and call the GitHub REST API directly with
``requests``. No ``gh`` CLI, no env vars, no ``gh auth`` swap.

What this script does
---------------------
1. Decrypts the classic PAT inside this Python process (one pinentry prompt)
2. PATCH /repos/martymcenroe/Clio with:
   - description (the canonical Clio one-liner)
   - homepage (https://cliocast.com — Cloudflare Pages custom domain)
3. PUT /repos/martymcenroe/Clio/topics with the canonical topic set

Idempotent: re-running with no changes intended produces a no-op (the API
accepts unchanged values). The script reports what was sent and what came
back.

How to run it
-------------
**You** run this, not an agent. Per ADR-0216 §6.1 the Python process
must be your child, not the agent's, for the heap-only PAT protection
to hold.

::

    cd /c/Users/mcwiz/Projects/AssemblyZero
    poetry run python tools/update_clio_repo_metadata.py

Pinentry will prompt for your gpg passphrase. Up to 5 retries on
mistypes. Hit Ctrl-C to abort.

Verification
------------
After the script reports success, visit https://github.com/martymcenroe/Clio
and confirm the repo header shows:
- The new description text
- The homepage link `https://cliocast.com`
- The topic chips listed in TOPICS below
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the sibling _pat_session module importable regardless of CWD.
sys.path.insert(0, str(Path(__file__).parent))

import requests  # noqa: E402

from _pat_session import classic_pat_session  # noqa: E402

OWNER = "martymcenroe"
REPO = "Clio"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"

DESCRIPTION = (
    "Chrome extension that extracts full Gemini, Claude, and ChatGPT "
    "conversations to structured JSON with images. Privacy-first: "
    "strict-local processing, no telemetry."
)
HOMEPAGE = "https://cliocast.com"
TOPICS = [
    "chrome-extension",
    "llm",
    "ai-governance",
    "privacy",
    "conversation-archive",
    "gemini",
    "claude",
    "chatgpt",
    "data-portability",
    "manifest-v3",
]

REQUEST_TIMEOUT_S = 30


def _auth_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "update_clio_repo_metadata.py (ADR-0216)",
    }


def _patch_repo(pat: str) -> None:
    """PATCH description + homepage."""
    payload = {
        "description": DESCRIPTION,
        "homepage": HOMEPAGE,
    }
    print(f"PATCH {API}")
    print(f"  description: {DESCRIPTION[:60]}...")
    print(f"  homepage:    {HOMEPAGE}")
    response = requests.patch(
        API,
        json=payload,
        headers=_auth_headers(pat),
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    body = response.json()
    print(
        f"  [OK] HTTP {response.status_code} "
        f"— description={body['description'][:40]!r}... "
        f"homepage={body['homepage']!r}"
    )


def _put_topics(pat: str) -> None:
    """PUT topics."""
    url = f"{API}/topics"
    payload = {"names": TOPICS}
    print(f"PUT  {url}")
    print(f"  topics: {', '.join(TOPICS)}")
    response = requests.put(
        url,
        json=payload,
        headers=_auth_headers(pat),
        timeout=REQUEST_TIMEOUT_S,
    )
    response.raise_for_status()
    body = response.json()
    print(
        f"  [OK] HTTP {response.status_code} "
        f"— {len(body['names'])} topics applied"
    )


def main() -> int:
    print("=" * 60)
    print(f"Updating {OWNER}/{REPO} metadata (description, homepage, topics)")
    print("=" * 60)
    print()

    try:
        with classic_pat_session() as pat:
            _patch_repo(pat)
            print()
            _put_topics(pat)
    except requests.HTTPError as e:
        print(f"\nERROR: GitHub API rejected the request: {e}", file=sys.stderr)
        if e.response is not None:
            print(f"  Body: {e.response.text[:500]}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        # _pat_session raises this when ~/.secrets/classic-pat.gpg is missing;
        # its message includes the one-time setup commands.
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        # Raised after MAX_GPG_ATTEMPTS bad passphrases.
        print(f"\nERROR: {e}", file=sys.stderr)
        return 1

    print()
    print("=" * 60)
    print("Done. Verify at https://github.com/martymcenroe/Clio")
    print("=" * 60)
    print()
    print("Then close these issues with a confirming comment:")
    print(f"  - Clio #90  (https://github.com/{OWNER}/{REPO}/issues/90)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
