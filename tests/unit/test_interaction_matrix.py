"""The guard-vs-guard interaction matrix, linted (#2568).

The matrix is only worth writing once if a new mechanism cannot silently
join an artifact without appearing in it. That is what these tests are: the
"checklist lint" the issue asks for, plus the phantom checks that stop the
matrix rotting into a description of code that has moved.

Registry class 3 is the single-mechanism form of this; the matrix is the
pairwise form (`docs/standards/0029-defect-class-registry.md`).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from assemblyzero.core.interaction_matrix import ARTIFACTS, Cell, key

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Where a mechanism can live. `tools/` is included deliberately: several
#: janitor and report entry points are scripts, and a sweep that scanned
#: only the package would miss exactly the mechanisms that caused #2551.
SCAN_ROOTS = ("assemblyzero", "tools")

#: Modules that reference a signature symbol without being a mechanism:
#: the module that DEFINES it, and the test-facing corpus/replay code.
#: Each is listed with the reason it is not a participant.
SCAN_EXEMPT = {
    # Defines the vocabulary rather than participating in a round.
    "assemblyzero/speedrun/leavings.py": "defines is_pipeline_input",
    # Replays preserved artifacts; never runs inside a roll.
    "assemblyzero/speedrun/golden_disasters.py": "corpus replay, not a roll",
}


def _modules_calling(symbols: tuple[str, ...]) -> dict[str, set[str]]:
    """Repo-relative module -> the signature symbols it CALLS.

    A definition is not a call: `def enforce_pinning(` must not mark
    revision_pinning.py as a caller of itself, or every artifact's owner
    would be reported as an undeclared mechanism.
    """
    found: dict[str, set[str]] = {}
    for root in SCAN_ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            for symbol in symbols:
                defines = re.search(
                    rf"^\s*(?:async\s+)?def\s+{re.escape(symbol)}\s*\(",
                    text, re.MULTILINE,
                )
                calls = re.search(
                    rf"(?<!def )\b{re.escape(symbol)}\s*\(", text
                )
                if calls and not defines:
                    found.setdefault(rel, set()).add(symbol)
    return found


class TestTheLint:
    """A new mechanism touching a listed artifact fails until it appears."""

    @pytest.mark.parametrize("slug", sorted(ARTIFACTS))
    def test_no_undeclared_mechanism_touches_the_artifact(self, slug):
        artifact = ARTIFACTS[slug]
        callers = _modules_calling(artifact.signatures)
        declared = artifact.declared_modules()

        undeclared = {
            module: sorted(symbols)
            for module, symbols in callers.items()
            if module not in declared and module not in SCAN_EXEMPT
        }
        assert not undeclared, (
            f"module(s) touch the {slug!r} artifact but appear in no "
            f"mechanism: {undeclared}. Add each to a mechanism in "
            f"assemblyzero/core/interaction_matrix.py and rule its cells, "
            f"or add it to SCAN_EXEMPT with the reason it does not "
            f"participate in a round (#2568)."
        )

    @pytest.mark.parametrize("slug", sorted(ARTIFACTS))
    def test_every_declared_module_exists(self, slug):
        """A matrix naming code that has moved describes nothing."""
        missing = [
            module
            for module in sorted(ARTIFACTS[slug].declared_modules())
            if not (REPO_ROOT / module).is_file()
        ]
        assert not missing, f"{slug}: declared modules that do not exist: {missing}"

    def test_every_exemption_names_a_real_module(self):
        missing = [
            module for module in sorted(SCAN_EXEMPT)
            if not (REPO_ROOT / module).is_file()
        ]
        assert not missing, f"exemptions for modules that do not exist: {missing}"

    @pytest.mark.parametrize("slug", sorted(ARTIFACTS))
    def test_every_signature_is_called_somewhere(self, slug):
        """A signature nothing calls scans for nothing, so the lint for that
        artifact is weaker than it looks."""
        artifact = ARTIFACTS[slug]
        callers = _modules_calling(artifact.signatures)
        seen = {symbol for symbols in callers.values() for symbol in symbols}
        dead = sorted(set(artifact.signatures) - seen)
        assert not dead, (
            f"{slug}: signature symbol(s) {dead} are called nowhere, so they "
            f"contribute nothing to the scan. Remove them or fix the name."
        )


class TestEveryCellIsRuled:
    """No blank cells. A blank cell is indistinguishable from an
    unconsidered one, which is the state this matrix replaces."""

    @pytest.mark.parametrize("slug", sorted(ARTIFACTS))
    def test_every_mechanism_pair_has_a_cell(self, slug):
        artifact = ARTIFACTS[slug]
        missing = [
            pair for pair in artifact.pairs()
            if key(*pair) not in artifact.cells
        ]
        assert not missing, (
            f"{slug}: mechanism pair(s) with no cell: {missing}. Every pair "
            f"is either fixture-backed or marked non-interacting with a "
            f"reason."
        )

    @pytest.mark.parametrize("slug", sorted(ARTIFACTS))
    def test_no_cell_is_both_or_neither(self, slug):
        artifact = ARTIFACTS[slug]
        bad = [
            pair for pair, cell in artifact.cells.items() if not cell.ruled()
        ]
        assert not bad, (
            f"{slug}: cell(s) with both a fixture and a non-interacting "
            f"reason, or with neither: {bad}"
        )

    @pytest.mark.parametrize("slug", sorted(ARTIFACTS))
    def test_every_cell_states_an_invariant(self, slug):
        """Cells assert invariants, not implementations. An empty one is a
        pair somebody pointed at without saying what must hold."""
        thin = [
            pair for pair, cell in ARTIFACTS[slug].cells.items()
            if len(cell.invariant.strip()) < 20
        ]
        assert not thin, f"{slug}: cell(s) with no stated invariant: {thin}"

    @pytest.mark.parametrize("slug", sorted(ARTIFACTS))
    def test_every_named_fixture_exists(self, slug):
        """A cell citing a test file that does not exist is a green cell
        protecting nothing."""
        missing = sorted(
            {
                cell.fixture
                for cell in ARTIFACTS[slug].cells.values()
                if cell.fixture and not (REPO_ROOT / cell.fixture).is_file()
            }
        )
        assert not missing, f"{slug}: cells naming absent fixtures: {missing}"

    @pytest.mark.parametrize("slug", sorted(ARTIFACTS))
    def test_no_cell_references_an_unknown_mechanism(self, slug):
        artifact = ARTIFACTS[slug]
        known = set(artifact.mechanisms)
        unknown = sorted(
            {
                name
                for pair in artifact.cells
                for name in pair
                if name not in known
            }
        )
        assert not unknown, (
            f"{slug}: cell(s) reference mechanism(s) that do not exist: "
            f"{unknown}"
        )


class TestTheMatrixIsSubstantive:
    def test_the_campaigns_four_pairwise_failures_are_all_covered(self):
        """The four kills that motivated this issue, each with a cell."""
        draft = ARTIFACTS["draft-text"]
        tree = ARTIFACTS["working-tree-files"]
        # #2555: completeness demanded what pinning refused.
        assert draft.cells[
            key("pinning-enforcement", "completeness-checks")
        ].fixture
        # #2559: the merge destroyed what no verdict named.
        assert draft.cells[
            key("pinning-enforcement", "spec-generation")
        ].fixture
        # #2551: the janitor swept what the loader reads.
        assert tree.cells[key("leavings-janitor", "loaders")].fixture
        # #2571: the loader rebuilds from what preservation kept.
        assert tree.cells[key("loaders", "restore-machinery")].fixture

    def test_most_cells_are_fixture_backed_not_reasoned_away(self):
        """A matrix of non-interacting reasons is a matrix that gave up.
        This is a floor, not a target."""
        cells = [
            cell
            for artifact in ARTIFACTS.values()
            for cell in artifact.cells.values()
        ]
        backed = [cell for cell in cells if cell.fixture]
        assert len(backed) * 2 >= len(cells), (
            f"only {len(backed)} of {len(cells)} cells carry a fixture; the "
            f"rest are reasoned non-interacting, which is how a matrix "
            f"becomes decorative"
        )

    def test_the_standard_documents_every_artifact(self):
        """The written matrix and the data must not drift apart."""
        doc = (
            REPO_ROOT / "docs" / "standards"
            / "0030-guard-interaction-matrix.md"
        ).read_text(encoding="utf-8", errors="replace")
        for slug, artifact in ARTIFACTS.items():
            assert slug in doc, f"artifact {slug} is absent from the standard"
            for mechanism in artifact.mechanisms:
                assert mechanism in doc, (
                    f"mechanism {mechanism!r} of {slug} is absent from the "
                    f"standard"
                )


def test_cell_ruled_rejects_both_and_neither():
    assert Cell("inv", fixture="a.py").ruled() is True
    assert Cell("inv", non_interacting="because").ruled() is True
    assert Cell("inv").ruled() is False
    assert Cell("inv", fixture="a.py", non_interacting="because").ruled() is False


def test_key_is_order_insensitive():
    assert key("b", "a") == key("a", "b") == ("a", "b")
