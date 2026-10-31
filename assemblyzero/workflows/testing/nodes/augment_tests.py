"""N4c: add tests for uncovered lines (#2327).

A green-but-under-covered result is a TEST problem wearing an implementation
problem's clothes. Every test passes; the shortfall is in lines no test
reaches. Sending that to implementation revision is not merely useless, it is
dangerous: the cheapest edit that raises statement coverage is to DELETE the
uncovered code, and the uncovered code is typically the error handling the
spec mandates. The loop would be rewarded for removing it, and nothing in the
pipeline would notice.

Measured on boostgauge #7 (`run-issue7-153937`): the spec's own test
functions run against the implementation give 23 passed and 80% coverage
against a 95% gate, with all 19 uncovered statements in error paths that
spec section 11.1 requires the code to have and no requirement asks any test
to reach.

This node adds tests. It never touches implementation files, and it appends
rather than rewriting, so tests already proven to pass cannot be lost.

#3585 (ADR 0236): every failure of this node halts. It used to return to N5
with an empty error_message whatever went wrong, and N5 measured the same
shortfall and sent it back. A failure of the node's machinery (no test file,
an unreadable file or report, no audit dir, no seat, a failed model call, a
vetting run that ran nothing) halts through `_halt_augment_cannot_run`; a
spent allowance (generation attempts, the one repair pass, no added test
passing) through `_halt_augment_spent`. `route_after_augment` sends either
to HALT, which alerts. The suite left on disk always passes: what was there,
plus only the additions that ran and passed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

from assemblyzero.workflows.testing.audit import (
    gate_log,
    next_file_number,
    save_audit_file,
)
from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
    call_claude_for_file,
)
from assemblyzero.workflows.testing.nodes.implementation.parsers import (
    extract_code_block,
)
from assemblyzero.core.seats import resolve
from assemblyzero.workflows.testing.state import TestingWorkflowState
from assemblyzero.workflows.testing.symbol_validator import validate_test_imports

#: Cap on how many uncovered lines to name in one request. Beyond this the
#: prompt stops being a specific instruction and becomes a wish.
MAX_TARGET_LINES = 40

#: #2336: how many times to ask, counting the first. A hallucinated symbol is
#: a near-miss an explicit correction usually fixes; a model that cannot
#: produce an importable file in two tries is not going to on the third, and
#: the passing suite is worth more than another 194-second call.
MAX_GENERATION_ATTEMPTS = 2

#: #2899: the wall-clock ceiling on one coverage generation. The first live
#: N4c call took 194 s for twelve tests; boostgauge run-issue4-021938's took
#: 3,335 s and 187,699 output tokens for nine, and the provider gate has no
#: output-token knob to stop it sooner. Fifteen minutes is five times the
#: honest case; a generation that needs more is not writing tests.
AUGMENT_TIMEOUT_SECONDS = 900

#: #2899, the cause: at the CLI's default effort this prompt is one the model
#: thinks about past the ceiling -- 1,201 events and no text on Opus (run 35),
#: 1,244 on Sonnet (run 36), sixty redacted thinking deltas and no text in a
#: ninety-second probe, and MAX_THINKING_TOKENS=2000 in the environment
#: changed nothing. `--effort low` on the same prompt returned the tests in
#: ten seconds. The provider has carried the flag since #773; nothing on this
#: path passed it. #3563: that `low` now lives in the profile, as the
#: `impl.augment_tests` seat's effort in `claude.toml`; the Gemini transport
#: takes no effort flag.


def parse_uncovered_lines(output: str) -> dict[str, list[str]]:
    """Map source file -> uncovered line ranges from `--cov-report=term-missing`.

    The report's last column is the "Missing" list, e.g. `25-27, 53, 88-89`.
    Rows without one (100% covered files, the TOTAL row) are skipped.
    """
    uncovered: dict[str, list[str]] = {}
    for line in output.splitlines():
        # Name  Stmts  Miss  Cover  Missing
        match = re.match(
            r"^(\S+\.py)\s+\d+\s+\d+\s+\d+%\s+(\S.*)$", line.strip()
        )
        if not match:
            continue
        path, missing = match.group(1), match.group(2).strip()
        if not missing or missing == "-":
            continue
        ranges = [part.strip() for part in missing.split(",") if part.strip()]
        if ranges:
            uncovered[path] = ranges
    return uncovered


class CoverageRangeUnreadable(ValueError):
    """A coverage report's Missing column holds a part that is no line or range."""


class AugmentInvariantBroken(RuntimeError):
    """An addition the node compiled before writing does not parse alone."""


class VettingRanNothing(RuntimeError):
    """The vetting run of the extended file executed no test at all."""


def _line_numbers(ranges: list[str]) -> list[int]:
    """`["56-58", "63"]` -> `[56, 57, 58, 63]`.

    #3585 (ledger 0908, augment_tests.py:101, :106): a malformed part raises
    CoverageRangeUnreadable naming it. It used to be skipped, so the request
    named fewer lines than the report did and nothing said why.
    """
    wanted: list[int] = []
    for part in ranges:
        start, dash, end = part.partition("-")
        try:
            if dash:
                wanted.extend(range(int(start), int(end) + 1))
            else:
                wanted.append(int(part))
        except ValueError as err:
            raise CoverageRangeUnreadable(
                f"the coverage report's Missing column holds {part!r}, which "
                f"is neither a line number nor a range"
            ) from err
    return wanted


#: A function longer than this is quoted as its head plus a window around
#: each uncovered line, not whole (#2903).
_WHOLE_FUNCTION_LIMIT = 120
_CONTEXT_WINDOW = 25
_LOOSE_CONTEXT = 3


def _read_context(path: Path, ranges: list[str]) -> str:
    """Quote each uncovered line inside the function it lives in (#2903).

    `_read_lines` handed the model `56: if value >= band.red:` with no
    signature, no docstring and no `else`, and it asserted `0.0` where
    `normalize` returns `30.0` -- on every pass of run-issue4-041810,
    because nothing on the page said what the function does. Each function
    that holds an uncovered line is quoted once, whole, with line numbers and
    the uncovered lines marked `>>`; a long function gets its head and a
    window around each uncovered line; a line outside any function gets its
    neighbours. Falls back to the bare lines when the file does not parse:
    that is a documented degradation of the quote, not a failure.

    #3585 (ledger 0908, augment_tests.py:134): a source that cannot be read
    raises its OSError, and a malformed range CoverageRangeUnreadable. The
    read used to return "", and the request named bare line numbers with no
    code beside them.
    """
    import ast

    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    wanted = [n for n in _line_numbers(ranges)[:MAX_TARGET_LINES] if 1 <= n <= len(lines)]
    if not wanted:
        return ""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _read_lines(path, ranges)

    functions: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            functions.append((start, node.end_lineno or node.lineno, node.name))

    def _innermost(n: int) -> tuple[int, int, str] | None:
        holding = [f for f in functions if f[0] <= n <= f[1]]
        return min(holding, key=lambda f: f[1] - f[0]) if holding else None

    grouped: dict[tuple[int, int, str], list[int]] = {}
    loose: list[int] = []
    for n in wanted:
        owner = _innermost(n)
        if owner is None:
            loose.append(n)
        else:
            grouped.setdefault(owner, []).append(n)

    marked = set(wanted)

    def _render(numbers: list[int]) -> list[str]:
        return [
            f"{'>>' if n in marked else '  '} {n}: {lines[n - 1]}" for n in numbers
        ]

    blocks: list[str] = []
    for (start, end, name), hits in sorted(grouped.items()):
        header = f"# {name}, lines {start}-{end}; uncovered lines marked >>"
        if end - start + 1 <= _WHOLE_FUNCTION_LIMIT:
            blocks.append("\n".join([header, *_render(list(range(start, end + 1)))]))
            continue
        shown: set[int] = set(range(start, min(start + 8, end) + 1))
        for hit in hits:
            shown.update(range(max(start, hit - _CONTEXT_WINDOW), min(end, hit + _CONTEXT_WINDOW) + 1))
        ordered = sorted(shown)
        out: list[str] = [header]
        previous = None
        for n in ordered:
            if previous is not None and n != previous + 1:
                out.append("   ...")
            out.extend(_render([n]))
            previous = n
        blocks.append("\n".join(out))
    if loose:
        shown = sorted({
            m for n in loose
            for m in range(max(1, n - _LOOSE_CONTEXT), min(len(lines), n + _LOOSE_CONTEXT) + 1)
        })
        out = ["# module level; uncovered lines marked >>"]
        previous = None
        for n in shown:
            if previous is not None and n != previous + 1:
                out.append("   ...")
            out.extend(_render([n]))
            previous = n
        blocks.append("\n".join(out))
    return "\n\n".join(blocks)


def _read_lines(path: Path, ranges: list[str]) -> str:
    """Quote the uncovered source so the request names real code, not numbers.

    #3585 (ledger 0908, augment_tests.py:209, :218, :223): an unreadable
    source raises its OSError, and a malformed range CoverageRangeUnreadable
    (the ranges are read by `_line_numbers`, not a second parser). Both used
    to be skipped.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    wanted = _line_numbers(ranges)

    out: list[str] = []
    for number in wanted[:MAX_TARGET_LINES]:
        if 1 <= number <= len(lines):
            out.append(f"{number}: {lines[number - 1]}")
    return "\n".join(out)


def build_augment_prompt(
    test_file: str,
    existing_tests: str,
    targets: dict[str, str],
    coverage_achieved: float,
    coverage_target: int,
) -> str:
    """Ask for ADDITIONAL tests against named lines, and nothing else."""
    sections = [
        f"The test suite passes in full. Coverage is {coverage_achieved:.1f}% "
        f"against a target of {coverage_target}%.",
        "",
        "Write ADDITIONAL pytest test functions that exercise the uncovered "
        "lines quoted below. The uncovered code is usually error handling and "
        "edge-case branches, so the new tests will mostly drive failure paths: "
        "missing files, malformed input, permission errors, platform branches.",
        "",
        "Rules:",
        "- Do NOT modify the implementation. It is correct; the tests are the gap.",
        "- Do NOT rewrite or restate the existing tests. Emit only NEW functions.",
        "- Every new test must assert real behaviour. Never `assert True`, "
        "never a test that passes without exercising the target line.",
        "- Every test must be able to PASS on the machine running it. #2347: "
        "patching `os.name` or `sys.platform` does not change which `Path` "
        "flavour pathlib builds, so a test that forces a foreign-platform "
        "branch and then touches `Path.home()` raises UnsupportedOperation "
        "and can never pass. To cover a platform branch, patch the thing the "
        "branch actually calls, or skip the test on the wrong platform with "
        "`pytest.mark.skipif` — never write a test the host cannot satisfy.",
        "- Use the same fixtures and import style as the existing tests.",
        "- Give each test a name that says which condition it covers.",
        "",
        f"Test file being extended: {test_file}",
        "",
        "Uncovered lines, by file:",
    ]
    for path, quoted in targets.items():
        sections.append(f"\n--- {path} ---\n{quoted}")

    sections.extend([
        "",
        "Existing tests (for fixtures and import style — do not repeat them):",
        "```python",
        existing_tests[:6000],
        "```",
        "",
        "Return ONLY the new test functions in a single ```python block, with "
        "any imports they need at the top of that block.",
    ])
    return "\n".join(sections)


_OUTCOME_LINE = re.compile(
    r"^(?:FAILED|ERROR)\s+\S+::(?P<name>\w+)(?:\s+-\s+(?P<reason>.*))?$", re.MULTILINE
)


class Vetted(NamedTuple):
    """What running the additions decided (#2902, #2903)."""

    kept: str                          #: the added source, failing tests removed
    dropped: list[tuple[str, str]]     #: (name, first error line)
    dropped_source: dict[str, str]     #: name -> the dropped test's source
    output: str                        #: pytest's output, coverage report included


def _keep_passing_additions(
    test_path: Path, existing: str, addition: str, repo_root: Path,
    coverage_module: str | list[str] | None = None,
) -> Vetted:
    """Run the merged file and keep only the added tests that pass (#2902).

    Runs pytest on the merged file alone -- the file is already written --
    and reads the outcome lines for the added test names. Helpers and imports
    the addition carries are kept whenever any test survives. The dropped
    tests' source travels back so a repair pass can name them (#2903), and
    the output carries the coverage report when asked for.

    #3585 (ledger 0908, augment_tests.py:317, :347): an addition that does
    not parse raises AugmentInvariantBroken (the caller compiled the merged
    file before writing it, so this is a broken invariant, not a verdict on
    the tests). A run that executed no test raises VettingRanNothing with the
    first error line and the exit code: the check could not run, whatever the
    cause. Both used to return "keep nothing", which the node read as "none
    passed" and went back to N5 without a word.
    """
    import ast

    try:
        tree = ast.parse(addition)
    except SyntaxError as err:
        raise AugmentInvariantBroken(
            f"the addition to {test_path} does not parse ({err}), though the "
            f"merged file compiled before it was written"
        ) from err
    lines = addition.splitlines()

    def _segment(node: ast.stmt) -> str:
        start = min(
            [node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]
        )
        return "\n".join(lines[start - 1:(node.end_lineno or node.lineno)])

    test_nodes = {
        node.name: node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }
    if not test_nodes:
        return Vetted(addition, [], {}, "")

    from assemblyzero.workflows.testing.nodes.verify_phases import run_pytest

    result = run_pytest(
        [str(test_path)], coverage_module=coverage_module, repo_root=repo_root,
    )
    output = (result.get("stdout") or "") + "\n" + (result.get("stderr") or "")
    parsed = result.get("parsed") or {}
    ran = int(parsed.get("passed", 0) or 0) + int(parsed.get("failed", 0) or 0) \
        + int(parsed.get("errors", 0) or 0)

    if ran == 0:
        reason = next(
            (line.strip() for line in output.splitlines()
             if re.match(r"(?:E\s+)?[\w.]*(?:Error|Exception)\b\s*:", line.strip())),
            "no error line in pytest's output",
        )
        raise VettingRanNothing(
            f"the vetting run of {test_path} executed no test (exit "
            f"{result.get('returncode')}): {reason}"
        )

    dropped: list[tuple[str, str]] = []
    for match in _OUTCOME_LINE.finditer(output):
        name = match.group("name")
        if name in test_nodes and name not in {n for n, _ in dropped}:
            dropped.append((name, (match.group("reason") or "failed").strip()))
    if not dropped:
        return Vetted(addition, [], {}, output)

    failed_names = {n for n, _ in dropped}
    dropped_source = {name: _segment(test_nodes[name]) for name in failed_names}
    kept_segments = [
        _segment(node) for node in tree.body
        if not (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in failed_names
        )
    ]
    survivors = [name for name in test_nodes if name not in failed_names]
    if not survivors:
        return Vetted("", dropped, dropped_source, output)
    return Vetted("\n\n\n".join(kept_segments) + "\n", dropped, dropped_source, output)


def _without_named_tests(source: str, names: set[str]) -> tuple[str, list[str]]:
    """`source` minus the top-level tests named in `names`, and which were removed.

    Nothing to remove (no source, no names, or no name matching) returns the
    source unchanged; that is the answer, not a failure.

    #3585 (ledger 0908, augment_tests.py:389): a source that does not parse
    raises its SyntaxError. It used to pass through unchanged, trusting a
    later compile to reject it; the node now rejects an unparseable repair
    before it gets here.
    """
    import ast

    if not source.strip() or not names:
        return source, []
    tree = ast.parse(source)
    lines = source.splitlines()
    removed: list[str] = []
    segments: list[str] = []
    for node in tree.body:
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        segment = "\n".join(lines[start - 1:(node.end_lineno or node.lineno)])
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            removed.append(node.name)
            continue
        segments.append(segment)
    if not removed:
        return source, []
    return "\n\n\n".join(segments) + "\n", removed


def build_repair_prompt(
    original_prompt: str, dropped: list[tuple[str, str]], dropped_source: dict[str, str],
) -> str:
    """Send back the tests that failed, with the line that says why (#2903).

    A second pass with no memory of the first repeats the first: every pass
    of run-issue4-041810 asserted `0.0` where `normalize` returns `30.0`.
    The failing tests and their first error line are the one thing the
    model did not have.
    """
    parts = [
        original_prompt,
        "",
        "=" * 60,
        "Your previous attempt was RUN on this machine. The tests below FAILED "
        "and were removed; the rest were accepted and are already in the file.",
        "",
    ]
    for name, reason in dropped:
        parts.append(f"- {name}: {reason}")
    parts.extend([
        "",
        "Their source:",
        "```python",
        "\n\n\n".join(dropped_source.get(name, "") for name, _ in dropped)[:6000],
        "```",
        "",
        "Write corrected versions of ONLY these tests, against the code quoted "
        "above and the error each one produced. Keep the name when the intent "
        "stands; rename when it changes. A test that cannot be made to pass on "
        "this machine is omitted, never forced. Return ONLY the corrected test "
        "functions in a single ```python block, with any imports they need at "
        "the top of that block.",
    ])
    return "\n".join(parts)


def _reached(before: dict[str, list[str]], output: str) -> tuple[int, int]:
    """(uncovered lines the vetting run reached, uncovered lines targeted) (#2903)."""
    def _posix(path: str) -> str:
        return path.replace("\\", "/")

    targeted = {
        (_posix(path), n) for path, ranges in before.items() for n in _line_numbers(ranges)
    }
    if not targeted or not output:
        return 0, len(targeted)
    after = {_posix(path): ranges for path, ranges in parse_uncovered_lines(output).items()}
    still = {
        (path, n) for path, ranges in after.items() for n in _line_numbers(ranges)
    }
    # A file the report names at all was measured; one it does not name was
    # not, and its lines are not "reached" -- they were never looked at.
    report = _posix(output)
    measured = set(after) | {path for path, _ in targeted if path in report}
    reached = {
        (path, n) for path, n in targeted
        if path in measured and (path, n) not in still
    }
    return len(reached), len(targeted)


def build_revision_prompt(
    original_prompt: str, rejected: str, problems: list[str],
) -> str:
    """Re-ask, naming exactly what was wrong (#2336).

    The rejected code is included because the failure is nearly always a
    single wrong name in an otherwise usable file -- asking for a fresh start
    would discard work that was substantially correct.
    """
    return "\n".join([
        original_prompt,
        "",
        "=" * 60,
        "Your previous attempt was REJECTED before it ran. Problems:",
        *(f"  - {problem}" for problem in problems),
        "",
        "Fix exactly those problems. Import only names that exist in the "
        "module. Keep everything else about the tests the same -- the rest of "
        "the previous attempt was accepted.",
        "",
        "Previous attempt:",
        "```python",
        rejected[:6000],
        "```",
    ])


def coverage_target_file(
    test_files: list[str], repo_root: Path, issue_number: int | None,
) -> Path:
    """The file N4c appends to: the first plan-owned test file (#2908).

    Never the spec's suite while there is any other. The scaffold re-emits
    `tests/test_issue_<N>.py` from the spec on every resume (#2709 keeps it
    as the contract), so an addition there lasts exactly until the next
    resume: run-issue4-131639 measured 38 of the 51 tests run 39 left,
    because run 39's N4c had appended its thirteen to the suite. A
    plan-owned file survives a resume (#2897 registers it) and #2905 keeps
    its passing tests as written. Without an issue number the suite cannot
    be named, and the first file stands as before; with only the suite in
    the list, the suite is the only place there is.

    #4246: only a Python test file is a candidate. This node writes pytest
    functions, and in a run with a Vitest suite too the first plan-owned
    test file can be a `.test.ts`.
    """
    python = [f for f in test_files if str(f).endswith(".py")]
    test_files = python or test_files
    if issue_number is None or not test_files:
        return Path(test_files[0])
    suite = (Path(repo_root) / "tests" / f"test_issue_{issue_number}.py").resolve()
    for candidate in test_files:
        if Path(candidate).resolve() != suite:
            return Path(candidate)
    return Path(test_files[0])


def _halt_gap_not_augmentable(state: TestingWorkflowState, framework: str) -> dict[str, Any]:
    """N4c's halt for a coverage gap in a suite it cannot add tests to
    (#4246). Routed to HALT by `route_after_augment`, which alerts. Sending
    the gap to the coder instead is what #2327 forbids: the cheapest edit
    that raises coverage is deleting the code no test reaches."""
    achieved = float(state.get("coverage_achieved", 0) or 0)
    target = state.get("coverage_target", 90)
    message = (
        f"[N4c] the {framework} suite's coverage is {achieved:.1f}% against "
        f"a target of {target}%, and N4c adds pytest tests only: it cannot "
        f"add {framework} tests for the uncovered lines. The run stops here "
        f"rather than send a test gap to implementation (#2327, #4246)."
    )
    print(f"ERROR {message}", file=sys.stderr)
    return {"next_node": "end", "error_message": message}


def _halt_augment_cannot_run(reason: str) -> dict[str, Any]:
    """N4c's halt when its own machinery fails (#3585). Said at ERROR on
    stderr; routed to HALT by `route_after_augment`, which alerts."""
    print(f"ERROR [N4c] N4c cannot add tests: {reason}", file=sys.stderr)
    return {"next_node": "end", "error_message": f"[N4c] N4c cannot add tests: {reason}"}


def _halt_augment_spent(reason: str) -> dict[str, Any]:
    """N4c's halt when an allowance is spent (#3585): the generation
    attempts, the one repair pass, or every added test failing. Said at ERROR
    on stderr; routed to HALT by `route_after_augment`, which alerts."""
    print(f"ERROR [N4c] Coverage test additions spent: {reason}", file=sys.stderr)
    return {"next_node": "end", "error_message": f"Coverage test additions spent: {reason}"}


def _parse_failure(err: SyntaxError) -> list[str]:
    """The rejection for a candidate that does not parse."""
    return [f"the file does not parse: {err}"]


def _candidate_failures(candidate: str, test_path: Path, repo_root: Path) -> list[str]:
    """Why `candidate` may not be written: it does not parse, or an import
    names nothing (#2336). [] when it may."""
    try:
        compile(candidate, str(test_path), "exec")
    except SyntaxError as err:
        return _parse_failure(err)
    return validate_test_imports(candidate, repo_root)


def _restore_passing(test_path: Path, existing: str, kept: str) -> None:
    """Put back the suite that passes: what was there, plus the kept tests."""
    if kept.strip():
        test_path.write_text(existing.rstrip() + "\n\n\n" + kept.strip() + "\n", encoding="utf-8")
    else:
        test_path.write_text(existing, encoding="utf-8")


def augment_tests_for_coverage(state: TestingWorkflowState) -> dict[str, Any]:
    """N4c: append tests targeting uncovered lines (#2327).

    Returns to N5 when tests were added. #3585: any failure halts, with the
    reason in error_message; it used to return to N5 with none. Either way it
    must never damage a passing suite, and it must never route the shortfall
    to implementation revision.
    """
    gate_log("[N4c] Adding tests for uncovered lines...")

    # #4246: N5 routes every framework's coverage shortfall here, never to
    # the coder. This node reads pytest-cov's term-missing report and writes
    # and vets pytest functions, so a gap in any other framework's suite is
    # one it cannot fill. A state with no framework named is from before
    # #4246, when only pytest's shortfall came here.
    gap = state.get("coverage_gap_framework") or "pytest"
    if gap != "pytest":
        return _halt_gap_not_augmentable(state, gap)

    output = state.get("green_phase_output", "") or ""
    coverage_achieved = float(state.get("coverage_achieved", 0) or 0)
    coverage_target = int(state.get("coverage_target", 90) or 90)
    test_files = state.get("test_files", []) or []
    repo_root = Path(state.get("repo_root", "") or ".")

    if not test_files:
        # #3585 (ledger 0908, augment_tests.py:537)
        return _halt_augment_cannot_run(
            f"the run has no test file to extend, with coverage "
            f"{coverage_achieved:.1f}% against a target of {coverage_target}%"
        )

    # #2637: read the report ONCE, through the accessor N5 also uses. This
    # branch used to render an ABSENT target as "no uncovered lines" -- an
    # all-clear -- while N5 rendered the same empty report as "0.0%" and
    # routed here. Neither had measured anything, and the two bounced until a
    # stagnation halt blamed the LLD and spec.
    from assemblyzero.workflows.testing.coverage_report import read_coverage

    reading = read_coverage(output, state.get("coverage_module", "") or "")
    if not reading.measured:
        print(f"    [N4c] {reading.failure_message()}")
        return {"next_node": "end", "error_message": reading.failure_message()}

    uncovered = reading.uncovered
    if not uncovered:
        # #3585 (ledger 0908, augment_tests.py:554): it returned to N5, which
        # measured the same shortfall and sent it back, uncounted.
        return _halt_augment_cannot_run(
            f"coverage is {coverage_achieved:.1f}% against a target of "
            f"{coverage_target}%, and the coverage report names no uncovered "
            f"line to target"
        )

    # #2899's record of the prompt and every response. #3585 (ledger 0908,
    # augment_tests.py:593): with no audit dir the writes were skipped
    # silently, so a generation could not be examined afterwards.
    audit_dir = Path(state.get("audit_dir", "") or "")
    if not state.get("audit_dir") or not audit_dir.is_dir():
        return _halt_augment_cannot_run(
            f"the audit directory {state.get('audit_dir', '')!r} is not a "
            f"directory, so the prompt and responses would not be kept"
        )

    targets: dict[str, str] = {}
    try:
        for path, ranges in uncovered.items():
            # #2903: the function around the line, not the line alone.
            quoted = _read_context(repo_root / path, ranges)
            if not quoted:
                quoted = ", ".join(ranges)
            targets[path] = quoted
    except (OSError, CoverageRangeUnreadable) as err:
        # #3585 (ledger 0908, augment_tests.py:101, :106, :134, :209)
        return _halt_augment_cannot_run(
            f"the uncovered source could not be quoted: "
            f"{type(err).__name__}: {err}"
        )

    total_lines = sum(len(r) for r in uncovered.values())
    print(
        f"    [N4c] {coverage_achieved:.1f}% vs {coverage_target}% target; "
        f"targeting uncovered lines in {len(uncovered)} file(s)"
    )
    for path, ranges in uncovered.items():
        print(f"      {path}: {', '.join(ranges)}")

    test_path = coverage_target_file(test_files, repo_root, state.get("issue_number"))
    print(f"    [N4c] appending to {test_path.name} (#2908)")
    try:
        existing = test_path.read_text(encoding="utf-8")
    except OSError as err:
        # #3585 (ledger 0908, augment_tests.py:581)
        return _halt_augment_cannot_run(
            f"the test file {test_path} could not be read: "
            f"{type(err).__name__}: {err}"
        )

    prompt = build_augment_prompt(
        str(test_path), existing, targets, coverage_achieved, coverage_target,
    )

    # #2899: this node saved nothing, so a 3,335-second generation could not
    # be examined afterwards. The prompt and every attempt's response go to
    # the audit dir the way N4's do, and the call carries a ceiling.
    def _audit(name: str, content: str) -> None:
        save_audit_file(audit_dir, next_file_number(audit_dir), name, content)

    _audit("augment-prompt.md", prompt)

    # #2899, the cause: this call went out as bare `opus`, which the CLI runs
    # with extended thinking and no ceiling on it. Reproduced on
    # 2026-09-06 03:40 with run 35's own prompt: sixty `thinking_tokens`
    # events in ninety seconds and not one character of text. Run 34's
    # 187,699 "output" tokens were thinking. N4 routes every file through
    # `select_model_for_file` -- Sonnet by default, Haiku for scaffolds --
    # and its calls return in twenty seconds. N4c routed the same way, with
    # `--effort low`. #3563: N4c is now its own seat, `impl.augment_tests`,
    # and the profile carries both its model and that effort (`claude.toml`
    # keeps `claude:sonnet` at `low`).
    try:
        seat = resolve(state, "impl.augment_tests")
    except ValueError as err:
        # #3585 (ledger 0908, augment_tests.py:613)
        return _halt_augment_cannot_run(
            f"the impl.augment_tests seat could not be resolved: {err}"
        )
    model = seat.spec
    effort = seat.effort
    print(
        f"    [N4c] generation ceiling {AUGMENT_TIMEOUT_SECONDS:.0f} s per "
        f"attempt, model {model}, effort {effort} (#2899)"
    )

    # #2336: validate BEFORE writing, and revise in place.
    #
    # The first live N4c run spent 194s producing 12 good tests whose import
    # block asked for `default_config_path` when the module exports
    # `get_default_config_path`. One name in one shared import statement, so
    # collection died for the whole file: the 23 tests already passing were
    # destroyed along with the 12 new ones, and the stage ended. Correcting
    # only that name gives 34 passed and 100% coverage on the target module.
    #
    # Validating before the write is what makes "tests already passing are
    # never destroyed by a later addition" absolute rather than likely: a
    # file that does not import cleanly is never written at all.
    merged = ""
    addition = ""
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        response, error = call_claude_for_file(
            prompt, file_path=str(test_path), model=model,
            timeout_seconds=AUGMENT_TIMEOUT_SECONDS, effort=effort,
            seat="impl.augment_tests",  # #3577: the call record names this seat
        )
        suffix = f"-retry{attempt}" if attempt > 1 else ""
        _audit(f"augment-response{suffix}.md", response or f"(no response: {error})")
        if error or not response:
            # #3585 (ledger 0908, augment_tests.py:645): the provider's error
            # used to be printed and dropped, with no attempt counted.
            return _halt_augment_cannot_run(
                f"the generation call ({model}) failed on attempt {attempt}: "
                f"{error or 'empty response'}; the suite is unchanged"
            )

        addition = extract_code_block(response, str(test_path)) or ""
        if not addition.strip():
            # #3585 (ledger 0908, augment_tests.py:650): a reply with no code
            # is a rejected attempt, revised like any other, not a quiet
            # return to N5.
            problems = ["the response contained no ```python code block"]
        else:
            # Append. Never rewrite: the existing tests are proven to pass,
            # and a regeneration that loses one trades a coverage point for a
            # real test.
            candidate = existing.rstrip() + "\n\n\n" + addition.strip() + "\n"
            problems = _candidate_failures(candidate, test_path, repo_root)
            if not problems:
                merged = candidate
                break

        for problem in problems:
            print(f"    [N4c] rejected: {problem}")
        if attempt >= MAX_GENERATION_ATTEMPTS:
            # #3585 (ledger 0908, augment_tests.py:671): it returned to N5 as
            # a skip.
            return _halt_augment_spent(
                f"{MAX_GENERATION_ATTEMPTS} generation attempt(s) for "
                f"{test_path.name} produced no tests that can be written: "
                f"{'; '.join(problems)}; the suite is unchanged"
            )

        print(f"    [N4c] revising (attempt {attempt + 1}/{MAX_GENERATION_ATTEMPTS})")
        prompt = build_revision_prompt(prompt, addition, problems)

    test_path.write_text(merged, encoding="utf-8")

    # #2902: run what was added, keep what passes. The node's own premise is
    # that the implementation is correct and the tests are the gap, so an
    # addition that fails is a wrong test -- and one that faults the
    # interpreter (run-issue4-040614: two of nine, `OSError: exception:
    # access violation` under a null-buffer mock of the native call) is not
    # a test at all. Appended unverified, they became the contract and N4
    # was sent to fix collector.py for failures no edit of it can touch.
    coverage_module = state.get("coverage_module") or None
    try:
        vetted = _keep_passing_additions(
            test_path, existing, addition, repo_root, coverage_module=coverage_module,
        )
    except VettingRanNothing as err:
        # #3585 (ledger 0908, augment_tests.py:347): the check could not run.
        test_path.write_text(existing, encoding="utf-8")
        return _halt_augment_cannot_run(
            f"{err}; the additions are removed and the suite is as it was"
        )
    except AugmentInvariantBroken:
        test_path.write_text(existing, encoding="utf-8")
        raise
    # #3585 (ledger 0908, augment_tests.py:701): a dropped test is a failed
    # test, said at ERROR; the ones that pass are kept.
    for name, reason in vetted.dropped:
        print(f"ERROR [N4c] dropped {name}: {reason} (#2902)", file=sys.stderr)
    kept = vetted.kept
    last_output = vetted.output
    dropped_names = {name for name, _ in vetted.dropped}

    # #2903: one repair pass. The dropped tests go back with the line that
    # says why each failed; the model corrects those and only those, and the
    # corrections are validated, run and filtered exactly like the first
    # pass. Without this, the second pass repeated the first pass's guess.
    # #3585 (ledger 0908, augment_tests.py:721, :734, :755): a repair that
    # cannot be made (the call failed, no code, it does not parse, it imports
    # nothing real, or it only repeats tests the file has) halts. Each used
    # to be printed and passed over. The suite left on disk is what was
    # there plus the first pass's passing tests.
    if vetted.dropped and vetted.dropped_source:
        repair_prompt = build_repair_prompt(prompt, vetted.dropped, vetted.dropped_source)
        print(
            f"    [N4c] repair pass for {len(vetted.dropped)} dropped test(s) (#2903)"
        )
        response, error = call_claude_for_file(
            repair_prompt, file_path=str(test_path), model=model,
            timeout_seconds=AUGMENT_TIMEOUT_SECONDS, effort=effort,
            seat="impl.augment_tests",  # #3577: the call record names this seat
        )
        _audit("augment-response-repair.md", response or f"(no response: {error})")
        if error or not response:
            _restore_passing(test_path, existing, kept)
            return _halt_augment_cannot_run(
                f"the repair call ({model}) failed: {error or 'empty response'}; "
                f"the suite keeps only the additions that passed"
            )
        repaired = extract_code_block(response, str(test_path)) or ""
        base = existing.rstrip() + ("\n\n\n" + kept.strip() if kept.strip() else "")
        # A repair may only answer for the dropped names; a test that repeats a
        # name already in the file would define it twice.
        taken = set(re.findall(r"^def\s+(test_\w+)", base, re.MULTILINE))
        try:
            repaired, duplicates = _without_named_tests(repaired, taken)
        except SyntaxError as err:
            _restore_passing(test_path, existing, kept)
            return _halt_augment_spent(
                f"the repair pass's code does not parse ({err}); the suite keeps "
                f"only the additions that passed"
            )
        for name in duplicates:
            print(f"    [N4c] repair returned {name}, which the file already has; not added (#2903)")
        if not repaired.strip():
            _restore_passing(test_path, existing, kept)
            return _halt_augment_spent(
                "the repair pass returned no new test (no ```python code block, "
                "or only tests the file already has); the suite keeps only the "
                "additions that passed"
            )
        candidate = base + "\n\n\n" + repaired.strip() + "\n"
        problems = _candidate_failures(candidate, test_path, repo_root)
        if problems:
            _restore_passing(test_path, existing, kept)
            return _halt_augment_spent(
                f"the repair pass was rejected: {'; '.join(problems)}; the suite "
                f"keeps only the additions that passed"
            )
        test_path.write_text(candidate, encoding="utf-8")
        try:
            repaired_vetted = _keep_passing_additions(
                test_path, base, repaired, repo_root, coverage_module=coverage_module,
            )
        except VettingRanNothing as err:
            _restore_passing(test_path, existing, kept)
            return _halt_augment_cannot_run(
                f"{err}; the suite keeps only the first pass's additions that passed"
            )
        except AugmentInvariantBroken:
            _restore_passing(test_path, existing, kept)
            raise
        for name, reason in repaired_vetted.dropped:
            print(f"ERROR [N4c] repair dropped {name}: {reason} (#2903)", file=sys.stderr)
        dropped_names |= {name for name, _ in repaired_vetted.dropped}
        if repaired_vetted.kept.strip():
            kept = (kept.rstrip() + "\n\n\n" + repaired_vetted.kept.strip() + "\n"
                    if kept.strip() else repaired_vetted.kept)
            last_output = repaired_vetted.output or last_output
            repaired_names = re.findall(r"^def\s+(test_\w+)", repaired_vetted.kept, re.MULTILINE)
            print(f"    [N4c] repair kept {len(repaired_names)} test(s): {', '.join(repaired_names)}")

    if not kept.strip():
        # #3585 (ledger 0908, augment_tests.py:761): it returned to N5 with no
        # error, and N5 sent the same shortfall back.
        test_path.write_text(existing, encoding="utf-8")
        return _halt_augment_spent(
            f"none of the {len(dropped_names)} added test(s) pass on this "
            f"machine, after the repair pass; the suite is as it was (#2902)"
        )
    merged = existing.rstrip() + "\n\n\n" + kept.strip() + "\n"
    test_path.write_text(merged, encoding="utf-8")
    added = len(re.findall(r"^def\s+test_\w+", kept, re.MULTILINE))
    still_dropped = dropped_names - set(re.findall(r"^def\s+(test_\w+)", kept, re.MULTILINE))
    if still_dropped:
        print(
            f"ERROR [N4c] {len(still_dropped)} added test(s) failed and were "
            f"dropped: {', '.join(sorted(still_dropped))} (#2902)",
            file=sys.stderr,
        )
    try:
        reached, targeted = _reached(uncovered, last_output)
    except CoverageRangeUnreadable as err:
        return _halt_augment_cannot_run(
            f"the vetting run's coverage report could not be read: {err}; the "
            f"{added} added test(s) that passed are in {test_path.name}"
        )
    print(
        f"    [N4c] added {added} test(s) targeting {total_lines} uncovered "
        f"range(s); the vetting run reached {reached} of {targeted} uncovered "
        f"line(s) (#2903)"
    )

    # #2900: the list this node was given, with the extended file still in its
    # place. It used to hand back `[test_path]` alone -- on run-issue4-021938
    # that dropped the plan's three test files (25 tests) from the next
    # measurement, N5 read 20 of 22 as a regression against 38, the
    # best-iteration restore put the pre-N4c scaffold back, and the nine tests
    # this call had just spent 3,335 s producing were gone.
    return {
        "test_files": [str(p) for p in test_files],
        "generated_tests": merged,
        "coverage_augment_attempts": int(
            state.get("coverage_augment_attempts", 0) or 0
        ) + 1,
        "next_node": "N5_verify_green",
        "error_message": "",
    }
