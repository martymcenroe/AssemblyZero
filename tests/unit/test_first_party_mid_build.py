"""A mid-build repo must not be blind to its own names (#2412).

`_first_party_tops` recognised a package only by `__init__.py`. Measured on
boostgauge, 2026-08-15:

    src/boostgauge/            exists
    src/boostgauge/__init__.py MISSING
    _first_party_tops(repo) -> set()

So for the campaign's own target repo, nothing was first-party -- and
`boostgauge.gauge.nonexistent()` cleared instead of flagging, which is the
#1527 founding true positive. Greenfield repos are the population this campaign
runs against, so "no `__init__.py` yet" is the normal early state.

The acceptance is two-sided, and the second side is the reason this was not
folded into #2411: a first-party top gets the STRICTER
exists-or-created-by-this-spec rule (#1901/#842), and over-strictness is what
killed five rolls of the receiver-resolution class. Widening must not sweep in
directories that are not packages.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

vc = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
)
_first_party_tops = vc._first_party_tops


@pytest.fixture
def repo(tmp_path):
    return tmp_path / "target"


def _make(repo: Path, *relative: str, pyproject: str = "") -> Path:
    for rel in relative:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    if pyproject:
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return repo


# ---------------------------------------------------------------------------
# Side one: the mid-build repo is recognised
# ---------------------------------------------------------------------------


class TestTheMeasuredCase:
    """boostgauge as it stood on 2026-08-15, reconstructed exactly."""

    def test_a_src_package_without_init_is_first_party(self, repo):
        _make(repo, "src/boostgauge/gauge.py", "src/boostgauge/config.py")
        assert "boostgauge" in _first_party_tops(repo)

    def test_the_old_rule_would_have_returned_nothing(self, repo):
        """Pins WHY: no `__init__.py` anywhere, so the pre-#2412 rule found
        nothing and the test above is not passing for another reason."""
        _make(repo, "src/boostgauge/gauge.py")
        assert not (repo / "src" / "boostgauge" / "__init__.py").exists()

    def test_an_init_py_still_works(self, repo):
        """The original signal is unchanged."""
        _make(repo, "src/boostgauge/__init__.py")
        assert "boostgauge" in _first_party_tops(repo)

    def test_a_flat_layout_package_still_works(self, repo):
        _make(repo, "boostgauge/__init__.py")
        assert "boostgauge" in _first_party_tops(repo)


class TestThePyprojectSignal:
    """The authoritative signal, needing no filesystem heuristic. It is what
    covers a FLAT-layout mid-build repo, where the src/ rule cannot apply."""

    def test_a_poetry_name_is_first_party(self, repo):
        _make(repo, "README.md", pyproject='[tool.poetry]\nname = "boostgauge"\n')
        assert "boostgauge" in _first_party_tops(repo)

    def test_a_pep621_project_name_is_first_party(self, repo):
        _make(repo, "README.md", pyproject='[project]\nname = "boostgauge"\n')
        assert "boostgauge" in _first_party_tops(repo)

    def test_a_dashed_distribution_name_yields_the_import_name(self, repo):
        """`name = "my-tool"` is imported as `my_tool`."""
        _make(repo, "README.md", pyproject='[project]\nname = "my-tool"\n')
        tops = _first_party_tops(repo)
        assert "my_tool" in tops

    def test_poetry_packages_include_is_first_party(self, repo):
        _make(
            repo, "README.md",
            pyproject=(
                '[tool.poetry]\nname = "dist-name"\n'
                'packages = [{include = "realpkg", from = "src"}]\n'
            ),
        )
        assert "realpkg" in _first_party_tops(repo)

    def test_a_malformed_pyproject_is_not_fatal(self, repo):
        _make(repo, "src/pkg/mod.py", pyproject="this is not toml [[[")
        assert "pkg" in _first_party_tops(repo)

    def test_a_missing_pyproject_is_not_fatal(self, repo):
        _make(repo, "src/pkg/mod.py")
        assert "pkg" in _first_party_tops(repo)


# ---------------------------------------------------------------------------
# Side two: widening must not sweep in what is not a package
# ---------------------------------------------------------------------------


class TestItDoesNotOverInclude:
    """'the #1901 import check does not start rejecting imports of packages a
    spec legitimately creates' -- a first-party top gets the STRICTER rule, so
    every name added here makes that check harsher."""

    @pytest.mark.parametrize("name", ["tests", "scripts", "docs", "examples"])
    def test_repo_root_siblings_are_not_first_party(self, repo, name):
        """The `src/` rule is deliberately NOT applied at the repo root, where
        these all sit beside the package rather than being packages."""
        _make(repo, f"{name}/thing.py", "src/pkg/mod.py")
        tops = _first_party_tops(repo)
        assert "pkg" in tops
        assert name not in tops

    def test_a_root_directory_with_an_init_is_still_first_party(self, repo):
        """The original signal is not narrowed -- a real flat-layout package
        at the root still counts, `tests/` included when it declares itself."""
        _make(repo, "tests/__init__.py")
        assert "tests" in _first_party_tops(repo)

    def test_a_src_directory_with_no_python_is_not_first_party(self, repo):
        _make(repo, "src/assets/logo.svg", "src/pkg/mod.py")
        tops = _first_party_tops(repo)
        assert "pkg" in tops
        assert "assets" not in tops

    def test_a_loose_file_beside_src_packages_is_not_a_top(self, repo):
        _make(repo, "src/setup_helper.py", "src/pkg/mod.py")
        tops = _first_party_tops(repo)
        assert "setup_helper" not in tops

    def test_an_empty_repo_yields_nothing(self, repo):
        repo.mkdir(parents=True)
        assert _first_party_tops(repo) == set()

    def test_a_nonexistent_repo_yields_nothing(self, tmp_path):
        assert _first_party_tops(tmp_path / "nope") == set()


# ---------------------------------------------------------------------------
# The founding true positive, end to end
# ---------------------------------------------------------------------------


class TestTheFoundingTruePositiveIsRestored:
    def test_a_hallucinated_call_on_a_mid_build_package_is_reachable(self, repo):
        """#1527's case: `boostgauge.gauge.nonexistent()` must be judged
        against the repo's symbols rather than exempted as foreign. The
        judgement needs the root recognised first; this pins that half."""
        _make(repo, "src/boostgauge/gauge.py")
        tops = vc._first_party_tops_for(str(repo))
        assert "boostgauge" in tops

    def test_the_lookup_fails_open_on_a_bad_path(self):
        """#2411's contract: an unknown root is treated as foreign, never
        raised over."""
        assert vc._first_party_tops_for("") == frozenset()
