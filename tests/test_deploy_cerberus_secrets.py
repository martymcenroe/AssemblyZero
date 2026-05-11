"""Tests for tools/deploy_cerberus_secrets.py argparse + filter behavior (Issue #763)."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
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
    """Build a fake verify_secrets that says `present_repos` are configured."""
    def fake_verify(repo, pat):
        if repo in present_repos:
            return (True, [])
        return (False, ["REVIEWER_APP_ID", "REVIEWER_APP_PRIVATE_KEY"])
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
    assert "pem_path is required" in err
