"""Tests for tools/deploy_auto_reviewer_workflow.py (#1128, #1135).

#1135 introduces a bootstrap path for STRICT-protected repos missing the
workflow file: temporarily DELETE enforce_admins, PUT, restore. These
tests cover both the permissive and strict deploy paths plus the
try/finally restoration behavior.
"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_spec = importlib.util.spec_from_file_location(
    "deploy_auto_reviewer_workflow",
    TOOLS_DIR / "deploy_auto_reviewer_workflow.py",
)
deploy = importlib.util.module_from_spec(_spec)
sys.modules["deploy_auto_reviewer_workflow"] = deploy
_spec.loader.exec_module(deploy)


# ---------------------------------------------------------------------------
# is_enforce_admins_on
# ---------------------------------------------------------------------------

def test_is_enforce_admins_on_none_is_false():
    assert deploy.is_enforce_admins_on(None) is False


def test_is_enforce_admins_on_missing_field_is_false():
    assert deploy.is_enforce_admins_on({}) is False


def test_is_enforce_admins_on_disabled_is_false():
    assert deploy.is_enforce_admins_on({"enforce_admins": {"enabled": False}}) is False


def test_is_enforce_admins_on_enabled_is_true():
    assert deploy.is_enforce_admins_on({"enforce_admins": {"enabled": True}}) is True


def test_is_enforce_admins_on_malformed_field_is_false():
    """If the API returns a non-dict in enforce_admins, treat as off."""
    assert deploy.is_enforce_admins_on({"enforce_admins": "true"}) is False


# ---------------------------------------------------------------------------
# get_protection
# ---------------------------------------------------------------------------

def _fake_response(status: int, json_body: dict | list | None = None,
                   text: str = "") -> object:
    class _R:
        status_code = status

        def json(self):
            return json_body

    r = _R()
    r.text = text
    return r


def test_get_protection_404_returns_none_no_error():
    with patch.object(deploy.requests, "get", return_value=_fake_response(404)):
        prot, err = deploy.get_protection("repo", "main", "pat")
    assert prot is None
    assert err is None


def test_get_protection_200_returns_dict():
    body = {"enforce_admins": {"enabled": True}}
    with patch.object(deploy.requests, "get", return_value=_fake_response(200, body)):
        prot, err = deploy.get_protection("repo", "main", "pat")
    assert prot == body
    assert err is None


def test_get_protection_5xx_returns_error():
    with patch.object(deploy.requests, "get",
                      return_value=_fake_response(503, text="upstream error")):
        prot, err = deploy.get_protection("repo", "main", "pat")
    assert prot is None
    assert err is not None
    assert "503" in err


def test_get_protection_network_failure_returns_error():
    from requests.exceptions import RequestException
    with patch.object(deploy.requests, "get",
                      side_effect=RequestException("boom")):
        prot, err = deploy.get_protection("repo", "main", "pat")
    assert prot is None
    assert err is not None
    assert "network" in err


# ---------------------------------------------------------------------------
# disable_enforce_admins / enable_enforce_admins
# ---------------------------------------------------------------------------

def test_disable_enforce_admins_204_succeeds():
    with patch.object(deploy.requests, "delete", return_value=_fake_response(204)):
        ok, err = deploy.disable_enforce_admins("repo", "main", "pat")
    assert ok is True
    assert err is None


def test_disable_enforce_admins_403_fails():
    with patch.object(deploy.requests, "delete",
                      return_value=_fake_response(403, text="forbidden")):
        ok, err = deploy.disable_enforce_admins("repo", "main", "pat")
    assert ok is False
    assert err is not None
    assert "403" in err


def test_enable_enforce_admins_200_succeeds():
    with patch.object(deploy.requests, "post", return_value=_fake_response(200)):
        ok, err = deploy.enable_enforce_admins("repo", "main", "pat")
    assert ok is True
    assert err is None


def test_enable_enforce_admins_403_fails():
    with patch.object(deploy.requests, "post",
                      return_value=_fake_response(403, text="forbidden")):
        ok, err = deploy.enable_enforce_admins("repo", "main", "pat")
    assert ok is False
    assert err is not None
    assert "403" in err


# ---------------------------------------------------------------------------
# deploy_with_bootstrap
# ---------------------------------------------------------------------------

def test_deploy_permissive_uses_direct_put_no_bootstrap():
    """No protection on the branch -> direct PUT, bootstrap_used=False."""
    with patch.object(deploy, "get_protection", return_value=(None, None)), \
         patch.object(deploy, "put_workflow", return_value=(True, None)) as mock_put, \
         patch.object(deploy, "disable_enforce_admins") as mock_disable, \
         patch.object(deploy, "enable_enforce_admins") as mock_enable:
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is True
    assert err is None
    assert bootstrap_used is False
    mock_put.assert_called_once()
    mock_disable.assert_not_called()
    mock_enable.assert_not_called()


def test_deploy_protected_but_enforce_admins_off_uses_direct_put():
    """Protected branch with enforce_admins=False -> still direct PUT.
    Admin push bypasses required reviews/checks naturally."""
    prot = {"enforce_admins": {"enabled": False}}
    with patch.object(deploy, "get_protection", return_value=(prot, None)), \
         patch.object(deploy, "put_workflow", return_value=(True, None)) as mock_put, \
         patch.object(deploy, "disable_enforce_admins") as mock_disable:
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is True
    assert bootstrap_used is False
    mock_put.assert_called_once()
    mock_disable.assert_not_called()


def test_deploy_strict_uses_bootstrap_path():
    """enforce_admins=True -> DELETE enforce_admins, PUT, POST enforce_admins."""
    prot = {"enforce_admins": {"enabled": True}}
    call_order: list[str] = []

    def record_disable(*args, **kwargs):
        call_order.append("disable")
        return (True, None)

    def record_put(*args, **kwargs):
        call_order.append("put")
        return (True, None)

    def record_enable(*args, **kwargs):
        call_order.append("enable")
        return (True, None)

    with patch.object(deploy, "get_protection", return_value=(prot, None)), \
         patch.object(deploy, "disable_enforce_admins", side_effect=record_disable), \
         patch.object(deploy, "put_workflow", side_effect=record_put), \
         patch.object(deploy, "enable_enforce_admins", side_effect=record_enable):
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is True
    assert err is None
    assert bootstrap_used is True
    assert call_order == ["disable", "put", "enable"]


def test_deploy_strict_restoration_happens_even_when_put_fails():
    """If the PUT fails inside bootstrap, enforce_admins must still be
    restored via finally."""
    prot = {"enforce_admins": {"enabled": True}}
    call_order: list[str] = []

    def record(name, ok_result):
        def _fn(*args, **kwargs):
            call_order.append(name)
            return ok_result
        return _fn

    with patch.object(deploy, "get_protection", return_value=(prot, None)), \
         patch.object(deploy, "disable_enforce_admins",
                      side_effect=record("disable", (True, None))), \
         patch.object(deploy, "put_workflow",
                      side_effect=record("put", (False, "PUT 409: blocked"))), \
         patch.object(deploy, "enable_enforce_admins",
                      side_effect=record("enable", (True, None))):
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "blocked" in err
    assert bootstrap_used is True
    # finally must have run -- enable_enforce_admins was called
    assert "enable" in call_order
    assert call_order.index("enable") > call_order.index("put")


def test_deploy_strict_restoration_failure_is_surfaced(capsys):
    """If the PUT succeeds but the restore fails, the restore error is
    surfaced (load-bearing) and a recovery hint is printed to stderr."""
    prot = {"enforce_admins": {"enabled": True}}

    with patch.object(deploy, "get_protection", return_value=(prot, None)), \
         patch.object(deploy, "disable_enforce_admins", return_value=(True, None)), \
         patch.object(deploy, "put_workflow", return_value=(True, None)), \
         patch.object(deploy, "enable_enforce_admins",
                      return_value=(False, "POST 502: upstream")):
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "PUT succeeded but enforce_admins restore failed" in err
    assert "502" in err
    assert bootstrap_used is True
    # Recovery hint must be printed
    err_stream = capsys.readouterr().err
    assert "CRITICAL" in err_stream
    assert "protection/enforce_admins" in err_stream


def test_deploy_strict_disable_fails_no_put_attempt():
    """If we can't disable enforce_admins, never attempt the PUT --
    restoration also doesn't run because there's nothing to restore."""
    prot = {"enforce_admins": {"enabled": True}}

    with patch.object(deploy, "get_protection", return_value=(prot, None)), \
         patch.object(deploy, "disable_enforce_admins",
                      return_value=((False, "DELETE 403: forbidden"))), \
         patch.object(deploy, "put_workflow") as mock_put, \
         patch.object(deploy, "enable_enforce_admins") as mock_enable:
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "could not disable enforce_admins" in err
    assert bootstrap_used is False
    mock_put.assert_not_called()
    mock_enable.assert_not_called()


def test_deploy_get_protection_error_aborts_early():
    """GET protection failure is fatal -- never touch enforce_admins
    or attempt PUT when we can't even see the current state."""
    with patch.object(deploy, "get_protection", return_value=(None, "GET 503: upstream")), \
         patch.object(deploy, "disable_enforce_admins") as mock_disable, \
         patch.object(deploy, "put_workflow") as mock_put, \
         patch.object(deploy, "enable_enforce_admins") as mock_enable:
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "could not GET protection" in err
    assert bootstrap_used is False
    mock_disable.assert_not_called()
    mock_put.assert_not_called()
    mock_enable.assert_not_called()


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------

def test_main_apply_uses_deploy_with_bootstrap_not_direct_put():
    """Regression guard for the #1135 fix: main's apply path must call
    deploy_with_bootstrap (the wrapper that handles strict repos),
    not put_workflow directly."""
    with patch.object(deploy, "classic_pat_session") as mock_ctx, \
         patch.object(deploy, "get_default_branch", return_value="main"), \
         patch.object(deploy, "workflow_status", return_value=(False, None)), \
         patch.object(deploy, "deploy_with_bootstrap",
                      return_value=(True, None, True)) as mock_deploy, \
         patch.object(deploy, "put_workflow") as mock_direct_put:
        mock_ctx.return_value.__enter__.return_value = "fake-pat"
        rc = deploy.main(["--repos", "boostgauge", "--apply", "--confirm-yes"])

    assert rc == 0
    mock_deploy.assert_called_once_with("boostgauge", "main", "fake-pat")
    # The direct put_workflow MUST NOT be called from main's apply path --
    # all PUT routing goes through deploy_with_bootstrap.
    mock_direct_put.assert_not_called()


def test_main_apply_path_handles_failures():
    def fake_deploy(repo, branch, pat):
        if repo == "boostgauge":
            return (False, "PUT 409: blocked", False)
        return (True, None, True)

    with patch.object(deploy, "classic_pat_session") as mock_ctx, \
         patch.object(deploy, "get_default_branch", return_value="main"), \
         patch.object(deploy, "workflow_status", return_value=(False, None)), \
         patch.object(deploy, "deploy_with_bootstrap", side_effect=fake_deploy):
        mock_ctx.return_value.__enter__.return_value = "fake-pat"
        rc = deploy.main([
            "--repos", "boostgauge,gh-galaxy-quest,comp-environ",
            "--apply", "--confirm-yes",
        ])

    assert rc == 2  # at least one failure


def test_main_rejects_apply_without_confirm_yes(capsys):
    rc = deploy.main(["--repos", "boostgauge", "--apply"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "--confirm-yes" in err


def test_main_dry_run_does_not_call_deploy_with_bootstrap():
    """Dry-run inspects but does NOT call deploy_with_bootstrap."""
    with patch.object(deploy, "classic_pat_session") as mock_ctx, \
         patch.object(deploy, "get_default_branch", return_value="main"), \
         patch.object(deploy, "workflow_status", return_value=(False, None)), \
         patch.object(deploy, "deploy_with_bootstrap") as mock_deploy:
        mock_ctx.return_value.__enter__.return_value = "fake-pat"
        rc = deploy.main(["--repos", "boostgauge,gh-galaxy-quest"])  # no --apply

    assert rc == 0
    mock_deploy.assert_not_called()


def test_main_skips_repos_with_existing_workflow():
    """Idempotent: if workflow_status reports the file is already present,
    deploy_with_bootstrap is not called for that repo."""
    def fake_status(repo, branch, pat):
        if repo == "boostgauge":
            return (True, "sha-abc")  # already present
        return (False, None)

    with patch.object(deploy, "classic_pat_session") as mock_ctx, \
         patch.object(deploy, "get_default_branch", return_value="main"), \
         patch.object(deploy, "workflow_status", side_effect=fake_status), \
         patch.object(deploy, "deploy_with_bootstrap",
                      return_value=(True, None, False)) as mock_deploy:
        mock_ctx.return_value.__enter__.return_value = "fake-pat"
        rc = deploy.main([
            "--repos", "boostgauge,comp-environ",
            "--apply", "--confirm-yes",
        ])

    assert rc == 0
    # boostgauge skipped (already has file); only comp-environ deploys
    assert mock_deploy.call_count == 1
    assert mock_deploy.call_args.args[0] == "comp-environ"
