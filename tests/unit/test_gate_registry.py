"""The gate registry and the walker that keeps it honest (#2719, #2720).

Two halves, tested in both directions: every halt site the walker finds in the
workflow tree names a registry row, and every row's sites exist. Plus the
ratchet: the count of rows that halt may fall and may not rise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPO_ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import audit_halt_sites as cli  # noqa: E402

from assemblyzero.core.gate_registry import (  # noqa: E402
    ACTION_HALT,
    ACTIONS,
    GATE_REGISTRY,
    JUDGES,
    JUDGES_BUDGET,
    JUDGES_INFRASTRUCTURE,
    JUDGES_ISSUE_BODY,
    JUDGES_MODEL_OUTPUT,
    KIND_RAISE,
    KIND_RETURN,
    KIND_STAGE_RESULT,
    STAGES,
    gate_key_of,
    halt_counts,
    halted,
    phantoms,
    registry_by_key,
    scan_halt_sites,
    unregistered,
)
from assemblyzero.speedrun.factory_report import (  # noqa: E402
    CAUSE_KILLED,
    CAUSE_TABLE,
    CAUSE_UNCLASSIFIED,
    CAUSE_UNRECORDED,
)

BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "gate_registry_baseline.json"


@pytest.fixture(scope="module")
def walked():
    sites, coverage = scan_halt_sites(REPO_ROOT)
    assert coverage.files_scanned > 0, "the walker scanned nothing"
    assert not coverage.files_unparseable, coverage.files_unparseable
    return sites


# ---------------------------------------------------------------------------
# The table itself
# ---------------------------------------------------------------------------


class TestVocabulary:
    def test_keys_are_unique(self):
        keys = [gate.key for gate in GATE_REGISTRY]
        assert len(keys) == len(set(keys)), sorted(
            k for k in keys if keys.count(k) > 1
        )

    def test_every_row_uses_the_closed_vocabularies(self):
        for gate in GATE_REGISTRY:
            assert gate.stage in STAGES, gate.key
            assert gate.judges in JUDGES, gate.key
            assert gate.action in ACTIONS, gate.key
            assert gate.emits.strip(), f"{gate.key} emits nothing"

    def test_every_row_names_where_it_is_decided(self):
        """Sites from the walker, or a decided_in for a gate whose halt is a
        router edge or a core budget the walker does not see."""
        for gate in GATE_REGISTRY:
            assert gate.sites or gate.decided_in, (
                f"{gate.key} names no site and no decided_in"
            )

    def test_no_site_belongs_to_two_rows(self):
        seen: dict[str, str] = {}
        for gate in GATE_REGISTRY:
            for site in gate.sites:
                assert site not in seen, (
                    f"{site} is in both {seen[site]} and {gate.key}"
                )
                seen[site] = gate.key

    def test_decided_in_names_a_real_file(self):
        for gate in GATE_REGISTRY:
            if not gate.decided_in:
                continue
            path = REPO_ROOT / gate.decided_in.split("::")[0]
            assert path.is_file(), f"{gate.key}: {gate.decided_in} is not a file"


# ---------------------------------------------------------------------------
# The walker and the registry agree, both ways
# ---------------------------------------------------------------------------


class TestWalkerAgreesWithRegistry:
    def test_every_walked_site_names_a_row(self, walked):
        fresh = unregistered(walked)
        assert not fresh, (
            "halt sites no registry row names -- add each to a row, or a new "
            "row with its issue and the run that justified it:\n  "
            + "\n  ".join(f"{s.key}  line {s.line}  {s.head[:60]!r}" for s in fresh)
        )

    def test_no_row_names_a_site_the_walker_cannot_find(self, walked):
        ghosts = phantoms(walked)
        assert not ghosts, (
            "registry sites the walker did not find (the code moved or the "
            "index shifted):\n  "
            + "\n  ".join(f"{g}: {s}" for g, s in ghosts)
        )

    def test_emits_is_a_true_statement_about_the_code(self, walked):
        """A row's `emits` is the head the run log shows. It must be found at
        one of the row's sites, or in the file the row says decides it."""
        heads_by_key: dict[str, list[str]] = {}
        for site in walked:
            heads_by_key.setdefault(site.key, []).append(site.head)
        for gate in GATE_REGISTRY:
            heads = [h for s in gate.sites for h in heads_by_key.get(s, [])]
            if any(gate.emits in head for head in heads):
                continue
            if gate.decided_in:
                text = (REPO_ROOT / gate.decided_in.split("::")[0]).read_text(
                    encoding="utf-8", errors="replace"
                )
                if gate.emits in text:
                    continue
            pytest.fail(
                f"{gate.key}: emits {gate.emits!r} but no covered site's head "
                f"carries it (heads: {[h[:50] for h in heads]})"
            )

    def test_the_cli_check_passes(self, capsys):
        assert cli.main(["--check"]) == 0
        assert "PASS" in capsys.readouterr().out


class TestWalkerCatchesANewSite:
    """The zero needs a negative test: a fresh, unregistered gate is found."""

    def _fixture_tree(self, tmp_path: Path) -> Path:
        module = tmp_path / "assemblyzero" / "workflows" / "fresh" / "node.py"
        module.parent.mkdir(parents=True)
        module.write_text(
            "\n".join(
                [
                    "def n1(state):",
                    "    if state.get('bad'):",
                    "        return {'error_message': 'NEW GATE: something', 'x': 1}",
                    "    return {'error_message': ''}",
                    "",
                    "def n2(path):",
                    "    raise ImplementationError(filepath=path, reason=f'Boom {path}')",
                    "",
                    "def n3():",
                    "    msg = 'Stage failed: ' + 'x'",
                    "    return _make_stage_result(status='failed', error_message=msg)",
                    "",
                    "def n4():",
                    "    raise ValueError('a bug, not a gate')",
                ]
            ),
            encoding="utf-8",
        )
        return tmp_path

    def test_finds_each_kind_and_reads_the_head(self, tmp_path):
        sites, coverage = scan_halt_sites(self._fixture_tree(tmp_path))
        assert coverage.files_scanned == 1
        by_qual = {s.qualname: s for s in sites}
        assert set(by_qual) == {"n1", "n2", "n3"}, [s.key for s in sites]
        assert by_qual["n1"].kind == KIND_RETURN
        assert by_qual["n1"].head == "NEW GATE: something"
        assert by_qual["n2"].kind == KIND_RAISE
        assert by_qual["n2"].head == "Boom {}"
        assert by_qual["n3"].kind == KIND_STAGE_RESULT
        # The name resolves to its nearest assignment; the concatenation
        # reads its left side.
        assert by_qual["n3"].head == "Stage failed: "
        assert by_qual["n1"].key == (
            "assemblyzero/workflows/fresh/node.py::n1::return::0"
        )

    def test_a_fresh_site_is_reported_unregistered(self, tmp_path):
        sites, _ = scan_halt_sites(self._fixture_tree(tmp_path))
        assert {s.qualname for s in unregistered(sites)} == {"n1", "n2", "n3"}

    def test_an_empty_error_message_is_not_a_site(self, tmp_path):
        sites, _ = scan_halt_sites(self._fixture_tree(tmp_path))
        assert all(s.index == 0 for s in sites if s.qualname == "n1")


# ---------------------------------------------------------------------------
# The tag for new sites
# ---------------------------------------------------------------------------


class TestHaltedTag:
    def test_tags_and_round_trips(self):
        key = GATE_REGISTRY[0].key
        tagged = halted(key, "something went wrong ")
        assert tagged.endswith(f"[gate:{key}]")
        assert gate_key_of(tagged) == key

    def test_an_unregistered_key_is_refused(self):
        with pytest.raises(KeyError):
            halted("no.such.gate", "x")

    def test_an_untagged_message_has_no_key(self):
        assert gate_key_of("Iteration cap: 3 review rounds ended REVISE") == ""


# ---------------------------------------------------------------------------
# The join to the report's cause-of-death table
# ---------------------------------------------------------------------------


class TestCauseTableJoins:
    def test_every_cause_key_is_a_registered_gate(self):
        absences = {CAUSE_UNRECORDED, CAUSE_UNCLASSIFIED, CAUSE_KILLED}
        keys = registry_by_key()
        missing = sorted(
            cause.key for cause in CAUSE_TABLE
            if cause.key not in absences and cause.key not in keys
        )
        assert not missing, (
            f"cause keys the report can print but the registry does not know: "
            f"{missing}"
        )

    def test_the_judges_columns_agree(self):
        keys = registry_by_key()
        for cause in CAUSE_TABLE:
            gate = keys.get(cause.key)
            if gate is None:
                continue
            assert gate.judges == cause.judges, (
                f"{cause.key}: report says {cause.judges}, registry says "
                f"{gate.judges}"
            )


# ---------------------------------------------------------------------------
# The ratchet (#2720)
# ---------------------------------------------------------------------------


class TestRatchet:
    """The expense-report rule as a test: the count of gates that halt may
    fall, and may not rise without the baseline moving in the same PR."""

    def test_baseline_exists(self):
        assert BASELINE_PATH.is_file(), (
            f"{BASELINE_PATH} missing -- write it with the current halt_counts()"
        )

    def test_halt_rows_did_not_rise_in_any_stage(self):
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        allowed = baseline["halt_rows_per_stage"]
        counts = halt_counts()
        risen = {
            stage: (allowed.get(stage, 0), n)
            for stage, n in counts.items()
            if n > allowed.get(stage, 0)
        }
        assert not risen, (
            f"halt-action rows rose (baseline, now): {risen}. A new gate that "
            f"can end a run needs an operator ruling named in its row's "
            f"created_by, and the baseline raised in the same PR so the "
            f"increase is in the diff."
        )

    def test_a_fall_is_reported_so_the_baseline_gets_lowered(self, capsys):
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        allowed = baseline["halt_rows_per_stage"]
        counts = halt_counts()
        fallen = {
            stage: (allowed.get(stage, 0), counts.get(stage, 0))
            for stage in allowed
            if counts.get(stage, 0) < allowed.get(stage, 0)
        }
        if fallen:
            print(f"halt rows fell (baseline, now): {fallen} -- lower the baseline")

    def test_model_output_gates_that_halt_are_counted_for_the_policy(self):
        """Not a gate on the number -- #2723 brings it to zero -- but the
        number must be visible: it is the maze.

        Exact, not `<=` (#2759): the operator's rule for #2723 is that a row
        leaving the model-output category lowers the baseline IN THE SAME PR.
        Under `<=` a reclassification that forgot the baseline still passed,
        and the ratchet then read as the old number for as long as nobody
        looked -- a stale denominator that reads as evidence, which is the
        #2780 finding in a different column.
        """
        halting = [
            g.key for g in GATE_REGISTRY
            if g.action == ACTION_HALT and g.judges == JUDGES_MODEL_OUTPUT
        ]
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        assert len(halting) == baseline["model_output_halt_rows"], (
            f"model-output gates that halt: {len(halting)}, baseline says "
            f"{baseline['model_output_halt_rows']}. Rows: {sorted(halting)}. "
            f"Rerun tools/audit_halt_sites.py --write-baseline in this PR."
        )


# ---------------------------------------------------------------------------
# The #2723 routing-policy rulings (operator, 2026-09-04)
# ---------------------------------------------------------------------------


class TestRulingOneRetryBudgets:
    """Question 1, answered yes: a retry budget's exhaustion is a `budget`
    gate, not a `model_output` gate.

    Each of these six already revises what it judges and already stops when a
    cap is spent. What ended the run is the cap, so that is whose gate it is.
    The rows are named here rather than counted, because the count alone
    cannot tell a reclassification the operator ruled on from one that drifted.
    """

    #: gate key -> the issue carrying that row's statement of the question.
    RECLASSIFIED = {
        "lld.mechanical_validation": "#2759",
        "impl.file_generation_failed": "#2760",
        "spec.edit_script_rejected": "#2762",
        "lld.edit_script_rejected": "#2763",
        "lld.test_plan_validation": "#2764",
        "lld.best_of_n_unusable": "#2774",
    }

    def test_every_ruled_row_now_judges_a_budget(self):
        keys = registry_by_key()
        for key in self.RECLASSIFIED:
            gate = keys.get(key)
            assert gate is not None, f"{key} is not in the registry"
            assert gate.judges == JUDGES_BUDGET, (
                f"{key}: operator ruled budget on #2723, registry says "
                f"{gate.judges}"
            )

    def test_the_ruling_is_named_in_the_row(self):
        """A reclassification with no ruling named is indistinguishable from
        drift, which is how 189 places to say no accumulated unremarked."""
        keys = registry_by_key()
        for key, issue in self.RECLASSIFIED.items():
            gate = keys[key]
            assert gate.justified_by == "#2723", (
                f"{key}: justified_by is {gate.justified_by!r}, expected "
                f"'#2723' -- the ruling that reclassified it"
            )
            assert issue in gate.notes, (
                f"{key}: notes do not name {issue}, the issue that stated the "
                f"question this row's ruling answered"
            )

    def test_behaviour_did_not_change(self):
        """The ruling reclassified; it did not soften. Every one still halts,
        and still on the same message -- so no run's outcome moves."""
        keys = registry_by_key()
        for key in self.RECLASSIFIED:
            assert keys[key].action == ACTION_HALT, (
                f"{key}: the ruling changed judges, not action"
            )
            assert keys[key].emits, f"{key}: lost its message head"


class TestRulingTwoOutputNobodyCanRevise:
    """Question 2, answered yes: a gate that judges output nobody in the loop
    can revise is not a `model_output` gate.

    These three judge the REVIEWER's output, and the reviewer is not the
    drafter -- sending the drafter back to fix a verdict it did not write asks
    it to repair someone else's mistake.

    Halting stays legal for all three. The ruling says what the halt is ABOUT,
    which is what `judges` records; it does not say the run should continue.

    **A fourth row was ruled on and is no longer here.** #2771 reclassified
    `pr.commit_message_guard` on the reasoning that by the time a commit
    message is validated the graph is past every loop. #2787 measured the
    stronger fact: no graph validates one at all. All four graphs were built
    and their nodes enumerated, none declares a commit-message node, and the
    code that opens the PR computes `Closes #N` itself. The row's two sites
    lived in a function no run enters, and it was retired with that function.
    The ruling is not overturned -- it was answered about code that turned
    out never to run.
    """

    #: gate key -> (new judges, the issue that stated the question).
    RECLASSIFIED = {
        "impl.reviewer_verdict_unreadable": (JUDGES_INFRASTRUCTURE, "#2768"),
        "spec.reviewer_verdict_unreadable": (JUDGES_INFRASTRUCTURE, "#2769"),
        "spec.review_blocked": (JUDGES_ISSUE_BODY, "#2770"),
    }

    #: Ruled on by #2771, retired by #2787. Asserted ABSENT, so a future PR
    #: that resurrects the row has to come back here and answer the wiring
    #: question in the same change.
    RETIRED = {"pr.commit_message_guard": "#2787"}

    def test_the_retired_row_stays_retired(self):
        keys = registry_by_key()
        for key, issue in self.RETIRED.items():
            assert key not in keys, (
                f"{key} was retired by {issue} because no graph runs the "
                f"function its sites lived in. If it is back, wire it and "
                f"say so here."
            )

    def test_every_ruled_row_carries_its_new_category(self):
        keys = registry_by_key()
        for key, (judges, _) in self.RECLASSIFIED.items():
            gate = keys.get(key)
            assert gate is not None, f"{key} is not in the registry"
            assert gate.judges == judges, (
                f"{key}: operator ruled {judges} on #2723, registry says "
                f"{gate.judges}"
            )

    def test_the_ruling_is_named_in_the_row(self):
        keys = registry_by_key()
        for key, (_, issue) in self.RECLASSIFIED.items():
            gate = keys[key]
            assert gate.justified_by == "#2723", (
                f"{key}: justified_by is {gate.justified_by!r}, expected "
                f"'#2723' -- the ruling that reclassified it"
            )
            assert issue in gate.notes, (
                f"{key}: notes do not name {issue}, the issue that stated the "
                f"question this row's ruling answered"
            )

    def test_halting_stays_legal(self):
        keys = registry_by_key()
        for key in self.RECLASSIFIED:
            assert keys[key].action == ACTION_HALT, (
                f"{key}: the ruling permitted the halt, it did not remove it"
            )

    def test_blocked_and_its_escalation_agree(self):
        """#2770's finding, pinned. `spec.review_blocked` shows 0 kills and
        ended five runs: the report files them under the escalation marker
        carried INSIDE a BLOCKED verdict. The two keys are one code path, so
        they must not sit in different categories -- a reader comparing the
        counts would otherwise be told the same five deaths were about two
        different things."""
        keys = registry_by_key()
        assert (
            keys["spec.review_blocked"].judges
            == keys["spec.requirements_conflict"].judges
            == JUDGES_ISSUE_BODY
        )


class TestRulingThreeImpossibleStates:
    """Question 3, answered yes: a guard against an impossible state is an
    `infrastructure` check, not a gate on the drafter.

    Each of these asserts an invariant the pipeline is supposed to maintain,
    rather than judging content the drafter chose to produce. Two catch an
    empty draft at a point where the draft has already been validated and
    approved, so emptiness means something upstream lied; the third catches
    pytest collecting nothing, which is a broken suite and not a failing one.

    The reason this is a reclassification and not a convenience: an empty
    draft has no span for a revision to cite. The policy's permitted action
    for a model-output gate is to ask for a revision citing what it objects
    to, and there is nothing to cite. Asking the drafter to revise nothing is
    regeneration, which #2569 removed from the revision path deliberately.
    """

    RECLASSIFIED = {
        "impl.green.collection_broken": "#2765",
        "spec.finalize.draft_guard": "#2772",
        "spec.review.empty_draft": "#2773",
    }

    def test_every_ruled_row_is_infrastructure(self):
        keys = registry_by_key()
        for key in self.RECLASSIFIED:
            gate = keys.get(key)
            assert gate is not None, f"{key} is not in the registry"
            assert gate.judges == JUDGES_INFRASTRUCTURE, (
                f"{key}: operator ruled infrastructure on #2723, registry "
                f"says {gate.judges}"
            )

    def test_the_ruling_is_named_in_the_row(self):
        keys = registry_by_key()
        for key, issue in self.RECLASSIFIED.items():
            gate = keys[key]
            assert gate.justified_by == "#2723", (
                f"{key}: justified_by is {gate.justified_by!r}, expected "
                f"'#2723' -- the ruling that reclassified it"
            )
            assert issue in gate.notes, (
                f"{key}: notes do not name {issue}, the issue that stated the "
                f"question this row's ruling answered"
            )

    def test_halting_stays_legal(self):
        keys = registry_by_key()
        for key in self.RECLASSIFIED:
            assert keys[key].action == ACTION_HALT, (
                f"{key}: the ruling permitted the halt, it did not remove it"
            )

    def test_both_finalize_guards_agree(self):
        """`spec.finalize.draft_guard` and `spec.finalize.precondition` are
        two last-line assertions in the same node, both firing when something
        upstream has already gone wrong. `precondition` was infrastructure
        before this ruling and `draft_guard` was not, which was the split the
        ruling closed."""
        keys = registry_by_key()
        assert (
            keys["spec.finalize.draft_guard"].judges
            == keys["spec.finalize.precondition"].judges
            == JUDGES_INFRASTRUCTURE
        )


class TestEveryRegisteredGateLivesInANodeSomeGraphRuns:
    """#2753: a row whose code no graph can reach is not protection.

    Two rows -- `impl.test_file_validation` and `impl.test_execution_failed`
    -- named sites only in `testing/nodes/run_tests.py`, a node added by
    52992973 (#381) and never declared by any graph. They were counted in the
    ratchet's halt-site total and in the per-stage halt-row counts for six
    months, and the registry's `action` column, documented as "what the gate
    DOES today", described code that never ran.

    This is the general form, so the next unwired node is caught when it is
    added rather than six months later.
    """

    #: Every module reachable by import from a compiled graph, as the import
    #: system resolves it rather than as a regex guesses.
    #:
    #: The graphs are BUILT, not merely imported, and two wrong versions of
    #: this check are the reason.
    #:
    #: Reading `from ...nodes import X` out of each graph.py with a regex
    #: reported `nodes/implementation/orchestrator` and
    #: `validate_commit_message` as unreachable; both are reached, one through
    #: a subpackage and one indirectly. Importing the graph modules instead
    #: then reported `compile_manifest`, which `implementation_spec/graph.py`
    #: imports INSIDE the builder function -- a lazy import that only happens
    #: when the graph is built. Each version was a check crying wolf on live
    #: code on its first run.
    #:
    #: Building executes those deferred imports, which is what makes this the
    #: real reachability set rather than an approximation of it.
    #:
    #: In a SUBPROCESS, because `sys.modules` is shared interpreter state and
    #: the third wrong version of this check read it in-process: under the
    #: suite's random ordering it reported `review_test_plan` unreachable,
    #: which is node N1. Whatever else the session had imported or discarded
    #: decided the answer, so the check was a coin-flip on a live node. A
    #: fresh interpreter sees exactly what the graphs pull in and nothing else.
    def _reachable_modules(self) -> set[str]:
        import subprocess

        probe = (
            "import sys, json;"
            "sys.path.insert(0, r'" + str(REPO_ROOT) + "');"
            "from assemblyzero.workflows.testing.graph import"
            " build_testing_workflow as b;"
            "from assemblyzero.workflows.implementation_spec.graph import"
            " create_implementation_spec_graph as c;"
            "from assemblyzero.workflows.requirements.graph import"
            " create_requirements_graph as r;"
            "[f() for f in (b, c, r)];"
            "print(json.dumps(sorted({"
            "n.rsplit('.', 1)[-1] for n in list(sys.modules)"
            " if n.startswith('assemblyzero.')})))"
        )
        done = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=300,
        )
        assert done.returncode == 0, (
            f"the reachability probe could not build the graphs:\n{done.stderr}"
        )
        return set(json.loads(done.stdout.strip().splitlines()[-1]))

    def test_no_registry_row_names_a_site_in_an_unreachable_node(self):
        reachable = self._reachable_modules()
        orphans: dict[str, set[str]] = {}
        for gate in GATE_REGISTRY:
            for site in gate.sites:
                path = site.split("::", 1)[0]
                if "/nodes/" not in path or not path.endswith(".py"):
                    continue
                module = Path(path).stem
                if module not in reachable:
                    orphans.setdefault(module, set()).add(gate.key)
        assert not orphans, (
            "registry rows name halt sites in node modules no graph imports: "
            + "; ".join(
                f"{module} ({', '.join(sorted(keys))})"
                for module, keys in sorted(orphans.items())
            )
            + ". Wire the node, or retire it and its rows (#2753)."
        )

    def test_the_retired_node_is_gone(self):
        """Named explicitly as well as caught generally: the general check
        passes trivially if someone re-adds the file without a registry row,
        and the file itself is what should not come back unwired."""
        assert not (
            REPO_ROOT / "assemblyzero" / "workflows" / "testing" / "nodes"
            / "run_tests.py"
        ).exists(), (
            "run_tests.py is back. If it was wired into the testing graph, "
            "delete this assertion and register its halt sites; if not, it is "
            "the same dead node #2753 retired."
        )
