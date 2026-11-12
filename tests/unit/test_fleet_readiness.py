"""Tests for the fleet auto-merge readiness audit (#1128).

The tests of the caller deploy tool went with the tool (#4719).
"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS_DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


audit = _load("audit_fleet_auto_merge_readiness")


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


def test_audit_one_repo_without_the_caller_is_ready():
    """#4719: the Auto Review caller is retired and being removed fleet-wide.
    A repo with strict protection and the secrets but no auto-reviewer.yml is
    READY, and the caller's absence is still reported in its column."""
    repo = {"name": "no-caller", "defaultBranchRef": {"name": "main"}}

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

    assert r.verdict == "READY"
    assert r.failures == []
    assert r.error is None
    assert r.workflow_present is False


def test_audit_one_caller_lookup_error_changes_no_verdict():
    """#4719: the caller is informational, so an error reading it leaves the
    column blank instead of turning the repo UNKNOWN."""
    repo = {"name": "flaky", "defaultBranchRef": {"name": "main"}}

    def fake_get(url, pat):
        if "/protection" in url:
            return 200, _strict_protection_body()
        if "/contents/.github/workflows/auto-reviewer.yml" in url:
            return 502, None
        if "/actions/secrets" in url or "/dependabot/secrets" in url:
            return 200, _ready_secrets_body()
        return 200, {}

    with patch.object(audit, "_api_get", side_effect=fake_get):
        r = audit.audit_one(repo, "pat")

    assert r.verdict == "READY"
    assert r.error is None
    assert r.workflow_present is None


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
    # 2 readiness failures (protection, actions-secrets). The caller is
    # reported but NOT in failures (#4719), and so is Dependabot-scope (#1131).
    assert sorted(r.failures) == ["actions_secrets_incomplete", "branch_protection_not_strict"]
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
