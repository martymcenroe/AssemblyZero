"""Tests for tools/deploy_cerberus_secrets.py argparse + filter behavior (Issue #763)."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
# _pat_session uses gpg-decrypted PAT and triggers pinentry on import-time
# touch in some cases; ensure the module loads in test env by faking sys.path
# behavior the script uses.
sys.path.insert(0, str(TOOLS_DIR))

_spec = importlib.util.spec_from_file_location(
    "deploy_cerberus_secrets", TOOLS_DIR / "deploy_cerberus_secrets.py"
)
deploy_cerberus_secrets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deploy_cerberus_secrets)


# ---- _parse_args ----

def test_parse_args_default_no_pem_no_flags():
    args = deploy_cerberus_secrets._parse_args([])
    assert args.pem_path is None
    assert args.all is False
    assert args.repo is None
    assert args.dry_run is False


def test_parse_args_with_pem_only():
    args = deploy_cerberus_secrets._parse_args(["/path/to/key.pem"])
    assert args.pem_path == "/path/to/key.pem"
    assert args.all is False


def test_parse_args_with_all_flag():
    args = deploy_cerberus_secrets._parse_args(["/x.pem", "--all"])
    assert args.all is True


def test_parse_args_with_repo_flag():
    args = deploy_cerberus_secrets._parse_args(["/x.pem", "--repo", "boostgauge"])
    assert args.repo == "boostgauge"


def test_parse_args_with_dry_run_no_pem():
    args = deploy_cerberus_secrets._parse_args(["--dry-run"])
    assert args.dry_run is True
    assert args.pem_path is None


# ---- _select_target_repos ----

def _verify_factory(present_repos: set[str]):
    """Build a fake verify_secrets that says `present_repos` are configured.

    Returns the post-#1118 missing-descriptor shape: when a repo is missing,
    the list contains '<scope>/<name>' entries covering both scopes.
    """
    def fake_verify(repo, pat):
        if repo in present_repos:
            return (True, [])
        missing = [
            "actions/REVIEWER_APP_ID",
            "actions/REVIEWER_APP_PRIVATE_KEY",
            "dependabot/REVIEWER_APP_ID",
            "dependabot/REVIEWER_APP_PRIVATE_KEY",
        ]
        return (False, missing)
    return fake_verify


def test_select_target_repos_default_filters_already_configured():
    args = deploy_cerberus_secrets._parse_args([])  # no flags
    with patch.object(deploy_cerberus_secrets, "get_all_repos",
                      return_value=["alpha", "beta", "gamma"]):
        with patch.object(deploy_cerberus_secrets, "verify_secrets",
                          side_effect=_verify_factory({"alpha", "beta"})):
            targets, skipped = deploy_cerberus_secrets._select_target_repos(args, "fake-pat")
    assert targets == ["gamma"]  # only the one missing secrets
    assert set(skipped) == {"alpha", "beta"}


def test_select_target_repos_all_flag_returns_everything():
    args = deploy_cerberus_secrets._parse_args(["x.pem", "--all"])
    with patch.object(deploy_cerberus_secrets, "get_all_repos",
                      return_value=["alpha", "beta", "gamma"]):
        # verify_secrets should not be called when --all is set
        with patch.object(deploy_cerberus_secrets, "verify_secrets") as mock_verify:
            targets, skipped = deploy_cerberus_secrets._select_target_repos(args, "fake-pat")
    assert targets == ["alpha", "beta", "gamma"]
    assert skipped == []
    mock_verify.assert_not_called()


def test_select_target_repos_repo_flag_targets_one_only():
    args = deploy_cerberus_secrets._parse_args(["x.pem", "--repo", "boostgauge"])
    with patch.object(deploy_cerberus_secrets, "get_all_repos") as mock_list_all:
        with patch.object(deploy_cerberus_secrets, "verify_secrets",
                          side_effect=_verify_factory(set())):  # boostgauge missing
            targets, skipped = deploy_cerberus_secrets._select_target_repos(args, "fake-pat")
    assert targets == ["boostgauge"]
    assert skipped == []
    # get_all_repos must NOT be called when --repo is set (we don't need the fleet)
    mock_list_all.assert_not_called()


def test_select_target_repos_repo_flag_with_already_configured_returns_empty_targets():
    """If --repo is given but that repo already has secrets, target list is empty (unless --all)."""
    args = deploy_cerberus_secrets._parse_args(["x.pem", "--repo", "already-set"])
    with patch.object(deploy_cerberus_secrets, "verify_secrets",
                      side_effect=_verify_factory({"already-set"})):
        targets, skipped = deploy_cerberus_secrets._select_target_repos(args, "fake-pat")
    assert targets == []
    assert skipped == ["already-set"]


def test_select_target_repos_repo_flag_plus_all_skips_filtering():
    args = deploy_cerberus_secrets._parse_args(["x.pem", "--repo", "already-set", "--all"])
    with patch.object(deploy_cerberus_secrets, "verify_secrets") as mock_verify:
        targets, skipped = deploy_cerberus_secrets._select_target_repos(args, "fake-pat")
    assert targets == ["already-set"]
    assert skipped == []
    mock_verify.assert_not_called()


# ---- main() rejects bad invocations ----

def test_main_returns_1_when_no_pem_and_no_dry_run(capsys):
    rc = deploy_cerberus_secrets.main([])  # neither pem nor --dry-run
    assert rc == 1
    err = capsys.readouterr().err
    assert "pem_path (plaintext) or --cerberus-pem-gpg PATH (encrypted) is required" in err


# ---- #1118: dual-scope (Actions + Dependabot) deployment ----

def test_scopes_constant_includes_both_actions_and_dependabot():
    """Regression guard against single-scope regression."""
    assert deploy_cerberus_secrets._SCOPES == ("actions", "dependabot"), \
        "Cerberus must deploy to both scopes; dependabot PRs fail without it (#1118)"


def test_get_public_key_uses_scope_in_url():
    """Default scope is actions (back-compat); dependabot scope hits a
    different URL path. #1118."""
    captured_urls: list[str] = []

    def fake_request(method, url, pat, **kw):
        captured_urls.append(url)
        # Minimal valid public-key response shape
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"key_id": "k", "key": "AAAA"}
        return r

    with patch.object(deploy_cerberus_secrets, "_request_with_retry", side_effect=fake_request):
        deploy_cerberus_secrets._get_public_key("alpha", "pat")
        deploy_cerberus_secrets._get_public_key("alpha", "pat", scope="dependabot")

    assert "/actions/secrets/public-key" in captured_urls[0]
    assert "/dependabot/secrets/public-key" in captured_urls[1]


def test_set_secret_uses_scope_in_url():
    """PUT must go to the correct scope-specific path. #1118."""
    captured: list[tuple[str, str]] = []  # (method, url)

    def fake_request(method, url, pat, **kw):
        captured.append((method, url))
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"key_id": "k", "key": "AAAA" * 8}  # valid b64 32-byte key
        return r

    # Use a real-ish 32-byte public key b64 so the sealed-box encryption works.
    import base64
    import nacl.public
    real_key = nacl.public.PrivateKey.generate().public_key
    real_key_b64 = base64.b64encode(bytes(real_key)).decode("ascii")

    def fake_request_with_real_key(method, url, pat, **kw):
        captured.append((method, url))
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"key_id": "k", "key": real_key_b64}
        return r

    with patch.object(deploy_cerberus_secrets, "_request_with_retry",
                      side_effect=fake_request_with_real_key):
        deploy_cerberus_secrets.set_secret("alpha", "TEST", "value", "pat", scope="actions")
        deploy_cerberus_secrets.set_secret("alpha", "TEST", "value", "pat", scope="dependabot")

    # 4 calls total: 2x (public-key GET + secret PUT)
    methods_urls = [(m, u.split("/repos/")[-1]) for m, u in captured]
    # Actions scope
    assert any("actions/secrets/public-key" in u for m, u in methods_urls if m == "GET")
    assert any("actions/secrets/TEST" in u for m, u in methods_urls if m == "PUT")
    # Dependabot scope
    assert any("dependabot/secrets/public-key" in u for m, u in methods_urls if m == "GET")
    assert any("dependabot/secrets/TEST" in u for m, u in methods_urls if m == "PUT")


def test_deploy_to_repo_writes_to_both_scopes():
    """deploy_to_repo must write each secret to BOTH Actions and Dependabot.
    Four total set_secret calls per repo: 2 secrets × 2 scopes. #1118."""
    set_secret_calls: list[tuple[str, str, str]] = []

    def fake_set_secret(repo, name, value, pat, scope="actions"):
        set_secret_calls.append((repo, name, scope))
        return True

    with patch.object(deploy_cerberus_secrets, "set_secret", side_effect=fake_set_secret):
        ok, failed = deploy_cerberus_secrets.deploy_to_repo("alpha", "pem-content", "pat")

    assert ok is True
    assert failed == []
    # Should be 4 calls: REVIEWER_APP_ID + REVIEWER_APP_PRIVATE_KEY × actions + dependabot
    scope_name_pairs = {(name, scope) for _, name, scope in set_secret_calls}
    assert ("REVIEWER_APP_ID", "actions") in scope_name_pairs
    assert ("REVIEWER_APP_PRIVATE_KEY", "actions") in scope_name_pairs
    assert ("REVIEWER_APP_ID", "dependabot") in scope_name_pairs
    assert ("REVIEWER_APP_PRIVATE_KEY", "dependabot") in scope_name_pairs
    assert len(scope_name_pairs) == 4


def test_deploy_to_repo_reports_failures_by_scope_and_name():
    """Failed entries must include the scope so the operator can see exactly
    which scope failed. #1118."""
    def fake_set_secret(repo, name, value, pat, scope="actions"):
        # Simulate only the dependabot/REVIEWER_APP_PRIVATE_KEY failing
        if scope == "dependabot" and name == "REVIEWER_APP_PRIVATE_KEY":
            return False
        return True

    with patch.object(deploy_cerberus_secrets, "set_secret", side_effect=fake_set_secret):
        ok, failed = deploy_cerberus_secrets.deploy_to_repo("alpha", "pem-content", "pat")

    assert ok is False
    assert failed == ["dependabot/REVIEWER_APP_PRIVATE_KEY"]


def test_verify_secrets_reports_missing_per_scope():
    """verify_secrets must check BOTH scopes and report which scope-name
    combos are missing. #1118."""
    def fake_request(method, url, pat, **kw):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status_code = 200
        # Actions scope has REVIEWER_APP_ID only; Dependabot scope has both.
        if "/actions/secrets" in url and "public-key" not in url:
            r.json.return_value = {"secrets": [{"name": "REVIEWER_APP_ID"}]}
        elif "/dependabot/secrets" in url and "public-key" not in url:
            r.json.return_value = {"secrets": [
                {"name": "REVIEWER_APP_ID"},
                {"name": "REVIEWER_APP_PRIVATE_KEY"},
            ]}
        else:
            r.json.return_value = {}
        return r

    with patch.object(deploy_cerberus_secrets, "_request_with_retry", side_effect=fake_request):
        ok, missing = deploy_cerberus_secrets.verify_secrets("alpha", "pat")

    assert ok is False
    assert "actions/REVIEWER_APP_PRIVATE_KEY" in missing
    # Dependabot was complete; nothing missing from that scope
    assert not any(m.startswith("dependabot/") for m in missing)


def test_verify_secrets_passes_when_both_scopes_have_both_secrets():
    def fake_request(method, url, pat, **kw):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status_code = 200
        if "secrets" in url and "public-key" not in url:
            r.json.return_value = {"secrets": [
                {"name": "REVIEWER_APP_ID"},
                {"name": "REVIEWER_APP_PRIVATE_KEY"},
            ]}
        return r

    with patch.object(deploy_cerberus_secrets, "_request_with_retry", side_effect=fake_request):
        ok, missing = deploy_cerberus_secrets.verify_secrets("alpha", "pat")
    assert ok is True
    assert missing == []
