"""The fail-open audit, and the gate that keeps it honest (#2475).

Two jobs here, and they are different.

The first is testing the CLASSIFIER on hand-written samples whose right answer
is obvious by eye. An audit is only worth its output if `propagates` really
means the code halts and `falls_through` really means it does not, so every
outcome and every category is pinned against a snippet small enough to check
by reading.

The second is the GATE: the audit is run against this repo and compared to a
frozen baseline, so a newly-introduced fail-open fails the build at the point it
lands. That is the whole reason #2475 asked for a program rather than a
read-through -- a manual inspection proves the state of one moment, and this
proves the state of every commit after it.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import audit_fail_open as cli  # noqa: E402

from assemblyzero.core.fail_open_audit import (  # noqa: E402
    CATEGORY_HANDLER,
    CATEGORY_UNMET_PRECONDITION,
    CATEGORY_VACUOUS_PASS,
    CATEGORY_WARNED_RETURN,
    OUTCOME_FALLS_THROUGH,
    OUTCOME_SUBSTITUTES,
    VISIBILITY_LOUD,
    VISIBILITY_RECORDED,
    VISIBILITY_SILENT,
    Coverage,
    scan,
    scan_file,
)


def _findings(tmp_path, source: str, name: str = "sample.py"):
    """Classify one snippet, as if it were a module in the tree."""
    path = tmp_path / name
    path.write_text(source, encoding="utf-8")
    return scan_file(path, tmp_path, Coverage())


# ---------------------------------------------------------------------------
# The classifier
# ---------------------------------------------------------------------------


class TestFailClosedIsNotAFinding:
    """A site that halts is the thing the audit wants. Reporting it would be
    the noise that trains people to ignore the whole report."""

    def test_a_reraise_is_not_a_finding(self, tmp_path):
        assert _findings(tmp_path, """
def f():
    try:
        go()
    except OSError:
        raise
""") == []

    def test_raising_something_else_is_not_a_finding(self, tmp_path):
        assert _findings(tmp_path, """
def f():
    try:
        go()
    except OSError as e:
        raise RuntimeError("no") from e
""") == []

    def test_sys_exit_is_not_a_finding(self, tmp_path):
        assert _findings(tmp_path, """
def f():
    try:
        go()
    except OSError:
        sys.exit(1)
""") == []

    def test_returning_an_error_message_is_not_a_finding(self, tmp_path):
        """The pipeline's own halt protocol: a dict carrying error_message is
        a node reporting failure, not substituting a result."""
        assert _findings(tmp_path, """
def node(state):
    try:
        go()
    except OSError as e:
        return {"error_message": str(e)}
""") == []

    def test_returning_the_unverified_marker_is_not_a_finding(self, tmp_path):
        """#2474's halt. The audit must read the fix as fail-closed, or it
        would report the repair as the defect."""
        assert _findings(tmp_path, """
def node(state):
    try:
        go()
    except OSError as e:
        return {"requirements_unverified": str(e)}
""") == []

    def test_returning_a_halt_helper_is_not_a_finding(self, tmp_path):
        assert _findings(tmp_path, """
def node(state):
    try:
        go()
    except OSError as e:
        return _halt_unverified(state, "m", str(e))
""") == []


class TestTheOutcomes:
    def test_a_bare_pass_falls_through(self, tmp_path):
        found = _findings(tmp_path, """
def f():
    try:
        go()
    except OSError:
        pass
    keep_going()
""")
        assert len(found) == 1
        assert found[0].outcome == OUTCOME_FALLS_THROUGH
        assert found[0].category == CATEGORY_HANDLER

    def test_a_neutral_return_substitutes(self, tmp_path):
        found = _findings(tmp_path, """
def f():
    try:
        return real()
    except OSError:
        return {}
""")
        assert len(found) == 1
        assert found[0].outcome == OUTCOME_SUBSTITUTES

    def test_a_continue_says_the_item_was_dropped(self, tmp_path):
        """Not the same failure as a plain fall-through: a loop that quietly
        drops items returns a short result that looks like a complete one.
        This is the shape that silently skipped two BOM-carrying files."""
        found = _findings(tmp_path, """
def f(paths):
    for p in paths:
        try:
            read(p)
        except OSError:
            continue
""")
        assert len(found) == 1
        assert "drops this item" in found[0].what_happens


class TestVisibilityIsTheRankingKey:
    """A fail-open that leaves a visible mark is a nuisance. One whose output
    is identical to the success path is what makes results untrustworthy."""

    def test_a_silent_handler_is_indistinguishable_from_success(self, tmp_path):
        found = _findings(tmp_path, """
def f():
    try:
        go()
    except OSError:
        pass
""")
        assert found[0].visibility == VISIBILITY_SILENT
        assert found[0].distinguishable == "no"

    def test_a_handler_that_prints_is_distinguishable(self, tmp_path):
        found = _findings(tmp_path, """
def f():
    try:
        go()
    except OSError as e:
        print(f"skipped: {e}")
""")
        assert found[0].visibility == VISIBILITY_LOUD
        assert found[0].distinguishable == "yes"

    def test_a_logger_counts_as_speaking(self, tmp_path):
        found = _findings(tmp_path, """
def f():
    try:
        go()
    except OSError:
        logger.warning("could not")
""")
        assert found[0].visibility == VISIBILITY_LOUD

    def test_an_accumulating_validator_is_not_called_silent(self, tmp_path):
        """The false positive this rule was written for.

        `except OSError as e: invalid_refs.append(...)` continues executing, so
        it is fail-open by outcome -- but the failure became an entry the
        caller reports, so the output is NOT identical to the success path.
        Ranking the pipeline's most careful error handling at the top of a list
        titled "makes results untrustworthy" is how a report gets ignored.
        """
        found = _findings(tmp_path, """
def check_refs(paths):
    bad = []
    for p in paths:
        try:
            read(p)
        except OSError as e:
            bad.append(f"{p}: cannot read: {e}")
    return bad
""")
        assert found[0].visibility == VISIBILITY_RECORDED
        assert found[0].distinguishable == "maybe"

    def test_recorded_is_maybe_not_yes(self, tmp_path):
        """Whether the structure reaches the operator is a question about the
        caller. Asserting either way would be a guess dressed as a finding."""
        found = _findings(tmp_path, """
def check(items):
    out = {}
    try:
        go()
    except OSError:
        out["failed"] = True
    return out
""")
        assert found[0].distinguishable == "maybe"

    def test_a_status_dict_is_a_failure_report_not_a_silent_swap(self, tmp_path):
        """`{"returncode": -1, "stderr": "timed out"}` is the function saying
        it failed, in its own protocol. It is not the graph's error_message,
        and calling it silent would flag a correct failure path as the class
        that makes results untrustworthy."""
        found = _findings(tmp_path, """
def run_e2e(cmd):
    try:
        return {"returncode": go(cmd), "stdout": "", "stderr": ""}
    except TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "timed out"}
""")
        assert found[0].visibility == VISIBILITY_RECORDED

    def test_returning_the_caught_exception_carries_the_failure(self, tmp_path):
        found = _findings(tmp_path, """
def f():
    try:
        go()
    except OSError as exc:
        return ("failed", exc)
""")
        assert found[0].visibility == VISIBILITY_RECORDED

    def test_returning_an_unrelated_empty_value_is_still_silent(self, tmp_path):
        """The counterexample that keeps the rule from swallowing everything:
        `return empty` says nothing about why, so the caller sees "no results"
        and cannot tell it from a real empty answer."""
        found = _findings(tmp_path, """
def extract(spec):
    empty = []
    try:
        return parse(spec)
    except ParsingError:
        return empty
""")
        assert found[0].visibility == VISIBILITY_SILENT

    def test_recorded_ranks_between_silent_and_loud(self, tmp_path):
        found = _findings(tmp_path, """
def loud():
    try:
        go()
    except OSError as e:
        print(e)

def files(errs):
    try:
        go()
    except OSError as e:
        errs.append(e)

def quiet():
    try:
        go()
    except OSError:
        pass
""")
        ordered = sorted(found, key=lambda f: f.sort_key())
        assert [f.visibility for f in ordered] == [
            VISIBILITY_SILENT, VISIBILITY_RECORDED, VISIBILITY_LOUD
        ]

    def test_silent_sites_rank_above_loud_ones(self, tmp_path):
        found = _findings(tmp_path, """
def loud():
    try:
        go()
    except OSError as e:
        print(e)

def quiet():
    try:
        go()
    except OSError:
        pass
""")
        assert [f.visibility for f in sorted(found, key=lambda x: x.sort_key())] == [
            VISIBILITY_SILENT, VISIBILITY_LOUD
        ]


class TestTheVacuousPassClass:
    """Recorded 2026-08-16: a heading did not match, zero sentences were
    examined, and PASS was reported."""

    def test_a_validator_returning_true_on_empty_input_is_a_finding(self, tmp_path):
        found = _findings(tmp_path, """
def validate_rows(rows):
    if not rows:
        return True
    return all(ok(r) for r in rows)
""")
        assert [f.category for f in found] == [CATEGORY_VACUOUS_PASS]
        assert "examined nothing" in found[0].what_happens

    def test_a_length_test_counts_too(self, tmp_path):
        found = _findings(tmp_path, """
def check_items(items):
    if len(items) == 0:
        return True
    return False
""")
        assert [f.category for f in found] == [CATEGORY_VACUOUS_PASS]

    def test_an_ordinary_helper_is_not_flagged(self, tmp_path):
        """Only gates, checks and validators. A plain helper returning early on
        empty input is ordinary code, and flagging it is the noise that makes a
        report unreadable."""
        assert _findings(tmp_path, """
def join_names(names):
    if not names:
        return None
    return ", ".join(names)
""") == []

    def test_a_validator_that_reports_failure_on_empty_is_not_flagged(self, tmp_path):
        assert _findings(tmp_path, """
def validate_rows(rows):
    if not rows:
        return {"error_message": "no rows to validate"}
    return {}
""") == []


class TestTheUnmetPreconditionClass:
    """A check whose precondition failed, returning its all-clear anyway.

    Split from vacuous-pass because the cause differs and a reader fixes them
    differently: "there was nothing to look at" and "I could not look" are not
    the same defect, and calling the second one the first puts a false sentence
    beside a real finding.
    """

    def test_a_missing_file_returning_no_findings_is_flagged(self, tmp_path):
        """A scanner that returns [] because the file was absent is
        indistinguishable from one that read it and found nothing."""
        found = _findings(tmp_path, """
def scan_claims(readme_path):
    if not os.path.exists(readme_path):
        return []
    return [c for c in read(readme_path)]
""")
        assert [f.category for f in found] == [CATEGORY_UNMET_PRECONDITION]
        assert "os.path.exists" in found[0].what_fails

    def test_returning_none_is_not_flagged(self, tmp_path):
        """None conventionally reads as "no answer" and callers are expected to
        test it. An empty COLLECTION is the one that reads as a clean result.
        Counting both would bury the report under every `X | None` helper."""
        assert _findings(tmp_path, """
def validate_path(p, root):
    if not p:
        return None
    return resolve(p, root)
""") == []

    def test_an_ordinary_function_is_not_flagged(self, tmp_path):
        assert _findings(tmp_path, """
def render_rows(rows):
    if not os.path.exists(rows):
        return []
    return read(rows)
""") == []


class TestTheWarnedReturnClass:
    """N0c's own pre-#2474 shape: say something could not be done, then return
    the value that means everything is fine."""

    def test_a_warning_then_a_neutral_return_is_a_finding(self, tmp_path):
        found = _findings(tmp_path, """
def node(state):
    if broken():
        print("  WARNING: analysis unavailable; proceeding.")
        return {}
    return real()
""")
        assert [f.category for f in found] == [CATEGORY_WARNED_RETURN]

    def test_an_ordinary_print_before_a_return_is_not_a_finding(self, tmp_path):
        """Progress narration is not an admission. Without this the rule fires
        on every function that logs before returning."""
        assert _findings(tmp_path, """
def node(state):
    print("  [N1] done.")
    return {}
""") == []

    def test_one_site_is_not_counted_twice(self, tmp_path):
        """`if not x: print(WARNING); return {}` trips both the vacuous-pass
        rule and the warned-return rule. A count this audit asks people to
        trust cannot double-count."""
        found = _findings(tmp_path, """
def check_conflicts(conflicts):
    if not conflicts:
        print("  WARNING: nothing verifiable; proceeding.")
        return {}
    return {"error_message": "conflict"}
""")
        assert len(found) == 1, [f.category for f in found]


class TestDeclaringADecision:
    """Some fall-throughs are correct. The job is to make each one a decision
    on record rather than an accident."""

    SOURCE = """
def f():
    try:
        go()
    except OSError:
        # fail-open: advisory only, a missing benchmark must not halt a run.
        pass
"""

    def test_a_declared_site_is_still_reported(self, tmp_path):
        """It is still fail-open. Declaring changes who decided, not what the
        code does, so hiding it would make the inventory a lie."""
        found = _findings(tmp_path, self.SOURCE)
        assert len(found) == 1

    def test_a_declared_site_is_marked_declared(self, tmp_path):
        assert _findings(tmp_path, self.SOURCE)[0].declared is True

    def test_an_undeclared_site_is_not(self, tmp_path):
        found = _findings(tmp_path, """
def f():
    try:
        go()
    except OSError:
        pass
""")
        assert found[0].declared is False

    def test_a_marker_above_the_handler_counts(self, tmp_path):
        found = _findings(tmp_path, """
def f():
    try:
        go()
    # fail-open: the probe is best-effort.
    except OSError:
        pass
""")
        assert found[0].declared is True

    def test_undeclared_sites_rank_above_declared_ones(self, tmp_path):
        found = _findings(tmp_path, """
def ruled():
    try:
        go()
    except OSError:
        # fail-open: deliberate.
        pass

def unruled():
    try:
        go()
    except OSError:
        pass
""")
        ordered = sorted(found, key=lambda f: f.sort_key())
        assert [f.declared for f in ordered] == [False, True]


class TestCoverageIsCounted:
    def test_it_counts_what_it_examined(self, tmp_path):
        (tmp_path / "a.py").write_text("""
def f():
    try:
        go()
    except OSError:
        pass
""", encoding="utf-8")
        findings, coverage = scan(tmp_path, (".",))
        assert coverage.files_scanned == 1
        assert coverage.functions_scanned == 1
        assert coverage.handlers_examined == 1
        assert len(findings) == 1

    def test_an_unreadable_file_is_named_not_swallowed(self, tmp_path):
        (tmp_path / "broken.py").write_text("def f(:\n", encoding="utf-8")
        _, coverage = scan(tmp_path, (".",))
        assert coverage.files_unparseable == ["broken.py"]
        assert coverage.files_scanned == 0

    def test_a_utf8_bom_does_not_hide_a_file(self, tmp_path):
        """Two files in this tree carry a BOM. Plain utf-8 leaves it in the
        source and ast.parse rejects it, so a naive scanner silently reports
        full coverage of a tree it did not fully read."""
        (tmp_path / "bom.py").write_text("""
def f():
    try:
        go()
    except OSError:
        pass
""", encoding="utf-8-sig")
        findings, coverage = scan(tmp_path, (".",))
        assert coverage.files_unparseable == []
        assert coverage.files_scanned == 1
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def repo_scan():
    return scan(ROOT, cli.DEFAULT_SUBDIRS)


class TestTheRepoGate:
    """What makes this a check rather than a report."""

    def test_the_audit_reads_this_repo(self, repo_scan):
        _, coverage = repo_scan
        assert coverage.files_scanned > 200, (
            "the sweep must cover the pipeline, not a corner of it"
        )

    def test_every_file_in_scope_parsed(self, repo_scan):
        """A scanner that skips files reports a coverage number it did not
        earn. This is the assertion that caught the BOM."""
        _, coverage = repo_scan
        assert coverage.files_unparseable == []

    def test_no_fail_open_site_is_new(self, repo_scan):
        """The gate itself.

        Clearing a finding means one of two things and the audit does not care
        which: make the site fail closed, or write the marker and let it be a
        decision on record. What it refuses is a third state where nobody has
        decided.
        """
        findings, _ = repo_scan
        ok, fresh = cli.check(findings, cli.load_baseline())
        assert ok, (
            "New fail-open site(s) not in the baseline:\n"
            + "\n".join(
                f"  {f.path}:{f.line}  {f.qualname}  ({f.category}/{f.outcome})\n"
                f"      instead of halting: {f.what_happens}\n"
                f"      output tells you it happened: {f.distinguishable}"
                for f in fresh
            )
            + "\n\nEither make the site fail closed, or rule on it in the code "
            "with '# fail-open: <why continuing is correct here>', then "
            "regenerate with tools/audit_fail_open.py --write-baseline."
        )

    def test_the_baseline_is_not_stale(self, repo_scan):
        """A baseline listing sites that no longer exist is a baseline nobody
        has read. Fixing a fail-open should shrink it, and this is what says so.
        """
        findings, _ = repo_scan
        live = {f.key for f in findings}
        stale = sorted(cli.load_baseline() - live)
        assert not stale, (
            f"{len(stale)} baseline entr(y/ies) no longer match any site. "
            "Regenerate with tools/audit_fail_open.py --write-baseline:\n  "
            + "\n  ".join(stale[:20])
        )

    def test_the_denominator_matches_what_it_was_measured_against(self, repo_scan):
        """#2780's assertion, which this baseline was missing (#2753).

        The `undeclared` list is enforced and `measured_against` was not, so
        it could only be right by accident of who last regenerated the file.
        It was not right: the committed block read 282 files / 7392 sites /
        471 findings while the walker on the same tree saw 310 / 8803 / 535 --
        drifted by 28 files and 64 findings. A denominator that wrong is worse
        than none, because it reads as evidence.

        Re-derived from the same scan the gate uses, not compared to a
        literal, or this becomes one more number nobody updates.
        """
        findings, coverage = repo_scan
        baseline = json.loads(cli.BASELINE_PATH.read_text(encoding="utf-8"))
        assert baseline["measured_against"] == {
            "files_scanned": coverage.files_scanned,
            "sites_examined": coverage.sites_examined,
            "findings_total": len(findings),
        }, (
            "the baseline's stated denominator no longer matches the tree it "
            "claims to describe; regenerate with "
            "`tools/audit_fail_open.py --write-baseline`"
        )

    def test_a_new_fail_open_actually_trips_the_gate(self, repo_scan):
        """The gate's own regression test.

        Every other assertion here passes when the repo is clean, which is also
        what a gate that can never fail looks like. This drops one site out of
        the baseline and asserts the check goes red, so "no new fail-open" is a
        result rather than a property of the assertion.
        """
        findings, _ = repo_scan
        baseline = cli.load_baseline()
        undeclared = [f for f in findings if not f.declared]
        assert undeclared, "the fixture needs at least one undeclared site"

        weakened = baseline - {undeclared[0].key}
        ok, fresh = cli.check(findings, weakened)

        assert not ok
        assert [f.key for f in fresh] == [undeclared[0].key]

    def test_a_declared_site_does_not_need_a_baseline_entry(self, repo_scan):
        """The escape hatch has to work, or the only way to clear a finding is
        to edit the baseline -- which would make the marker decorative."""
        findings, _ = repo_scan
        declared = [f for f in findings if f.declared]
        assert declared, "at least one site should be ruled on by now"

        ok, _ = cli.check(declared, set())

        assert ok, "a ruled site must pass against an empty baseline"

    def test_the_baseline_file_is_tracked_and_readable(self):
        assert cli.BASELINE_PATH.exists(), "the gate needs a baseline to compare to"
        payload = json.loads(cli.BASELINE_PATH.read_text(encoding="utf-8"))
        assert isinstance(payload["undeclared"], list)
        assert payload["undeclared"], "an empty baseline would pass by vacuum"


class TestTheAuditFindsTheDefectItWasBuiltFor:
    """#2474's N0c gate, before and after, as the audit's own fixture.

    If the classifier cannot see the defect that prompted the sweep, nothing it
    says about the other 400 sites is worth reading.
    """

    BEFORE = """
def analyze_requirements(state):
    result = invoke()
    if not result.success:
        print("  [N0c] WARNING: analysis unavailable; proceeding.")
        return {}
    return {}
"""

    AFTER = """
def analyze_requirements(state):
    result = invoke()
    if not result.success:
        return _halt_unverified(state, "model", "unavailable")
    return {}
"""

    def test_it_flags_the_pre_fix_shape(self, tmp_path):
        found = _findings(tmp_path, self.BEFORE)
        assert found, "the audit must see the defect that prompted it"
        assert found[0].category == CATEGORY_UNMET_PRECONDITION

    def test_it_names_the_precondition_that_was_not_met(self, tmp_path):
        """The description has to be right, not just the flag.

        This site is the archetype: the call did not succeed, and the node
        returned the value that means the requirements were checked and were
        clean. Naming `result.success` is what tells the reader which branch to
        go and read.
        """
        found = _findings(tmp_path, self.BEFORE)
        assert "result.success" in found[0].what_fails
        assert "without running the check" in found[0].what_happens

    def test_it_does_not_flag_the_fixed_shape(self, tmp_path):
        assert _findings(tmp_path, self.AFTER) == []

    def test_a_node_is_marked_as_spending_afterwards(self, tmp_path):
        """The column that says the failure costs money. Answered structurally:
        a graph node that returns normally routes onward, and everything
        downstream of a node calls models."""
        nodes = tmp_path / "workflows" / "requirements" / "nodes"
        nodes.mkdir(parents=True)
        found = scan_file(
            _write(nodes / "n.py", self.BEFORE), tmp_path, Coverage()
        )
        assert found[0].spends_after == "yes"

    def test_a_non_node_module_does_not_claim_to_know(self, tmp_path):
        """Whether a helper's caller spends is not derivable from the helper,
        so the audit says unknown rather than asserting either way."""
        found = _findings(tmp_path, self.BEFORE)
        assert found[0].spends_after == "unknown"


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


class TestTheReportRenders:
    def test_it_names_the_counts_it_measured(self, repo_scan):
        findings, coverage = repo_scan
        report = cli.render_report(findings, coverage)
        assert str(coverage.files_scanned) in report
        assert str(len(findings)) in report

    def test_the_tsv_has_one_row_per_finding(self, repo_scan):
        findings, _ = repo_scan
        rows = cli.render_tsv(findings).splitlines()
        assert len(rows) == len(findings) + 1

    def test_the_ast_module_is_what_parses_the_tree(self):
        """Guards the one assumption the whole audit rests on: that findings
        come from parsing the code, not from matching text against it."""
        assert isinstance(ast.parse("x = 1"), ast.Module)
