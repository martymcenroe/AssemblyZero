"""The edit script must actually be REACHED, not merely be correct (#2644).

#2407 gave the implementation stage an edit-script fix path: a revision emits
SEARCH/REPLACE blocks instead of regenerating the file, because a regeneration
re-derives everything including the parts that already pass. It landed
2026-08-15.

Two weeks later, `run-issue331-092220` still died the way #2407 was built to
prevent:

    [09:23:06] [N4] Implementing code file-by-file (iteration 0)...   -> 67s, fine
    [09:24:13] [N5] Results: 12 passed, 3 failed | Coverage: 92.0%
    [09:24:31] [N4] Implementing code file-by-file (iteration 1)...
               Base already ships src/boostgauge/skins/stingray.py;
               implementing as Modify so the earlier phase's work is extended
               Calling Claude... (15s) ... (1200s)
               ERROR=claude -p timed out after 1200s [ceiling_timeout]

`[EDIT-SCRIPT]` appears nowhere in that log, and the fix path prints
"Calling Claude (edit script)" rather than the plain "Calling Claude" the log
shows. The machinery never engaged.

**Why: `existing_content` is read before the change type is resolved.** The
read is guarded by `change_type.lower() == "modify"`, and at that point
change_type is still whatever the LLD said. For a file the LLD calls "Add"
that the base already ships -- the mid-arc case, and the case every Phase 2
run is in -- it is "Add" at the read and "Modify" sixty lines later, so
`existing_content` stays "" and `should_use_edit_script` declines on the
"you cannot SEARCH an empty file" condition.

`test_implementation_edit_script_fix.py::test_an_add_that_resolved_to_an_
existing_file_still_qualifies` already asserts this case returns True. It
passes, and always did: it hands `should_use_edit_script` the file content
directly. The unit was right; the caller never gave it the inputs. These tests
cover the wiring the unit test cannot see.
"""

from __future__ import annotations

from pathlib import Path

import importlib

import pytest

orch = importlib.import_module(
    "assemblyzero.workflows.testing.nodes.implementation.orchestrator"
)
esf = importlib.import_module(
    "assemblyzero.workflows.testing.nodes.implementation.edit_script_fix"
)

#: Big enough to clear MIN_BYTES_FOR_EDIT_SCRIPT, and shaped like the file the
#: run died on: an earlier phase's work that this phase extends.
BASE_FILE = '''"""Stingray skin."""


def draw_face(surface, radius):
    """Fill the dial face."""
    surface.fill((10, 10, 12))
    return surface


def draw_ticks(surface, radius, count=10):
    """Draw the major tick marks."""
    for index in range(count):
        surface.tick(index, radius)
    return surface


def draw_needle(surface, angle):
    """Draw the needle at the given angle."""
    surface.needle(angle)
    return surface
'''

FAILURES = (
    "FAILED tests/unit/test_stingray.py::test_bezel - AssertionError: "
    "expected a bezel ring\n"
)


@pytest.fixture
def repo(tmp_path):
    target = tmp_path / "src" / "boostgauge" / "skins"
    target.mkdir(parents=True)
    (target / "stingray.py").write_text(BASE_FILE, encoding="utf-8")
    return tmp_path


class TestTheGateSeesTheFileOnDisk:
    """The unit's three conditions, given the inputs the caller really has."""

    def test_the_base_file_clears_the_size_threshold(self):
        assert len(BASE_FILE) >= esf.MIN_BYTES_FOR_EDIT_SCRIPT

    def test_with_the_content_the_gate_opens(self):
        assert esf.should_use_edit_script("Modify", BASE_FILE, FAILURES) is True

    def test_with_an_empty_string_it_declines(self):
        """The observed state: change type resolved to Modify, content "".

        This is what the orchestrator handed it on run-issue331-092220, and
        why no edit script ran.
        """
        assert esf.should_use_edit_script("Modify", "", FAILURES) is False


class TestTheOrchestratorReadsAfterResolving:
    """The wiring, driven through the real loop.

    `implement_code` is exercised with the model call stubbed, so the
    assertion is about which path the loop CHOOSES, not about model output.
    """

    def _run(self, repo, monkeypatch, change_type: str, from_base: bool = True):
        seen: dict = {}

        def fake_should_use(ct, content, failures):
            seen["change_type"] = ct
            seen["content_len"] = len(content)
            seen["failures"] = failures
            return esf.should_use_edit_script(ct, content, failures)

        # `resolve_change_type` asks git whether the base ships this file.
        # The tmp tree is not a repo, so the query is the thing to stand in
        # for -- stubbing `resolve_change_type` itself would stub the subject.
        monkeypatch.setattr(orch, "came_from_base", lambda *a, **k: from_base)
        monkeypatch.setattr(orch, "should_use_edit_script", fake_should_use)
        monkeypatch.setattr(
            orch, "try_edit_script_fix",
            lambda **kw: esf.EditScriptOutcome(BASE_FILE, blocks=1, preserved=0.9),
        )
        # Keep the full-file fallback from making a model call: this asserts
        # which path is chosen, not what a model returns.
        monkeypatch.setattr(
            orch, "generate_file_with_retry",
            lambda **kw: (BASE_FILE, True),
        )

        state = {
            "issue_number": 331,
            "repo_root": str(repo),
            "worktree_path": str(repo),
            # #2699: REQUIRED, not decorative. `implement_code` resolves this
            # as `Path(state.get("audit_dir", ""))`, and `Path("")` is `.`,
            # whose `.exists()` is always true -- so omitting it does not mean
            # "no audit trail", it means "write the audit trail into whatever
            # directory pytest was started from". This test left four prompt
            # and response files in the AssemblyZero repo root the first time
            # it ran.
            "audit_dir": str(repo / "audit"),
            "lld_content": "# LLD\n\n## Files\n- src/boostgauge/skins/stingray.py\n",
            "spec_content": "# Spec\n",
            "files_to_modify": [
                {
                    "path": "src/boostgauge/skins/stingray.py",
                    "change_type": change_type,
                    "reason": "add the bezel ring",
                }
            ],
            "iteration_count": 1,
            "test_failure_summary": FAILURES,
            "green_phase_output": FAILURES,
            "test_files": [],
            "completed_files": [],
        }
        seen["state"] = state
        try:
            orch.implement_code(state)
        except Exception:  # noqa: BLE001 — the gate call is the subject
            pass
        return seen

    def test_an_add_the_base_already_ships_reaches_the_edit_script(
        self, repo, monkeypatch
    ):
        """The regression, in one assertion.

        The LLD says Add; the base ships the file; #2032 resolves it to
        Modify. The gate must see the file's real content, not "".
        """
        seen = self._run(repo, monkeypatch, "Add")

        assert seen, "should_use_edit_script was never called"
        assert seen["change_type"].lower() == "modify"
        assert seen["content_len"] == len(BASE_FILE), (
            "the gate was handed an empty file, so no edit script can run"
        )

    def test_a_plain_modify_is_unaffected(self, repo, monkeypatch):
        """The path that always worked keeps working."""
        seen = self._run(repo, monkeypatch, "Modify")

        assert seen["content_len"] == len(BASE_FILE)

    def test_the_failure_context_reaches_it_too(self, repo, monkeypatch):
        """The gate's other precondition, so a green result here is not an
        accident of one condition passing while another is empty."""
        seen = self._run(repo, monkeypatch, "Add")

        assert FAILURES.strip() in seen["failures"]

    def test_the_run_writes_nothing_outside_its_tmp_repo(
        self, repo, monkeypatch, tmp_path
    ):
        """#2699: this test drives the real loop, so it can litter.

        `implement_code` resolves `Path(state.get("audit_dir", ""))`, and
        `Path("")` is the current directory -- so a state dict missing
        `audit_dir` writes its prompt and response artifacts wherever pytest
        was started. That is the AssemblyZero repo root, and it happened: four
        files, untracked, indistinguishable from somebody's work in progress.

        Asserting on the process's own working directory is what catches a
        recurrence, because the failure is a file appearing somewhere nobody
        is looking.
        """
        cwd = Path.cwd()
        before = {p.name for p in cwd.iterdir()}

        self._run(repo, monkeypatch, "Add")

        new = {p.name for p in cwd.iterdir()} - before
        assert not new, f"the run wrote into the working directory: {sorted(new)}"

    def test_the_driver_points_the_audit_trail_at_the_tmp_repo(
        self, repo, monkeypatch
    ):
        """The containment itself, asserted directly.

        The guard above is a net, not a proof: with both the edit-script and
        the full-file paths stubbed, nothing writes an audit file at all, so
        it would stay green even if `audit_dir` went missing again. What
        actually prevents a recurrence is the field being SET to somewhere
        disposable, and that is what this asserts. Said plainly, because a
        test whose green light means nothing is worse than no test.
        """
        seen = self._run(repo, monkeypatch, "Add")
        audit_dir = seen["state"]["audit_dir"]

        assert audit_dir, "unset means Path('') means the working directory"
        assert str(repo) in audit_dir
