"""A resume after a hard-ceiling HALT engages, fresh-capped and preloaded (#2516).

The measured failure, boostgauge 2026-08-25: the spec stage halted at the
ceiling (round 9, still converging), its RESTORE grafted the attempt branch to
`graveyard/331-lld-<stamp>` and removed the worktree, and the advertised
resume died in 56.8 seconds -- the restored counter made the first resumed
round iteration 10 against a ceiling of 9, BLOCKED before any model call.

The #2514 ruling this implements: the cap regime is per launch. An explicit
relaunch grants one fresh regime (counter from zero, base cap 3, continuation
rules unchanged), the first regeneration is fed the halted run's final verdict
items, and the machinery's own archive (graveyard grafts, leavings refs,
lineage) is part of where a resume looks -- or, failing everything, part of
what the refusal names.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll  # noqa: E402

from assemblyzero.workflows.implementation_spec import lineage_seed as ls  # noqa: E402

ARC = "hardening-run-17"
ISSUE = 331
LLD_REL = "docs/lld/active/LLD-331.md"
GRAFT = f"graveyard/{ISSUE}-lld-20260825T152354Z"

#: The live case's final verdict shape: one objection, two explicit items.
FINAL_VERDICT = (
    "# Readiness Verdict\n\nREVISE\n\n"
    "## Outstanding\n\n"
    "- FEEDBACK ITEM ALPHA: the assertion for tick 60 must trace to R4.\n"
    "- FEEDBACK ITEM BETA: name the baseline flag in the test plan.\n"
)

CEILING_ROUNDS = 9  # the counter state of a real hard-ceiling halt (3 * 3)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args],
        capture_output=True, text=True,
    )


@pytest.fixture
def az_root(tmp_path) -> Path:
    root = tmp_path / "az"
    root.mkdir()
    return root


@pytest.fixture
def repo(tmp_path) -> Path:
    """The post-HALT+RESTORE shape: the lld branch exists ONLY as its
    graveyard graft, the working tree carries neither the LLD nor a worktree,
    and the spec lineage survives with the halted run's drafts and verdicts.
    """
    r = tmp_path / "boostgauge"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / "README.md").write_text("base\n", encoding="utf-8")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "base")

    # The attempt branch's one kept commit, grafted under the graveyard name.
    _git(r, "checkout", "-q", "-b", GRAFT)
    lld = r / LLD_REL
    lld.parent.mkdir(parents=True)
    lld.write_text("# LLD-331\n\nSTATUS: APPROVED\n", encoding="utf-8")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "docs: add LLD-331 via requirements workflow")
    _git(r, "checkout", "-q", "main")
    assert not lld.exists(), "fixture: RESTORE cleared the working tree"

    # The halted run's lineage: drafts and a ceiling's worth of verdicts.
    run_dir = r / "docs" / "lineage" / "active" / f"{ISSUE}-implspec" / "2026-08-25T04-46-02Z"
    run_dir.mkdir(parents=True)
    for i in range(1, CEILING_ROUNDS + 1):
        (run_dir / f"{i:03d}-spec-draft.md").write_text(
            f"# Implementation Spec\n\nDRAFT {i}\n", encoding="utf-8"
        )
        text = FINAL_VERDICT if i == CEILING_ROUNDS else (
            f"# Readiness Verdict\n\nREVISE\n\n- distinct objection {i}\n"
        )
        (run_dir / f"{i + 20:03d}-readiness-verdict.md").write_text(
            text, encoding="utf-8"
        )
    # The failed resume's own dir: a draft, no verdict (guard blocked before
    # reviewing). seed_from_lineage must skip it, not seed half a round.
    barren = run_dir.parent / "2026-08-25T15-22-56Z"
    barren.mkdir()
    (barren / "001-spec-draft.md").write_text("# unreviewed\n", encoding="utf-8")
    return r


@pytest.fixture
def log(tmp_path) -> "speedrun_roll.EventLog":
    return speedrun_roll.EventLog(tmp_path / "session-events.log")


def write_state(az_root: Path, repo: Path) -> Path:
    """331.json as the ceiling halt left it: lld passed, spec failed."""
    state_dir = az_root / ".assemblyzero" / "orchestrator" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "issue_number": ISSUE,
        "current_stage": "spec",
        "target_repo": str(repo),
        "base_branch": ARC,
        "lld_path": str(repo / LLD_REL),
        "spec_path": "",
        "resumed_from": "spec",
        "stage_results": {
            "triage": {"status": "skipped"},
            "lld": {"status": "passed"},
            "spec": {
                "status": "failed",
                "error_message": (
                    "Iteration cap: 3 review rounds ended BLOCKED, so the run "
                    "stopped rather than spend another round on the same "
                    "objection."
                ),
            },
        },
    }
    path = state_dir / f"{ISSUE}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestTheAcceptanceScenario:
    """State at the ceiling + graveyard-preserved branch: the resume runs,
    the counter starts fresh, the first regeneration sees the verdict items
    verbatim."""

    def test_resume_plan_engages_against_the_preserved_state(
        self, az_root, repo, log, monkeypatch
    ):
        monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
        monkeypatch.setattr(speedrun_roll, "_open_lld_pr_exists", lambda *_a: True)
        monkeypatch.setattr(speedrun_roll, "draft_is_stale", lambda *_a: False)
        write_state(az_root, repo)

        assert speedrun_roll.resume_plan(az_root, repo, ISSUE, log) == "spec"

    def test_the_plan_restored_the_lld_from_the_graveyard_graft(
        self, az_root, repo, log, monkeypatch
    ):
        monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: ARC)
        monkeypatch.setattr(speedrun_roll, "_open_lld_pr_exists", lambda *_a: True)
        monkeypatch.setattr(speedrun_roll, "draft_is_stale", lambda *_a: False)
        write_state(az_root, repo)

        speedrun_roll.resume_plan(az_root, repo, ISSUE, log)

        restored = repo / LLD_REL
        assert restored.is_file(), "the graft was the only holder of the LLD"
        assert "LLD-331" in restored.read_text(encoding="utf-8")

    def test_the_counter_starts_fresh(self, repo):
        lineage = repo / "docs" / "lineage" / "active" / f"{ISSUE}-implspec"
        seed = ls.seed_from_lineage(lineage)

        assert seed is not None
        assert seed.rounds_completed == CEILING_ROUNDS, (
            "precondition: the seed sees the full halted grant"
        )
        assert ls.resume_payload(seed)["review_iteration"] == 0

    def test_the_first_regeneration_input_carries_the_verdict_items_verbatim(
        self, repo
    ):
        lineage = repo / "docs" / "lineage" / "active" / f"{ISSUE}-implspec"
        seed = ls.seed_from_lineage(lineage)
        payload = ls.resume_payload(seed)

        assert "FEEDBACK ITEM ALPHA: the assertion for tick 60 must trace to R4." in (
            payload["review_feedback"]
        )
        assert "FEEDBACK ITEM BETA: name the baseline flag in the test plan." in (
            payload["review_feedback"]
        )

    def test_the_barren_resume_dir_is_not_the_seed(self, repo):
        """The failed resume's own dir holds a draft the guard never reviewed;
        seeding it would pair a draft with the WRONG grant's feedback."""
        lineage = repo / "docs" / "lineage" / "active" / f"{ISSUE}-implspec"
        seed = ls.seed_from_lineage(lineage)

        assert "2026-08-25T04-46-02Z" in seed.run_dir


class TestGraveyardGraftsAreASearchedPlace:
    def test_resolve_stage_artifact_finds_the_lld_on_the_graft(self, repo):
        found = speedrun_roll._resolve_stage_artifact(repo, ISSUE, {}, "lld")

        assert found, "no recorded path anywhere -- the graft is the only source"
        assert found.replace("\\", "/").endswith(LLD_REL)

    def test_the_newest_graft_wins(self, repo):
        newer = f"graveyard/{ISSUE}-lld-20260826T000000Z"
        _git(repo, "checkout", "-q", "-b", newer, GRAFT)
        lld = repo / LLD_REL
        lld.write_text("# LLD-331\n\nNEWER GRAFT\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "later graft")
        _git(repo, "checkout", "-q", "main")
        lld.unlink(missing_ok=True)

        assert speedrun_roll._restore_artifact(repo, ISSUE, str(lld)) is True
        assert "NEWER GRAFT" in lld.read_text(encoding="utf-8")

    def test_a_live_lld_branch_still_outranks_the_graft(self, repo):
        _git(repo, "checkout", "-q", "-b", f"{ISSUE}-lld", "main")
        lld = repo / LLD_REL
        lld.parent.mkdir(parents=True, exist_ok=True)
        lld.write_text("# LLD-331\n\nLIVE BRANCH\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "live lld branch")
        _git(repo, "checkout", "-q", "main")
        lld.unlink(missing_ok=True)

        speedrun_roll._restore_artifact(repo, ISSUE, str(lld))
        assert "LIVE BRANCH" in lld.read_text(encoding="utf-8")

    def test_the_graft_refs_are_discovered_newest_first(self, repo):
        newer = f"graveyard/{ISSUE}-lld-20260826T000000Z"
        _git(repo, "branch", newer, GRAFT)

        refs = speedrun_roll._graveyard_issue_lld_refs(repo, ISSUE)

        assert refs[0] == newer
        assert GRAFT in refs

    def test_another_issues_grafts_are_not_this_issues(self, repo):
        _git(repo, "branch", "graveyard/7-lld-20260826T000000Z", GRAFT)

        refs = speedrun_roll._graveyard_issue_lld_refs(repo, ISSUE)

        assert all(f"/{ISSUE}-lld-" in r for r in refs)


class TestTheRefusalNamesWhatWasPreserved:
    """When no attempt branch exists on origin, the machinery itself archived
    it -- a bare 'no attempt branch exists' reads as loss when everything is
    one rename away."""

    def test_the_refusal_inventories_the_graveyard_and_lineage(
        self, repo, log, monkeypatch
    ):
        monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: "")

        assert speedrun_roll.ensure_base_for_resume(repo, ISSUE, log) is None

        written = log.path.read_text(encoding="utf-8")
        assert "no attempt branch exists on origin" in written
        assert GRAFT in written, "the grafted lld branch must be named"
        assert f"{ISSUE}-implspec" in written, "the surviving lineage must be named"

    def test_a_repo_with_nothing_preserved_still_refuses_cleanly(
        self, tmp_path, log, monkeypatch
    ):
        bare = tmp_path / "plain"
        bare.mkdir()
        _git(bare, "init", "-q", "-b", "main")
        monkeypatch.setattr(speedrun_roll, "resolve_attempt_branch", lambda _r: "")

        assert speedrun_roll.ensure_base_for_resume(bare, ISSUE, log) is None
        assert "no attempt branch exists on origin" in log.path.read_text(
            encoding="utf-8"
        )
