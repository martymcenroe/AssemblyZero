"""A spec-stage requirements conflict must file its question (Closes #2192).

A conflict found at the LLD stage files a must-resolve issue per conflict; the
same conflict found at the SPEC stage exited 93 -- "blocked on an operator
ruling, no redraw can help" -- and filed nothing.

Observed 2026-08-10 on boostgauge `run-issue1-092650`: the LLD passed, spec
review blocked on a contradiction between two requirements, and no issue was
created. Three things followed from the one omission. The verdict block printed
"Next step: resolve ." with nothing in it. The launch gate recorded no numbers,
which is how the empty-blocking brick (#2196) got seeded. And the question had
to be filed by hand for the block to be tracked at all.

Exit 93 means "a human must rule before any roll". That is only real if the
thing to rule on exists.
"""

import subprocess
from unittest.mock import patch

import pytest

from assemblyzero.core.exit_codes import CONFLICT_MARKER
from assemblyzero.speedrun.must_resolve import (
    N0C_ORIGIN,
    SPEC_REVIEW_ORIGIN,
    build_body,
    conflict_fingerprint,
    conflict_from_rationale,
    file_must_resolve,
)
from assemblyzero.workflows.implementation_spec.nodes.review_spec import (
    _file_conflict_if_any,
)

# The reviewer's real shape, per the #1900 escalation instruction: the marker,
# the two conflicting sentences quoted verbatim, then where they diverge.
REVIEWER_RATIONALE = (
    f"{CONFLICT_MARKER} The LLD contains an unresolvable contradiction between "
    'REQ-2 and REQ-4. REQ-2 states "CLI values govern the session and are never '
    'written to the file", while REQ-4 states "launched with --reset-config '
    '--size N, the file holds size N". They diverge when the app is launched '
    "with both --reset-config and --size."
)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "boostgauge"
    (r / ".git").mkdir(parents=True)
    return r


class _Runner:
    """Records gh calls. Returns success with a created-issue URL."""

    def __init__(self, existing_search_output="[]"):
        self.calls: list[list[str]] = []
        self.existing = existing_search_output

    def __call__(self, args):
        self.calls.append(args)
        if args[:3] == ["git", "-C"] or args[:2] == ["git", "-C"]:
            return subprocess.CompletedProcess(
                args, 0, stdout="https://github.com/martymcenroe/boostgauge.git\n"
            )
        if args[:3] == ["gh", "issue", "list"]:
            return subprocess.CompletedProcess(args, 0, stdout=self.existing)
        if args[:3] == ["gh", "issue", "create"]:
            return subprocess.CompletedProcess(
                args, 0, stdout="https://github.com/martymcenroe/boostgauge/issues/253\n"
            )
        if args[:3] == ["gh", "issue", "comment"]:
            return subprocess.CompletedProcess(args, 0, stdout="")
        return subprocess.CompletedProcess(args, 0, stdout="")

    def created(self):
        return [c for c in self.calls if c[:3] == ["gh", "issue", "create"]]


class _Spy:
    """Stands in for file_must_resolve. `_default_runner` cannot be patched at
    module level -- it is bound as a default argument, so a patch never reaches
    an already-defined signature and the real `git` runs instead."""

    def __init__(self, boom=False):
        self.calls: list[tuple] = []
        self.kwargs: list[dict] = []
        self.boom = boom

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        self.kwargs.append(kwargs)
        if self.boom:
            raise RuntimeError("gh exploded")
        return None


class TestTheSpecStageFilesItsQuestion:
    def test_a_conflict_verdict_files_a_must_resolve_issue(self, repo):
        spy = _Spy()
        with patch("assemblyzero.speedrun.must_resolve.file_must_resolve", spy):
            _file_conflict_if_any(
                {"repo_root": str(repo), "issue_number": 1}, REVIEWER_RATIONALE
            )

        assert len(spy.calls) == 1, (
            "a spec-stage requirements conflict must file exactly one question; "
            "filing none is what left run-issue1-092650 with nothing to resolve"
        )
        repo_arg, issue_arg, conflict_arg = spy.calls[0]
        assert int(issue_arg) == 1
        assert "never written to the file" in conflict_arg["criterion_a"]
        assert spy.kwargs[0]["origin"] is SPEC_REVIEW_ORIGIN

    def test_an_ordinary_blocked_verdict_files_nothing(self, repo):
        """Only the escalation marker means the SOURCE requirements are at
        fault. A normal BLOCKED is a spec problem, and filing a question about
        the issue text would be a false alarm at the operator."""
        spy = _Spy()
        with patch("assemblyzero.speedrun.must_resolve.file_must_resolve", spy):
            _file_conflict_if_any(
                {"repo_root": str(repo), "issue_number": 1},
                "Spec omits the error path for a malformed config file.",
            )

        assert spy.calls == []

    def test_filing_never_masks_the_halt(self, repo, capsys):
        """Same contract as N0c's. The roll is already stopping; a filing
        problem is loud and nothing more."""
        spy = _Spy(boom=True)
        with patch("assemblyzero.speedrun.must_resolve.file_must_resolve", spy):
            _file_conflict_if_any(
                {"repo_root": str(repo), "issue_number": 1}, REVIEWER_RATIONALE
            )

        assert "WARNING" in capsys.readouterr().out

    def test_it_really_reaches_gh_issue_create(self, repo):
        """End to end through the filer, with the runner injected explicitly,
        so the wiring above is not the only thing under test."""
        runner = _Runner()
        conflict = conflict_from_rationale(REVIEWER_RATIONALE, CONFLICT_MARKER)

        file_must_resolve(
            repo, 1, conflict, origin=SPEC_REVIEW_ORIGIN,
            runner=runner, log=lambda *a: None,
        )

        created = runner.created()
        assert len(created) == 1
        assert "--label" in created[0] and "must-resolve" in created[0]
        body = created[0][created[0].index("--body") + 1]
        assert "implementation-spec reviewer" in body

    def test_a_missing_issue_number_is_skipped_not_crashed(self, repo):
        """Brief and idea entry paths carry file input, not an issue number."""
        runner = _Runner()
        result = file_must_resolve(
            repo, 0, conflict_from_rationale(REVIEWER_RATIONALE, CONFLICT_MARKER),
            origin=SPEC_REVIEW_ORIGIN, runner=runner, log=lambda *a: None,
        )

        assert result.action == "skipped"
        assert runner.created() == []


class TestParsingTheReviewersProse:
    """N0c hands over a structured conflict; the reviewer writes prose."""

    def test_the_two_quoted_criteria_are_separated(self):
        conflict = conflict_from_rationale(REVIEWER_RATIONALE, CONFLICT_MARKER)

        assert "never written to the file" in conflict["criterion_a"]
        assert "the file holds size N" in conflict["criterion_b"]

    def test_the_diverging_situation_is_captured(self):
        conflict = conflict_from_rationale(REVIEWER_RATIONALE, CONFLICT_MARKER)
        assert "--reset-config" in conflict["diverging_situation"]

    def test_curly_quotes_parse_too(self):
        """A run that filed nothing because of a typographic quote would
        reproduce the defect this closes."""
        rationale = (
            f"{CONFLICT_MARKER} REQ-1 says “the window opens at the saved "
            "position” but REQ-3 says “the window always opens "
            "centred”. They diverge on every launch with a saved position."
        )
        conflict = conflict_from_rationale(rationale, CONFLICT_MARKER)

        assert "saved position" in conflict["criterion_a"]
        assert "centred" in conflict["criterion_b"]

    def test_unquoted_prose_still_yields_a_filable_conflict(self):
        """Best-effort on purpose. A slightly coarse issue is worth having; a
        missing one is the defect."""
        rationale = (
            f"{CONFLICT_MARKER} REQ-2 and REQ-4 cannot both hold when the app "
            "is launched with both flags."
        )
        conflict = conflict_from_rationale(rationale, CONFLICT_MARKER)

        assert conflict["criterion_a"].strip()
        assert "did not quote two separable sentences" in conflict["diverging_situation"]

    def test_parsing_is_deterministic_so_the_fingerprint_is_stable(self):
        """A redraw storm must not file twenty copies of one ambiguity."""
        a = conflict_from_rationale(REVIEWER_RATIONALE, CONFLICT_MARKER)
        b = conflict_from_rationale(REVIEWER_RATIONALE, CONFLICT_MARKER)

        assert conflict_fingerprint(
            a["criterion_a"], a["criterion_b"]
        ) == conflict_fingerprint(b["criterion_a"], b["criterion_b"])


class TestTheIssueSaysWhichGateFoundIt:
    def test_a_spec_filing_does_not_claim_to_be_n0c(self):
        """The body stated "Found by N0c" unconditionally. On a spec-stage
        filing that is simply false, and the operator needs to know which
        document the ruling is against."""
        body = build_body(
            1, conflict_from_rationale(REVIEWER_RATIONALE, CONFLICT_MARKER),
            run_id="run-issue1-092650", run_start="2026-08-10 09:26",
            conflict_ts="2026-08-10 09:43", fingerprint="abc123",
            origin=SPEC_REVIEW_ORIGIN,
        )

        assert "Found by N0c" not in body
        assert "implementation-spec reviewer" in body

    def test_the_lld_filing_is_unchanged(self):
        """The default must stay N0c's, so every existing caller reads the same."""
        body = build_body(
            1, {"criterion_a": "a", "criterion_b": "b"},
            run_id="r", run_start="s", conflict_ts="t", fingerprint="f",
        )
        assert "Found by N0c" in body
        assert N0C_ORIGIN.tag == "N0c"

    def test_both_gates_share_one_question(self, repo):
        """The fingerprint excludes the origin deliberately. One contradiction
        found at both stages is ONE question for the operator, so the second
        detection comments rather than opening a duplicate."""
        conflict = conflict_from_rationale(REVIEWER_RATIONALE, CONFLICT_MARKER)
        fp = conflict_fingerprint(conflict["criterion_a"], conflict["criterion_b"])

        existing = (
            '[{"number": 253, "title": "must-resolve: #1 requirements conflict", '
            f'"body": "<!-- must-resolve source_issue=1 fingerprint={fp} -->"}}]'
        )
        runner = _Runner(existing_search_output=existing)

        result = file_must_resolve(
            repo, 1, conflict, origin=SPEC_REVIEW_ORIGIN, runner=runner, log=lambda *a: None
        )

        assert result.action == "commented"
        assert result.issue_number == 253
        assert runner.created() == [], "a duplicate question is noise at the operator"
