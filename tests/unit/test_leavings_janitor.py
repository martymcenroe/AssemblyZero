"""Acceptance tests for the file janitor and its consumers (#2144, #2145, #2146).

Standard 0027: preserve, then restore. Every test builds a throwaway repo
with a local bare origin under tmp_path -- preservation is only preservation
when the ref is pushed, so the tests give the janitor somewhere to push.

The run-16 scenario (untracked LLD droppings blocking a launch eight days
later) is replayed here as the acceptance case for all three issues.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _healthy_box(*_args, **_kwargs):
    from assemblyzero.speedrun.box_health import BoxHealth

    return BoxHealth(True, [], "")

import speedrun_new_attempt as attempt  # noqa: E402
import speedrun_roll as sr  # noqa: E402

from assemblyzero.speedrun.leavings import (  # noqa: E402
    classify_dirt,
    preserve_and_clear,
    untracked_files,
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo with a bare origin, gitignored data/, and origin/HEAD set."""
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(origin)],
        capture_output=True, text=True, check=True,
    )
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")
    (root / ".gitignore").write_text("data/\n", encoding="utf-8")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "push", "-qu", "origin", "main")
    _git(root, "remote", "set-head", "origin", "--auto")
    return root


def _drop_leaving(repo: Path, rel: str = "docs/lld/active/LLD-002.md") -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("drafted by the pipeline\n", encoding="utf-8")
    return path


def _leavings_branches(repo: Path) -> list[str]:
    out = _git(repo, "branch", "--list", "graveyard/leavings-*",
               "--format=%(refname:short)").stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


# --- the janitor itself (#2144) -------------------------------------------


class TestPreserveAndClear:
    def test_a_leaving_is_preserved_on_a_pushed_ref_then_cleared(self, repo):
        _drop_leaving(repo)

        result = preserve_and_clear(repo, ["docs/lld/active/LLD-002.md"])

        assert result.problems == []
        assert not (repo / "docs" / "lld" / "active" / "LLD-002.md").exists()
        branches = _leavings_branches(repo)
        assert len(branches) == 1
        shown = _git(
            repo, "show", f"{branches[0]}:docs/lld/active/LLD-002.md"
        ).stdout
        assert "drafted by the pipeline" in shown
        on_origin = _git(repo, "ls-remote", "--heads", "origin",
                         branches[0]).stdout
        assert branches[0] in on_origin, "unpushed is unpreserved"

    def test_the_emptied_directory_is_pruned_but_not_beyond(self, repo):
        _drop_leaving(repo, "docs/lld/drafts/spec-0002.md")
        (repo / "docs" / "keep.md").write_text("tracked-ish\n", encoding="utf-8")

        preserve_and_clear(repo, ["docs/lld/drafts/spec-0002.md"])

        assert not (repo / "docs" / "lld" / "drafts").exists()
        assert (repo / "docs").exists(), "docs/ still has content and must stay"

    def test_preservation_failure_leaves_the_file_in_place(self, repo):
        """No origin to push to == no durable ref == nothing may be removed."""
        _git(repo, "remote", "remove", "origin")
        leaving = _drop_leaving(repo)

        result = preserve_and_clear(repo, ["docs/lld/active/LLD-002.md"])

        assert leaving.exists(), "a file is never removed unpreserved"
        assert result.problems, "the failure must be reported, not swallowed"

    def test_the_main_checkout_is_undisturbed_by_preservation(self, repo):
        _drop_leaving(repo)
        head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()

        preserve_and_clear(repo, ["docs/lld/active/LLD-002.md"])

        assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
        assert _git(repo, "branch", "--show-current").stdout.strip() == "main"
        status = _git(repo, "status", "--porcelain").stdout.strip()
        assert status == "", f"preservation dirtied the checkout: {status}"


class TestClassification:
    def test_allowlisted_untracked_is_machinery_owned(self, repo):
        _drop_leaving(repo)
        machinery, operator = classify_dirt(repo)
        assert machinery == ["docs/lld/active/LLD-002.md"]
        assert operator == []

    def test_untracked_outside_the_allowlist_is_operator_owned(self, repo):
        (repo / "notes.md").write_text("mine\n", encoding="utf-8")
        machinery, operator = classify_dirt(repo)
        assert machinery == []
        assert any("notes.md" in entry for entry in operator)

    def test_a_tracked_modification_is_operator_owned(self, repo):
        (repo / "README.md").write_text("edited\n", encoding="utf-8")
        machinery, operator = classify_dirt(repo)
        assert machinery == []
        assert any("README.md" in entry for entry in operator)

    def test_gitignored_evidence_is_invisible(self, repo):
        (repo / "data" / "speedrun").mkdir(parents=True)
        (repo / "data" / "speedrun" / "run.log").write_text("evidence\n",
                                                            encoding="utf-8")
        machinery, operator = classify_dirt(repo)
        assert machinery == [] and operator == []


# --- the launcher's entry janitor and exit reconcile (#2144, #2145) --------


def _launch(repo: Path, roll_stub) -> int:
    with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
            patch.object(sr, "check_box_health", _healthy_box), \
            patch.object(sr, "open_must_resolve_issues", lambda r: ([], None)), \
            patch.object(sr, "roll_issue", roll_stub):
        return sr.main(["--repo", str(repo), "--issue", "7"])


class TestEntryJanitor:
    def test_a_predecessors_leavings_are_cleared_before_any_roll(self, repo):
        """The run-16 replay: droppings on disk at launch, gone (and
        preserved) before the roll starts, no human involved."""
        _drop_leaving(repo)
        seen = {}

        def _roll(repo_root, issue, log_dir, az_root, extra):
            seen["leavings_at_roll_time"] = [
                f for f in untracked_files(repo_root) if "lld" in f
            ]
            return 0

        code = _launch(repo, _roll)

        assert code == 0
        assert seen["leavings_at_roll_time"] == []
        assert _leavings_branches(repo), "cleared but never preserved"


class TestExitReconcile:
    def test_a_rolls_own_emission_is_preserved_and_cleared_on_exit(self, repo):
        def _roll(repo_root, issue, log_dir, az_root, extra):
            _drop_leaving(Path(repo_root))
            return 0

        code = _launch(repo, _roll)

        assert code == 0
        assert not (repo / "docs" / "lld" / "active" / "LLD-002.md").exists()
        assert _leavings_branches(repo)

    def test_reconcile_runs_on_the_failure_path_too(self, repo):
        def _roll(repo_root, issue, log_dir, az_root, extra):
            _drop_leaving(Path(repo_root))
            return 91

        code = _launch(repo, _roll)

        assert code == 91
        assert not (repo / "docs" / "lld" / "active" / "LLD-002.md").exists()
        assert _leavings_branches(repo)

    def test_a_file_the_machinery_cannot_prove_it_made_is_kept_and_named(
        self, repo, capsys
    ):
        def _roll(repo_root, issue, log_dir, az_root, extra):
            (Path(repo_root) / "mystery.md").write_text("whose?\n",
                                                        encoding="utf-8")
            return 0

        _launch(repo, _roll)

        assert (repo / "mystery.md").exists(), "never delete unproven authorship"
        out = capsys.readouterr().out
        assert "RESTORE INCOMPLETE" in out and "mystery.md" in out

    def test_evidence_under_data_is_exempt(self, repo, capsys):
        def _roll(repo_root, issue, log_dir, az_root, extra):
            # data/ is gitignored in the fixture, as in every campaign repo;
            # the run's own logs land there and must never fail the restore.
            return 0

        code = _launch(repo, _roll)

        assert code == 0
        assert "RESTORE INCOMPLETE" not in capsys.readouterr().out
        assert (repo / "data" / "speedrun" / "runs").exists()


# --- the branch-cutter's posture (#2146) -----------------------------------


class TestNewAttemptPosture:
    def test_a_tree_dirty_only_with_leavings_does_not_stop_a_launch(self, repo):
        _drop_leaving(repo)

        code = attempt.main(
            ["--repo", str(repo), "--name", "hardening-run-99", "--apply"]
        )

        assert code == 0
        assert not (repo / "docs" / "lld" / "active" / "LLD-002.md").exists()
        assert _leavings_branches(repo)
        assert "hardening-run-99" in _git(
            repo, "branch", "--list", "hardening-run-99",
            "--format=%(refname:short)",
        ).stdout

    def test_operator_owned_dirt_still_refuses_by_name(self, repo, capsys):
        (repo / "README.md").write_text("edited\n", encoding="utf-8")

        code = attempt.main(
            ["--repo", str(repo), "--name", "hardening-run-99", "--apply"]
        )

        assert code == 1
        out = capsys.readouterr().out
        assert "README.md" in out
        assert "not machinery-owned" in out

    def test_untracked_outside_the_allowlist_refuses_by_name(self, repo, capsys):
        (repo / "notes.md").write_text("mine\n", encoding="utf-8")

        code = attempt.main(
            ["--repo", str(repo), "--name", "hardening-run-99", "--apply"]
        )

        assert code == 1
        assert "notes.md" in capsys.readouterr().out

    def test_a_mixed_tree_preserves_the_machinerys_share_then_refuses(
        self, repo, capsys
    ):
        _drop_leaving(repo)
        (repo / "README.md").write_text("edited\n", encoding="utf-8")

        code = attempt.main(
            ["--repo", str(repo), "--name", "hardening-run-99", "--apply"]
        )

        assert code == 1, "the operator-owned entry still blocks"
        assert _leavings_branches(repo), (
            "the machinery's share is preserved-and-cleared even when the "
            "launch then refuses on the operator's"
        )
        assert not (repo / "docs" / "lld" / "active" / "LLD-002.md").exists()
        out = capsys.readouterr().out
        assert "README.md" in out and "not machinery-owned" in out

    def test_dry_run_mutates_nothing_and_classifies(self, repo, capsys):
        leaving = _drop_leaving(repo)

        code = attempt.main(
            ["--repo", str(repo), "--name", "hardening-run-99"]
        )

        assert code == 1, "dry run reports; only --apply may clean"
        assert leaving.exists()
        assert _leavings_branches(repo) == []
        assert "pipeline-authored leaving" in capsys.readouterr().out
