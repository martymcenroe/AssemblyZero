"""The verdict block must not under-report the questions a run filed (Closes #2179).

The numbers exist in-process at filing time and were thrown away. `must_resolve`
returns each one on its `FilingResult`; the N0c node discarded the return value;
and the launcher then re-derived the list from a live
`gh issue list --label must-resolve --state open` seconds later. That query
returns short while GitHub is still indexing a just-created issue, and the one
short answer fed BOTH the operator summary and the launch gate file.

Six occurrences across 2026-08-09, 08-10 and 08-11. The worst:
`run-issue7-083155` filed boostgauge #273, #274 and #275 within four seconds and
the block printed `Next step: resolve #273.` -- the operator would have ruled on
one question of three and been refused on the other two. The same short answer
is what wrote an empty `blocking` list into prereqs.json, the write half of
#2196's launch brick.

The remedy the issue itself proposed -- source the list from the live query --
was already the implementation and landed before the issue was filed, so it
would have changed nothing. The fix is to stop discarding the numbers.
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from assemblyzero.speedrun.must_resolve import (
    file_must_resolve,
    filed_ledger_path,
    merge_questions,
    read_filed,
    record_filed,
)

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import speedrun_roll as sr  # noqa: E402


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "boostgauge"
    (r / ".git").mkdir(parents=True)
    return r


# The run that listed one question of three.
RUN_083155 = [
    {"number": 273, "title": "must-resolve: #7 requirements conflict — a"},
    {"number": 274, "title": "must-resolve: #7 requirements conflict — b"},
    {"number": 275, "title": "must-resolve: #7 requirements conflict — c"},
]


#: A well-formed conflict. The divergence condition is load-bearing input, not
#: decoration: #2462 made a filing with an empty one impossible, because a
#: question with nothing to rule ON blocks every later launch and cannot be
#: closed by ruling. These tests are about the ledger, so they hand the filer
#: something it would really file.
CONFLICT = {
    "criterion_a": "A",
    "criterion_b": "B",
    "diverging_situation": "when the reading is at its stop",
}


class TestTheLedgerRecordsWhatWasFiled:
    def test_a_filed_number_is_recorded_at_filing_time(self, repo):
        def runner(args):
            if args[:2] == ["git", "-C"]:
                return subprocess.CompletedProcess(
                    args, 0, stdout="https://github.com/martymcenroe/boostgauge.git\n"
                )
            if args[:3] == ["gh", "issue", "list"]:
                return subprocess.CompletedProcess(args, 0, stdout="[]")
            if args[:3] == ["gh", "issue", "create"]:
                return subprocess.CompletedProcess(
                    args, 0,
                    stdout="https://github.com/martymcenroe/boostgauge/issues/273\n",
                )
            return subprocess.CompletedProcess(args, 0, stdout="")

        result = file_must_resolve(
            repo, 7, CONFLICT, runner=runner, log=lambda *a: None,
        )

        assert result.issue_number == 273
        assert [e["number"] for e in read_filed(repo)] == [273], (
            "the number was known in-process and must be recorded there; "
            "re-deriving it from GitHub seconds later is what returned short"
        )

    def test_a_recurrence_is_recorded_too(self, repo):
        """A commented recurrence is still an OPEN question blocking this run,
        so it belongs in the summary exactly like a fresh filing."""
        existing = json.dumps([{
            "number": 240, "title": "must-resolve: #7 x",
            "body": "<!-- must-resolve source_issue=7 fingerprint=deadbeef -->",
        }])

        def runner(args):
            if args[:2] == ["git", "-C"]:
                return subprocess.CompletedProcess(
                    args, 0, stdout="https://github.com/martymcenroe/boostgauge.git\n"
                )
            if args[:3] == ["gh", "issue", "list"]:
                return subprocess.CompletedProcess(args, 0, stdout=existing)
            return subprocess.CompletedProcess(args, 0, stdout="")

        with patch(
            "assemblyzero.speedrun.must_resolve.conflict_fingerprint",
            lambda a, b: "deadbeef",
        ):
            result = file_must_resolve(
                repo, 7, CONFLICT, runner=runner, log=lambda *a: None,
            )

        assert result.action == "commented"
        assert [e["number"] for e in read_filed(repo)] == [240]

    def test_recording_never_raises(self, repo):
        """The roll is already halting. Losing a ledger line costs the summary
        a number; raising would cost the halt."""
        with patch.object(Path, "mkdir", side_effect=OSError("read-only")):
            assert record_filed(repo, number=1, title="t") is False

    def test_a_corrupt_line_costs_one_entry_not_the_file(self, repo):
        path = filed_ledger_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"number": 273, "title": "a", "ts": "2026-08-11 08:34:45"}\n'
            "not json at all\n"
            '{"number": 275, "title": "c", "ts": "2026-08-11 08:34:49"}\n',
            encoding="utf-8",
        )

        assert [e["number"] for e in read_filed(repo)] == [273, 275]

    def test_entries_before_the_batch_are_excluded(self, repo):
        """A question ruled on last week must not reappear in tonight's block."""
        path = filed_ledger_path(repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            '{"number": 100, "title": "old", "ts": "2026-08-01 10:00:00"}\n'
            '{"number": 273, "title": "new", "ts": "2026-08-11 08:34:45"}\n',
            encoding="utf-8",
        )

        recent = read_filed(repo, since="2026-08-11 08:31:55")
        assert [e["number"] for e in recent] == [273]


class TestTheUnion:
    def test_a_short_live_query_is_completed_by_the_ledger(self):
        """The exact 2026-08-11 signature: three filed, one indexed."""
        live = [RUN_083155[0]]
        merged = merge_questions(live, RUN_083155)

        assert [q["number"] for q in merged] == [273, 274, 275], (
            "the block printed 'Next step: resolve #273.' for a run that filed "
            "three; the operator would have been refused on the other two"
        )

    def test_the_live_title_wins(self):
        """An operator may have renamed the issue since it was filed."""
        merged = merge_questions(
            [{"number": 273, "title": "renamed by the operator"}],
            [{"number": 273, "title": "must-resolve: #7 requirements conflict"}],
        )
        assert merged == [{"number": 273, "title": "renamed by the operator"}]

    def test_a_live_only_question_still_surfaces(self):
        """The ledger does not replace the query -- an earlier run's still-open
        question has no entry from this batch."""
        merged = merge_questions([{"number": 999, "title": "older"}], [])
        assert [q["number"] for q in merged] == [999]

    def test_numbers_are_not_duplicated(self):
        merged = merge_questions(RUN_083155, RUN_083155)
        assert [q["number"] for q in merged] == [273, 274, 275]


class TestTheVerdictBlock:
    def _blocked_verdict(self, repo, live, recorded, since=""):
        for entry in recorded:
            record_filed(
                repo, number=entry["number"], title=entry["title"],
                ts="2026-08-11 08:34:45",
            )
        with patch.object(
            sr, "open_must_resolve_issues", lambda r: (live, None)
        ):
            sr.print_verdict(
                repo, requested=[7], rolled=[], blocked=[7],
                stopped_at=None, code=93, since=since,
            )

    def test_every_filed_question_is_listed(self, repo, capsys):
        self._blocked_verdict(repo, live=[RUN_083155[0]], recorded=RUN_083155)
        out = capsys.readouterr().out

        for number in (273, 274, 275):
            assert f"#{number}" in out, (
                f"#{number} was filed by this run and is missing from the block"
            )
        assert "resolve #273 and #274 and #275" in out

    def test_the_gate_file_gets_the_same_full_list(self, repo, capsys):
        """The summary and the gate are fed from one result. Under-reporting
        wrote a short -- sometimes empty -- blocking list, which is #2196's
        brick."""
        self._blocked_verdict(repo, live=[RUN_083155[0]], recorded=RUN_083155)
        capsys.readouterr()

        data = json.loads(sr.prereqs_path(repo).read_text(encoding="utf-8"))
        assert [b["number"] for b in data["blocking"]] == [273, 274, 275]

    def test_an_offline_gh_still_names_what_this_machine_filed(self, repo, capsys):
        """gh unreachable used to mean an empty list for both surfaces."""
        for entry in RUN_083155:
            record_filed(
                repo, number=entry["number"], title=entry["title"],
                ts="2026-08-11 08:34:45",
            )
        with patch.object(
            sr, "open_must_resolve_issues", lambda r: ([], "no net")
        ):
            sr.print_verdict(
                repo, requested=[7], rolled=[], blocked=[7],
                stopped_at=None, code=93, since="",
            )

        out = capsys.readouterr().out
        assert "#273" in out and "#275" in out
        assert json.loads(
            sr.prereqs_path(repo).read_text(encoding="utf-8")
        )["blocking"]

    def test_no_questions_at_all_says_so_instead_of_resolve_nothing(
        self, repo, capsys
    ):
        """#2224, closed into this issue: the heading printed with nothing
        under it and 'Next step: resolve .' told the operator to resolve
        nothing."""
        with patch.object(sr, "open_must_resolve_issues", lambda r: ([], None)):
            sr.print_verdict(
                repo, requested=[7], rolled=[], blocked=[7],
                stopped_at=None, code=93, since="",
            )

        out = capsys.readouterr().out
        assert "Next step: resolve ." not in out
        assert "must-resolve" in out, "say what to check instead"
        assert not sr.prereqs_path(repo).exists(), (
            "#2196: an empty gate must not be written"
        )

    def test_the_verdict_still_never_raises(self, repo, capsys):
        with patch.object(
            sr, "open_must_resolve_issues", side_effect=RuntimeError("boom")
        ):
            sr.print_verdict(
                repo, requested=[7], rolled=[], blocked=[7],
                stopped_at=None, code=93,
            )
        assert "verdict rendering failed" in capsys.readouterr().out
