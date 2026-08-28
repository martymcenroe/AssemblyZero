"""Guard-vs-guard: the interaction matrix, as data (#2568).

Guard-vs-guard is the factory's emergent defect class, and nothing owned the
interaction matrix. The 2026-08-27 campaign was almost entirely PAIRWISE
failures between mechanisms that are each locally correct:

* the completeness check demanded the edit pinning refused (#2555);
* pinning's merge destroyed what the drafter and no verdict asked to remove
  (#2559);
* the cap halt blamed the drafter for what enforcement did (#2556, #2561);
* the leavings janitor swept what the loader reads (#2551).

Every one was found by a killed run. **None could have been found by any
single guard's own tests, because each guard passed its own tests.**

## The matrix is data so it can be linted

A matrix that lives only in prose goes stale the first time someone adds a
mechanism. Here the artifacts, their mechanisms and the cells between them
are Python, and `tests/unit/test_interaction_matrix.py` enforces three
things a document cannot:

1. **No undeclared mechanism.** A module that calls one of an artifact's
   signature symbols and is not declared for it fails the lint by name.
   This is the "new mechanism fails a checklist lint" the issue asks for.
2. **No unruled cell.** Every mechanism pair is either fixture-backed or
   marked non-interacting WITH A REASON. A blank cell is not allowed,
   because a blank cell is indistinguishable from an unconsidered one.
3. **No phantom.** Declared modules and named fixtures must exist, so the
   matrix cannot rot into a description of code that has moved.

## Cells assert invariants, not implementations

`test_completeness_pinning_deadlock.py` does not assert that pinning has a
particular branch; it asserts that a change one gate demands is never
refusable by another in the same round. Implementations change and the
invariant survives, which is what makes a cell worth writing down.

Registry class 3 (`docs/standards/0029-defect-class-registry.md`) is the
single-mechanism form of this; the matrix is the pairwise form.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Cell:
    """One mechanism pair, ruled.

    Exactly one of `fixture` or `non_interacting` must be set. A cell with
    neither is an unconsidered pair wearing the costume of a considered one.
    """

    invariant: str
    #: Repo-relative test file pinning this pair.
    fixture: str = ""
    #: Why this pair cannot interact. Required when there is no fixture.
    non_interacting: str = ""

    def ruled(self) -> bool:
        return bool(self.fixture) != bool(self.non_interacting)


@dataclass(frozen=True)
class Artifact:
    """A shared thing, and every mechanism that touches it."""

    slug: str
    title: str
    #: Function names whose CALL marks a module as touching this artifact.
    #: The lint scans for these; a symbol that is never called anywhere is a
    #: phantom and fails its own check.
    signatures: tuple[str, ...]
    #: mechanism name -> the repo-relative modules that implement it.
    mechanisms: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: (mechanism_a, mechanism_b) -> Cell. Order-insensitive by convention:
    #: the lint canonicalises to sorted order before looking a pair up.
    cells: dict[tuple[str, str], Cell] = field(default_factory=dict)

    def declared_modules(self) -> set[str]:
        return {mod for mods in self.mechanisms.values() for mod in mods}

    def pairs(self) -> list[tuple[str, str]]:
        names = sorted(self.mechanisms)
        return [
            (a, b)
            for index, a in enumerate(names)
            for b in names[index + 1:]
        ]


def key(a: str, b: str) -> tuple[str, str]:
    """Canonical, order-insensitive cell key."""
    return (a, b) if a <= b else (b, a)


DRAFT_TEXT = Artifact(
    slug="draft-text",
    title="The draft the drafter emits and every gate reads",
    signatures=(
        "enforce_pinning", "named_tokens", "named_line_ranges",
        "demands_additions",
    ),
    mechanisms={
        "pinning-enforcement": (
            "assemblyzero/workflows/implementation_spec/revision_pinning.py",
        ),
        "completeness-checks": (
            "assemblyzero/workflows/implementation_spec/nodes/"
            "validate_completeness.py",
        ),
        "message-addressability": (
            "assemblyzero/workflows/implementation_spec/"
            "message_addressability.py",
        ),
        "spec-generation": (
            "assemblyzero/workflows/implementation_spec/nodes/"
            "generate_spec.py",
        ),
    },
    cells={
        key("pinning-enforcement", "completeness-checks"): Cell(
            invariant=(
                "A change a completeness failure explicitly demands is never "
                "revertible by pinning in the same round."
            ),
            fixture="tests/unit/test_completeness_pinning_deadlock.py",
        ),
        key("pinning-enforcement", "message-addressability"): Cell(
            invariant=(
                "Enforcement can READ every complaint that demands an edit: "
                "the message addresses a draft line, or demands an addition "
                "and is exempt."
            ),
            fixture="tests/unit/test_completeness_message_addressability.py",
        ),
        key("pinning-enforcement", "spec-generation"): Cell(
            invariant=(
                "The merge never emits a document that lost or multiplied an "
                "unnamed test definition -- revision unenforced or previous "
                "entire, never the stitch."
            ),
            fixture="tests/unit/test_pinning_conservation.py",
        ),
        key("completeness-checks", "message-addressability"): Cell(
            invariant=(
                "Every check's real emitted message is classified, and a "
                "rewording that drops its address fails the suite."
            ),
            fixture="tests/unit/test_completeness_message_addressability.py",
        ),
        key("completeness-checks", "spec-generation"): Cell(
            invariant=(
                "A demanded addition lands: an expansion-replace passes "
                "unconditionally and a locked region introducing a new test "
                "is freed."
            ),
            fixture="tests/unit/test_generate_spec_pinning.py",
        ),
        key("message-addressability", "spec-generation"): Cell(
            invariant=(
                "Classification is a pure read of a message against a draft."
            ),
            non_interacting=(
                "message_addressability holds no draft state and is never "
                "called from the generation path -- it reads a message and a "
                "draft that generation has already produced. Neither can "
                "change what the other sees within a round."
            ),
        ),
    },
)


WORKING_TREE = Artifact(
    slug="working-tree-files",
    title="Untracked pipeline emissions on disk, and who may remove them",
    signatures=(
        "preserve_and_clear", "classify_dirt", "is_pipeline_input",
        "restore_artifact",
    ),
    mechanisms={
        "leavings-janitor": ("assemblyzero/speedrun/leavings.py",),
        "restore-machinery": ("assemblyzero/speedrun/restore.py",),
        "loaders": (
            "assemblyzero/workflows/testing/nodes/load_lld.py",
            "assemblyzero/workflows/implementation_spec/nodes/load_lld.py",
        ),
        # Found by the lint, not by reading: these are the SWEEP SITES, and
        # they are where #2551 actually happened. A matrix built only from
        # the package would have missed the mechanism that caused the kill.
        "launch-sweep": (
            "tools/speedrun_roll.py",
            "tools/speedrun_new_attempt.py",
        ),
    },
    cells={
        key("leavings-janitor", "loaders"): Cell(
            invariant=(
                "A file a later stage reads on entry is never removable by "
                "the sweep -- and the exemption is scoped to the ROLLING "
                "issue, because a blanket one re-creates #2144."
            ),
            fixture="tests/unit/test_leavings_janitor.py",
        ),
        key("leavings-janitor", "restore-machinery"): Cell(
            invariant=(
                "Preserve-then-clear is structural: whatever the sweep "
                "clears is recoverable from the refs the restorer searches."
            ),
            fixture="tests/unit/test_restore_from_graveyard.py",
        ),
        key("loaders", "restore-machinery"): Cell(
            invariant=(
                "A working copy is a cache: the loader rebuilds a missing "
                "input from refs before concluding absence."
            ),
            fixture="tests/unit/test_restore_best_on_failure.py",
        ),
        key("launch-sweep", "leavings-janitor"): Cell(
            invariant=(
                "The exemption is applied at BOTH sweep sites, and it is "
                "issue-scoped at each -- the janitor keeps clearing other "
                "issues' droppings."
            ),
            fixture="tests/unit/test_leavings_janitor.py",
        ),
        key("launch-sweep", "loaders"): Cell(
            invariant=(
                "A launch never clears the input the loader is about to "
                "read on entry. This is #2551's kill, replayed end to end "
                "against a real repo."
            ),
            fixture="tests/unit/test_mock_roll.py",
        ),
        key("launch-sweep", "restore-machinery"): Cell(
            invariant=(
                "Whatever a launch sweeps is recoverable: preserve-then-"
                "clear is structural, and the ref is pushed before the "
                "file is removed."
            ),
            fixture="tests/unit/test_restore_from_graveyard.py",
        ),
    },
)


HALT_RESUME = Artifact(
    slug="halt-resume-state",
    title="What a halt records and a resume reads",
    signatures=(
        "build_resume_contract", "check_and_consume", "build_halt_evidence",
        "write_halt_evidence", "save_state_snapshot",
    ),
    mechanisms={
        "resume-contract": ("assemblyzero/core/resume_contract.py",),
        "halt-evidence": ("assemblyzero/core/halt_evidence.py",),
        "halt-node": ("assemblyzero/core/halt_node.py",),
        # Also found by the lint: the runners are where a resume actually
        # verifies, so they are a participant in this artifact, not callers
        # of one.
        "workflow-runners": (
            "tools/run_implement_from_lld.py",
            "tools/run_implementation_spec_workflow.py",
        ),
    },
    cells={
        key("resume-contract", "halt-node"): Cell(
            invariant=(
                "Every halt writes a contract, and verification CONSUMES it "
                "-- a completed lifecycle leaves none behind."
            ),
            fixture="tests/unit/test_resume_after_ceiling_halt.py",
        ),
        key("halt-evidence", "halt-node"): Cell(
            invariant=(
                "Every halt emits its bundle, and a bundle that cannot be "
                "written never masks the halt it describes."
            ),
            fixture="tests/unit/test_halt_evidence.py",
        ),
        key("halt-evidence", "resume-contract"): Cell(
            invariant=(
                "Both are written at the same halt from the same state, and "
                "neither's failure suppresses the other."
            ),
            non_interacting=(
                "Both are write-only at halt and read by different readers "
                "-- the contract by the next launch, the bundle by a human "
                "or a report. Neither reads the other's output, and the halt "
                "node wraps each in its own fail-open so one cannot suppress "
                "the other. Their shared risk is the janitor, which is the "
                "working-tree artifact's concern, not this pair's."
            ),
        ),
        key("workflow-runners", "resume-contract"): Cell(
            invariant=(
                "The runner verifies the contract FIRST and refuses by name "
                "on any mismatch, before a single token is spent; "
                "--accept-changed-inputs is the loud, logged override."
            ),
            fixture="tests/unit/test_resume_after_ceiling_halt.py",
        ),
        key("workflow-runners", "halt-node"): Cell(
            invariant=(
                "A resume seeds from the snapshot the halt wrote, and "
                "inherits its counters rather than rediscovering them."
            ),
            fixture="tests/unit/test_resume_after_failure.py",
        ),
        key("workflow-runners", "halt-evidence"): Cell(
            invariant=(
                "A resume's behaviour never depends on the evidence bundle."
            ),
            non_interacting=(
                "The bundle is forensic output addressed to a human or a "
                "report; no runner reads it, and none should -- a resume "
                "that consulted the bundle would be reading a summary when "
                "the contract carries the authoritative hashes. Deliberate "
                "asymmetry, not an oversight."
            ),
        ),
    },
)


ARTIFACTS: dict[str, Artifact] = {
    artifact.slug: artifact
    for artifact in (DRAFT_TEXT, WORKING_TREE, HALT_RESUME)
}
