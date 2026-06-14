"""Tests for tools/audit_fleet_branch_protection.py classification logic (#1124)."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "audit_fleet_branch_protection",
    TOOLS_DIR / "audit_fleet_branch_protection.py",
)
audit = importlib.util.module_from_spec(_spec)
# Register in sys.modules BEFORE exec_module so @dataclass can resolve the
# module's namespace via cls.__module__ -> sys.modules lookup.
sys.modules["audit_fleet_branch_protection"] = audit
_spec.loader.exec_module(audit)


def _mk_verdict(**kwargs):
    return audit.RepoVerdict(name=kwargs.pop("name", "x"), **kwargs)


# ---- classify() -- the policy bar ----

def test_strict_when_all_bars_met():
    v = _mk_verdict(
        protected_flag=True,
        required_reviews=1,
        has_status_checks=True,
        enforce_admins=True,
        allow_force_pushes=False,
    )
    audit.classify(v)
    assert v.classification == "STRICT"
    assert v.failures == []


def test_weak_when_required_reviews_zero():
    """The exact failure mode that surfaced #1124 -- boostgauge had count=0."""
    v = _mk_verdict(
        protected_flag=True,
        required_reviews=0,
        has_status_checks=True,
        enforce_admins=True,
        allow_force_pushes=False,
    )
    audit.classify(v)
    assert v.classification == "WEAK"
    assert any("required_reviews=0" in f for f in v.failures)


def test_weak_when_no_status_checks():
    v = _mk_verdict(
        protected_flag=True,
        required_reviews=1,
        has_status_checks=False,
        enforce_admins=True,
        allow_force_pushes=False,
    )
    audit.classify(v)
    assert v.classification == "WEAK"
    assert "no_required_status_checks" in v.failures


def test_weak_when_enforce_admins_false():
    v = _mk_verdict(
        protected_flag=True,
        required_reviews=1,
        has_status_checks=True,
        enforce_admins=False,
        allow_force_pushes=False,
    )
    audit.classify(v)
    assert v.classification == "WEAK"
    assert "enforce_admins=false" in v.failures


def test_weak_when_force_pushes_allowed():
    v = _mk_verdict(
        protected_flag=True,
        required_reviews=1,
        has_status_checks=True,
        enforce_admins=True,
        allow_force_pushes=True,
    )
    audit.classify(v)
    assert v.classification == "WEAK"
    assert "allow_force_pushes=true" in v.failures


def test_unprotected_when_protected_flag_false():
    v = _mk_verdict(protected_flag=False)
    audit.classify(v)
    assert v.classification == "UNPROTECTED"


def test_unknown_when_error_present():
    v = _mk_verdict(error="network_error")
    audit.classify(v)
    assert v.classification == "UNKNOWN"


def test_weak_collects_multiple_failures():
    v = _mk_verdict(
        protected_flag=True,
        required_reviews=0,
        has_status_checks=False,
        enforce_admins=False,
        allow_force_pushes=True,
    )
    audit.classify(v)
    assert v.classification == "WEAK"
    assert len(v.failures) == 4


# ---- TSV row format ----

def test_tsv_row_includes_all_columns_in_order():
    v = _mk_verdict(
        default_branch="main",
        protected_flag=True,
        required_reviews=1,
        has_status_checks=True,
        enforce_admins=True,
        allow_force_pushes=False,
        ruleset_count=2,
        classification="STRICT",
    )
    cols = v.tsv_row().split("\t")
    assert cols[0] == "x"
    assert cols[1] == "STRICT"
    assert cols[2] == "main"
    assert cols[3] == "True"
    assert cols[4] == "1"


def test_tsv_row_omits_none_as_empty_strings():
    v = _mk_verdict(error="no_default_branch")
    audit.classify(v)
    cols = v.tsv_row().split("\t")
    assert cols[1] == "UNKNOWN"
    assert cols[2] == ""  # default_branch
    assert cols[3] == ""  # protected_flag
    assert cols[10] == "no_default_branch"  # error column


# ---- audit_one_repo with mocked _get ----

def _strict_protection_body():
    return {
        "required_pull_request_reviews": {"required_approving_review_count": 1},
        "required_status_checks": {"contexts": ["ci"], "checks": []},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
    }


def _weak_protection_body():
    """Matches boostgauge's actual state -- count=0."""
    return {
        "required_pull_request_reviews": {"required_approving_review_count": 0},
        "required_status_checks": {"contexts": [], "checks": []},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
    }


def test_audit_one_repo_strict_repo():
    repo = {"name": "good", "defaultBranchRef": {"name": "main"}}

    def fake_get(url, pat):
        if "/protection" in url:
            return 200, _strict_protection_body()
        if "/rulesets" in url:
            return 200, []
        return 200, {}

    with patch.object(audit, "_get", side_effect=fake_get):
        v = audit.audit_one_repo(repo, "fake-pat")

    assert v.classification == "STRICT"
    assert v.required_reviews == 1
    assert v.enforce_admins is True


def test_audit_one_repo_weak_repo_matches_boostgauge_pattern():
    repo = {"name": "boostgauge", "defaultBranchRef": {"name": "main"}}

    def fake_get(url, pat):
        if "/protection" in url:
            return 200, _weak_protection_body()
        if "/rulesets" in url:
            return 200, []
        return 200, {}

    with patch.object(audit, "_get", side_effect=fake_get):
        v = audit.audit_one_repo(repo, "fake-pat")

    assert v.classification == "WEAK"
    assert v.required_reviews == 0
    assert any("required_reviews=0" in f for f in v.failures)


def test_audit_one_repo_404_falls_back_to_protected_flag():
    """When /protection returns 404, we read /branches/{default} for the
    `protected` boolean to distinguish UNPROTECTED from PERMISSION_DENIED."""
    repo = {"name": "no-protection", "defaultBranchRef": {"name": "main"}}

    def fake_get(url, pat):
        if "/protection" in url:
            return 404, None
        if url.endswith("/branches/main"):
            return 200, {"protected": False}
        if "/rulesets" in url:
            return 200, []
        return 200, {}

    with patch.object(audit, "_get", side_effect=fake_get):
        v = audit.audit_one_repo(repo, "fake-pat")

    assert v.classification == "UNPROTECTED"
    assert v.protected_flag is False


def test_audit_one_repo_no_default_branch():
    repo = {"name": "empty-repo", "defaultBranchRef": None}

    with patch.object(audit, "_get") as mock_get:
        v = audit.audit_one_repo(repo, "fake-pat")

    assert v.classification == "UNKNOWN"
    assert v.error == "no_default_branch"
    mock_get.assert_not_called()


def test_audit_one_repo_network_error_classified_unknown():
    repo = {"name": "x", "defaultBranchRef": {"name": "main"}}

    def fake_get(url, pat):
        return 0, {"_error": "ConnectionError"}

    with patch.object(audit, "_get", side_effect=fake_get):
        v = audit.audit_one_repo(repo, "fake-pat")

    assert v.classification == "UNKNOWN"
    assert v.error == "network_error"
