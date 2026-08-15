"""The passed spec stage's handoff must survive the janitor (#2311).

Measured twice. On boostgauge #1, 2026-08-15, in a single launch:

    16:18:47  JANITOR pipeline file leavings
    16:18:48  docs/lld/drafts/spec-0001-...md: preserved-and-cleared
    16:18:50  RESUME abandoned for #1: spec artifact missing and not restorable
    16:18:53  ABORT could not establish a usable base

The janitor cleared the spec two seconds before the resume gate looked for it,
in the same process. A passed stage whose output no longer exists is not
resumable, so the relaunch was a guaranteed loss.

#2414 cannot reach this: `_resolve_stage_artifact` returns the recorded
`spec_path` at source 1, and it IS a real path -- to a file the same run had
already deleted, whose only surviving copy is on a `graveyard/leavings-*`
branch that `_restore_artifact` does not consult.

Both halves of the repair are pinned here, because either alone is incomplete:
finalize writes the handoff somewhere the janitor does not sweep, AND the
janitor's exemption is structural rather than inherited from a target repo's
.gitignore.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from assemblyzero.speedrun.leavings import (
    _EVIDENCE_PREFIXES,
    classify_dirt,
    untracked_files,
)
from assemblyzero.workflows.implementation_spec.nodes.finalize_spec import (
    LINEAGE_ACTIVE_DIR,
    SPEC_OUTPUT_DIR,
    durable_spec_path,
    finalize_spec,
)
from assemblyzero.workflows.testing.nodes.load_lld import find_spec_path

SPEC_BODY = "# Implementation Spec\n\n" + ("Section body line.\n" * 40)


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True,
    )


@pytest.fixture
def repo(tmp_path):
    """A target repo that does NOT gitignore docs/lineage/.

    Deliberate: boostgauge does ignore it, and that is what made the issue's
    "janitor-immune by the janitor's own selection rule" argument look true.
    The next target repo may not, so the fixture is the unforgiving case.
    """
    r = tmp_path / "target"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "t")
    (r / "README.md").write_text("base\n", encoding="utf-8")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "base")

    # A real remote, because the janitor clears a file only after the
    # graveyard ref is PUSHED -- preserve-then-clear is structural, and
    # without a remote nothing is ever removed. A fixture missing this would
    # pass the sweep tests for the wrong reason.
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", str(origin)], capture_output=True, text=True,
    )
    _git(r, "remote", "add", "origin", str(origin))
    _git(r, "push", "-q", "-u", "origin", "HEAD")
    return r


def _state(repo, issue=1):
    return {
        "issue_number": issue,
        "spec_draft": SPEC_BODY,
        "review_verdict": "APPROVED",
        "review_feedback": "",
        "review_iteration": 1,
        # The node reads `repo_root`; `target_repo` is the orchestrator's key.
        "repo_root": str(repo),
        "audit_dir": "",
    }


# ---------------------------------------------------------------------------
# finalize writes where the loader looks, and records what it wrote
# ---------------------------------------------------------------------------


class TestFinalizeWritesTheDurableHandoff:
    def test_the_handoff_copy_exists(self, repo):
        finalize_spec(_state(repo))
        assert durable_spec_path(repo, 1).is_file()

    def test_the_drafts_copy_still_exists(self, repo):
        """The drafts copy becomes a convenience, not a removal."""
        finalize_spec(_state(repo))
        assert list((repo / SPEC_OUTPUT_DIR).glob("spec-0001*.md"))

    def test_both_copies_have_the_same_content(self, repo):
        finalize_spec(_state(repo))
        drafts = list((repo / SPEC_OUTPUT_DIR).glob("spec-0001*.md"))[0]
        assert (
            durable_spec_path(repo, 1).read_text(encoding="utf-8")
            == drafts.read_text(encoding="utf-8")
        )

    def test_spec_path_records_the_durable_location(self, repo):
        """`resume_plan` reads this field FIRST. Recording the swept path is
        what made the recorded value a real path to a deleted file."""
        result = finalize_spec(_state(repo))
        assert result["spec_path"] == str(durable_spec_path(repo, 1))
        assert "lineage" in result["spec_path"]

    def test_the_handoff_is_written_FLAT_not_in_a_run_subdir(self, repo):
        """`find_spec_path` globs this directory flat, and
        `move_lineage_to_done` relocates the run subdir out from under it."""
        finalize_spec(_state(repo))
        handoff = durable_spec_path(repo, 1)
        assert handoff.parent == repo / LINEAGE_ACTIVE_DIR / "1-implspec"

    def test_the_loader_finds_it(self, repo):
        """End of the contract: what finalize wrote is what impl loads."""
        finalize_spec(_state(repo))
        found = find_spec_path(1, repo)
        assert found is not None
        assert found.resolve() == durable_spec_path(repo, 1).resolve()

    def test_a_second_run_overwrites_rather_than_accumulating(self, repo):
        finalize_spec(_state(repo))
        second = _state(repo)
        second["spec_draft"] = "# Implementation Spec\n\nsecond draft\n" * 10
        finalize_spec(second)
        matches = list(
            (repo / LINEAGE_ACTIVE_DIR / "1-implspec").glob("*-final-spec.md")
        )
        assert len(matches) == 1
        assert "second draft" in matches[0].read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The janitor exemption is structural, not inherited from .gitignore
# ---------------------------------------------------------------------------


class TestTheJanitorLeavesItAlone:
    def test_lineage_is_evidence_structurally(self):
        assert "docs/lineage/" in _EVIDENCE_PREFIXES

    def test_the_handoff_is_not_untracked_dirt_even_without_gitignore(self, repo):
        """The repo fixture does NOT ignore docs/lineage/, so this is the case
        boostgauge's .gitignore was hiding."""
        finalize_spec(_state(repo))
        assert not (repo / ".gitignore").exists()
        untracked = untracked_files(repo)
        assert not any("lineage" in p for p in untracked), untracked

    def test_the_drafts_copy_IS_still_seen_as_dirt(self, repo):
        """The exemption must be narrow. The drafts copy is a convenience and
        is still swept -- otherwise this repair is a licence to leave anything
        anywhere."""
        finalize_spec(_state(repo))
        untracked = untracked_files(repo)
        assert any("drafts" in p for p in untracked), untracked

    def test_the_janitor_does_not_classify_the_handoff_as_machinery_dirt(self, repo):
        finalize_spec(_state(repo))
        machinery, _operator = classify_dirt(repo)
        assert not any("lineage" in p for p in machinery), machinery

    def test_data_speedrun_is_still_exempt(self):
        """#2164's exemption must survive this change."""
        assert "data/speedrun/" in _EVIDENCE_PREFIXES


# ---------------------------------------------------------------------------
# The reproduction the acceptance asks for
# ---------------------------------------------------------------------------


class TestTheMeasuredRunReproduces:
    """'spec passes, impl fails, RESTORE sweeps, relaunch resumes at impl and
    loads the spec' -- the issue's second acceptance item, in order."""

    def test_the_spec_survives_a_janitor_sweep_and_is_still_loadable(self, repo):
        # 1. spec passes
        result = finalize_spec(_state(repo))
        recorded = Path(result["spec_path"])
        assert recorded.is_file()

        # 2. impl fails and RESTORE sweeps every untracked file the janitor
        #    owns -- reproduced by deleting exactly what the janitor clears.
        from assemblyzero.speedrun.leavings import preserve_and_clear

        machinery, _operator = classify_dirt(repo)
        preserve_and_clear(repo, machinery, log=lambda _m: None)

        # 3. the drafts copy is gone, exactly as on 2026-08-15 at 16:18:48
        assert not list((repo / SPEC_OUTPUT_DIR).glob("spec-0001*.md"))

        # 4. the relaunch's resume finds the recorded artifact anyway
        assert recorded.is_file(), (
            "the recorded spec_path was swept -- this is the 16:18:50 abandon"
        )

        # 5. and impl's own loader finds it
        found = find_spec_path(1, repo)
        assert found is not None
        assert found.read_text(encoding="utf-8") == recorded.read_text(
            encoding="utf-8"
        )

    def test_the_old_arrangement_would_have_failed_this(self, repo):
        """Pins WHY: a spec written only to drafts/ does not survive the sweep,
        so the test above is not passing for an unrelated reason."""
        from assemblyzero.speedrun.leavings import preserve_and_clear

        drafts = repo / SPEC_OUTPUT_DIR
        drafts.mkdir(parents=True, exist_ok=True)
        only_copy = drafts / "spec-0001-implementation-readiness.md"
        only_copy.write_text(SPEC_BODY, encoding="utf-8")

        machinery, _operator = classify_dirt(repo)
        preserve_and_clear(repo, machinery, log=lambda _m: None)

        assert not only_copy.exists()
