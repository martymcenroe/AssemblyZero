"""A gate that judges model output may advise; the budget ends the run (#2723).

Operator ruling 2026-09-02. The evidence: of boostgauge's 135 banner-bearing
kills, 59 were a gate refusing the drafter's own output, and 19 of those were
the stagnation guards. One of the 19 is `run-issue4-172600` -- the furthest any
run has reached, green phase with three passing at 72% coverage -- killed by the
coverage guard with four iterations unspent.

This file pins the half of the policy that landed: the five stagnation rows are
advisory, they still SEE what they saw, and nothing on the way to them ends a
run that a budget would not have ended anyway. The other fourteen model-output
halt rows are not yet moved; `test_the_ratchet_records_what_is_left` is what
keeps that number honest and falling.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import audit_halt_sites as cli  # noqa: E402

from assemblyzero.core.gate_registry import (  # noqa: E402
    ACTION_ADVISE,
    ACTION_HALT,
    GATE_REGISTRY,
    JUDGES_BUDGET,
    JUDGES_INFRASTRUCTURE,
    JUDGES_MODEL_OUTPUT,
    advised,
    gate_key_of,
    halt_counts,
    registry_by_key,
    scan_halt_sites,
)

BASELINE = ROOT / "tests" / "fixtures" / "gate_registry_baseline.json"

STAGNATION_KEYS = (
    "impl.stagnation.coverage",
    "impl.stagnation.test_count",
    "impl.stagnation.test_identity",
    "impl.stagnation.full_suite",
    "impl.stagnation.e2e",
)


class TestTheStagnationGuardsNoLongerEndARun:
    @pytest.mark.parametrize("key", STAGNATION_KEYS)
    def test_the_row_advises(self, key):
        assert registry_by_key()[key].action == ACTION_ADVISE

    @pytest.mark.parametrize("key", STAGNATION_KEYS)
    def test_the_row_names_no_halt_site(self, key):
        """An advisory row with a halt site would mean the walker found code
        that still ends a run under a key that says it does not."""
        assert registry_by_key()[key].sites == ()
        assert registry_by_key()[key].decided_in, (
            "a row with no sites must say where it lives, or it is unfindable"
        )

    @pytest.mark.parametrize("key", STAGNATION_KEYS)
    def test_the_row_still_judges_model_output(self, key):
        """The classification is a fact about the gate and does not change
        because its consequence did. Rewriting `judges` to make the
        model-output count fall would be cooking the number the policy is
        measured by."""
        assert registry_by_key()[key].judges == JUDGES_MODEL_OUTPUT


class TestAdvised:
    def test_it_carries_the_gate_key_like_a_halt_does(self):
        message = advised("impl.stagnation.coverage", "Coverage stagnant: 72 -> 70.")
        assert gate_key_of(message) == "impl.stagnation.coverage"

    def test_it_says_the_run_continues(self):
        """The identical sentence was terminal for as long as these guards have
        existed, and a reader will remember it that way."""
        message = advised("impl.stagnation.e2e", "E2E stagnant: 2 -> 2 passed.")
        assert "Continuing; the budget decides." in message

    def test_it_refuses_a_key_whose_row_still_halts(self):
        """An advisory printed by a gate that then ends the run anyway is the
        worst of both: a log that says the run continued and a run that did
        not."""
        with pytest.raises(ValueError, match="halt row"):
            advised("impl.green.iteration_cap", "Green phase failed after 5.")

    def test_it_refuses_an_unregistered_key(self):
        with pytest.raises(KeyError):
            advised("impl.not.a.gate", "x")


class TestOnlyABudgetOrTheEnvironmentEndsTheGreenLoop:
    """The policy's real claim, checked against the registry rather than
    asserted: everything that can still end the implement-iterate loop is a
    spending limit or a broken environment."""

    LOOP_ENDERS = (
        "impl.green.iteration_cap",
        "impl.circuit_breaker",
        "impl.e2e_cap",
        "impl.e2e_safety_limit",
    )

    @pytest.mark.parametrize("key", LOOP_ENDERS)
    def test_each_one_is_a_budget_or_the_environment(self, key):
        row = registry_by_key()[key]
        assert row.action == ACTION_HALT
        assert row.judges in (JUDGES_BUDGET, JUDGES_INFRASTRUCTURE), (
            f"{key} ends the loop while judging {row.judges}"
        )


class TestTheRatchet:
    def test_the_baseline_matches_the_registry(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        assert halt_counts() == baseline["halt_rows_per_stage"]

    def test_the_baseline_states_a_denominator(self):
        """`measured_against` exists so a reader can see the denominator
        without re-running anything (#2780). Whether it is still TRUE is
        `tools/audit_halt_sites.py --check --strict`'s question, not this
        gate's (#3527): asserting it here by re-walking failed every PR that
        added a walked file, halt site or not, and two PRs adding files
        collided on the same `files_scanned` line. The enforced counts below
        are what protect anything; this block is context for a reader, and
        the gate only insists that it is written.
        """
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        assert set(baseline["measured_against"]) == {
            "files_scanned", "halt_sites", "gates",
        }

    def test_the_ratchet_records_what_is_left(self):
        """2 model-output rows still halt. The number is pinned so it can only
        fall: #2723 took it from 24 to 19 by retiring the five stagnation
        guards, #2736 took it to 18 by making `impl.path_enforcement` advisory
        on the operator's ruling of 2026-09-04, and that day's three routing
        rulings take it down in three steps -- 12 for the six retry-budget
        rows whose halt belongs to the cap that decided it (#2759, #2760,
        #2762, #2763, #2764, #2774), 8 for the four rows judging output nobody
        in the loop can revise (#2768, #2769, #2770, #2771), and 5 for the
        three guards against an impossible state (#2765, #2772, #2773).

        #2753 then took it to 4 by retiring `impl.test_file_validation` with
        the unreachable node its only site lived in. That one is a fall the
        ratchet should read carefully: the count dropped without any gate
        softening, because the row had never been able to fire at all.

        #2775 then took it to 3, and that one is worth reading carefully too.
        `impl.test_plan_revision_incomplete` judged model output only because
        it fired on the FIRST short revision. It could not, in fact, fire at
        all: N1 clears `error_message` one node later (#1490), so the reason
        it recorded never reached a router, and the run spent its whole
        revision allowance before ending at `end` with no bundle. With the
        edge out of N1.5 made conditional and the reason recorded only at the
        cap, what is left is the allowance running out -- a budget, under
        ruling 1 of #2723.

        #2766 then took it to 2 by making `impl.red.import_errors` advisory,
        on the same reading as #2736: "unexpected" there means "not in the
        LLD's Section 2.1 file plan", and the plan is a plan rather than a
        contract. Its halt was unintended in any case -- the return named a
        forward route beside the reason, and the reason won.

        #2796 then took it to 1 by retiring `impl.red_phase_failed`. Read
        that fall carefully too: no gate softened. Its one remaining site --
        the non-pytest red phase's unexpected-pass return -- still halts, for
        the same reason, and now carries the DETERMINISTIC_FAILURE token so
        the orchestrator stops retrying a result an unchanged worktree
        reproduces. What changed is which row owns it. It moved to
        `impl.red.preexisting_implementation`, whose judgement is the state
        of the worktree the stage was handed, and the row left holding
        nothing was retired rather than kept as a name for no code.

        One remains: the green half of `impl.deterministic_failure`, which
        has never fired in 180 runs and has no path to it today. It cannot
        be moved against evidence, because there is none.

        The literal is deliberate, and is a second pin on the same claim. The
        baseline file is regenerated by a tool; this number is not, so a PR
        that moves the count has to say so here, in prose, in the diff."""
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        remaining = [
            gate for gate in GATE_REGISTRY
            if gate.action == ACTION_HALT and gate.judges == JUDGES_MODEL_OUTPUT
        ]
        assert len(remaining) == baseline["model_output_halt_rows"] == 1

    def test_no_stagnation_row_is_among_them(self):
        remaining = {
            gate.key for gate in GATE_REGISTRY
            if gate.action == ACTION_HALT and gate.judges == JUDGES_MODEL_OUTPUT
        }
        assert remaining.isdisjoint(STAGNATION_KEYS)


class TestTheDenominatorLeftThePRGate:
    """#3527. The denominator test failed every PR that added a walked file,
    and two concurrent PRs collided on its `files_scanned` line. The PR gate
    now fails only on what it enforces; the counts are checked by `--strict`.
    Same shape as #3523's `TestTheDenominatorLeftThePRGate` for the fail-open
    baseline, against this tool and this fixture."""

    def _baselined_tree(self, tmp_path):
        """A tree the walker recognises -- `assemblyzero/workflows/` under a
        root -- holding one module with no halt site, and a baseline written
        against it."""
        src = tmp_path / "assemblyzero" / "workflows"
        src.mkdir(parents=True)
        (src / "mod.py").write_text(
            "def step(state):\n    return {'answer': 1}\n", encoding="utf-8"
        )
        baseline = tmp_path / "baseline.json"
        sites, coverage = scan_halt_sites(tmp_path)
        cli.write_baseline(sites, coverage, baseline)
        return src, baseline

    def test_adding_a_walked_file_passes_the_gate_without_touching_the_baseline(
        self, tmp_path
    ):
        src, baseline = self._baselined_tree(tmp_path)
        before = baseline.read_bytes()
        (src / "more.py").write_text(
            "def helper(n):\n    return n + 1\n", encoding="utf-8"
        )

        sites, coverage = scan_halt_sites(tmp_path)
        stated = json.loads(baseline.read_text(encoding="utf-8"))

        # The PR gate's assertions, exactly as TestTheRatchet makes them.
        assert halt_counts() == stated["halt_rows_per_stage"]
        assert cli.model_output_halt_rows() == stated["model_output_halt_rows"]
        assert set(stated["measured_against"]) == {"files_scanned", "halt_sites", "gates"}
        assert baseline.read_bytes() == before
        # ...while strict mode still sees the tree has moved, and only there.
        assert cli.denominator_drift(sites, coverage, baseline) == {
            "files_scanned": (1, 2),
        }

    def test_strict_is_clean_on_the_tree_it_was_measured_against(self, tmp_path):
        _, baseline = self._baselined_tree(tmp_path)
        sites, coverage = scan_halt_sites(tmp_path)
        assert cli.denominator_drift(sites, coverage, baseline) == {}

    def test_a_missing_denominator_is_drift_not_a_pass(self, tmp_path):
        _, baseline = self._baselined_tree(tmp_path)
        payload = json.loads(baseline.read_text(encoding="utf-8"))
        del payload["measured_against"]
        baseline.write_text(json.dumps(payload), encoding="utf-8")

        sites, coverage = scan_halt_sites(tmp_path)
        drift = cli.denominator_drift(sites, coverage, baseline)

        assert set(drift) == {"files_scanned", "halt_sites", "gates"}
        assert all(stated is None for stated, _ in drift.values())

    def test_strict_mode_exits_one_when_the_file_count_moved(
        self, tmp_path, monkeypatch, capsys
    ):
        """Acceptance criterion 2: strict mode on a tree whose file count
        differs from the baseline exits 1 and names the count. The baseline
        is a copy of the real one with `files_scanned` moved off the live
        value by one, so the drift is exactly one count whatever the tree
        holds today."""
        sites, coverage = scan_halt_sites(ROOT)
        payload = json.loads(BASELINE.read_text(encoding="utf-8"))
        payload["measured_against"] = dict(
            cli.measured(sites, coverage),
            files_scanned=coverage.files_scanned + 1,
        )
        moved = tmp_path / "baseline.json"
        moved.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(cli, "BASELINE_PATH", moved)

        rc = cli.main(["--check", "--strict", "--root", str(ROOT)])

        out = capsys.readouterr().out
        assert rc == 1
        assert (
            f"files_scanned: baseline {coverage.files_scanned + 1}, "
            f"tree {coverage.files_scanned}"
        ) in out
        assert "Regenerate with tools/audit_halt_sites.py --write-baseline." in out

    def test_check_without_strict_ignores_the_denominator(
        self, tmp_path, monkeypatch, capsys
    ):
        """Requirement 1 at the command line: the same moved baseline, and
        plain `--check` does not look at it."""
        sites, coverage = scan_halt_sites(ROOT)
        payload = json.loads(BASELINE.read_text(encoding="utf-8"))
        payload["measured_against"] = dict(
            cli.measured(sites, coverage),
            files_scanned=coverage.files_scanned + 1,
        )
        moved = tmp_path / "baseline.json"
        moved.write_text(json.dumps(payload), encoding="utf-8")
        monkeypatch.setattr(cli, "BASELINE_PATH", moved)

        rc = cli.main(["--check", "--root", str(ROOT)])

        assert rc == 0
        assert "measured_against" not in capsys.readouterr().out

    def test_strict_without_check_is_a_usage_error(self, capsys):
        """The message is asserted, not only the exit code: before #3527
        argparse rejected `--strict` as an unrecognised flag with the same
        code 2, so the code alone cannot tell the flag exists."""
        with pytest.raises(SystemExit) as exc:
            cli.main(["--strict"])
        assert exc.value.code == 2
        assert "--strict only applies with --check" in capsys.readouterr().err
