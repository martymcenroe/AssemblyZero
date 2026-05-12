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
         patch.object(deploy, "list_blocking_rulesets", return_value=([], None)), \
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
    """Protected branch with enforce_admins=False AND no rulesets -> direct PUT."""
    prot = {"enforce_admins": {"enabled": False}}
    with patch.object(deploy, "get_protection", return_value=(prot, None)), \
         patch.object(deploy, "list_blocking_rulesets", return_value=([], None)), \
         patch.object(deploy, "put_workflow", return_value=(True, None)) as mock_put, \
         patch.object(deploy, "disable_enforce_admins") as mock_disable:
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is True
    assert bootstrap_used is False
    mock_put.assert_called_once()
    mock_disable.assert_not_called()


def test_deploy_strict_uses_bootstrap_path():
    """enforce_admins=True, no rulesets -> DELETE enforce_admins, PUT, POST enforce_admins."""
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
         patch.object(deploy, "list_blocking_rulesets", return_value=([], None)), \
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
         patch.object(deploy, "list_blocking_rulesets", return_value=([], None)), \
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
    assert "enable" in call_order
    assert call_order.index("enable") > call_order.index("put")


def test_deploy_strict_restoration_failure_is_surfaced(capsys):
    """If PUT succeeds but enforce_admins restore fails, surface restore error."""
    prot = {"enforce_admins": {"enabled": True}}

    with patch.object(deploy, "get_protection", return_value=(prot, None)), \
         patch.object(deploy, "list_blocking_rulesets", return_value=([], None)), \
         patch.object(deploy, "disable_enforce_admins", return_value=(True, None)), \
         patch.object(deploy, "put_workflow", return_value=(True, None)), \
         patch.object(deploy, "enable_enforce_admins",
                      return_value=(False, "POST 502: upstream")):
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "PUT succeeded but restoration failed" in err
    assert "502" in err
    assert bootstrap_used is True
    err_stream = capsys.readouterr().err
    assert "CRITICAL" in err_stream
    assert "protection/enforce_admins" in err_stream


def test_deploy_strict_disable_fails_no_put_attempt():
    """If we can't disable enforce_admins, never attempt the PUT."""
    prot = {"enforce_admins": {"enabled": True}}

    with patch.object(deploy, "get_protection", return_value=(prot, None)), \
         patch.object(deploy, "list_blocking_rulesets", return_value=([], None)), \
         patch.object(deploy, "disable_enforce_admins",
                      return_value=(False, "DELETE 403: forbidden")), \
         patch.object(deploy, "put_workflow") as mock_put, \
         patch.object(deploy, "enable_enforce_admins") as mock_enable:
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "could not disable enforce_admins" in err
    assert bootstrap_used is False
    mock_put.assert_not_called()
    mock_enable.assert_not_called()


def test_deploy_get_protection_error_aborts_early():
    """GET protection failure is fatal."""
    with patch.object(deploy, "get_protection", return_value=(None, "GET 503: upstream")), \
         patch.object(deploy, "list_blocking_rulesets") as mock_lrs, \
         patch.object(deploy, "disable_enforce_admins") as mock_disable, \
         patch.object(deploy, "put_workflow") as mock_put, \
         patch.object(deploy, "enable_enforce_admins") as mock_enable:
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "could not GET protection" in err
    assert bootstrap_used is False
    mock_lrs.assert_not_called()
    mock_disable.assert_not_called()
    mock_put.assert_not_called()
    mock_enable.assert_not_called()


def test_deploy_get_rulesets_error_aborts_early():
    """GET rulesets failure is fatal -- never touch any protection state."""
    with patch.object(deploy, "get_protection", return_value=(None, None)), \
         patch.object(deploy, "list_blocking_rulesets",
                      return_value=([], "GET rulesets 503")), \
         patch.object(deploy, "disable_enforce_admins") as mock_disable, \
         patch.object(deploy, "put_workflow") as mock_put, \
         patch.object(deploy, "enable_enforce_admins") as mock_enable:
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "could not GET rulesets" in err
    assert bootstrap_used is False
    mock_disable.assert_not_called()
    mock_put.assert_not_called()
    mock_enable.assert_not_called()


# ---------------------------------------------------------------------------
# #1137: ruleset bootstrap
# ---------------------------------------------------------------------------

def _fake_ruleset(rs_id: int, bypass_actors: list | None = None,
                  target: str = "branch", include: list | None = None,
                  enforcement: str = "active") -> dict:
    return {
        "id": rs_id,
        "name": "main",
        "target": target,
        "enforcement": enforcement,
        "conditions": {"ref_name": {"include": include or ["~DEFAULT_BRANCH"]}},
        "rules": [
            {"type": "deletion"},
            {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {"required_approving_review_count": 0}},
        ],
        "bypass_actors": bypass_actors or [],
    }


def test_deploy_ruleset_only_uses_bypass_path():
    """No classic strict protection but ruleset present -> add admin bypass,
    PUT, restore bypass."""
    rs = _fake_ruleset(14061333)
    call_order: list[str] = []

    def record_add(repo, rs_id, pat):
        call_order.append(f"add:{rs_id}")
        return (True, [], None)

    def record_put(*args, **kwargs):
        call_order.append("put")
        return (True, None)

    def record_restore(repo, rs_id, original, pat):
        call_order.append(f"restore:{rs_id}")
        return (True, None)

    with patch.object(deploy, "get_protection", return_value=(None, None)), \
         patch.object(deploy, "list_blocking_rulesets", return_value=([rs], None)), \
         patch.object(deploy, "add_admin_bypass", side_effect=record_add), \
         patch.object(deploy, "put_workflow", side_effect=record_put), \
         patch.object(deploy, "restore_bypass", side_effect=record_restore), \
         patch.object(deploy, "disable_enforce_admins") as mock_disable, \
         patch.object(deploy, "enable_enforce_admins") as mock_enable:
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is True
    assert err is None
    assert bootstrap_used is True
    assert call_order == ["add:14061333", "put", "restore:14061333"]
    # Classic toggles never fired
    mock_disable.assert_not_called()
    mock_enable.assert_not_called()


def test_deploy_classic_plus_ruleset_combined():
    """Both classic enforce_admins=True AND ruleset present -> both bypasses
    applied (classic first), PUT, both restored in reverse order (ruleset first)."""
    prot = {"enforce_admins": {"enabled": True}}
    rs = _fake_ruleset(14061333)
    call_order: list[str] = []

    def record(name, result):
        def _fn(*args, **kwargs):
            call_order.append(name)
            return result
        return _fn

    with patch.object(deploy, "get_protection", return_value=(prot, None)), \
         patch.object(deploy, "list_blocking_rulesets", return_value=([rs], None)), \
         patch.object(deploy, "disable_enforce_admins",
                      side_effect=record("classic_disable", (True, None))), \
         patch.object(deploy, "add_admin_bypass",
                      side_effect=lambda *a, **k: (call_order.append("rs_add"), (True, [], None))[1]), \
         patch.object(deploy, "put_workflow",
                      side_effect=record("put", (True, None))), \
         patch.object(deploy, "restore_bypass",
                      side_effect=lambda *a, **k: (call_order.append("rs_restore"), (True, None))[1]), \
         patch.object(deploy, "enable_enforce_admins",
                      side_effect=record("classic_enable", (True, None))):
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is True
    assert bootstrap_used is True
    # Apply order: classic_disable -> rs_add -> put
    # Restore order (reverse): rs_restore -> classic_enable
    assert call_order == ["classic_disable", "rs_add", "put", "rs_restore", "classic_enable"]


def test_deploy_ruleset_restoration_runs_even_on_put_failure():
    """PUT fails inside bootstrap -> ruleset bypass still gets restored."""
    rs = _fake_ruleset(14061333)
    call_order: list[str] = []

    with patch.object(deploy, "get_protection", return_value=(None, None)), \
         patch.object(deploy, "list_blocking_rulesets", return_value=([rs], None)), \
         patch.object(deploy, "add_admin_bypass",
                      side_effect=lambda *a, **k: (call_order.append("add"), (True, [], None))[1]), \
         patch.object(deploy, "put_workflow",
                      side_effect=lambda *a, **k: (call_order.append("put"), (False, "PUT 409: blocked"))[1]), \
         patch.object(deploy, "restore_bypass",
                      side_effect=lambda *a, **k: (call_order.append("restore"), (True, None))[1]):
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "blocked" in err
    assert bootstrap_used is True
    assert call_order == ["add", "put", "restore"]


def test_deploy_ruleset_restoration_failure_is_surfaced(capsys):
    """PUT succeeds but bypass restore fails -> CRITICAL stderr + restore error
    surfaced as load-bearing."""
    rs = _fake_ruleset(14061333)

    with patch.object(deploy, "get_protection", return_value=(None, None)), \
         patch.object(deploy, "list_blocking_rulesets", return_value=([rs], None)), \
         patch.object(deploy, "add_admin_bypass", return_value=(True, [], None)), \
         patch.object(deploy, "put_workflow", return_value=(True, None)), \
         patch.object(deploy, "restore_bypass",
                      return_value=(False, "PATCH ruleset 502")):
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "PUT succeeded but restoration failed" in err
    assert "ruleset 14061333" in err
    assert "502" in err
    err_stream = capsys.readouterr().err
    assert "CRITICAL" in err_stream
    assert "rulesets/14061333" in err_stream


def test_deploy_ruleset_add_bypass_fails_unwinds_prior_state(capsys):
    """If add_admin_bypass fails on the Nth ruleset, prior rulesets' bypasses
    AND classic enforce_admins must be unwound before returning."""
    prot = {"enforce_admins": {"enabled": True}}
    rs1 = _fake_ruleset(111)
    rs2 = _fake_ruleset(222)

    call_order: list[str] = []
    add_results = iter([(True, [], None), (False, None, "PATCH 403")])

    def fake_add(repo, rs_id, pat):
        call_order.append(f"add:{rs_id}")
        return next(add_results)

    with patch.object(deploy, "get_protection", return_value=(prot, None)), \
         patch.object(deploy, "list_blocking_rulesets", return_value=([rs1, rs2], None)), \
         patch.object(deploy, "disable_enforce_admins",
                      side_effect=lambda *a, **k: (call_order.append("classic_disable"), (True, None))[1]), \
         patch.object(deploy, "add_admin_bypass", side_effect=fake_add), \
         patch.object(deploy, "put_workflow") as mock_put, \
         patch.object(deploy, "restore_bypass",
                      side_effect=lambda *a, **k: (call_order.append("rs_restore"), (True, None))[1]), \
         patch.object(deploy, "enable_enforce_admins",
                      side_effect=lambda *a, **k: (call_order.append("classic_enable"), (True, None))[1]):
        ok, err, bootstrap_used = deploy.deploy_with_bootstrap("repo", "main", "pat")

    assert ok is False
    assert "could not add bypass to ruleset 222" in err
    assert bootstrap_used is True
    # Sequence: classic_disable -> add:111 (ok) -> add:222 (fails) ->
    #           emergency_unwind: rs_restore(111) -> classic_enable
    # PUT is never called.
    assert call_order == ["classic_disable", "add:111", "add:222", "rs_restore", "classic_enable"]
    mock_put.assert_not_called()


# ---------------------------------------------------------------------------
# list_blocking_rulesets
# ---------------------------------------------------------------------------

def test_list_blocking_rulesets_skips_inactive():
    """enforcement != 'active' rulesets are not blocking."""
    summaries = [{"id": 1, "name": "x", "target": "branch", "enforcement": "disabled"}]
    with patch.object(deploy.requests, "get",
                      return_value=_fake_response(200, summaries)):
        rulesets, err = deploy.list_blocking_rulesets("repo", "main", "pat")
    assert rulesets == []
    assert err is None


def test_list_blocking_rulesets_filters_by_target():
    """target != 'branch' rulesets are skipped."""
    summaries = [{"id": 1, "name": "x", "target": "tag", "enforcement": "active"}]
    with patch.object(deploy.requests, "get",
                      return_value=_fake_response(200, summaries)):
        rulesets, err = deploy.list_blocking_rulesets("repo", "main", "pat")
    assert rulesets == []


def test_list_blocking_rulesets_filters_by_ref_include():
    """Ruleset targeting a different branch is not returned for ours."""
    summaries = [{"id": 1, "name": "x", "target": "branch", "enforcement": "active"}]
    detail = _fake_ruleset(1, include=["refs/heads/dev"])  # not main
    responses = iter([
        _fake_response(200, summaries),
        _fake_response(200, detail),
    ])
    with patch.object(deploy.requests, "get",
                      side_effect=lambda *a, **k: next(responses)):
        rulesets, err = deploy.list_blocking_rulesets("repo", "main", "pat")
    assert rulesets == []


def test_list_blocking_rulesets_includes_default_branch_match():
    """Ruleset with ~DEFAULT_BRANCH include is captured."""
    summaries = [{"id": 99, "name": "main", "target": "branch", "enforcement": "active"}]
    detail = _fake_ruleset(99, include=["~DEFAULT_BRANCH"])
    responses = iter([
        _fake_response(200, summaries),
        _fake_response(200, detail),
    ])
    with patch.object(deploy.requests, "get",
                      side_effect=lambda *a, **k: next(responses)):
        rulesets, err = deploy.list_blocking_rulesets("repo", "main", "pat")
    assert len(rulesets) == 1
    assert rulesets[0]["id"] == 99


def test_list_blocking_rulesets_includes_explicit_ref_match():
    """Ruleset with refs/heads/main include is captured."""
    summaries = [{"id": 99, "name": "main", "target": "branch", "enforcement": "active"}]
    detail = _fake_ruleset(99, include=["refs/heads/main"])
    responses = iter([
        _fake_response(200, summaries),
        _fake_response(200, detail),
    ])
    with patch.object(deploy.requests, "get",
                      side_effect=lambda *a, **k: next(responses)):
        rulesets, err = deploy.list_blocking_rulesets("repo", "main", "pat")
    assert len(rulesets) == 1


def test_list_blocking_rulesets_404_means_empty_no_error():
    """Repo with no rulesets surface (404) returns empty list, no error."""
    with patch.object(deploy.requests, "get", return_value=_fake_response(404)):
        rulesets, err = deploy.list_blocking_rulesets("repo", "main", "pat")
    assert rulesets == []
    assert err is None


def test_list_blocking_rulesets_5xx_returns_error():
    with patch.object(deploy.requests, "get",
                      return_value=_fake_response(503, text="upstream")):
        rulesets, err = deploy.list_blocking_rulesets("repo", "main", "pat")
    assert rulesets == []
    assert err is not None
    assert "503" in err


# ---------------------------------------------------------------------------
# add_admin_bypass / restore_bypass
# ---------------------------------------------------------------------------

def test_add_admin_bypass_captures_existing_actors():
    """GET ruleset returns existing bypass_actors -> PATCH adds admin to
    the list AND returns the original for later restoration."""
    existing = [{"actor_id": 9999, "actor_type": "Team", "bypass_mode": "always"}]
    get_resp = _fake_response(200, {"bypass_actors": existing})
    patch_resp = _fake_response(200)

    captured: dict = {}

    def fake_patch(url, **kwargs):
        captured["json"] = kwargs.get("json")
        return patch_resp

    with patch.object(deploy.requests, "get", return_value=get_resp), \
         patch.object(deploy.requests, "patch", side_effect=fake_patch):
        ok, original, err = deploy.add_admin_bypass("repo", 14061333, "pat")

    assert ok is True
    assert err is None
    assert original == existing
    # New list contains the original Team actor PLUS the admin role
    sent_actors = captured["json"]["bypass_actors"]
    assert len(sent_actors) == 2
    assert any(a["actor_type"] == "Team" for a in sent_actors)
    assert any(
        a["actor_type"] == "RepositoryRole"
        and a["actor_id"] == deploy.REPO_ADMIN_ROLE_ID
        and a["bypass_mode"] == "always"
        for a in sent_actors
    )


def test_add_admin_bypass_idempotent_when_already_present():
    """If admin role is already a bypass_actor, no PATCH is sent."""
    existing = [{
        "actor_id": deploy.REPO_ADMIN_ROLE_ID,
        "actor_type": "RepositoryRole",
        "bypass_mode": "always",
    }]
    get_resp = _fake_response(200, {"bypass_actors": existing})

    with patch.object(deploy.requests, "get", return_value=get_resp), \
         patch.object(deploy.requests, "patch") as mock_patch:
        ok, original, err = deploy.add_admin_bypass("repo", 14061333, "pat")

    assert ok is True
    assert err is None
    assert original == existing
    mock_patch.assert_not_called()


def test_add_admin_bypass_get_failure_no_patch():
    with patch.object(deploy.requests, "get",
                      return_value=_fake_response(404, text="not found")), \
         patch.object(deploy.requests, "patch") as mock_patch:
        ok, original, err = deploy.add_admin_bypass("repo", 999, "pat")
    assert ok is False
    assert original is None
    assert err is not None
    mock_patch.assert_not_called()


def test_restore_bypass_sends_original_list():
    captured: dict = {}

    def fake_patch(url, **kwargs):
        captured["json"] = kwargs.get("json")
        return _fake_response(200)

    original = [{"actor_id": 1, "actor_type": "OrganizationAdmin", "bypass_mode": "always"}]
    with patch.object(deploy.requests, "patch", side_effect=fake_patch):
        ok, err = deploy.restore_bypass("repo", 123, original, "pat")
    assert ok is True
    assert err is None
    assert captured["json"]["bypass_actors"] == original


def test_restore_bypass_failure_returns_error():
    with patch.object(deploy.requests, "patch",
                      return_value=_fake_response(502, text="upstream")):
        ok, err = deploy.restore_bypass("repo", 123, [], "pat")
    assert ok is False
    assert err is not None
    assert "502" in err


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
