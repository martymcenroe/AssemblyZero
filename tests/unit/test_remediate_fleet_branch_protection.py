"""Tests for tools/remediate_fleet_branch_protection.py (#1126)."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
_spec = importlib.util.spec_from_file_location(
    "remediate_fleet_branch_protection",
    TOOLS_DIR / "remediate_fleet_branch_protection.py",
)
remediate = importlib.util.module_from_spec(_spec)
sys.modules["remediate_fleet_branch_protection"] = remediate
_spec.loader.exec_module(remediate)


# ---- Target list is hard-coded (scope guard) ----

def test_target_repos_is_exactly_three_named_repos():
    """Regression guard: the target list must not widen accidentally."""
    assert remediate.TARGET_REPOS == ("boostgauge", "gh-galaxy-quest", "comp-environ")


def test_target_config_matches_fleet_canonical_strict():
    cfg = remediate.TARGET_CONFIG
    assert cfg["required_pull_request_reviews"]["required_approving_review_count"] == 1
    assert cfg["enforce_admins"] is True
    assert cfg["allow_force_pushes"] is False
    assert cfg["allow_deletions"] is False
    # Status check requires the canonical pr-sentinel context
    contexts = [c["context"] for c in cfg["required_status_checks"]["checks"]]
    assert "pr-sentinel / issue-reference" in contexts


# ---- summarize_protection ----

def test_summarize_none_reports_unprotected():
    s = remediate.summarize_protection(None)
    assert s["protected"] is False
    assert s["required_reviews"] is None
    assert s["enforce_admins"] is False


def test_summarize_strict_protection_blob():
    blob = {
        "required_pull_request_reviews": {"required_approving_review_count": 1},
        "required_status_checks": {"contexts": ["pr-sentinel / issue-reference"]},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
    }
    s = remediate.summarize_protection(blob)
    assert s["protected"] is True
    assert s["required_reviews"] == 1
    assert s["has_status_checks"] is True
    assert s["enforce_admins"] is True


def test_summarize_weak_blob_matches_boostgauge():
    """Audit reported `required_reviews=None` for boostgauge -- the API
    returns the section but with no count field."""
    blob = {
        "required_pull_request_reviews": {},  # no count -> reports None
        "required_status_checks": None,
        "enforce_admins": {"enabled": False},
    }
    s = remediate.summarize_protection(blob)
    assert s["protected"] is True
    assert s["required_reviews"] is None
    assert s["has_status_checks"] is False
    assert s["enforce_admins"] is False


# ---- diff_lines ----

def test_diff_strict_repo_returns_empty():
    summary = {
        "protected": True,
        "required_reviews": 1,
        "has_status_checks": True,
        "enforce_admins": True,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    assert remediate.diff_lines(summary) == []


def test_diff_weak_repo_reports_all_failed_bars():
    """boostgauge / gh-galaxy-quest -- weak protected repo."""
    summary = {
        "protected": True,
        "required_reviews": None,
        "has_status_checks": False,
        "enforce_admins": False,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    deltas = remediate.diff_lines(summary)
    assert any("required_reviews" in d for d in deltas)
    assert any("required_status_checks" in d for d in deltas)
    assert any("enforce_admins" in d for d in deltas)


def test_diff_unprotected_repo_includes_protection_creation_line():
    """comp-environ -- has no protection at all."""
    summary = remediate.summarize_protection(None)
    deltas = remediate.diff_lines(summary)
    # The first line should communicate "creating protection from scratch"
    assert deltas[0].startswith("protected: false -> true")


# ---- main() guard: --apply requires --confirm-yes ----

def test_main_rejects_apply_without_confirm_yes(capsys):
    rc = remediate.main(["--apply"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "--confirm-yes" in err


# ---- main() dry-run does NOT call apply_protection ----

def test_main_dry_run_never_calls_apply(capsys):
    """Even if every target repo needs changes, dry-run must not PUT."""
    with patch.object(remediate, "classic_pat_session") as mock_ctx, \
         patch.object(remediate, "get_default_branch", return_value="main"), \
         patch.object(remediate, "get_current_protection", return_value=None) as mock_get, \
         patch.object(remediate, "apply_protection") as mock_apply:
        mock_ctx.return_value.__enter__.return_value = "fake-pat"
        rc = remediate.main([])  # no flags = dry-run

    # All three targets were inspected (None protection -> needs changes)
    assert mock_get.call_count == 3
    # But no PUTs
    mock_apply.assert_not_called()
    assert rc == 0


# ---- main() apply path does call apply_protection ----

def test_main_apply_path_calls_apply_for_each_target():
    with patch.object(remediate, "classic_pat_session") as mock_ctx, \
         patch.object(remediate, "get_default_branch", return_value="main"), \
         patch.object(remediate, "get_current_protection", return_value=None), \
         patch.object(remediate, "apply_protection", return_value=True) as mock_apply:
        mock_ctx.return_value.__enter__.return_value = "fake-pat"
        rc = remediate.main(["--apply", "--confirm-yes"])

    assert mock_apply.call_count == 3
    repos_called = [c.args[0] for c in mock_apply.call_args_list]
    assert set(repos_called) == {"boostgauge", "gh-galaxy-quest", "comp-environ"}
    assert rc == 0


def test_main_returns_2_when_any_apply_fails():
    def fake_apply(repo, branch, pat):
        return repo != "boostgauge"  # boostgauge fails

    with patch.object(remediate, "classic_pat_session") as mock_ctx, \
         patch.object(remediate, "get_default_branch", return_value="main"), \
         patch.object(remediate, "get_current_protection", return_value=None), \
         patch.object(remediate, "apply_protection", side_effect=fake_apply):
        mock_ctx.return_value.__enter__.return_value = "fake-pat"
        rc = remediate.main(["--apply", "--confirm-yes"])

    assert rc == 2


def test_main_skips_target_with_unresolvable_default_branch():
    """If a repo's default branch can't be fetched (archived? deleted?),
    the script must report it as a failure but continue with the others."""
    def fake_default(repo, pat):
        return None if repo == "comp-environ" else "main"

    with patch.object(remediate, "classic_pat_session") as mock_ctx, \
         patch.object(remediate, "get_default_branch", side_effect=fake_default), \
         patch.object(remediate, "get_current_protection", return_value=None), \
         patch.object(remediate, "apply_protection", return_value=True):
        mock_ctx.return_value.__enter__.return_value = "fake-pat"
        rc = remediate.main(["--apply", "--confirm-yes"])

    assert rc == 2  # one failure
