"""Tests for the fleet auto-merge readiness audit + workflow deploy (#1128)."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


audit = _load("audit_fleet_auto_merge_readiness")
deploy = _load("deploy_auto_reviewer_workflow")


# =========================================================================
# audit_fleet_auto_merge_readiness
# =========================================================================

def _strict_protection_body():
    return {
        "required_pull_request_reviews": {"required_approving_review_count": 1},
        "required_status_checks": {"contexts": ["pr-sentinel / issue-reference"]},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
    }


def _ready_secrets_body():
    return {"secrets": [
        {"name": "REVIEWER_APP_ID"},
        {"name": "REVIEWER_APP_PRIVATE_KEY"},
    ]}


def test_audit_one_ready_repo_passes_all_four_dimensions():
    repo = {"name": "good", "defaultBranchRef": {"name": "main"}}

    def fake_get(url, pat):
        if "/protection" in url:
            return 200, _strict_protection_body()
        if "/contents/.github/workflows/auto-reviewer.yml" in url:
            return 200, {"name": "auto-reviewer.yml"}
        if "/actions/secrets" in url or "/dependabot/secrets" in url:
            return 200, _ready_secrets_body()
        return 200, {}

    with patch.object(audit, "_api_get", side_effect=fake_get):
        r = audit.audit_one(repo, "pat")

    assert r.verdict == "READY"
    assert r.failures == []
    assert r.protection_strict is True
    assert r.workflow_present is True
    assert r.actions_secrets_complete is True
    assert r.dependabot_secrets_complete is True


def test_audit_one_repo_missing_workflow_classified_not_ready():
    """The exact scenario that motivated #1128 -- comp-environ has strict
    protection but no auto-reviewer.yml."""
    repo = {"name": "comp-environ", "defaultBranchRef": {"name": "main"}}

    def fake_get(url, pat):
        if "/protection" in url:
            return 200, _strict_protection_body()
        if "/contents/.github/workflows/auto-reviewer.yml" in url:
            return 404, None
        if "/actions/secrets" in url or "/dependabot/secrets" in url:
            return 200, _ready_secrets_body()
        return 200, {}

    with patch.object(audit, "_api_get", side_effect=fake_get):
        r = audit.audit_one(repo, "pat")

    assert r.verdict == "NOT_READY"
    assert "auto_reviewer_yml_missing" in r.failures
    # The other 3 dimensions should be OK; workflow is the only failure
    assert "branch_protection_not_strict" not in r.failures


def test_audit_one_repo_missing_dependabot_secrets_still_classified_ready():
    """Per #1131: Dependabot-scope is INFORMATIONAL ONLY -- not a readiness
    blocker. Cerberus skips dependabot PRs at the workflow level so the
    scope's emptiness is irrelevant to whether the repo can auto-merge
    agent PRs."""
    repo = {"name": "any-repo", "defaultBranchRef": {"name": "main"}}

    def fake_get(url, pat):
        if "/protection" in url:
            return 200, _strict_protection_body()
        if "/contents/.github/workflows/auto-reviewer.yml" in url:
            return 200, {}
        if "/actions/secrets" in url:
            return 200, _ready_secrets_body()
        if "/dependabot/secrets" in url:
            return 200, {"secrets": []}  # empty -- previously failed; now OK
        return 200, {}

    with patch.object(audit, "_api_get", side_effect=fake_get):
        r = audit.audit_one(repo, "pat")

    assert r.verdict == "READY", \
        "Dependabot-scope emptiness must not flag a repo as NOT_READY (#1131)"
    assert "dependabot_secrets_incomplete" not in r.failures
    # The dimension is still reported for visibility
    assert r.dependabot_secrets_complete is False


def test_audit_one_repo_with_no_default_branch_unknown():
    repo = {"name": "empty", "defaultBranchRef": None}
    with patch.object(audit, "_api_get") as mock_get:
        r = audit.audit_one(repo, "pat")
    assert r.verdict == "UNKNOWN"
    assert r.error == "no_default_branch"
    mock_get.assert_not_called()


def test_audit_one_accumulates_multiple_failures():
    """A repo can fail multiple dimensions; we report all of them.

    Post-#1131: only 3 dimensions count as readiness failures. Dependabot
    scope is reported but not in failures."""
    repo = {"name": "x", "defaultBranchRef": {"name": "main"}}

    def fake_get(url, pat):
        if "/protection" in url:
            return 404, None  # unprotected
        if "/contents/.github/workflows/auto-reviewer.yml" in url:
            return 404, None  # missing
        if "/actions/secrets" in url:
            return 200, {"secrets": []}  # missing both
        if "/dependabot/secrets" in url:
            return 200, {"secrets": []}
        return 200, {}

    with patch.object(audit, "_api_get", side_effect=fake_get):
        r = audit.audit_one(repo, "pat")

    assert r.verdict == "NOT_READY"
    # 3 readiness failures (protection, workflow, actions-secrets)
    # Dependabot-scope is reported in the field but NOT in failures (#1131)
    assert len(r.failures) == 3
    assert "dependabot_secrets_incomplete" not in r.failures


def test_audit_tsv_row_includes_all_four_dims():
    r = audit.RepoReadiness(
        name="x", default_branch="main",
        protection_strict=True, workflow_present=True,
        actions_secrets_complete=True, dependabot_secrets_complete=False,
        failures=["dependabot_secrets_incomplete"],
    )
    cols = r.tsv_row().split("\t")
    assert cols[0] == "x"
    assert cols[1] == "NOT_READY"
    assert cols[2] == "main"
    assert cols[3] == "True"
    assert cols[4] == "True"
    assert cols[5] == "True"
    assert cols[6] == "False"


# =========================================================================
# deploy_auto_reviewer_workflow
# =========================================================================

def test_caller_workflow_calls_az_reusable():
    """The caller content must reference the AZ reusable workflow path."""
    assert "uses: martymcenroe/AssemblyZero/.github/workflows/auto-reviewer.yml@main" \
        in deploy.CALLER_WORKFLOW
    assert "secrets: inherit" in deploy.CALLER_WORKFLOW
    assert "pull_request" in deploy.CALLER_WORKFLOW


def test_caller_workflow_triggers_on_only_needed_pr_events():
    """opened/synchronize/reopened -- nothing else. 'edited' must NOT be
    here per the existing auto-reviewer / pr-sentinel architecture."""
    assert "opened" in deploy.CALLER_WORKFLOW
    assert "synchronize" in deploy.CALLER_WORKFLOW
    assert "reopened" in deploy.CALLER_WORKFLOW
    assert "edited" not in deploy.CALLER_WORKFLOW


def test_deploy_main_rejects_apply_without_confirm_yes(capsys):
    rc = deploy.main(["--repos", "x", "--apply"])
    assert rc == 1
    assert "--confirm-yes" in capsys.readouterr().err


def test_deploy_main_rejects_empty_repos(capsys):
    rc = deploy.main(["--repos", ""])
    assert rc == 1
    err = capsys.readouterr().err
    assert "empty" in err.lower()


def test_deploy_skips_repo_that_already_has_workflow():
    with patch.object(deploy, "classic_pat_session") as mock_ctx, \
         patch.object(deploy, "get_default_branch", return_value="main"), \
         patch.object(deploy, "workflow_status", return_value=(True, "existing-sha")), \
         patch.object(deploy, "put_workflow") as mock_put:
        mock_ctx.return_value.__enter__.return_value = "pat"
        rc = deploy.main(["--repos", "alpha", "--apply", "--confirm-yes"])
    mock_put.assert_not_called()
    assert rc == 0


def test_deploy_puts_when_missing():
    # Test was missing two mocks. deploy.main probes BOTH classic
    # branch protection AND repository rulesets before deciding the
    # repo is "permissive" enough for a direct PUT. Without those
    # mocks the live GitHub API got hit with the fake "pat" string
    # and returned 401. Returning non-strict-protection + empty
    # rulesets sends deploy.main down the direct-PUT path -- which
    # is the path this test exercises (put_workflow called once
    # per repo, no bootstrap toggle).
    non_strict_protection = (
        {"enforce_admins": {"enabled": False}, "required_pull_request_reviews": None},
        None,
    )
    with patch.object(deploy, "classic_pat_session") as mock_ctx, \
         patch.object(deploy, "get_default_branch", return_value="main"), \
         patch.object(deploy, "get_protection", return_value=non_strict_protection), \
         patch.object(deploy, "list_blocking_rulesets", return_value=([], None)), \
         patch.object(deploy, "workflow_status", return_value=(False, None)), \
         patch.object(deploy, "put_workflow", return_value=(True, None)) as mock_put:
        mock_ctx.return_value.__enter__.return_value = "pat"
        rc = deploy.main(["--repos", "alpha,beta", "--apply", "--confirm-yes"])
    assert mock_put.call_count == 2
    assert rc == 0


def test_deploy_dry_run_never_calls_put():
    with patch.object(deploy, "classic_pat_session") as mock_ctx, \
         patch.object(deploy, "get_default_branch", return_value="main"), \
         patch.object(deploy, "workflow_status", return_value=(False, None)), \
         patch.object(deploy, "put_workflow") as mock_put:
        mock_ctx.return_value.__enter__.return_value = "pat"
        rc = deploy.main(["--repos", "alpha"])  # no --apply
    mock_put.assert_not_called()
    assert rc == 0


def test_deploy_returns_2_when_put_fails():
    with patch.object(deploy, "classic_pat_session") as mock_ctx, \
         patch.object(deploy, "get_default_branch", return_value="main"), \
         patch.object(deploy, "workflow_status", return_value=(False, None)), \
         patch.object(deploy, "put_workflow", return_value=(False, "PUT 403")):
        mock_ctx.return_value.__enter__.return_value = "pat"
        rc = deploy.main(["--repos", "alpha", "--apply", "--confirm-yes"])
    assert rc == 2
