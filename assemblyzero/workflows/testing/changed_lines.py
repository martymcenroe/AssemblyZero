"""What the run changed, and whether its tests ran those lines (#4436).

The green phase graded whole files. The LLD promised 95% of new code and N5
measured every line of every module the run touched, so a run that added ten
covered lines to a 562-statement module read 25% and could never pass. The
whole suites of the target that measured this do not reach 95% on those
modules either. A run was sent back until the cap, and N4c was asked to test
code the run never wrote.

The gate now judges the lines the run added or changed against its base
commit, for each framework. A new file counts whole. This module answers the
three questions that takes.

## Which commit is the run's base

`run_base_commit`. Both entry points name the integration branch; the base is
where the run's history left it, `git merge-base`, and of `origin/<branch>` and
`<branch>` the one nearest to HEAD, because the orchestrator cuts its worktree
from origin and the standalone tool from the local branch, and a commit on
either one is not the run's. Being a merge-base it does not depend on how this
worktree came to be: a resume carved from a graveyard attempt and a roll on a
seed branch both answer the commit they forked at, and the base branch moving
on afterwards changes nothing. A run with no integration branch works in
place, on a branch its own checkpoints move, so a merge-base with it would
always read as nothing changed; the launcher freezes HEAD as `base_commit`
instead, and the checkpoint database carries it across a resume.

No answer raises ChangedLinesError and the phase halts. It never reads as
"no changed lines".

## Which lines changed

`changed_lines`: `git diff --unified=0` from the base to the working tree, so
the line numbers are the numbers coverage just measured, plus the untracked
files git diff cannot see, each counted whole. The diff is read by a parser
that counts each hunk's own lines, because a hunk body can hold a line that
looks like a file header. Renames are followed, so a moved file is judged on
what changed in it, and a file whose line endings alone changed has not
changed. A hunk that only deletes adds no line, and a deleted file none.

## Which of them count

`judge_changed_lines`. A line is executable when the coverage tool says so:
comments, blank lines, docstrings and excluded lines are in no report, so a
changed one is in no denominator. Type-only Python lines are a statement to
coverage.py, so they are taken out here (`python_line_facts`); the types
TypeScript erases are in no statement at all. A later line of a multi-line
statement is judged as that statement, whose first line is the one the tool
reports. A file the report does not name is a measurement that failed
(#2637), never a file with nothing to judge: N5 puts every changed file in the
measured scope, so a file no test reaches is present at zero.
"""

from __future__ import annotations

import ast
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from assemblyzero.utils.shell import run_command
from assemblyzero.workflows.testing.coverage_report import (
    CoverageReportError,
    FileLines,
)

#: Directories that hold tests and their support, never code under test.
#: Closed: the names the fleet's Python and JavaScript test trees use.
_TEST_DIRECTORIES = frozenset({"tests", "test", "__tests__", "__mocks__"})

#: Python files a tool runs and no test imports. Closed.
_TOOL_PYTHON_FILES = frozenset({"setup.py", "noxfile.py", "conftest.py"})

#: Trees a tool fills, never code under test: installed packages and build
#: output, which a target may not ignore. Closed. A hidden directory (`.venv`,
#: `.tox`, `.az-best-iteration`) is the same case, and is matched by its dot.
_GENERATED_DIRECTORIES = frozenset({"node_modules", "dist", "build", "coverage", "__pycache__"})

#: Where the workflow keeps its own record of a run, inside the worktree. The
#: audit directory holds copies of the run's source: every best-iteration
#: snapshot (`best-iteration/00-engine.py`) and each `NNN-test-scaffold.py`,
#: and a checkpoint commits them. To git they are new Python files, so they
#: would be judged whole, at zero, on every iteration after the first. Closed.
_RUN_RECORDS = ("docs/lineage/", "data/lineage/", "data/hourglass/")

#: What opens a comment line, by file type (#4436): a changed comment inside a
#: multi-line statement is not a changed statement. Closed.
_PYTHON_COMMENT = ("#",)
_SCRIPT_COMMENT = ("//", "/*", "*")


class ChangedLinesError(CoverageReportError):
    """What the run changed cannot be established (#4436): no base commit, or
    a git that fails. Raised, never read as zero changed lines. A kind of
    CoverageReportError because it halts the same way, for the same reason:
    without it no line can be judged."""


def _git(repo_root: Path | str, *args: str) -> subprocess.CompletedProcess:
    """Run git in `repo_root`. A git that cannot start raises; a git that
    fails comes back for the caller, which knows what the exit means."""
    try:
        return run_command(
            ["git", *args], cwd=str(repo_root), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        raise ChangedLinesError(
            f"`git {args[0]}` cannot run in {repo_root}: {type(e).__name__}: {e}"
        ) from e


def _git_said(result: subprocess.CompletedProcess) -> str:
    return (result.stderr or result.stdout or "").strip()[:300] or "(git printed nothing)"


def run_base_commit(repo_root: Path | str, base_branch: str, base_commit: str = "") -> str:
    """The commit the run's changes are measured from. See the module docstring.

    `base_commit`, frozen by the launcher for a run in place, wins, and must
    be an ancestor of HEAD. Otherwise it is the merge-base with `base_branch`.

    Raises:
        ChangedLinesError: the state names neither, a frozen commit is not an
            ancestor of HEAD, or no ref of the branch shares history with
            HEAD. Each halts the phase.
    """
    if base_commit:
        ancestry = _git(repo_root, "merge-base", "--is-ancestor", base_commit, "HEAD")
        if ancestry.returncode != 0:
            raise ChangedLinesError(
                f"the run's base commit {base_commit} is not an ancestor of HEAD "
                f"in {repo_root} (exit {ancestry.returncode}): {_git_said(ancestry)}"
            )
        return base_commit
    if not base_branch:
        raise ChangedLinesError(
            f"the run names no base branch and no base commit, so what it "
            f"changed in {repo_root} cannot be told from what it did not"
        )
    refs = [base_branch] if base_branch.startswith("origin/") else [
        f"origin/{base_branch}", base_branch,
    ]
    found: dict[str, int] = {}
    said: list[str] = []
    for ref in refs:
        fork = _git(repo_root, "merge-base", ref, "HEAD")
        sha = fork.stdout.strip()
        if fork.returncode != 0 or not sha:
            said.append(f"{ref}: exit {fork.returncode}: {_git_said(fork)}")
            continue
        ahead = _git(repo_root, "rev-list", "--count", f"{sha}..HEAD")
        if ahead.returncode != 0:
            raise ChangedLinesError(
                f"cannot count the commits from {sha} to HEAD in {repo_root} "
                f"(exit {ahead.returncode}): {_git_said(ahead)}"
            )
        found[sha] = int(ahead.stdout.strip())
    if not found:
        raise ChangedLinesError(
            f"the run's base branch {base_branch!r} shares no history with HEAD "
            f"in {repo_root}: {'; '.join(said)}"
        )
    return min(found, key=lambda sha: found[sha])


def _unquoted(path: str) -> str:
    """A path as git printed it: `"..."` with C escapes when it holds a
    character git will not print bare."""
    if not path.startswith('"'):
        return path
    return (
        path[1:-1].encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")
    )


def _new_side_path(header: str) -> str | None:
    """The file a `+++ ` header names, or None for /dev/null (a deleted file).
    git ends the name with a tab when it holds a space."""
    name = header.rstrip("\t")
    if name == "/dev/null":
        return None
    name = _unquoted(name)
    if not name.startswith("b/"):
        raise ChangedLinesError(f"the diff header `+++ {header}` names no b/ path")
    return name[2:]


def _hunk_counts(line: str) -> tuple[int, int, int]:
    """(lines removed, first new line, lines added) from `@@ -a,b +c,d @@`.
    A count git leaves out is 1."""
    fields = line.split(" ")
    try:
        _, removed = _hunk_range(fields[1], "-")
        start, added = _hunk_range(fields[2], "+")
    except (IndexError, ValueError) as e:
        raise ChangedLinesError(f"the diff hunk header `{line}` cannot be read") from e
    return removed, start, added


def _hunk_range(field_text: str, sign: str) -> tuple[int, int]:
    if not field_text.startswith(sign):
        raise ValueError(field_text)
    start, _, count = field_text[1:].partition(",")
    return int(start), int(count) if count else 1


def parse_unified_diff(text: str) -> dict[str, set[int]]:
    """Each file's added or changed lines, in new-file numbering, from a
    `git diff --unified=0`.

    A parser, not a pattern: a hunk header says how many lines its body
    holds, and those lines are consumed by count, so a body line that reads
    `+++ b/other.py` is never taken for a header. Only `\\n` ends a line: a
    form feed in a source file is not a line end to git. A file with no added
    line has no entry.
    """
    changed: dict[str, set[int]] = {}
    current: str | None = None
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()  # the end of the last line, not a line
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if line.startswith("diff --git "):
            current = None
        elif line.startswith("+++ "):
            current = _new_side_path(line[4:])
        elif line.startswith("@@ "):
            removed, start, added = _hunk_counts(line)
            if added:
                if current is None:
                    raise ChangedLinesError(f"the diff hunk `{line}` adds lines to no file")
                changed.setdefault(current, set()).update(range(start, start + added))
            remaining = removed + added
            while remaining:
                if index >= len(lines):
                    raise ChangedLinesError(f"the diff ends inside the hunk `{line}`")
                if not lines[index].startswith("\\"):  # `\ No newline at end of file`
                    remaining -= 1
                index += 1
    return changed


def _whole_file(repo_root: Path, path: str) -> set[int]:
    """Every line of a file git does not track yet: all of it is new."""
    try:
        data = (repo_root / path).read_bytes()
    except OSError as e:
        raise ChangedLinesError(
            f"the new file {path} cannot be read to count its lines: "
            f"{type(e).__name__}: {e}"
        ) from e
    if not data:
        return set()
    return set(range(1, data.count(b"\n") + (0 if data.endswith(b"\n") else 1) + 1))


def changed_lines(
    repo_root: Path | str, base: str, wanted: Callable[[str], bool],
) -> dict[str, set[int]]:
    """Every line the run added or changed since `base`, in the files `wanted`
    accepts, by POSIX path relative to the repository. See the module
    docstring. An empty answer is an answer: git ran, and nothing `wanted`
    accepts changed. Raises ChangedLinesError when git cannot say.
    """
    root = Path(repo_root)
    diff = _git(
        root, "-c", "core.quotePath=false", "diff", "--no-ext-diff", "--no-textconv",
        "--no-color", "--unified=0", "--find-renames", "--ignore-cr-at-eol",
        "--src-prefix=a/", "--dst-prefix=b/", base, "--",
    )
    if diff.returncode != 0:
        raise ChangedLinesError(
            f"`git diff {base}` failed in {root} (exit {diff.returncode}): {_git_said(diff)}"
        )
    changed = {
        path: lines for path, lines in parse_unified_diff(diff.stdout).items() if wanted(path)
    }
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if untracked.returncode != 0:
        raise ChangedLinesError(
            f"`git ls-files` failed in {root} (exit {untracked.returncode}): "
            f"{_git_said(untracked)}"
        )
    for path in untracked.stdout.split("\0"):
        if path and wanted(path):
            lines = _whole_file(root, path)
            if lines:
                changed[path] = lines
    return changed


def is_code_under_test(path: str) -> bool:
    """Whether a file is judged on coverage at all: not a test or its support,
    not a declaration file, not a file a tool runs and no test imports, and
    not in a generated tree or the workflow's own record of the run. A run
    that changes only these has no line to judge (R2)."""
    if path.startswith(_RUN_RECORDS):
        return False
    parts = path.split("/")
    name = parts[-1]
    for part in parts[:-1]:
        if (
            part.startswith(".")
            or part.lower() in _TEST_DIRECTORIES
            or part in _GENERATED_DIRECTORIES
        ):
            return False
    if name.endswith(".py"):
        return not (
            name.startswith("test_") or name.endswith("_test.py") or name in _TOOL_PYTHON_FILES
        )
    pieces = name.split(".")
    # `a.test.tsx`, `a.spec.js`, `vite.config.ts`, `a.d.ts`: the word before
    # the extension says what the file is.
    return not (len(pieces) > 2 and pieces[-2] in ("test", "spec", "config", "d"))


def _names(value: Any, name: str) -> bool:
    """`value` is the bare or dotted name `name`: `overload`, `typing.overload`."""
    return (
        (isinstance(value, ast.Name) and value.id == name)
        or (isinstance(value, ast.Attribute) and value.attr == name)
    )


def _is_overload(node: ast.AST) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
        _names(decorator, "overload") for decorator in node.decorator_list
    )


def _is_protocol(node: ast.ClassDef) -> bool:
    return any(
        _names(base.value if isinstance(base, ast.Subscript) else base, "Protocol")
        for base in node.bases
    )


def _is_stub(node: ast.stmt) -> bool:
    """A function whose body, past its docstring, is `...`: it never runs."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    return all(
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and (statement.value.value is Ellipsis or isinstance(statement.value.value, str))
        for statement in node.body
    )


def _span(node: ast.stmt) -> range:
    decorators = getattr(node, "decorator_list", [])
    first = min([node.lineno] + [decorator.lineno for decorator in decorators])
    return range(first, (node.end_lineno or node.lineno) + 1)


def _first_inner_line(node: ast.stmt) -> int | None:
    """Where the body of a compound statement starts, or None for a simple
    statement. A `match` holds cases, which carry their line on the pattern."""
    inner = getattr(node, "body", None) or getattr(node, "cases", None)
    if not inner:
        return None
    first = inner[0]
    return first.lineno if hasattr(first, "lineno") else first.pattern.lineno


def python_line_facts(source: str) -> tuple[dict[int, int], set[int]]:
    """What a Python file's syntax says that coverage.py's line lists do not.

    Returns (continuation, type_only). `continuation` maps each later line of
    a multi-line statement to its first line: coverage.py reports the first
    line alone. For a compound statement that is its header, down to its
    body. `type_only` holds the lines that exist for a type checker and never
    do work: the body of `if TYPE_CHECKING:`, an `@overload`, a bare
    annotation, and a Protocol's stub methods.

    Raises SyntaxError when the source does not parse.
    """
    continuation: dict[int, int] = {}
    type_only: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.If) and _names(node.test, "TYPE_CHECKING"):
            for child in node.body:
                type_only.update(_span(child))
        elif _is_overload(node) or (isinstance(node, ast.AnnAssign) and node.value is None):
            type_only.update(_span(node))
        elif isinstance(node, ast.ClassDef) and _is_protocol(node):
            for child in node.body:
                if _is_stub(child):
                    type_only.update(_span(child))
        if isinstance(node, ast.stmt):
            inner = _first_inner_line(node)
            last = inner - 1 if inner is not None else (node.end_lineno or node.lineno)
            for line in range(node.lineno + 1, last + 1):
                continuation[line] = node.lineno
    return continuation, type_only


@dataclass(frozen=True)
class ChangedLineCoverage:
    """What the gate reads (#4436). `total` is the changed executable lines,
    so zero is a framework with nothing to judge (R2), and it can only come
    from a report that was read."""

    covered: int
    total: int
    percent: float
    uncovered: dict[str, list[int]] = field(default_factory=dict)

    @property
    def judged(self) -> bool:
        return self.total > 0


def _python_facts(path: str, source: str) -> tuple[dict[int, int], set[int]]:
    """`python_line_facts`, or CoverageReportError when the source does not
    parse here. The target can run a newer Python than the harness, and then
    its type-only lines cannot be told from real ones, so its denominator
    cannot be established. The tests passed, so that is a measurement that
    could not be read, and never a test gap."""
    try:
        return python_line_facts(source)
    except (SyntaxError, ValueError) as e:
        raise CoverageReportError(
            f"the changed file {path} does not parse under the harness's "
            f"Python, so which of its lines are executable cannot be "
            f"established: {type(e).__name__}: {e}"
        ) from e


def _judged_lines(path: str, lines: set[int], entry: FileLines, root: Path) -> set[int]:
    """The executable lines `lines` comes to in one file: a changed line the
    tool counts, or the first line of the statement it continues."""
    try:
        source = (root / path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise CoverageReportError(
            f"the changed file {path} cannot be read to judge its lines: "
            f"{type(e).__name__}: {e}"
        ) from e
    is_python = path.endswith(".py")
    continuation, type_only = _python_facts(path, source) if is_python else ({}, set())
    continuation = {**entry.continuation, **continuation}
    comment = _PYTHON_COMMENT if is_python else _SCRIPT_COMMENT
    text = source.split("\n")
    judged: set[int] = set()
    for line in lines:
        if line in entry.hits:
            statement = line
        elif line in continuation and line <= len(text):
            written = text[line - 1].strip()
            if not written or written.startswith(comment):
                continue
            statement = continuation[line]
        else:
            continue
        if statement in entry.hits and statement not in type_only:
            judged.add(statement)
    return judged


def judge_changed_lines(
    changed: Mapping[str, set[int]], report: Mapping[str, FileLines], repo_root: Path | str,
) -> ChangedLineCoverage:
    """How many of the run's changed executable lines its tests ran.

    Raises CoverageReportError when a changed file is not in the report: the
    file was not measured, which is not the same as nothing to judge.
    """
    absent = sorted(path for path in changed if path not in report)
    if absent:
        named = ", ".join(sorted(report)[:8]) or "no file at all"
        raise CoverageReportError(
            f"the changed file(s) {', '.join(absent)} do not appear in the "
            f"coverage report, which names {named}. A file no test reaches is "
            f"reported at zero, so one that is absent was not measured: the "
            f"project's coverage configuration omits it, or the report is wrong"
        )
    root = Path(repo_root)
    covered = total = 0
    uncovered: dict[str, list[int]] = {}
    for path in sorted(changed):
        entry = report[path]
        judged = _judged_lines(path, changed[path], entry, root)
        missed = sorted(line for line in judged if not entry.hits[line])
        total += len(judged)
        covered += len(judged) - len(missed)
        if missed:
            uncovered[path] = missed
    return ChangedLineCoverage(
        covered, total, 100.0 * covered / total if total else 0.0, uncovered,
    )


def line_ranges(lines: list[int]) -> list[str]:
    """`[56, 57, 58, 63]` -> `["56-58", "63"]`, the form N4c reads."""
    ranges: list[str] = []
    numbers = sorted(set(lines))
    index = 0
    while index < len(numbers):
        end = index
        while end + 1 < len(numbers) and numbers[end + 1] == numbers[end] + 1:
            end += 1
        first, last = numbers[index], numbers[end]
        ranges.append(str(first) if first == last else f"{first}-{last}")
        index = end + 1
    return ranges


def describe_uncovered(uncovered: Mapping[str, list[int]]) -> str:
    """`pkg/a.py: 12-13, 20; pkg/b.py: 7`, for a log line or a halt."""
    return "; ".join(
        f"{path}: {', '.join(line_ranges(lines))}" for path, lines in sorted(uncovered.items())
    )
