"""parsers.py under standard 0034 (ADR 0236), the #3585 sweep.

``validate_conftest_options`` (#2547) compares a generated conftest's pytest
options with every ancestor conftest's. An ancestor that did not parse, could
not be read, or a directory that could not resolve used to end the comparison
under a ``# fail-open:`` tag, and the check passed. A check that cannot run is
a failure: each now writes an ERROR line naming the file and raises. Test
names carry ledger 0908's line numbers at its base ``79e18ad1``.
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.nodes.implementation import parsers

NEW_CONFTEST = (
    "def pytest_addoption(parser):\n"
    "    parser.addoption('--generate-baselines', action='store_true')\n"
)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "tests" / "visual").mkdir(parents=True)
    (tmp_path / "tests" / "conftest.py").write_text(
        "def pytest_addoption(parser):\n    parser.addoption('--other')\n",
        encoding="utf-8",
    )
    return tmp_path


def _check(repo: Path):
    return parsers.validate_conftest_options(NEW_CONFTEST, "tests/visual/conftest.py", repo)


def _loud(err: str, *needles: str) -> bool:
    return any(
        line.startswith("ERROR") and all(n in line for n in needles)
        for line in err.splitlines()
    )


class TestTheAncestorComparison:
    def test_142_an_ancestor_conftest_that_does_not_parse_raises(self, repo, capsys):
        (repo / "tests" / "conftest.py").write_text("def pytest_addoption(parser:\n", encoding="utf-8")

        with pytest.raises(SyntaxError):
            _check(repo)

        assert _loud(capsys.readouterr().err, "conftest.py", "does not parse")

    def test_197_an_unreadable_ancestor_conftest_raises(self, repo, monkeypatch, capsys):
        ancestor = str((repo / "tests" / "conftest.py").resolve())
        real = Path.read_text

        def read_text(self, *args, **kwargs):
            if str(Path(self).resolve()) == ancestor:
                raise PermissionError(13, "Permission denied", str(self))
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)

        with pytest.raises(PermissionError):
            _check(repo)

        assert _loud(capsys.readouterr().err, "conftest.py", "could not read")

    def test_212_a_directory_that_cannot_resolve_raises(self, repo, monkeypatch, capsys):
        """The first resolve (the walk's start) answers; the walk's own does not."""
        target = str(repo / "tests")
        real = Path.resolve
        seen = {"n": 0}

        def resolve(self, *args, **kwargs):
            if str(self) == target:
                seen["n"] += 1
                if seen["n"] > 1:
                    raise OSError(5, "Input/output error", str(self))
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", resolve)

        with pytest.raises(OSError):
            _check(repo)

        assert _loud(capsys.readouterr().err, "tests", "could not resolve")

    def test_a_duplicate_option_is_still_refused(self, repo):
        """Kept: #2547's refusal."""
        (repo / "tests" / "conftest.py").write_text(NEW_CONFTEST, encoding="utf-8")
        valid, error = _check(repo)
        assert valid is False
        assert "--generate-baselines" in error

    def test_distinct_options_pass(self, repo):
        """Kept: nothing duplicated is a pass the check measured."""
        assert _check(repo) == (True, "")


class TestTheNewCodeIsSyntaxCheckedFirst:
    def test_a_generated_conftest_that_does_not_parse_fails_validation(self, repo):
        """Kept: the syntax check reports it before the option check runs."""
        valid, error = parsers.validate_code_response(
            "def pytest_addoption(parser:\n    pass\n", "tests/visual/conftest.py",
            repo_root=str(repo),
        )
        assert valid is False
        assert "syntax error" in error


def test_143_198_213_the_module_carries_no_fail_open_tag():
    source = Path(parsers.__file__).read_text(encoding="utf-8")
    tags = [
        tok.start[0]
        for tok in tokenize.generate_tokens(io.StringIO(source).readline)
        if tok.type == tokenize.COMMENT and "fail-open:" in tok.string
    ]
    assert tags == []
