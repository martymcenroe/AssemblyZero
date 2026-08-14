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
from typing import Any

from assemblyzero.workflows.testing.audit import gate_log
from assemblyzero.workflows.testing.nodes.implementation.claude_client import (
    call_claude_for_file,
)
from assemblyzero.workflows.testing.nodes.implementation.parsers import (
    extract_code_block,
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

    uncovered = parse_uncovered_lines(output)
    if not uncovered:
        print(
            "    [N4c] coverage report named no uncovered lines; nothing "
            "specific to target — returning to verification"
        )
        return {"next_node": "N5_verify_green", "error_message": ""}

    targets: dict[str, str] = {}
    for path, ranges in uncovered.items():
        quoted = _read_lines(repo_root / path, ranges)
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

    test_path = Path(test_files[0])
    try:
        existing = test_path.read_text(encoding="utf-8")
    except OSError as err:
        print(f"    [N4c] could not read {test_path}: {err}")
        return {"next_node": "N5_verify_green", "error_message": ""}

    prompt = build_augment_prompt(
        str(test_path), existing, targets, coverage_achieved, coverage_target,
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
        response, error = call_claude_for_file(prompt, file_path=str(test_path))
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
    added = len(re.findall(r"^def\s+test_\w+", addition, re.MULTILINE))
    print(f"    [N4c] added {added} test(s) targeting {total_lines} uncovered range(s)")

    return {
        "test_files": [str(test_path)],
        "generated_tests": merged,
        "coverage_augment_attempts": int(
            state.get("coverage_augment_attempts", 0) or 0
        ) + 1,
        "next_node": "N5_verify_green",
        "error_message": "",
    }
