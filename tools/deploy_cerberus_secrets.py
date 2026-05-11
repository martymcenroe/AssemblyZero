#!/usr/bin/env python3
"""Deploy Cerberus (GitHub App) secrets to repos missing them.

THIS SCRIPT MUST BE RUN BY THE USER, NOT BY AN AGENT.
It handles a private key file -- agents must never touch this.

Usage:
    1. Download the .pem from GitHub App settings (only if you'll deploy)
    2. Run one of:
         # Default: scan, deploy ONLY to repos missing both secrets (#763)
         poetry run python tools/deploy_cerberus_secrets.py /path/to/cerberus.pem

         # All repos (use for key rotation -- old default behavior):
         poetry run python tools/deploy_cerberus_secrets.py /path/to/cerberus.pem --all

         # Single repo:
         poetry run python tools/deploy_cerberus_secrets.py /path/to/cerberus.pem --repo NAME

         # Dry-run: report which repos are missing secrets, no PUTs.
         # .pem is optional in dry-run.
         poetry run python tools/deploy_cerberus_secrets.py --dry-run
         poetry run python tools/deploy_cerberus_secrets.py /path/to/cerberus.pem --dry-run

    3. DELETE the .pem file immediately after (skip if dry-run with no .pem)

The script sets two GitHub Actions secrets on each target repo:
    - REVIEWER_APP_ID (3079970)
    - REVIEWER_APP_PRIVATE_KEY (contents of the .pem)

All secret writes use an in-process classic PAT via
`tools/_pat_session.classic_pat_session()` (ADR-0216). The PAT is
never placed in the shell env block or subprocess argv. Secret values
are encrypted with libsodium sealed-box against the repo's public key
per GitHub's API contract.

Issue: #736 | Related: #732, #763 (auto-detect flags), #1007 (in-process PAT migration)
"""

import argparse
import base64
import subprocess
import sys
from pathlib import Path

import requests
from nacl import encoding, public

# Shared with new_repo_setup.py and other v3 callers.
try:
    from _pat_session import classic_pat_session
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from _pat_session import classic_pat_session

APP_ID = "3079970"
GITHUB_USER = "martymcenroe"
_GH_API = "https://api.github.com"

# Shared retry helper (#1052). Imported as _request_with_retry to keep
# existing call-sites unchanged. Loud-failure variant: retry exhaustion
# raises requests.HTTPError / ConnectionError / Timeout (all
# RequestException subclasses, so existing except handlers still catch).
try:
    from _gh_retry import request_with_retry as _request_with_retry
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from _gh_retry import request_with_retry as _request_with_retry  # noqa: F401


def get_all_repos() -> list[str]:
    """Get all repos for the user via gh CLI. Read-only — fine-grained PAT OK."""
    result = subprocess.run(
        ["gh", "repo", "list", GITHUB_USER, "--limit", "200",
         "--json", "name", "--jq", ".[].name"],
        capture_output=True, text=True, check=True
    )
    repos = [r.strip() for r in result.stdout.strip().split("\n") if r.strip()]
    return sorted(repos)


_SCOPES = ("actions", "dependabot")


def _get_public_key(repo: str, pat: str, scope: str = "actions") -> tuple[str, str] | None:
    """Fetch the repo's secrets public key for a given scope.

    Args:
        scope: Either "actions" (default) or "dependabot". GitHub maintains
            SEPARATE secret stores for these two contexts -- a secret set in
            one is not visible to workflow runs in the other. Dependabot PRs
            run with the Dependabot scope, regular workflow runs with the
            Actions scope. (#1118)

    Returns (key_id, base64_public_key) on success, or None on failure.
    """
    try:
        resp = _request_with_retry(
            "GET",
            f"{_GH_API}/repos/{GITHUB_USER}/{repo}/{scope}/secrets/public-key",
            pat,
        )
    except requests.RequestException:
        return None
    if resp.status_code >= 300:
        return None
    data = resp.json()
    return data["key_id"], data["key"]


# Backwards-compat alias (still imported by external callers / tests).
_get_repo_public_key = _get_public_key


def _encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Sealed-box encrypt `secret_value` against the repo's public key.

    Matches the scheme documented at
    https://docs.github.com/en/rest/actions/secrets#create-or-update-a-repository-secret
    """
    pk = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(pk)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def set_secret(repo: str, name: str, value: str, pat: str, scope: str = "actions") -> bool:
    """Set a GitHub secret on a repo via REST API in the given scope.

    Args:
        repo: Repo name (no owner prefix); paired with GITHUB_USER.
        name: Secret name (e.g. "REVIEWER_APP_ID").
        value: Plaintext secret value (will be sealed-box encrypted before PUT).
        pat: Classic PAT from classic_pat_session().
        scope: "actions" (default) or "dependabot". The dependabot scope's
            secrets are the ones visible to workflows triggered by Dependabot
            PR events. Cerberus needs both scopes populated to function. (#1118)

    Returns:
        True on HTTP 2xx; False otherwise (including failure to fetch public key).
    """
    pk = _get_public_key(repo, pat, scope=scope)
    if pk is None:
        return False
    key_id, public_key_b64 = pk
    encrypted_value = _encrypt_secret(public_key_b64, value)
    try:
        resp = _request_with_retry(
            "PUT",
            f"{_GH_API}/repos/{GITHUB_USER}/{repo}/{scope}/secrets/{name}",
            pat,
            json={"encrypted_value": encrypted_value, "key_id": key_id},
        )
    except requests.RequestException:
        return False
    return resp.status_code < 300


def deploy_to_repo(repo: str, pem_content: str, pat: str) -> tuple[bool, list[str]]:
    """Deploy REVIEWER_APP_ID + REVIEWER_APP_PRIVATE_KEY to BOTH scopes
    (Actions and Dependabot) on a single repo.

    Args:
        repo: Repo name (not owner/name) under GITHUB_USER.
        pem_content: The raw .pem file contents.
        pat: Classic PAT from classic_pat_session().

    Returns:
        (success, failed_descriptors). Each failed entry is
        "<scope>/<secret-name>" so the operator can see exactly which
        scope-secret combo did not land. (#1118)
    """
    failed: list[str] = []
    for scope in _SCOPES:
        if not set_secret(repo, "REVIEWER_APP_ID", APP_ID, pat, scope=scope):
            failed.append(f"{scope}/REVIEWER_APP_ID")
        if not set_secret(repo, "REVIEWER_APP_PRIVATE_KEY", pem_content, pat, scope=scope):
            failed.append(f"{scope}/REVIEWER_APP_PRIVATE_KEY")
    return (len(failed) == 0, failed)


def verify_secrets(repo: str, pat: str) -> tuple[bool, list[str]]:
    """Check that both required Cerberus secrets are present on the repo
    in BOTH the Actions and Dependabot scopes.

    Uses the same in-process PAT as deploy_to_repo for consistency (avoids
    depending on whatever gh auth happens to be pointed at).

    Args:
        repo: Repo name (not owner/name) under GITHUB_USER.
        pat: Classic PAT from classic_pat_session().

    Returns:
        (all_present, missing_descriptors). Each missing entry is
        "<scope>/<secret-name>" so the caller can see which scope and
        which secret is missing -- a repo with secrets only in Actions
        scope (the pre-#1118 default) will report all 2 dependabot/*
        entries as missing. (#1118)
    """
    required_names = {"REVIEWER_APP_ID", "REVIEWER_APP_PRIVATE_KEY"}
    missing: list[str] = []
    for scope in _SCOPES:
        try:
            resp = _request_with_retry(
                "GET",
                f"{_GH_API}/repos/{GITHUB_USER}/{repo}/{scope}/secrets",
                pat,
            )
        except requests.RequestException:
            missing.extend(f"{scope}/{n}" for n in sorted(required_names))
            continue
        if resp.status_code >= 300:
            missing.extend(f"{scope}/{n}" for n in sorted(required_names))
            continue
        present = {s["name"] for s in resp.json().get("secrets", [])}
        for n in sorted(required_names):
            if n not in present:
                missing.append(f"{scope}/{n}")
    return (len(missing) == 0, missing)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deploy Cerberus GitHub App secrets to repos missing them.",
        epilog="Default behavior: scan all repos, deploy only to ones missing both secrets.",
    )
    parser.add_argument(
        "pem_path", nargs="?", default=None,
        help="Path to the Cerberus .pem private key. "
             "Required unless --dry-run is set.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Deploy to all repos (skip the missing-secrets filter). "
             "Use for key rotation.",
    )
    parser.add_argument(
        "--repo", metavar="NAME", default=None,
        help="Target a single repo by name (no owner prefix). "
             "If the repo already has both secrets it is still skipped unless --all is set.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Scan and print which repos would be deployed to. "
             "Performs no PUTs. .pem is optional in this mode.",
    )
    return parser.parse_args(argv)


def _load_pem(pem_path: Path) -> str:
    """Read and validate a .pem file. Exits the process on error."""
    if not pem_path.exists():
        print(f"ERROR: File not found: {pem_path}", file=sys.stderr)
        sys.exit(1)
    if pem_path.suffix != ".pem":
        print(f"WARNING: Expected .pem file, got: {pem_path.name}")
        response = input("Continue anyway? [y/N] ")
        if response.lower() != "y":
            sys.exit(1)
    pem_content = pem_path.read_text(encoding="utf-8").strip()
    if "PRIVATE KEY" not in pem_content:
        print("ERROR: File doesn't look like a private key", file=sys.stderr)
        sys.exit(1)
    return pem_content


def _select_target_repos(args: argparse.Namespace, pat: str) -> tuple[list[str], list[str]]:
    """Return (target_repos, skipped_already_configured).

    Selection rules:
        --repo NAME            -> only that repo (still respects missing-secrets filter unless --all)
        --all                  -> every repo, no filtering
        (default)              -> every repo MINUS those that already have both secrets
    """
    if args.repo:
        candidates = [args.repo]
    else:
        candidates = get_all_repos()

    if args.all:
        return candidates, []

    targets: list[str] = []
    already_configured: list[str] = []
    for repo in candidates:
        all_present, _missing = verify_secrets(repo, pat)
        if all_present:
            already_configured.append(repo)
        else:
            targets.append(repo)
    return targets, already_configured


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if not args.dry_run and args.pem_path is None:
        print("ERROR: pem_path is required unless --dry-run is set.", file=sys.stderr)
        return 1

    pem_content: str | None = None
    pem_path: Path | None = None
    if args.pem_path is not None:
        pem_path = Path(args.pem_path)
        pem_content = _load_pem(pem_path)
        print(f"Cerberus App ID: {APP_ID}")
        print(f"Private key: {pem_path.name} ({len(pem_content)} chars)")
        print()
    elif args.dry_run:
        print("Dry-run mode (no .pem provided). Scanning only.\n")

    with classic_pat_session() as pat:
        print("Fetching target repos...")
        targets, skipped = _select_target_repos(args, pat)
        print(f"Targets: {len(targets)} | Already configured: {len(skipped)}\n")

        if args.dry_run:
            if targets:
                print("Would deploy to:")
                for r in targets:
                    print(f"  - {r}")
            else:
                print("All scanned repos already have both Cerberus secrets. Nothing to do.")
            if skipped and not args.all:
                print(f"\nAlready configured ({len(skipped)}): {', '.join(skipped)}")
            return 0

        if not targets:
            print("All scanned repos already have both Cerberus secrets. Nothing to do.")
            return 0

        assert pem_content is not None  # _load_pem populated this above

        succeeded = 0
        failed: list[str] = []
        for i, repo in enumerate(targets, 1):
            prefix = f"[{i}/{len(targets)}] {repo}"
            ok, failed_names = deploy_to_repo(repo, pem_content, pat)
            if ok:
                print(f"  {prefix}: OK")
                succeeded += 1
            else:
                print(f"  {prefix}: FAILED ({', '.join(failed_names)})")
                failed.append(repo)

    print(f"\n{'=' * 50}")
    print(f"Done: {succeeded}/{len(targets)} repos configured")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    if pem_path is not None:
        print(f"\n*** NOW DELETE THE .pem FILE: {pem_path} ***")
        print("The secret is stored in GitHub -- you never need the file again.")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
