"""A GitHub App JWT, minted from the App ID and its private key (#4784).

    from _github_app_jwt import mint_app_jwt
    token = mint_app_jwt(app_id, pem)       # Authorization: Bearer <token>

The logic is new_repo.py's former `_mint_github_app_jwt` (#1822), moved here so
that `tools/store_pr_sentinel_app_key.py` can prove a key with GitHub before it
stores it. new_repo.py's pr-sentinel check calls this module too, and keeps no
copy of its own (#4791), so the key program and the check mint one token.

GitHub's App JWT has one fixed shape: header `{"alg": "RS256", "typ": "JWT"}`,
`iat` backdated 60 seconds for clock drift, `exp` nine minutes on (GitHub caps it
at ten), `iss` the App ID. It is signed with the App's private key through
`cryptography`, a project dependency, so no JWT library is needed.

The token and the key stay in this process. A caller sends the token only in an
Authorization header, never in argv, the environment or a file.
"""

from __future__ import annotations

import base64
import json
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

#: Seconds `iat` is set back from now, for a clock running slightly ahead of GitHub's.
BACKDATE_S = 60
#: Seconds from now to `exp`. GitHub refuses a token that lives longer than ten minutes.
LIFETIME_S = 540


def _b64url(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def mint_app_jwt(app_id: str, pem: str) -> str:
    """An RS256 JWT authenticating as the GitHub App `app_id`, signed with `pem`.

    Raises whatever `cryptography` raises for a PEM it cannot load (ValueError,
    TypeError for a passphrase-protected key, UnsupportedAlgorithm).
    """
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(
        {"iat": now - BACKDATE_S, "exp": now + LIFETIME_S, "iss": app_id}
    ).encode())
    signing_input = header + b"." + payload
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return (signing_input + b"." + _b64url(signature)).decode()
