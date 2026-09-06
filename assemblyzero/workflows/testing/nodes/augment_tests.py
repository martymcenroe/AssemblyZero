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
"""

from __future__ import annotations

import re
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
from assemblyzero.workflows.testing.nodes.implementation.routing import (
    select_model_for_file,
)
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
#: path passed it.
AUGMENT_EFFORT = "low"


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


def _line_numbers(ranges: list[str]) -> list[int]:
    """`["56-58", "63"]` -> `[56, 57, 58, 63]`, malformed parts skipped."""
    wanted: list[int] = []
    for part in ranges:
        if "-" in part:
            start, _, end = part.partition("-")
            try:
                wanted.extend(range(int(start), int(end) + 1))
            except ValueError:
                continue
        else:
            try:
                wanted.append(int(part))
            except ValueError:
                continue
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
    neighbours. Falls back to the bare lines when the file does not parse.
    """
    import ast

    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return ""
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
    """Quote the uncovered source so the request names real code, not numbers."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""

    wanted: list[int] = []
    for part in ranges:
        if "-" in part:
            start, _, end = part.partition("-")
            try:
                wanted.extend(range(int(start), int(end) + 1))
            except ValueError:
                continue
        else:
            try:
                wanted.append(int(part))
            except ValueError:
                continue

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
    and reads the outcome lines for the added test names. A file that
    collects nothing drops every addition, with the collection error as
    the reason: the additions broke the file, whatever the cause. Helpers
    and imports the addition carries are kept whenever any test survives.
    The dropped tests' source travels back so a repair pass can name them
    (#2903), and the output carries the coverage report when asked for.
    """
    import ast

    try:
        tree = ast.parse(addition)
    except SyntaxError:
        # fail-open: the caller compiled the merged file before writing it,
        # so this cannot happen; if it did, keeping nothing is the safe side.
        return Vetted("", [("(addition)", "does not parse")], {}, "")
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
            f"pytest ran nothing (exit {result.get('returncode')})",
        )
        return Vetted(
            "", [(name, reason) for name in sorted(test_nodes)],
            {name: _segment(node) for name, node in test_nodes.items()}, output,
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
    """`source` minus the top-level tests named in `names`, and which were removed."""
    import ast

    if not source.strip() or not names:
        return source, []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # fail-open: the caller compiles the merged candidate next and
        # reports a file that does not parse; nothing is hidden by passing
        # the source through unchanged here.
        return source, []
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
    """
    if issue_number is None or not test_files:
        return Path(test_files[0])
    suite = (Path(repo_root) / "tests" / f"test_issue_{issue_number}.py").resolve()
    for candidate in test_files:
        if Path(candidate).resolve() != suite:
            return Path(candidate)
    return Path(test_files[0])


def augment_tests_for_coverage(state: TestingWorkflowState) -> dict[str, Any]:
    """N4c: append tests targeting uncovered lines (#2327).

    Returns to N5 either way. A failure to add tests is reported and leaves
    the suite untouched -- it must never damage a passing suite, and it must
    never route the shortfall to implementation revision.
    """
    gate_log("[N4c] Adding tests for uncovered lines...")

    output = state.get("green_phase_output", "") or ""
    coverage_achieved = float(state.get("coverage_achieved", 0) or 0)
    coverage_target = int(state.get("coverage_target", 90) or 90)
    test_files = state.get("test_files", []) or []
    repo_root = Path(state.get("repo_root", "") or ".")

    if not test_files:
        print("    [N4c] no test file to extend — returning to verification")
        return {"next_node": "N5_verify_green", "error_message": ""}

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
        print(
            "    [N4c] coverage report named no uncovered lines; nothing "
            "specific to target — returning to verification"
        )
        return {"next_node": "N5_verify_green", "error_message": ""}

    targets: dict[str, str] = {}
    for path, ranges in uncovered.items():
        # #2903: the function around the line, not the line alone.
        quoted = _read_context(repo_root / path, ranges)
        if not quoted:
            quoted = ", ".join(ranges)
        targets[path] = quoted

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
        print(f"    [N4c] could not read {test_path}: {err}")
        return {"next_node": "N5_verify_green", "error_message": ""}

    prompt = build_augment_prompt(
        str(test_path), existing, targets, coverage_achieved, coverage_target,
    )

    # #2899: this node saved nothing, so a 3,335-second generation could not
    # be examined afterwards. The prompt and every attempt's response go to
    # the audit dir the way N4's do, and the call carries a ceiling.
    audit_dir = Path(state.get("audit_dir", "") or "")
    audit_ok = bool(state.get("audit_dir")) and audit_dir.is_dir()

    def _audit(name: str, content: str) -> None:
        if audit_ok:
            save_audit_file(audit_dir, next_file_number(audit_dir), name, content)

    _audit("augment-prompt.md", prompt)

    # #2899, the cause: this call went out as bare `opus`, which the CLI runs
    # with extended thinking and no ceiling on it. Reproduced on
    # 2026-09-06 03:40 with run 35's own prompt: sixty `thinking_tokens`
    # events in ninety seconds and not one character of text. Run 34's
    # 187,699 "output" tokens were thinking. N4 routes every file through
    # `select_model_for_file` -- Sonnet by default, Haiku for scaffolds --
    # and its calls return in twenty seconds. N4c now routes the same way.
    model = select_model_for_file(str(test_path))
    print(
        f"    [N4c] generation ceiling {AUGMENT_TIMEOUT_SECONDS:.0f} s per "
        f"attempt, model {model}, effort {AUGMENT_EFFORT} (#2899)"
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
            timeout_seconds=AUGMENT_TIMEOUT_SECONDS, effort=AUGMENT_EFFORT,
        )
        suffix = f"-retry{attempt}" if attempt > 1 else ""
        _audit(f"augment-response{suffix}.md", response or f"(no response: {error})")
        if error or not response:
            print(f"    [N4c] no new tests generated: {error or 'empty response'}")
            return {"next_node": "N5_verify_green", "error_message": ""}

        addition = extract_code_block(response, str(test_path)) or ""
        if not addition.strip():
            print("    [N4c] response contained no code block; suite unchanged")
            return {"next_node": "N5_verify_green", "error_message": ""}

        # Append. Never rewrite: the existing tests are proven to pass, and a
        # regeneration that loses one trades a coverage point for a real test.
        candidate = existing.rstrip() + "\n\n\n" + addition.strip() + "\n"

        try:
            compile(candidate, str(test_path), "exec")
        except SyntaxError as err:
            problems = [f"the file does not parse: {err}"]
        else:
            problems = validate_test_imports(candidate, repo_root)

        if not problems:
            merged = candidate
            break

        for problem in problems:
            print(f"    [N4c] rejected: {problem}")
        if attempt >= MAX_GENERATION_ATTEMPTS:
            print(
                f"    [N4c] {MAX_GENERATION_ATTEMPTS} attempt(s) did not "
                f"produce importable tests; suite left unchanged so the "
                f"passing tests survive"
            )
            return {
                "coverage_augment_attempts": int(
                    state.get("coverage_augment_attempts", 0) or 0
                ) + 1,
                "next_node": "N5_verify_green",
                "error_message": "",
            }

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
    vetted = _keep_passing_additions(
        test_path, existing, addition, repo_root, coverage_module=coverage_module,
    )
    for name, reason in vetted.dropped:
        print(f"    [N4c] dropped {name}: {reason} (#2902)")
    kept = vetted.kept
    last_output = vetted.output

    # #2903: one repair pass. The dropped tests go back with the line that
    # says why each failed; the model corrects those and only those, and the
    # corrections are validated, run and filtered exactly like the first
    # pass. Without this, the second pass repeated the first pass's guess.
    if vetted.dropped and vetted.dropped_source:
        repair_prompt = build_repair_prompt(prompt, vetted.dropped, vetted.dropped_source)
        print(
            f"    [N4c] repair pass for {len(vetted.dropped)} dropped test(s) (#2903)"
        )
        response, error = call_claude_for_file(
            repair_prompt, file_path=str(test_path), model=model,
            timeout_seconds=AUGMENT_TIMEOUT_SECONDS, effort=AUGMENT_EFFORT,
        )
        _audit("augment-response-repair.md", response or f"(no response: {error})")
        repaired = extract_code_block(response or "", str(test_path)) or ""
        base = existing.rstrip() + ("\n\n\n" + kept.strip() if kept.strip() else "")
        # A repair may only answer for the dropped names; a test that repeats a
        # name already in the file would define it twice.
        taken = set(re.findall(r"^def\s+(test_\w+)", base, re.MULTILINE))
        repaired, duplicates = _without_named_tests(repaired, taken)
        for name in duplicates:
            print(f"    [N4c] repair returned {name}, which the file already has; not added (#2903)")
        candidate = base + "\n\n\n" + repaired.strip() + "\n" if repaired.strip() else ""
        problems: list[str] = []
        if candidate:
            try:
                compile(candidate, str(test_path), "exec")
            except SyntaxError as err:
                # fail-open: a repair that does not parse is a rejected repair,
                # not a halt -- the kept tests from the first pass stand, the
                # rejection is printed below with the error, and the file on
                # disk is never the unparseable candidate.
                problems = [f"the file does not parse: {err}"]
            else:
                problems = validate_test_imports(candidate, repo_root)
        if candidate and not problems:
            test_path.write_text(candidate, encoding="utf-8")
            repaired_vetted = _keep_passing_additions(
                test_path, base, repaired, repo_root, coverage_module=coverage_module,
            )
            for name, reason in repaired_vetted.dropped:
                print(f"    [N4c] repair dropped {name}: {reason} (#2903)")
            if repaired_vetted.kept.strip():
                kept = (kept.rstrip() + "\n\n\n" + repaired_vetted.kept.strip() + "\n"
                        if kept.strip() else repaired_vetted.kept)
                last_output = repaired_vetted.output or last_output
                repaired_names = re.findall(r"^def\s+(test_\w+)", repaired_vetted.kept, re.MULTILINE)
                print(f"    [N4c] repair kept {len(repaired_names)} test(s): {', '.join(repaired_names)}")
        elif candidate:
            for problem in problems:
                print(f"    [N4c] repair rejected: {problem}")
        else:
            print("    [N4c] repair pass returned no code; nothing added by it")

    if not kept.strip():
        test_path.write_text(existing, encoding="utf-8")
        print(
            "    [N4c] none of the added tests pass on this machine; suite "
            "left as it was (#2902)"
        )
        return {
            "test_files": [str(p) for p in test_files],
            "coverage_augment_attempts": int(
                state.get("coverage_augment_attempts", 0) or 0
            ) + 1,
            "next_node": "N5_verify_green",
            "error_message": "",
        }
    merged = existing.rstrip() + "\n\n\n" + kept.strip() + "\n"
    test_path.write_text(merged, encoding="utf-8")
    added = len(re.findall(r"^def\s+test_\w+", kept, re.MULTILINE))
    reached, targeted = _reached(uncovered, last_output)
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
