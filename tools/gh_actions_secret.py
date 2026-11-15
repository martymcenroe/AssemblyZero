"""Set a repository's Actions or Dependabot secret, in process, under the classic PAT.

`set_secret` fetches the repository's public key for the scope, seals the value
against it with libsodium's sealed box, and PUTs the sealed value with the key's
id, as GitHub's REST API requires. The PAT comes from
`_pat_session.classic_pat_session()` (ADR-0216) and stays in this process: it is
never put in argv or the environment.

`tools/new_repo.py` runs the operator's post-create hooks in its own process, and
an operator-configured post-create hook imports `set_secret` from here
(`new_repo.HOOK_IMPORTABLE` names it). Removing or renaming it breaks that hook,
and `tests/unit/test_gh_actions_secret.py` fails first (#4783). The function's
behaviour is the one the secret deploy tool carried before #4731 removed it.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import requests
from nacl import encoding, public

# Shared retry helper (#1052): retries transient failures, returns a permanent
# 4xx as-is, and raises a RequestException subclass on retry exhaustion.
try:
    from _gh_retry import request_with_retry as _request_with_retry
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from _gh_retry import request_with_retry as _request_with_retry

GITHUB_USER = "martymcenroe"
_GH_API = "https://api.github.com"

# GitHub keeps a separate secret store for each: a secret set in one is not
# visible to workflow runs in the other. Dependabot PRs run with the Dependabot
# scope, other workflow runs with the Actions scope (#1118).
SCOPES = ("actions", "dependabot")


def _get_public_key(
    repo: str, pat: str, scope: str = "actions", *, owner: str = GITHUB_USER,
) -> tuple[str, str] | None:
    """Fetch the repository's secrets public key for `scope`.

    Returns (key_id, base64 public key), or None when the request fails or
    answers with a status of 300 or above.
    """
    try:
        resp = _request_with_retry(
            "GET",
            f"{_GH_API}/repos/{owner}/{repo}/{scope}/secrets/public-key",
            pat,
        )
    except requests.RequestException:
        return None
    if resp.status_code >= 300:
        return None
    data = resp.json()
    return data["key_id"], data["key"]


def _encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Seal `secret_value` against the repository's public key; return it base64.

    The scheme GitHub documents at
    https://docs.github.com/en/rest/actions/secrets#create-or-update-a-repository-secret
    """
    pk = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(pk)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def set_secret(
    repo: str,
    name: str,
    value: str,
    pat: str,
    scope: str = "actions",
    *,
    owner: str = GITHUB_USER,
) -> bool:
    """Set the secret `name` on `owner/repo` in `scope` through the REST API.

    Args:
        repo: Repository name, without the owner.
        name: Secret name.
        value: Plaintext value; it is sealed before it leaves this process.
        pat: Classic PAT from classic_pat_session().
        scope: "actions" (default) or "dependabot".
        owner: Repository owner; defaults to GITHUB_USER.

    Returns:
        True on HTTP 2xx. False otherwise, including when the public key
        cannot be fetched.
    """
    pk = _get_public_key(repo, pat, scope=scope, owner=owner)
    if pk is None:
        return False
    key_id, public_key_b64 = pk
    encrypted_value = _encrypt_secret(public_key_b64, value)
    try:
        resp = _request_with_retry(
            "PUT",
            f"{_GH_API}/repos/{owner}/{repo}/{scope}/secrets/{name}",
            pat,
            json={"encrypted_value": encrypted_value, "key_id": key_id},
        )
    except requests.RequestException:
        return False
    return resp.status_code < 300
