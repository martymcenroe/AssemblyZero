"""The archive bundles the branches the pipeline actually writes (#2355).

Measured 2026-08-14, archiving hardening-run-17: the campaign held **64**
graveyard branches, the whole evidence record the preserve-not-delete
discipline had built that week, and the archiver's dry run reported
``graveyard 0``.

The bundle rule matched ``graveyard/<run>*``. The pipeline writes
``graveyard/issue-7-<stamp>``, ``graveyard/7-lld-<stamp>`` and
``graveyard/leavings-<stamp>``. Not one carries the run prefix, so the default
archive bundled zero evidence branches and reported ``complete: true`` anyway.

These tests use the names the pipeline demonstrably produces, not names
invented to match the rule. A fixture that spells its branches
``graveyard/<run>-attempt1`` proves the old rule works and proves nothing
about the pipeline.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from assemblyzero.speedrun.archive import (
    archive_run,
    graveyard_branches_for,
)
from assemblyzero.speedrun.preserved import (
    read_ledger,
    record_preserved,
)

RUN = "hardening-run-17"

#: Verbatim shapes from the incident. `issue-7` is the worktree sweep's
#: preserve step, `7-lld` its LLD sibling, `leavings` the file janitor's.
PIPELINE_BRANCHES = (
    "graveyard/issue-7-20260814T002812Z",
    "graveyard/7-lld-20260814T063916Z",
    "graveyard/leavings-20260813-221501",
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result


def _events(log_dir: Path, tag: str, issue: int, base: str) -> None:
    (log_dir / f"{tag}-events.log").write_text(
        f"2026-08-14 01:00:00 START issue=#{issue} repo=C:\\repo pid=1\n"
        f"2026-08-14 01:00:02 BASE '{base}' verified clean for #{issue}\n"
        f"2026-08-14 01:00:02 LAUNCH base={base} -> {tag}.log\n"
        "2026-08-14 01:07:36 EXIT rc=0\n",
        encoding="utf-8",
    )
    (log_dir / f"{tag}.log").write_text("stdout\n", encoding="utf-8")
    (log_dir / f"{tag}-heartbeat.log").write_text("alive\n", encoding="utf-8")


@pytest.fixture
def campaign(tmp_path: Path) -> dict:
    """A repo carrying pipeline-named graveyard branches, as run-17 did."""
    repo = tmp_path / "boostgauge"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")

    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")

    _git(repo, "checkout", "-q", "-b", RUN)
    (repo / "feature.py").write_text("value = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "arc work")

    for branch in PIPELINE_BRANCHES:
        _git(repo, "branch", branch, RUN)

    log_dir = repo / "data" / "speedrun" / "runs"
    log_dir.mkdir(parents=True)
    _events(log_dir, "run-issue7-153937", 7, RUN)

    return {"repo": repo, "log_dir": log_dir}


class TestTheDefaultRuleFindsThem:
    def test_pipeline_named_branches_need_no_branch_flags(self, campaign):
        """The acceptance criterion, and the measurement that produced it."""
        found = graveyard_branches_for(campaign["repo"], RUN)
        assert sorted(found) == sorted(PIPELINE_BRANCHES)

    def test_the_old_prefix_rule_would_have_found_none(self, campaign):
        """Pin the defect so a regression is visible, not just absent.

        `graveyard/<run>*` against these three names is the exact comparison
        that returned `graveyard 0` on a campaign holding sixty-four.
        """
        prefix = f"graveyard/{RUN}"
        assert [b for b in PIPELINE_BRANCHES if b.startswith(prefix)] == []

    def test_a_default_archive_captures_them(self, campaign):
        result = archive_run(campaign["repo"], RUN, log_dir=campaign["log_dir"])
        bundled = {e["name"] for e in result.index["branches"]["graveyard"]}

        assert bundled == set(PIPELINE_BRANCHES)
        assert result.complete

    def test_complete_now_means_the_evidence_is_in_the_box(self, campaign):
        """`complete: true` with `graveyard 0` was the vacuous-complete case."""
        result = archive_run(campaign["repo"], RUN, log_dir=campaign["log_dir"])

        assert result.complete
        assert len(result.index["branches"]["graveyard"]) == 3


class TestTheBundleSourceIsRecordedOrMeasured:
    def test_the_index_no_longer_states_a_prefix_convention(self, campaign):
        result = archive_run(campaign["repo"], RUN, log_dir=campaign["log_dir"])
        rule = result.index["branches"]["graveyard_match_rule"]

        assert f"graveyard/{RUN}-*" not in rule
        assert "ledger" in rule

    def test_each_branch_records_where_it_came_from(self, campaign):
        record_preserved(
            campaign["repo"], PIPELINE_BRANCHES[0], run=RUN, source="sweep"
        )
        result = archive_run(campaign["repo"], RUN, log_dir=campaign["log_dir"])
        sources = {
            e["name"]: e["source"] for e in result.index["branches"]["graveyard"]
        }

        assert sources[PIPELINE_BRANCHES[0]] == "ledger"
        assert sources[PIPELINE_BRANCHES[1]] == "discovered"

    def test_an_explicit_branch_flag_is_labelled_as_such(self, campaign):
        _git(campaign["repo"], "branch", "salvage/by-hand", RUN)
        result = archive_run(
            campaign["repo"], RUN,
            log_dir=campaign["log_dir"],
            extra_branches=["salvage/by-hand"],
        )
        sources = {
            e["name"]: e["source"] for e in result.index["branches"]["graveyard"]
        }
        assert sources["salvage/by-hand"] == "explicit"


class TestAttributionToAnotherRun:
    def test_another_runs_recorded_branch_is_left_alone(self, campaign):
        """The only thing that excludes a branch is a positive attribution.

        Over-inclusion costs disk in a tool that only ever writes.
        Under-inclusion costs the evidence record, which is the failure here.
        """
        record_preserved(
            campaign["repo"], PIPELINE_BRANCHES[2],
            run="hardening-run-16", source="leavings",
        )
        found = graveyard_branches_for(campaign["repo"], RUN)

        assert PIPELINE_BRANCHES[2] not in found
        assert PIPELINE_BRANCHES[0] in found

    def test_an_unattributed_record_still_belongs_to_this_run(self, campaign):
        """Pre-ledger branches carry no run, and losing them is the defect."""
        record_preserved(campaign["repo"], PIPELINE_BRANCHES[0], source="sweep")
        assert PIPELINE_BRANCHES[0] in graveyard_branches_for(campaign["repo"], RUN)


class TestTheLedger:
    def test_the_sweep_records_what_it_preserves(self, tmp_path):
        assert record_preserved(
            tmp_path, "graveyard/issue-7-20260814T002812Z",
            run=RUN, source="sweep", detail="stranded worktree 7",
        )
        records = read_ledger(tmp_path)

        assert len(records) == 1
        assert records[0].branch == "graveyard/issue-7-20260814T002812Z"
        assert records[0].source == "sweep"
        assert records[0].at

    def test_it_appends_rather_than_replaces(self, tmp_path):
        record_preserved(tmp_path, "graveyard/a", run=RUN)
        record_preserved(tmp_path, "graveyard/b", run=RUN)
        assert [r.branch for r in read_ledger(tmp_path)] == [
            "graveyard/a", "graveyard/b",
        ]

    def test_recording_never_raises_on_a_caller_saving_work(self, tmp_path):
        """A bookkeeping failure must never become lost evidence."""
        blocked = tmp_path / "file-not-dir"
        blocked.write_text("x", encoding="utf-8")

        assert record_preserved(blocked, "graveyard/x") is False

    def test_a_malformed_line_does_not_hide_the_others(self, tmp_path):
        record_preserved(tmp_path, "graveyard/good-1", run=RUN)
        from assemblyzero.speedrun.preserved import ledger_path

        with ledger_path(tmp_path).open("a", encoding="utf-8") as handle:
            handle.write("{not json\n")
        record_preserved(tmp_path, "graveyard/good-2", run=RUN)

        assert [r.branch for r in read_ledger(tmp_path)] == [
            "graveyard/good-1", "graveyard/good-2",
        ]

    def test_a_record_without_a_branch_is_not_a_record(self, tmp_path):
        assert record_preserved(tmp_path, "") is False
        assert read_ledger(tmp_path) == []

    def test_no_ledger_reads_as_empty_not_as_an_error(self, tmp_path):
        assert read_ledger(tmp_path) == []


class TestTheWritersRecord:
    def test_the_worktree_sweep_writes_the_ledger(self):
        import inspect

        from assemblyzero.speedrun import worktrees

        source = inspect.getsource(worktrees._preserve_dirty)
        assert "record_preserved" in source

    def test_the_file_janitor_writes_the_ledger(self):
        import inspect

        from assemblyzero.speedrun import leavings

        source = inspect.getsource(leavings.preserve_and_clear)
        assert "record_preserved" in source

    def test_the_ledger_is_json_lines(self, tmp_path):
        """Append-only and line-delimited, so a crash mid-write loses one row."""
        from assemblyzero.speedrun.preserved import ledger_path

        record_preserved(tmp_path, "graveyard/x", run=RUN, source="sweep")
        text = ledger_path(tmp_path).read_text(encoding="utf-8")

        assert text.endswith("\n")
        assert json.loads(text.strip())["branch"] == "graveyard/x"
