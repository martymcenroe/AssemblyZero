"""The healing ledger and its report (#2164).

Every self-heal leaves a structured record; the report rolls them up and
proposes (never files) issues for recurring heals. An empty ledger is a
real answer with a denominator, never an empty-but-confident report.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import heal_report  # noqa: E402
import speedrun_roll as sr  # noqa: E402

from assemblyzero.speedrun.healing import (  # noqa: E402
    heals_path,
    is_per_roll,
    read_heals,
    record_heal,
)


class TestRecording:
    def test_a_heal_lands_as_one_jsonl_record(self, tmp_path):
        assert record_heal(
            tmp_path, "janitor", "docs/lld/active/LLD-002.md", "healed",
            detail="preserved on graveyard/leavings", run_tag="run-issue1-x",
        )
        records = read_heals(tmp_path)
        assert len(records) == 1
        assert records[0]["category"] == "janitor"
        assert records[0]["outcome"] == "healed"
        assert records[0]["run_tag"] == "run-issue1-x"

    def test_partial_outcomes_are_first_class(self, tmp_path):
        record_heal(
            tmp_path, "reset", "docs/lineage/active/1-lld", "partial",
            detail="WinError 5 Access is denied", run_tag="run-issue1-152826",
        )
        assert read_heals(tmp_path)[0]["outcome"] == "partial"

    def test_recording_never_raises(self, tmp_path):
        """A file in the directory's place makes mkdir fail; the ledger
        swallows it and reports False -- a ledger problem never costs a roll."""
        blocker = tmp_path / "data"
        blocker.write_text("not a directory", encoding="utf-8")
        assert record_heal(tmp_path, "sweep", "x", "healed") is False

    def test_corrupt_lines_are_skipped_not_fatal(self, tmp_path):
        record_heal(tmp_path, "sweep", "a", "healed")
        with heals_path(tmp_path).open("a", encoding="utf-8") as fh:
            fh.write("{not json\n")
        record_heal(tmp_path, "sweep", "b", "healed")
        assert [r["target"] for r in read_heals(tmp_path)] == ["a", "b"]

    def test_the_ledger_lives_under_gitignored_telemetry(self, tmp_path):
        assert "telemetry" in str(heals_path(tmp_path))
        assert str(heals_path(tmp_path)).endswith("heals.jsonl")


class TestReport:
    def _seed(self, repo, runs):
        for tag in runs:
            record_heal(
                repo, "reset", "docs/lineage/active/1-lld", "partial",
                detail="WinError 5", run_tag=tag,
            )

    def test_an_empty_ledger_says_so_with_the_cold_start_rule(
        self, tmp_path, capsys
    ):
        assert heal_report.main(["--repo", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "No heal records" in out
        assert "never fabricate" in out

    def test_per_run_rollup_flags_non_healed_outcomes(self, tmp_path, capsys):
        self._seed(tmp_path, ["run-a"])
        record_heal(tmp_path, "janitor", "leaving.md", "healed", run_tag="run-a")

        heal_report.main(["--repo", str(tmp_path)])

        out = capsys.readouterr().out
        assert "run-a: 2 heal(s)" in out
        assert "! reset: docs/lineage/active/1-lld -- partial" in out

    def test_recurrence_across_three_runs_proposes_an_issue_stub(
        self, tmp_path, capsys
    ):
        # A category that can genuinely keep finding the same stale object.
        # This fixture used to use `reset`, which #2269 reclassified as
        # per-roll -- that exact fixture is the #2242 false alarm, and it now
        # has its own test below.
        for tag in ("run-a", "run-b", "run-c"):
            record_heal(
                tmp_path, "janitor", "stale-lockfile.json", "partial",
                detail="could not remove", run_tag=tag,
            )

        heal_report.main(["--repo", str(tmp_path)])

        out = capsys.readouterr().out
        assert "TITLE: fix: the machinery keeps healing" in out
        assert "3 runs" in out
        assert "operator's call, never automatic" in out

    def test_below_the_threshold_proposes_nothing(self, tmp_path, capsys):
        self._seed(tmp_path, ["run-a", "run-b"])

        heal_report.main(["--repo", str(tmp_path)])

        out = capsys.readouterr().out
        assert "TITLE:" not in out
        assert "nothing proposes an issue" in out


def _healthy_box(*_args, **_kwargs):
    from assemblyzero.speedrun.box_health import BoxHealth

    return BoxHealth(True, [], "")


def _git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result


class TestLauncherHooks:
    def test_the_janitor_writes_heal_records_through_a_real_launch(self, tmp_path):
        """The run-16 shape again: a leaving at launch becomes a janitor heal
        record, not only a narration line."""
        origin = tmp_path / "origin.git"
        subprocess.run(
            ["git", "init", "-q", "--bare", "--initial-branch=main", str(origin)],
            capture_output=True, text=True, check=True,
        )
        repo = tmp_path / "proj"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@t")
        _git(repo, "config", "user.name", "t")
        (repo / ".gitignore").write_text("data/\n", encoding="utf-8")
        (repo / "README.md").write_text("x\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", "base")
        _git(repo, "remote", "add", "origin", str(origin))
        _git(repo, "push", "-qu", "origin", "main")
        _git(repo, "remote", "set-head", "origin", "--auto")
        leaving = repo / "docs" / "lld" / "active" / "LLD-002.md"
        leaving.parent.mkdir(parents=True)
        leaving.write_text("drafted\n", encoding="utf-8")

        with patch.object(sr, "check_assemblyzero_tree", lambda p: []), \
                patch.object(sr, "check_box_health", _healthy_box), \
                patch.object(sr, "open_must_resolve_issues", lambda r: ([], None)), \
                patch.object(sr, "roll_issue", lambda *a: 0):
            code = sr.main(["--repo", str(repo), "--issue", "7"])

        assert code == 0
        heals = read_heals(repo)
        janitor = [h for h in heals if h["category"] == "janitor"]
        assert janitor and janitor[0]["outcome"] == "healed"
        assert "LLD-002.md" in janitor[0]["target"]

    def test_a_storm_is_recorded_without_a_backoff_heal(self):
        """#2206 retired the redraw loop, and the storm BACKOFF heal with it:
        a heal records something the machinery fixed about itself, and with
        no redraw to protect there is no wait to record. The storm is still
        announced in the events log -- pinned in test_provider_storm.py."""
        import inspect

        source = inspect.getsource(sr.main)
        assert "storm-backoff" not in source
        assert "STORM ended" in source


class TestEvidenceExemption:
    def test_the_ledger_is_never_classified_as_dirt(self, tmp_path):
        """#2164's CI catch: in a repo that does not gitignore data/, the
        ledger itself blocked the branch-cutter. Evidence is exempt from
        classification structurally, not by convention."""
        import subprocess as sp

        from assemblyzero.speedrun.leavings import classify_dirt, untracked_files

        repo = tmp_path / "proj"
        repo.mkdir()
        for args in (["init", "-q", "-b", "main"],
                     ["config", "user.email", "t@t"],
                     ["config", "user.name", "t"]):
            sp.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True)
        (repo / "README.md").write_text("x\n", encoding="utf-8")
        sp.run(["git", "-C", str(repo), "add", "."], check=True,
               capture_output=True)
        sp.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True,
               capture_output=True)
        # No .gitignore at all: the ledger would be visible dirt without
        # the structural exemption.
        record_heal(repo, "reset", "#4", "partial", detail="x")

        machinery, operator = classify_dirt(repo)
        assert machinery == [] and operator == []
        assert untracked_files(repo) == []


class TestPerRollArtifactVsRecurringDefect:
    """A stable target string is not a recurring object (#2269).

    The two worked examples are the boostgauge signatures that were root-caused
    to correct-by-design behaviour in #2242 and #2243. Both must stop proposing
    an issue, and a genuine recurrence must keep proposing one -- suppressing a
    real defect would be a worse failure than the noise it replaces.
    """

    def _run(self, tmp_path, capsys, recurrence=3):
        heal_report.main(["--repo", str(tmp_path), "--recurrence", str(recurrence)])
        return capsys.readouterr().out

    # -- the two worked examples ------------------------------------------
    def test_the_2242_signature_proposes_nothing(self, tmp_path, capsys):
        """reset healed '#1' in 9 distinct runs -- nine DIFFERENT LLD PRs."""
        for n in range(9):
            record_heal(tmp_path, "reset", "#1", "healed",
                        detail="base clean after self-heal", run_tag=f"run-{n}")

        out = self._run(tmp_path, capsys)

        assert "TITLE:" not in out, (
            "the #2242 signature still proposes an issue -- this is the false "
            "alarm #2269 exists to remove"
        )
        assert "Set aside as per-roll artifacts" in out
        assert "reset: '#1' in 9 runs" in out

    def test_the_2243_signature_proposes_nothing(self, tmp_path, capsys):
        """restore-reconcile healed a per-issue LLD path in 5 distinct runs."""
        for n in range(5):
            record_heal(
                tmp_path, "restore-reconcile", "docs/lld/active/LLD-001.md",
                "healed", detail="preserved-and-cleared", run_tag=f"run-{n}",
            )

        out = self._run(tmp_path, capsys)

        assert "TITLE:" not in out
        assert "restore-reconcile: 'docs/lld/active/LLD-001.md' in 5 runs" in out

    # -- the case the report was built for, which must survive -------------
    def test_a_genuine_recurrence_still_proposes_an_issue(self, tmp_path, capsys):
        for n in range(4):
            record_heal(tmp_path, "sweep", "orphaned-worktree", "partial",
                        detail="could not remove", run_tag=f"run-{n}")

        out = self._run(tmp_path, capsys)

        assert "TITLE: fix: the machinery keeps healing" in out
        assert "'orphaned-worktree' (sweep)" in out

    # -- instance beats category, in both directions -----------------------
    def test_a_repeated_instance_fires_even_for_a_per_roll_category(
        self, tmp_path, capsys
    ):
        """The same object healed run after run IS a defect, whatever the
        category says. Recorded fact outranks the heuristic."""
        for n in range(4):
            record_heal(tmp_path, "reset", "#1", "partial",
                        detail="same PR again", run_tag=f"run-{n}",
                        instance="PR-244")

        out = self._run(tmp_path, capsys)

        assert "TITLE: fix: the machinery keeps healing" in out, (
            "a reset that keeps failing on the SAME pull request is a real "
            "recurrence and must not be set aside by its category"
        )

    def test_distinct_instances_are_per_roll_even_for_a_recurring_category(
        self, tmp_path, capsys
    ):
        for n in range(4):
            record_heal(tmp_path, "janitor", "docs/lld/active/LLD-001.md",
                        "healed", run_tag=f"run-{n}", instance=f"emission-{n}")

        out = self._run(tmp_path, capsys)

        assert "TITLE:" not in out
        assert "4 distinct recorded instances" in out

    # -- nothing is hidden -------------------------------------------------
    def test_a_set_aside_group_is_still_named_with_its_reason(
        self, tmp_path, capsys
    ):
        for n in range(3):
            record_heal(tmp_path, "reset", "#7", "healed", run_tag=f"run-{n}")

        out = self._run(tmp_path, capsys)

        assert "Set aside as per-roll artifacts" in out
        assert "heals the previous roll's leavings" in out
        assert "is_per_roll" in out, (
            "the report must point at where the rule lives, so a reader who "
            "disagrees knows what to argue with"
        )

    def test_below_threshold_is_not_reported_as_set_aside(self, tmp_path, capsys):
        """Set-aside is about groups that DID recur. A group under the
        threshold was never a candidate and must not appear."""
        for n in range(2):
            record_heal(tmp_path, "reset", "#9", "healed", run_tag=f"run-{n}")

        out = self._run(tmp_path, capsys)

        assert "Set aside" not in out
        assert "nothing proposes an issue" in out


class TestIsPerRollDirectly:
    """The rule itself, away from the report's rendering."""

    def test_no_instances_falls_back_to_category(self):
        assert is_per_roll("reset", []) is True
        assert is_per_roll("restore-reconcile", []) is True
        assert is_per_roll("janitor", []) is False
        assert is_per_roll("sweep", []) is False

    def test_one_known_instance_is_not_enough_to_compare(self):
        # A single data point cannot show sameness or difference.
        assert is_per_roll("janitor", ["only-one"]) is False
        assert is_per_roll("reset", ["only-one"]) is True

    def test_blank_instances_are_not_treated_as_a_shared_object(self):
        """"Not recorded" is not evidence of sameness -- otherwise every
        legacy record would collapse into one instance and read as a
        recurrence."""
        assert is_per_roll("reset", ["", "", ""]) is True
        assert is_per_roll("janitor", ["", "", ""]) is False

    def test_all_distinct_is_per_roll(self):
        assert is_per_roll("janitor", ["a", "b", "c"]) is True

    def test_any_repeat_is_a_recurrence(self):
        assert is_per_roll("reset", ["a", "b", "a"]) is False
