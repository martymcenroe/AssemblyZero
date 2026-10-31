"""The three answers the changed-line gate rests on (#4436): the run's base
commit, the lines it changed, and which of them are executable.

Git is real: every repository here is a real one under tmp_path, built to the
shape a run leaves. The reports are read in the shape the tools write, and the
Istanbul statements are the shape of a real Jest `coverage-final.json`, where
an outer statement holds the ones inside it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from assemblyzero.workflows.testing.changed_lines import (
    ChangedLinesError,
    changed_lines,
    describe_uncovered,
    is_code_under_test,
    judge_changed_lines,
    line_ranges,
    parse_unified_diff,
    python_line_facts,
    run_base_commit,
)
from assemblyzero.workflows.testing.coverage_report import (
    CoverageReportError,
    FileLines,
    read_coverage_py_report,
    read_istanbul_report,
)
from assemblyzero.workflows.testing.framework_detector import TestFramework
from assemblyzero.workflows.testing.framework_ownership import (
    RunFramework,
    judges_source,
)
from assemblyzero.workflows.testing.runners import jest_runner


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(root), check=True, capture_output=True, text=True,
    ).stdout.strip()


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    (root / "a.py").write_text("one = 1\ntwo = 2\nthree = 3\n", encoding="utf-8")
    _commit(root, "base")
    return root


def _everything(_path: str) -> bool:
    return True


# ---------------------------------------------------------------------------
# Which commit is the run's base
# ---------------------------------------------------------------------------


def test_the_base_is_where_the_run_left_its_branch(repo):
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-c", "issue-7")
    (repo / "a.py").write_text("changed\n", encoding="utf-8")
    _commit(repo, "[CP:post-impl]")
    _git(repo, "switch", "main")
    (repo / "b.py").write_text("moved on\n", encoding="utf-8")
    _commit(repo, "the base branch moved on")
    _git(repo, "switch", "issue-7")

    assert run_base_commit(repo, "main") == base, "the fork point, not the branch's tip"


def test_a_resume_carved_from_a_preserved_attempt_has_the_same_base(repo):
    """stages.py cuts a resumed worktree from `graveyard/issue-N-...`, so its
    HEAD is the prior attempt, several commits past the base."""
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-c", "issue-7")
    (repo / "a.py").write_text("attempt one\n", encoding="utf-8")
    _commit(repo, "[CP:post-impl]")
    (repo / "a.py").write_text("attempt two\n", encoding="utf-8")
    _commit(repo, "[CP:post-impl]")
    _git(repo, "branch", "-m", "issue-7", "graveyard/issue-7-20261031T010203Z")
    _git(repo, "switch", "-c", "issue-7", "graveyard/issue-7-20261031T010203Z")

    assert run_base_commit(repo, "main") == base
    changed = changed_lines(repo, base, _everything)
    assert changed == {"a.py": {1}}, "both attempts' work is the run's"


def test_a_seed_branch_is_the_base_and_main_is_not(repo):
    """A roll on a seed branch is judged on what it adds to the seed, not on
    what the seed itself holds that main does not."""
    _git(repo, "switch", "-c", "speedrun-attempt-3")
    (repo / "seeded.py").write_text("seeded = True\n", encoding="utf-8")
    seed = _commit(repo, "the seed")
    _git(repo, "switch", "-c", "issue-7")
    (repo / "new.py").write_text("new = True\n", encoding="utf-8")
    _commit(repo, "[CP:post-impl]")

    assert run_base_commit(repo, "speedrun-attempt-3") == seed
    assert set(changed_lines(repo, seed, _everything)) == {"new.py"}


def test_origin_is_preferred_when_it_is_nearer_to_head(repo, tmp_path):
    """The orchestrator cuts from `origin/<base>`, and nothing fast-forwards
    the local branch (#2021), so a stale local ref must not widen the diff."""
    bare = tmp_path / "origin.git"
    _git(repo, "clone", "--bare", str(repo), str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    stale = _git(repo, "rev-parse", "HEAD")
    (repo / "merged.py").write_text("merged = True\n", encoding="utf-8")
    fork = _commit(repo, "merged on origin")
    _git(repo, "push", "origin", "main")
    _git(repo, "fetch", "origin")
    _git(repo, "switch", "-c", "issue-7")
    _git(repo, "branch", "--force", "main", stale)

    assert run_base_commit(repo, "main") == fork


def test_the_local_branch_is_preferred_when_it_is_nearer_to_head(repo, tmp_path):
    """The standalone tool cuts from the local branch, which can be ahead of
    origin: those commits are not the run's either."""
    bare = tmp_path / "origin.git"
    _git(repo, "clone", "--bare", str(repo), str(bare))
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "fetch", "origin")
    (repo / "unpushed.py").write_text("unpushed = True\n", encoding="utf-8")
    fork = _commit(repo, "local only")
    _git(repo, "switch", "-c", "issue-7")

    assert run_base_commit(repo, "main") == fork


def test_a_frozen_commit_wins(repo):
    frozen = _git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text("in place\n", encoding="utf-8")
    _commit(repo, "[CP:post-impl] on the branch the run is on")

    assert run_base_commit(repo, "", frozen) == frozen


def test_a_merge_base_with_the_branch_the_run_is_on_would_read_as_nothing(repo):
    """Why a run in place freezes HEAD. This is the failure it prevents."""
    frozen = _git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text("in place\n", encoding="utf-8")
    _commit(repo, "[CP:post-impl]")

    assert changed_lines(repo, run_base_commit(repo, "main"), _everything) == {}
    assert changed_lines(repo, frozen, _everything) == {"a.py": {1}}


def test_a_frozen_commit_that_is_not_an_ancestor_refuses(repo):
    _git(repo, "switch", "-c", "other")
    (repo / "a.py").write_text("other\n", encoding="utf-8")
    other = _commit(repo, "elsewhere")
    _git(repo, "switch", "main")

    with pytest.raises(ChangedLinesError, match="not an ancestor of HEAD"):
        run_base_commit(repo, "", other)


def test_no_base_at_all_refuses(repo):
    with pytest.raises(ChangedLinesError, match="no base branch and no base commit"):
        run_base_commit(repo, "")


def test_a_branch_that_does_not_exist_refuses(repo):
    with pytest.raises(ChangedLinesError, match="shares no history"):
        run_base_commit(repo, "no-such-branch")


def test_a_directory_that_is_no_repository_refuses(tmp_path):
    with pytest.raises(ChangedLinesError):
        run_base_commit(tmp_path, "main")


def test_a_changed_lines_error_halts_as_a_coverage_report_error():
    assert issubclass(ChangedLinesError, CoverageReportError)


# ---------------------------------------------------------------------------
# Which lines changed
# ---------------------------------------------------------------------------


def test_a_modified_line_and_an_added_line_are_found_in_new_numbering(repo):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text("one = 1\ninserted = 0\ntwo = 22\nthree = 3\n", encoding="utf-8")

    assert changed_lines(repo, base, _everything) == {"a.py": {2, 3}}


def test_a_new_tracked_file_counts_whole(repo):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "new.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
    _commit(repo, "added")

    assert changed_lines(repo, base, _everything) == {"new.py": {1, 2}}


def test_an_untracked_file_counts_whole(repo):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "new.py").write_text("a = 1\nb = 2", encoding="utf-8")

    assert changed_lines(repo, base, _everything) == {"new.py": {1, 2}}, "no final newline"


def test_an_ignored_file_is_no_change(repo):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    (repo / "ignored.py").write_text("a = 1\n", encoding="utf-8")

    assert "ignored.py" not in changed_lines(repo, base, _everything)


def test_a_deletion_adds_no_line(repo):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text("one = 1\nthree = 3\n", encoding="utf-8")

    assert changed_lines(repo, base, _everything) == {}


def test_a_deleted_file_adds_no_line(repo):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "a.py").unlink()

    assert changed_lines(repo, base, _everything) == {}


def test_a_moved_file_is_judged_on_what_changed_in_it(repo):
    base = _git(repo, "rev-parse", "HEAD")
    body = "".join(f"line_{n} = {n}\n" for n in range(40))
    (repo / "big.py").write_text(body, encoding="utf-8")
    base = _commit(repo, "a file big enough to be seen as moved")
    (repo / "big.py").unlink()
    (repo / "moved.py").write_text(body.replace("line_9 = 9", "line_9 = 99"), encoding="utf-8")
    _commit(repo, "moved it")

    assert changed_lines(repo, base, _everything) == {"moved.py": {10}}


def test_a_change_of_line_endings_alone_is_no_change(repo):
    """On Windows `write_text` writes CRLF, and a Modify of an LF file would
    otherwise read as every line of it changed."""
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_bytes(b"one = 1\r\ntwo = 2\r\nthree = 3\r\n")

    assert changed_lines(repo, base, _everything) == {}


def test_wanted_filters_both_the_diff_and_the_untracked_files(repo):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "a.py").write_text("changed\n", encoding="utf-8")
    (repo / "notes.md").write_text("a note\n", encoding="utf-8")

    assert set(changed_lines(repo, base, lambda path: path.endswith(".py"))) == {"a.py"}


def test_a_failing_git_diff_refuses(repo):
    with pytest.raises(ChangedLinesError, match="git diff"):
        changed_lines(repo, "0" * 40, _everything)


# The parser, on text git really writes.

DIFF = """\
diff --git a/x.py b/x.py
index 1111111..2222222 100644
--- a/x.py
+++ b/x.py
@@ -2,0 +3,2 @@ def f():
+++ this body line reads as a file header
+--- so does this one
@@ -10 +12 @@
-old
+new
\\ No newline at end of file
diff --git a/gone.py b/gone.py
deleted file mode 100644
--- a/gone.py
+++ /dev/null
@@ -1,2 +0,0 @@
-a
-b
diff --git a/mode.sh b/mode.sh
old mode 100644
new mode 100755
"""


def test_the_parser_counts_hunks_so_a_body_line_is_never_a_header():
    assert parse_unified_diff(DIFF) == {"x.py": {3, 4, 12}}


def test_the_parser_reads_a_quoted_path():
    text = (
        'diff --git "a/caf\\303\\251 \\"x\\".py" "b/caf\\303\\251 \\"x\\".py"\n'
        '--- "a/caf\\303\\251 \\"x\\".py"\n'
        '+++ "b/caf\\303\\251 \\"x\\".py"\n'
        "@@ -0,0 +1 @@\n+a\n"
    )
    assert parse_unified_diff(text) == {'café "x".py': {1}}


def test_the_parser_reads_a_path_with_a_space():
    """git ends such a name with a tab."""
    text = "diff --git a/a b.py b/a b.py\n--- a/a b.py\t\n+++ b/a b.py\t\n@@ -0,0 +1 @@\n+a\n"
    assert parse_unified_diff(text) == {"a b.py": {1}}


def test_a_real_quoted_path_comes_through_git(repo):
    base = _git(repo, "rev-parse", "HEAD")
    (repo / "a b.py").write_text("x = 1\n", encoding="utf-8")
    _commit(repo, "a space")

    assert changed_lines(repo, base, _everything) == {"a b.py": {1}}


@pytest.mark.parametrize("text, match", [
    ("--- a/x\n+++ b/x\n@@ nonsense @@\n", "cannot be read"),
    ("--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n", "ends inside the hunk"),
    ("@@ -0,0 +1 @@\n+a\n", "adds lines to no file"),
    ("+++ x\n", "names no b/ path"),
], ids=["bad-header", "cut-short", "no-file", "no-prefix"])
def test_a_diff_that_cannot_be_read_refuses(text, match):
    with pytest.raises(ChangedLinesError, match=match):
        parse_unified_diff(text)


# ---------------------------------------------------------------------------
# Which files count
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path, judged", [
    ("src/pkg/engine.py", True),
    ("web/src/engine.ts", True),
    ("web/src/App.tsx", True),
    ("tests/unit/test_engine.py", False),
    ("src/pkg/test_engine.py", False),
    ("src/pkg/engine_test.py", False),
    ("tests/helpers.py", False),
    ("conftest.py", False),
    ("setup.py", False),
    ("web/src/engine.test.ts", False),
    ("web/src/App.spec.tsx", False),
    ("web/tests/helpers.ts", False),
    ("web/src/__tests__/engine.ts", False),
    ("web/src/__mocks__/fetch.ts", False),
    ("web/src/types.d.ts", False),
    ("web/vite.config.ts", False),
    # The workflow's own copies of the run's source.
    ("docs/lineage/active/7-testing/best-iteration/00-engine.py", False),
    ("docs/lineage/active/7-testing/042-test-scaffold.py", False),
    ("docs/lineage/done/7-testing/best-iteration/01-page.tsx", False),
    ("data/lineage/7/engine.py", False),
    (".az-best-iteration/best-iteration/00-engine.py", False),
    (".assemblyzero/engine.py", False),
    # Trees a tool fills, which a target may not ignore.
    (".venv/lib/python3.12/site-packages/x/y.py", False),
    (".tox/py312/lib/z.py", False),
    ("web/node_modules/left-pad/index.js", False),
    ("web/dist/assets/index.js", False),
    ("web/coverage/sorter.js", False),
    ("build/lib/pkg/engine.py", False),
    # A directory merely named like one of these is still source.
    ("src/pkg/builders/engine.py", True),
    ("docs/conf.py", True),
])
def test_only_code_under_test_is_judged(path, judged):
    assert is_code_under_test(path) is judged


def _run(framework: TestFramework, directory: str) -> RunFramework:
    return RunFramework({}, framework, directory)


def test_a_deeper_framework_owns_its_directorys_source():
    jest = _run(TestFramework.JEST, ".")
    vitest = _run(TestFramework.VITEST, "web")
    frameworks = [jest, vitest]

    assert judges_source("web/src/a.ts", vitest, frameworks) is True
    assert judges_source("web/src/a.ts", jest, frameworks) is False
    assert judges_source("scripts/a.ts", jest, frameworks) is True


def test_playwright_judges_no_source_and_takes_none_from_vitest():
    vitest = _run(TestFramework.VITEST, "web")
    playwright = _run(TestFramework.PLAYWRIGHT, "web/e2e")
    frameworks = [vitest, playwright]

    assert judges_source("web/e2e/page.ts", playwright, frameworks) is False
    assert judges_source("web/e2e/page.ts", vitest, frameworks) is True


def test_python_is_pytests_and_typescript_is_vitests():
    pytest_run = _run(TestFramework.PYTEST, ".")
    vitest = _run(TestFramework.VITEST, "web")
    frameworks = [pytest_run, vitest]

    assert judges_source("web/tool.py", pytest_run, frameworks) is True
    assert judges_source("web/src/a.ts", pytest_run, frameworks) is False


# ---------------------------------------------------------------------------
# Which lines count
# ---------------------------------------------------------------------------


def _judge(tmp_path: Path, source: str, changed: set[int], hits: dict[int, bool], *,
           name: str = "m.py", continuation: dict[int, int] | None = None):
    (tmp_path / name).write_text(source, encoding="utf-8")
    report = {name: FileLines(hits, continuation or {})}
    return judge_changed_lines({name: changed}, report, tmp_path)


def test_comments_blanks_and_docstrings_are_in_no_denominator(tmp_path):
    source = '"""Module."""\n\n# a comment\ndef f():\n    """Doc."""\n    return 1\n'
    verdict = _judge(tmp_path, source, {1, 2, 3, 4, 5, 6}, {4: True, 6: False})

    assert (verdict.covered, verdict.total) == (1, 2)
    assert verdict.uncovered == {"m.py": [6]}


def test_an_excluded_line_is_in_no_denominator(tmp_path):
    source = "def f():\n    return 1  # pragma: no cover\n"
    verdict = _judge(tmp_path, source, {2}, {1: True})

    assert verdict.judged is False


def test_only_non_executable_changes_are_a_real_zero(tmp_path):
    verdict = _judge(tmp_path, "# one\n# two\nx = 1\n", {1, 2}, {3: True})

    assert verdict.judged is False
    assert verdict.total == 0


def test_a_changed_line_of_a_multi_line_statement_is_that_statement(tmp_path):
    source = "result = compute(\n    1,\n    2,\n)\n"
    verdict = _judge(tmp_path, source, {3}, {1: False})

    assert verdict.uncovered == {"m.py": [1]}, "the tool reports the first line"


def test_two_changed_lines_of_one_statement_count_once(tmp_path):
    source = "result = compute(\n    1,\n    2,\n)\n"
    verdict = _judge(tmp_path, source, {2, 3}, {1: True})

    assert (verdict.covered, verdict.total) == (1, 1)


def test_a_changed_comment_inside_a_multi_line_statement_is_no_change_to_it(tmp_path):
    source = "result = compute(\n    1,\n    # why\n\n    2,\n)\n"
    verdict = _judge(tmp_path, source, {3, 4}, {1: False})

    assert verdict.judged is False


def test_a_changed_line_of_a_multi_line_header_is_the_header(tmp_path):
    source = "if (\n    a\n    and b\n):\n    c()\n"
    verdict = _judge(tmp_path, source, {3}, {1: True, 5: False})

    assert (verdict.covered, verdict.total) == (1, 1)


def test_a_changed_line_of_a_multi_line_docstring_is_no_statement(tmp_path):
    source = 'def f():\n    """One.\n\n    Two.\n    """\n    return 1\n'
    verdict = _judge(tmp_path, source, {3, 4}, {1: True, 6: True})

    assert verdict.judged is False


TYPE_ONLY = '''\
from typing import TYPE_CHECKING, Protocol, overload
import typing

if TYPE_CHECKING:
    from x import Y
if typing.TYPE_CHECKING:
    from x import Z


@overload
def f(a: int) -> int: ...
@overload
def f(a: str) -> str: ...
def f(a):
    return a


class Shape(Protocol):
    def area(self) -> float:
        """Area."""
        ...

    def real(self) -> float:
        return 1.0


class Point:
    x: int
    y: int = 0
'''


def test_type_only_lines_are_named():
    _continuation, type_only = python_line_facts(TYPE_ONLY)

    assert {5, 7} <= type_only, "the TYPE_CHECKING bodies"
    assert {10, 11, 12, 13} <= type_only, "the overloads and their decorators"
    assert {19, 20, 21} <= type_only, "a Protocol's stub"
    assert 28 in type_only, "a bare annotation"
    assert 14 not in type_only, "the implementation"
    assert 24 not in type_only, "a Protocol method with a body"
    assert 29 not in type_only, "an annotation with a value does work"


def test_a_changed_type_only_line_does_not_count_as_uncovered(tmp_path):
    verdict = _judge(tmp_path, TYPE_ONLY, {5, 7, 11, 28}, {5: False, 7: False, 11: False, 28: True})

    assert verdict.judged is False


def test_a_file_the_harness_cannot_parse_halts_rather_than_guess_its_lines(tmp_path):
    """A target can run a newer Python than the harness. Its type-only lines
    cannot then be told from real ones, so the denominator is unknown."""
    with pytest.raises(CoverageReportError) as raised:
        _judge(tmp_path, "def f(:\n    return 1\n", {2}, {2: False})

    assert "m.py" in str(raised.value)
    assert "does not parse" in str(raised.value)


def test_a_match_statements_header_lines_are_found():
    source = "match (\n    a\n):\n    case 1:\n        pass\n"
    continuation, _type_only = python_line_facts(source)

    assert continuation[2] == 1


def test_a_changed_file_absent_from_the_report_is_refused(tmp_path):
    (tmp_path / "m.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(CoverageReportError) as raised:
        judge_changed_lines({"m.py": {1}}, {"other.py": FileLines({1: True})}, tmp_path)

    assert "m.py" in str(raised.value)
    assert "other.py" in str(raised.value)
    assert "omits" in str(raised.value)


def test_an_empty_report_with_changed_files_is_refused(tmp_path):
    (tmp_path / "m.py").write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(CoverageReportError, match="no file at all"):
        judge_changed_lines({"m.py": {1}}, {}, tmp_path)


def test_no_changed_file_is_a_real_zero(tmp_path):
    verdict = judge_changed_lines({}, {"other.py": FileLines({1: True})}, tmp_path)

    assert verdict.judged is False


def test_a_vanished_source_is_refused(tmp_path):
    with pytest.raises(CoverageReportError, match="cannot be read"):
        judge_changed_lines({"m.py": {1}}, {"m.py": FileLines({1: True})}, tmp_path)


def test_percent_is_the_covered_share_across_every_file(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("z = 3\nw = 4\n", encoding="utf-8")
    verdict = judge_changed_lines(
        {"a.py": {1, 2}, "b.py": {1, 2}},
        {"a.py": FileLines({1: True, 2: True}), "b.py": FileLines({1: True, 2: False})},
        tmp_path,
    )

    assert (verdict.covered, verdict.total, verdict.percent) == (3, 4, 75.0)


# ---------------------------------------------------------------------------
# Naming lines
# ---------------------------------------------------------------------------


def test_line_ranges_read_the_way_n4c_reads_them():
    assert line_ranges([58, 56, 57, 63]) == ["56-58", "63"]
    assert line_ranges([]) == []


def test_describe_uncovered_names_each_file():
    assert describe_uncovered({"b.py": [7], "a.py": [12, 13, 20]}) == "a.py: 12-13, 20; b.py: 7"


# ---------------------------------------------------------------------------
# The reports
# ---------------------------------------------------------------------------


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_the_coverage_py_report_gives_every_executable_line(tmp_path):
    report = _write(tmp_path / "c.json", {"files": {
        "src/a.py": {"executed_lines": [1, 2], "missing_lines": [3], "excluded_lines": [4]},
        "src\\b.py": {"executed_lines": [], "missing_lines": []},
    }})

    lines = read_coverage_py_report(report, tmp_path)

    assert lines["src/a.py"].hits == {1: True, 2: True, 3: False}
    assert lines["src/b.py"].hits == {}, "a Windows name reads as a repository path"


def test_an_absolute_name_in_the_repository_reads_relative(tmp_path):
    (tmp_path / "src").mkdir()
    report = _write(tmp_path / "c.json", {"files": {
        str(tmp_path / "src" / "a.py"): {"executed_lines": [1], "missing_lines": []},
    }})

    assert "src/a.py" in read_coverage_py_report(report, tmp_path)


def test_a_file_outside_the_repository_keeps_its_own_name(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    elsewhere = str(tmp_path / "other" / "a.py")
    report = _write(tmp_path / "c.json", {"files": {
        elsewhere: {"executed_lines": [1], "missing_lines": []},
    }})

    assert elsewhere in read_coverage_py_report(report, root)


def test_the_istanbul_reader_reads_a_jest_shaped_report(tmp_path):
    """Statements as a real Jest report holds them (Clio's, 2026-01-19): the
    first holds the second, so it is not a simple statement."""
    source = tmp_path / "web" / "src" / "a.js"
    report = _write(tmp_path / "final.json", {str(source): {
        "path": str(source),
        "statementMap": {
            "0": {"start": {"line": 11, "column": 0}, "end": {"line": 13, "column": 3}},
            "1": {"start": {"line": 12, "column": 2}, "end": {"line": 12, "column": 57}},
            "2": {"start": {"line": 16, "column": 0}, "end": {"line": 20, "column": 3}},
        },
        "s": {"0": 9, "1": 0, "2": 3},
        "fnMap": {}, "f": {}, "branchMap": {}, "b": {},
        "hash": "x", "_coverageSchema": "y",
    }})

    lines = read_istanbul_report(report, tmp_path, tmp_path / "web")

    entry = lines["web/src/a.js"]
    assert entry.hits == {11: True, 12: False, 16: True}
    assert entry.continuation == {17: 16, 18: 16, 19: 16, 20: 16}, "only the simple statement"


def test_a_line_runs_when_any_statement_starting_on_it_ran(tmp_path):
    source = tmp_path / "a.ts"
    report = _write(tmp_path / "final.json", {str(source): {
        "statementMap": {
            "0": {"start": {"line": 5, "column": 0}, "end": {"line": 5, "column": 9}},
            "1": {"start": {"line": 5, "column": 10}, "end": {"line": 5, "column": 20}},
        },
        "s": {"0": 0, "1": 2},
    }})

    assert read_istanbul_report(report, tmp_path, tmp_path)["a.ts"].hits == {5: True}


def test_a_statement_no_source_map_could_place_is_passed_over(tmp_path):
    source = tmp_path / "a.ts"
    report = _write(tmp_path / "final.json", {str(source): {
        "statementMap": {
            "0": {"start": {}, "end": {}},
            "1": {"start": {"line": 3, "column": 0}, "end": {"line": 3, "column": 9}},
        },
        "s": {"0": 1, "1": 1},
    }})

    assert read_istanbul_report(report, tmp_path, tmp_path)["a.ts"].hits == {3: True}


def test_a_types_only_file_reports_no_executable_line(tmp_path):
    source = tmp_path / "types.ts"
    report = _write(tmp_path / "final.json", {str(source): {"statementMap": {}, "s": {}}})

    assert read_istanbul_report(report, tmp_path, tmp_path)["types.ts"].hits == {}


def test_a_changed_line_inside_a_simple_javascript_statement_is_that_statement(tmp_path):
    source = "const a = {\n  b: 1,\n  // why\n  c: 2,\n};\n"
    verdict = _judge(
        tmp_path, source, {2, 3}, {1: False}, name="m.ts",
        continuation={2: 1, 3: 1, 4: 1, 5: 1},
    )

    assert verdict.uncovered == {"m.ts": [1]}


def test_a_changed_comment_in_a_javascript_block_is_in_no_statement(tmp_path):
    source = "if (x) {\n  // why\n  y();\n}\n"
    verdict = _judge(tmp_path, source, {2}, {1: False, 3: False}, name="m.ts")

    assert verdict.judged is False


@pytest.mark.parametrize("reader", ["python", "istanbul"])
def test_a_missing_report_is_refused_naming_it(tmp_path, reader):
    missing = tmp_path / "absent.json"
    read = read_coverage_py_report if reader == "python" else (
        lambda path, root: read_istanbul_report(path, root, root)
    )
    with pytest.raises(CoverageReportError) as raised:
        read(missing, tmp_path)

    assert str(missing) in str(raised.value)


@pytest.mark.parametrize("value", [
    [], {"a.ts": "x"}, {"a.ts": {"statementMap": {}}}, {"a.ts": {"s": {}}},
    {"a.ts": {"statementMap": {"0": {"start": {"line": 1}, "end": {"line": 1}}}, "s": {}}},
], ids=["a-list", "not-an-entry", "no-counts", "no-statements", "no-count-for-a-statement"])
def test_a_broken_istanbul_report_is_refused(tmp_path, value):
    with pytest.raises(CoverageReportError):
        read_istanbul_report(_write(tmp_path / "final.json", value), tmp_path, tmp_path)


# ---------------------------------------------------------------------------
# What the runner asks for
# ---------------------------------------------------------------------------


def _jest_runner(framework: TestFramework, root: Path) -> jest_runner.JestRunner:
    from unittest.mock import patch

    from assemblyzero.workflows.testing.runner_registry import get_runner

    with patch.object(jest_runner.shutil, "which", return_value="/usr/bin/npx"):
        return get_runner(framework, str(root), working_directory="web")


def test_vitest_asks_for_the_per_line_report_and_switches_thresholds_off(tmp_path):
    args = _jest_runner(TestFramework.VITEST, tmp_path)._coverage_args(["src/a.ts"])

    assert "--coverage.reporter=json-summary" in args
    assert "--coverage.reporter=json" in args
    assert "--coverage.include=src/a.ts" in args
    for metric in ("lines", "functions", "branches", "statements"):
        assert f"--coverage.thresholds.{metric}=0" in args


def test_jest_asks_for_the_per_line_report_and_switches_its_threshold_off(tmp_path):
    args = _jest_runner(TestFramework.JEST, tmp_path)._coverage_args(["src/a.ts"])

    assert "--coverageReporters=json-summary" in args
    assert "--coverageReporters=json" in args
    assert "--collectCoverageFrom=src/a.ts" in args
    assert "--coverageThreshold={}" in args


def test_jests_last_coverage_flag_takes_no_array(tmp_path):
    """Jest's `--coverageReporters` is an array flag, and yargs gives an array
    flag every word after it that is not a flag, so the test paths that follow
    must not sit right behind one."""
    args = _jest_runner(TestFramework.JEST, tmp_path)._coverage_args(["src/a.ts"])

    assert args[-1].startswith("--coverageDirectory=")


def test_a_route_file_name_reaches_the_glob_literally(tmp_path):
    args = _jest_runner(TestFramework.VITEST, tmp_path)._coverage_args(["src/[id]/page.tsx"])

    assert "--coverage.include=src/\\[id\\]/page.tsx" in args


def test_with_nothing_changed_the_project_keeps_its_own_scope(tmp_path):
    args = _jest_runner(TestFramework.VITEST, tmp_path)._coverage_args()

    assert not any(arg.startswith("--coverage.include") for arg in args)


def test_a_stale_per_line_report_is_cleared_before_a_coverage_run(tmp_path):
    from unittest.mock import patch

    from assemblyzero.workflows.testing.runners import base_runner

    runner = _jest_runner(TestFramework.VITEST, tmp_path)
    (tmp_path / "web" / "coverage").mkdir(parents=True)
    stale = tmp_path / "web" / "coverage" / "coverage-final.json"
    stale.write_text("{}", encoding="utf-8")

    def nothing_written(command, **_kwargs):
        return subprocess.CompletedProcess(
            args=command, returncode=0, stderr="",
            stdout=json.dumps({"numPassedTests": 0, "numFailedTests": 1}),
        )

    with patch.object(base_runner, "run_command", side_effect=nothing_written):
        runner.run_tests(test_paths=["a.test.ts"], measure_coverage=True)

    assert not stale.exists()
