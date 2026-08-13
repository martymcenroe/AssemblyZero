"""A missing required input is deterministic, not transient (#2298).

On the 2026-08-13 boostgauge #7 roll the impl stage found no implementation
spec — the upstream spec stage had halted — and retried it three times, 0.1s
apart, each attempt printing the full "No Implementation Spec found" banner and
a "Next attempt will be regenerated (discarding the previous attempt's
generated files)" warning about files that were never generated.

Zero chance of a different outcome on any attempt: the file is absent and
running the same stage again cannot conjure it.
"""
from __future__ import annotations

from unittest.mock import patch

from assemblyzero.workflows.orchestrator.stages import _classify_halt_transience
from assemblyzero.workflows.testing.nodes.load_lld import MISSING_REQUIRED_INPUT


def _sub_result(message: str) -> dict:
    """A halt with no recovery plan — the shape the guard actually returns."""
    return {"error_message": message}


class TestTheClassifierSeparatesDeterministicFromTransient:
    def test_a_missing_required_input_is_not_transient(self):
        result = _classify_halt_transience(
            _sub_result(
                f"{MISSING_REQUIRED_INPUT}: no implementation spec found for "
                f"issue #7. The spec stage should have produced it."
            )
        )
        assert result is False, (
            "a missing upstream artifact was classified retryable — three "
            "attempts at 0.1s each, all guaranteed to fail identically"
        )

    def test_the_marker_is_matched_case_insensitively(self):
        assert _classify_halt_transience(
            _sub_result("missing required input: nothing to build from")
        ) is False

    def test_a_stagnation_halt_is_still_non_transient(self):
        """The pre-existing deterministic case must keep its verdict."""
        assert _classify_halt_transience(
            _sub_result("Implementation stagnant after 3 rounds")
        ) is False

    def test_an_unrecognised_bare_failure_is_still_unset(self):
        """None means "no opinion" and preserves the retry loop's behaviour for
        genuine flakes such as a gh CLI hiccup. Narrowing that to False here
        would silently stop retrying things that SHOULD be retried."""
        assert _classify_halt_transience(
            _sub_result("gh: connection reset by peer")
        ) is None

    def test_no_error_message_at_all_is_unset(self):
        assert _classify_halt_transience({}) is None


class TestTheGuardEmitsTheMarkerAndNamesTheUpstreamStage:
    def test_the_message_carries_the_marker_and_names_the_spec_stage(self, tmp_path):
        import importlib

        mod = importlib.import_module(
            "assemblyzero.workflows.testing.nodes.load_lld"
        )
        worktree = tmp_path / "worktrees" / "7"
        worktree.mkdir(parents=True)
        durable = tmp_path / "repo"
        durable.mkdir()

        out = mod.load_lld({
            "issue_number": 7,
            "repo_root": str(worktree),
            "original_repo_root": str(durable),
            "spec_path": "",
            "lld_path": "",
        })

        message = out.get("error_message", "")
        assert MISSING_REQUIRED_INPUT in message
        assert "spec stage" in message.lower(), (
            "the halt must name the upstream stage that should have produced "
            "the input, so the operator is not sent back to this one"
        )

    def test_the_command_names_the_durable_repo_not_the_worktree(self, tmp_path):
        """#2298: the worktree is torn down by RESTORE seconds after this
        prints, so a command naming it is stale before it is read.

        (The filed claim that the banner printed AFTER teardown is not borne
        out by the events log — RESTORE began at 11:08:15, after the child
        exited at 11:08:15, and the banner was part of the child's output. The
        real defect is the ephemeral path, not the ordering.)
        """
        import importlib

        mod = importlib.import_module(
            "assemblyzero.workflows.testing.nodes.load_lld"
        )
        worktree = tmp_path / "worktrees" / "7"
        worktree.mkdir(parents=True)
        durable = tmp_path / "repo"
        durable.mkdir()

        out = mod.load_lld({
            "issue_number": 7,
            "repo_root": str(worktree),
            "original_repo_root": str(durable),
            "spec_path": "",
            "lld_path": "",
        })

        message = out.get("error_message", "")
        assert str(durable) in message
        assert "worktrees" not in message, (
            "the suggested command still points into the worktree RESTORE removes"
        )


# ---------------------------------------------------------------------------
# #2301 — a deliberately-ignored path is not a failure
# ---------------------------------------------------------------------------


class TestRidingTheSpecRespectsTheTargetRepoIgnores:
    """boostgauge gitignores docs/lineage, so every roll printed
    `[spec] git add failed (non-fatal): The following paths are ignored`.

    A repo doing exactly what it configured must not produce a failure line.
    """

    def _repo_with_ignore(self, tmp_path, ignore_line: str):
        import subprocess

        repo = tmp_path / "wt"
        repo.mkdir()
        for args in (["init", "-q", "-b", "main"],
                     ["config", "user.email", "t@t"],
                     ["config", "user.name", "t"]):
            subprocess.run(["git", "-C", str(repo), *args], check=True,
                           capture_output=True)
        (repo / ".gitignore").write_text(f"{ignore_line}\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"],
                       check=True, capture_output=True)
        return repo

    def _ride(self, tmp_path, worktree, spec_rel):
        from assemblyzero.workflows.orchestrator import stages as stages_mod

        target = tmp_path / "target"
        spec = target / spec_rel
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text("# spec\n", encoding="utf-8")

        # stages.py imports this INSIDE the function, so it is not an attribute
        # of stages — patch it where it is defined.
        import assemblyzero.workflows.requirements.git_operations as git_ops

        with patch.object(
            git_ops, "lld_worktree_path_for", lambda *a, **k: worktree
        ):
            return stages_mod._ride_spec_on_lld_pr(
                spec_path=str(spec), target_repo=str(target), issue_number=7,
            )

    def test_an_ignored_path_is_skipped_without_a_failure_line(self, tmp_path, capsys):
        worktree = self._repo_with_ignore(tmp_path, "docs/lineage")

        result = self._ride(tmp_path, worktree, "docs/lineage/active/7/spec.md")
        out = capsys.readouterr().out

        assert result is False
        assert "gitignored in this repo" in out
        assert "git add failed" not in out, (
            "a repo honouring its own .gitignore printed a failure line"
        )

    def test_a_tracked_path_is_still_ridden(self, tmp_path, capsys):
        """The ignore check must not become a blanket skip."""
        worktree = self._repo_with_ignore(tmp_path, "docs/lineage")

        result = self._ride(tmp_path, worktree, "docs/lld/drafts/spec-0007.md")
        out = capsys.readouterr().out

        assert "gitignored in this repo" not in out
        assert result is True
