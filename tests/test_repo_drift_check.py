"""Tests for tools/repo_drift_check.py (Issue #1077)."""
import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

# Load the tools/ script as a module without polluting sys.path with the whole tools dir.
TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_spec = importlib.util.spec_from_file_location(
    "repo_drift_check", TOOLS_DIR / "repo_drift_check.py"
)
repo_drift_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repo_drift_check)


# ---- extract_handoff_body ----

def test_extract_handoff_body_returns_text_unchanged_when_no_markers():
    text = "Just a plain handoff body. /c/Users/mcwiz/Projects/foo here."
    assert repo_drift_check.extract_handoff_body(text) == text


def test_extract_handoff_body_returns_only_last_handoff_block():
    text = (
        "preamble\n"
        "<!-- handoff-start -->\n"
        "first handoff body /c/Users/mcwiz/Projects/older\n"
        "<!-- handoff-end -->\n"
        "interlude\n"
        "<!-- handoff-start -->\n"
        "newest body /c/Users/mcwiz/Projects/newer\n"
        "<!-- handoff-end -->\n"
        "trailing\n"
    )
    body = repo_drift_check.extract_handoff_body(text)
    assert "newer" in body
    assert "older" not in body
    assert "preamble" not in body
    assert "trailing" not in body


# ---- parse_repo_names (pure regex, no filesystem) ----

def test_parse_repo_names_dedupes_and_preserves_order():
    text = (
        "Touched /c/Users/mcwiz/Projects/alpha and "
        "C:\\Users\\mcwiz\\Projects\\beta and "
        "Projects/gamma. Then back to /c/Users/mcwiz/Projects/alpha."
    )
    names = repo_drift_check.parse_repo_names(text)
    assert names == ["alpha", "beta", "gamma"]


def test_parse_repo_names_filters_denylist():
    text = (
        "/c/Users/mcwiz/Projects/legit "
        "/c/Users/mcwiz/Projects/node_modules "
        "/c/Users/mcwiz/Projects/.git"
    )
    names = repo_drift_check.parse_repo_names(text)
    assert names == ["legit"]


def test_parse_repo_names_skips_filenames_with_extensions():
    # "Projects/CLAUDE.md" should not produce "CLAUDE.md" because "." is excluded
    # from the capture char class. The regex stops at the dot, so the capture is
    # "CLAUDE" -- which extract_repo_names then filters via the directory check.
    text = "/c/Users/mcwiz/Projects/CLAUDE.md was edited"
    names = repo_drift_check.parse_repo_names(text)
    assert "CLAUDE.md" not in names
    assert names == ["CLAUDE"]  # the dot truncates the match


def test_parse_repo_names_empty_when_no_paths():
    assert repo_drift_check.parse_repo_names("nothing relevant here") == []


# ---- extract_repo_names (regex + filesystem validation) ----

def test_extract_repo_names_drops_names_without_real_directories(tmp_path, monkeypatch):
    fake_root = tmp_path / "Projects"
    (fake_root / "real").mkdir(parents=True)
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)
    text = "/c/Users/mcwiz/Projects/real and /c/Users/mcwiz/Projects/CLAUDE.md"
    names = repo_drift_check.extract_repo_names(text)
    assert names == ["real"]


def test_extract_repo_names_strips_worktree_suffix_when_parent_exists(tmp_path, monkeypatch):
    fake_root = tmp_path / "Projects"
    (fake_root / "alpha").mkdir(parents=True)
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)

    text = "Worked in /c/Users/mcwiz/Projects/alpha-1099 today."
    names = repo_drift_check.extract_repo_names(text)
    assert names == ["alpha"]


def test_extract_repo_names_skips_suffix_name_when_neither_parent_nor_full_exists(tmp_path, monkeypatch):
    fake_root = tmp_path / "Projects"
    fake_root.mkdir(parents=True)
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)

    text = "/c/Users/mcwiz/Projects/standalone-1077"
    names = repo_drift_check.extract_repo_names(text)
    assert names == []  # neither "standalone-1077" nor "standalone" exists -> dropped


def test_extract_repo_names_keeps_suffix_name_when_full_path_exists(tmp_path, monkeypatch):
    # If the full "name-NNNN" path actually exists (e.g., a real repo that
    # happens to end in digits), keep it instead of incorrectly stripping.
    fake_root = tmp_path / "Projects"
    (fake_root / "standalone-1077").mkdir(parents=True)
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)

    text = "/c/Users/mcwiz/Projects/standalone-1077"
    names = repo_drift_check.extract_repo_names(text)
    assert names == ["standalone-1077"]


# ---- _run_git ----

def test_run_git_returns_timeout_code_on_subprocess_timeout(tmp_path):
    with patch.object(
        repo_drift_check.subprocess,
        "run",
        side_effect=subprocess.TimeoutExpired(cmd="git", timeout=30),
    ):
        rc, stdout, stderr = repo_drift_check._run_git(["status"], tmp_path)
    assert rc == 124
    assert "timeout" in stderr


def test_run_git_returns_127_when_git_missing(tmp_path):
    with patch.object(
        repo_drift_check.subprocess, "run", side_effect=FileNotFoundError
    ):
        rc, _, stderr = repo_drift_check._run_git(["status"], tmp_path)
    assert rc == 127
    assert "not found" in stderr


# ---- check_repo_drift -- non-existent and non-git paths ----

def test_check_repo_drift_marks_missing_for_nonexistent_path(tmp_path, monkeypatch):
    fake_root = tmp_path / "Projects"
    fake_root.mkdir()
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)
    result = repo_drift_check.check_repo_drift("nope")
    assert result["status"] == "missing"
    assert result["name"] == "nope"


def test_check_repo_drift_marks_not_git_when_dir_lacks_dot_git(tmp_path, monkeypatch):
    fake_root = tmp_path / "Projects"
    (fake_root / "plain-dir").mkdir(parents=True)
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)
    result = repo_drift_check.check_repo_drift("plain-dir")
    assert result["status"] == "not_git"


# ---- check_repo_drift -- happy paths via _run_git mocking ----

def _make_git_responder(responses: dict[tuple, tuple]) -> callable:
    """
    Build a fake _run_git that returns canned responses keyed by the args tuple.
    Any unmatched call returns (1, '', 'unmatched'); helps surface test gaps.
    """
    def _fake(args, cwd):
        return responses.get(tuple(args), (1, "", f"unmatched: {args}"))
    return _fake


def test_check_repo_drift_reports_in_sync_when_both_counts_zero(tmp_path, monkeypatch):
    fake_root = tmp_path / "Projects"
    repo = fake_root / "alpha"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)

    responses = {
        ("symbolic-ref", "--short", "refs/remotes/origin/HEAD"): (0, "origin/main", ""),
        ("fetch", "origin", "--quiet"): (0, "", ""),
        ("rev-list", "--count", "main..origin/main"): (0, "0", ""),
        ("rev-list", "--count", "origin/main..main"): (0, "0", ""),
    }
    monkeypatch.setattr(repo_drift_check, "_run_git", _make_git_responder(responses))

    result = repo_drift_check.check_repo_drift("alpha")
    assert result["status"] == "in_sync"
    assert result["behind"] == 0
    assert result["ahead"] == 0
    assert result["branch"] == "main"


def test_check_repo_drift_reports_drift_with_counts(tmp_path, monkeypatch):
    fake_root = tmp_path / "Projects"
    repo = fake_root / "beta"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)

    responses = {
        ("symbolic-ref", "--short", "refs/remotes/origin/HEAD"): (0, "origin/main", ""),
        ("fetch", "origin", "--quiet"): (0, "", ""),
        ("rev-list", "--count", "main..origin/main"): (0, "3", ""),
        ("rev-list", "--count", "origin/main..main"): (0, "1", ""),
    }
    monkeypatch.setattr(repo_drift_check, "_run_git", _make_git_responder(responses))

    result = repo_drift_check.check_repo_drift("beta")
    assert result["status"] == "drift"
    assert result["behind"] == 3
    assert result["ahead"] == 1


def test_check_repo_drift_reports_fetch_error_when_fetch_fails(tmp_path, monkeypatch):
    fake_root = tmp_path / "Projects"
    repo = fake_root / "gamma"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)

    responses = {
        ("symbolic-ref", "--short", "refs/remotes/origin/HEAD"): (0, "origin/main", ""),
        ("fetch", "origin", "--quiet"): (128, "", "could not resolve host"),
    }
    monkeypatch.setattr(repo_drift_check, "_run_git", _make_git_responder(responses))

    result = repo_drift_check.check_repo_drift("gamma")
    assert result["status"] == "fetch_error"
    assert "could not resolve" in result["error"]


def test_check_repo_drift_falls_back_to_main_when_origin_head_unset(tmp_path, monkeypatch):
    fake_root = tmp_path / "Projects"
    repo = fake_root / "delta"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)

    responses = {
        # symbolic-ref fails (no origin/HEAD) -- script should fall through to checking 'main' / 'master'
        ("symbolic-ref", "--short", "refs/remotes/origin/HEAD"): (1, "", "no symbolic ref"),
        ("rev-parse", "--verify", "refs/heads/main"): (0, "", ""),
        ("fetch", "origin", "--quiet"): (0, "", ""),
        ("rev-list", "--count", "main..origin/main"): (0, "0", ""),
        ("rev-list", "--count", "origin/main..main"): (0, "0", ""),
    }
    monkeypatch.setattr(repo_drift_check, "_run_git", _make_git_responder(responses))

    result = repo_drift_check.check_repo_drift("delta")
    assert result["branch"] == "main"
    assert result["status"] == "in_sync"


# ---- format_text_report ----

def test_format_text_report_quiet_returns_empty_when_no_drift_or_errors():
    report = {"repos": [{"name": "x", "status": "in_sync", "behind": 0, "ahead": 0, "branch": "main"}]}
    assert repo_drift_check.format_text_report(report, quiet=True) == ""


def test_format_text_report_lists_drift_with_pull_hint():
    report = {
        "repos": [
            {"name": "alpha", "status": "drift", "behind": 2, "ahead": 0, "branch": "main"},
        ]
    }
    out = repo_drift_check.format_text_report(report, quiet=False)
    assert "alpha" in out
    assert "2 behind origin/main" in out
    assert "pull before any local work" in out


def test_format_text_report_handles_no_repos_gracefully():
    report = {"repos": []}
    assert "No repo references" in repo_drift_check.format_text_report(report, quiet=False)


# ---- main (CLI integration) ----

def test_main_emits_json_when_flag_passed(tmp_path, monkeypatch, capsys):
    # Set up a fake Projects root with one real "real-repo" dir lacking .git --
    # this drives extract_repo_names through the dir-validation path AND lets
    # check_repo_drift report "not_git" so we exercise the error-exit-code branch.
    fake_root = tmp_path / "Projects"
    (fake_root / "real-repo").mkdir(parents=True)
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)

    handoff = tmp_path / "h.md"
    handoff.write_text("Worked in /c/Users/mcwiz/Projects/real-repo today.", encoding="utf-8")

    rc = repo_drift_check.main(["--handoff", str(handoff), "--json"])
    captured = capsys.readouterr().out
    parsed = json.loads(captured)
    assert parsed["names_extracted"] == ["real-repo"]
    assert parsed["repos"][0]["status"] == "not_git"
    # not_git is treated as an error status in main()'s exit-code logic
    assert rc == 2


def test_main_filters_filename_false_positives_via_dir_check(tmp_path, monkeypatch, capsys):
    # Regression test for the actual bug surfaced in smoke testing:
    # "/c/Users/mcwiz/Projects/CLAUDE.md" used to extract as "CLAUDE.md".
    # After the fix, the regex captures "CLAUDE" (period excluded from char class)
    # and the dir-check filter drops it because no "CLAUDE" directory exists.
    fake_root = tmp_path / "Projects"
    fake_root.mkdir()
    monkeypatch.setattr(repo_drift_check, "PROJECTS_ROOT", fake_root)

    handoff = tmp_path / "h.md"
    handoff.write_text(
        "Edited C:\\Users\\mcwiz\\Projects\\CLAUDE.md and "
        "/c/Users/mcwiz/Projects/dependabot-fleet.log today.",
        encoding="utf-8",
    )

    rc = repo_drift_check.main(["--handoff", str(handoff), "--json"])
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["names_extracted"] == []
    assert parsed["repos"] == []
    assert rc == 0  # no extracted repos = no errors


def test_main_returns_1_when_handoff_path_missing(tmp_path, capsys):
    rc = repo_drift_check.main(["--handoff", str(tmp_path / "nope.md")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "not found" in err
