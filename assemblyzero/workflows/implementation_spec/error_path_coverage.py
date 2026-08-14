"""Error paths a spec mandates and never tests (#2333).

The spec stage reports requirement coverage. A spec can be complete by that
measure, internally consistent, and structurally unable to clear the statement
coverage gate it is graded against two stages later.

run-issue7-153937 is the exhibit. Its Section 10.1 supplies twenty-three tests,
all passing, and its own Section 11.1 mandates an error-handling convention no
test reaches. Measured against the implementation the pipeline produced, with
the flags N5 uses:

    boostgauge.config    45 statements, 10 missed, 78%
    boostgauge (both)    95 statements, 19 missed, 80%

The gate is 95 percent. Every missed statement is an error path or a platform
branch. The spec reported ``Coverage: 100.0% (22/22 requirements)``, which was
true and said nothing about any of them.

What this checks, and what it cannot
------------------------------------

Two gaps here are decidable by reading the spec, and both were real in that
run:

1. **An exception type the spec's own code raises, with no test asserting it.**
   spec-0007 raises ``FileNotFoundError`` once and ``ValueError`` twice, and
   writes a single ``pytest.raises(ValueError)``. The unasserted
   ``FileNotFoundError`` is ``config.py`` line 53 in the coverage report.
2. **A platform branch with no test that varies the platform.** spec-0007
   branches on ``os.name`` once and no test mentions it. Those are lines 25
   through 27 of the same report.

A third gap is real and NOT decidable here. Reaching an ``except`` handler
needs a test that constructs the failure, and no lexical signal says whether
one does. Handlers are therefore counted and disclosed, never failed. Guessing
would produce findings this module cannot defend, and a check that cries wolf
is one the drafter learns to skip.

Nothing here measures statement coverage. It finds specific error paths that
provably have no test, which is a lower bound on the gap and enough to stop a
requirement-complete spec from reaching implementation with an unreachable
gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from assemblyzero.workflows.implementation_spec.criteria_coverage import (
    _CODE_FENCE,
    _TEST_DEF,
)

#: An exception type raised by the spec's implementation code.
_RAISE = re.compile(r"\braise\s+([A-Z][A-Za-z0-9_]*)")

#: An exception type a test asserts. Both the pytest form and the unittest one,
#: because specs in this fleet have used each.
_ASSERTED = re.compile(
    r"(?:pytest\.raises|assertRaises)\s*\(\s*([A-Z][A-Za-z0-9_]*)"
)

#: A branch on the host platform. These are the three spellings the fleet's
#: specs use; each produces a branch only one platform ever executes.
_PLATFORM = re.compile(r"\b(os\.name|sys\.platform|platform\.system)\b")

#: A test that varies the platform. `patch("os.name")` is caught by the pattern
#: above, since the target is a string holding the dotted name. The monkeypatch
#: form splits the module from the attribute -- `setattr(os, "name", "nt")` --
#: so the dotted name never appears and it needs its own pattern. Missing it
#: would report a covered branch as uncovered, which is the false alarm this
#: module is otherwise built to avoid.
_PLATFORM_PATCHED = re.compile(
    r"setattr\(\s*(?:os|sys|platform)\s*,\s*['\"](?:name|platform|system)['\"]"
)

_EXCEPT = re.compile(r"(?m)^[ \t]*except\b")

#: Raised to signal control flow rather than an error condition, so a test can
#: exercise the path without asserting the type. StopIteration ends a generator
#: and SystemExit is argparse's normal exit, which a test asserts by exit code.
_CONTROL_FLOW = frozenset({"StopIteration", "SystemExit", "GeneratorExit", "KeyboardInterrupt"})


@dataclass
class ErrorPathReport:
    """Which mandated error paths have a test, and which provably do not."""

    ran: bool = False
    reason: str = ""
    raised: dict[str, int] = field(default_factory=dict)
    asserted: set[str] = field(default_factory=set)
    untested: list[str] = field(default_factory=list)
    platform_branches: int = 0
    platform_tested: bool = False
    handlers: int = 0
    test_count: int = 0

    @property
    def ok(self) -> bool:
        return not self.untested and not self.platform_gap

    @property
    def platform_gap(self) -> bool:
        return self.platform_branches > 0 and not self.platform_tested


def split_fences(spec: str) -> tuple[str, str]:
    """(implementation code, test code) from the spec's fenced blocks.

    A fence holding a ``def test_`` is test code and the rest is
    implementation. Classification is per fence rather than per function
    because a spec snippet is frequently not a valid standalone module, which
    is the same reason `spec_tests` does not parse them.
    """
    implementation, tests = [], []
    for fence in _CODE_FENCE.findall(spec):
        (tests if _TEST_DEF.search(fence) else implementation).append(fence)
    return "\n".join(implementation), "\n".join(tests)


def error_path_coverage(spec: str) -> ErrorPathReport:
    """Error paths the spec mandates, against the tests it writes for them."""
    code, tests = split_fences(spec)
    if not code.strip():
        return ErrorPathReport(
            ran=False,
            reason="the spec carries no implementation code fence to read",
        )

    raised: dict[str, int] = {}
    for name in _RAISE.findall(code):
        if name not in _CONTROL_FLOW:
            raised[name] = raised.get(name, 0) + 1

    asserted = set(_ASSERTED.findall(tests))
    platform_branches = len(_PLATFORM.findall(code))

    return ErrorPathReport(
        ran=True,
        raised=raised,
        asserted=asserted,
        untested=sorted(name for name in raised if name not in asserted),
        platform_branches=platform_branches,
        platform_tested=bool(
            _PLATFORM.search(tests) or _PLATFORM_PATCHED.search(tests)
        ),
        handlers=len(_EXCEPT.findall(code)),
        test_count=len(_TEST_DEF.findall(tests)),
    )


def format_report(report: ErrorPathReport) -> str:
    """The failure text the drafter reads. Every gap named in one pass.

    The disclosure at the end is the point of the check as much as the
    failures are. Requirement coverage and statement coverage are different
    numbers, and the spec stage reported only the first as though it settled
    the second.
    """
    if not report.ran:
        return f"Error-path coverage not applicable: {report.reason}."

    lines: list[str] = []

    if report.untested:
        lines.append(
            f"{len(report.untested)} exception type(s) the spec raises have no "
            f"test asserting them. Section 10 owes each a test:"
        )
        for name in report.untested:
            times = report.raised[name]
            occurrence = "once" if times == 1 else f"{times} times"
            lines.append(
                f"  - {name}: raised {occurrence} by the spec's own code, and no "
                f"test uses pytest.raises({name})"
            )

    if report.platform_gap:
        lines.append(
            f"{report.platform_branches} platform branch(es) in the spec's code, "
            f"and no test varies the platform. One side of each branch cannot "
            f"execute on the machine the gate runs on."
        )

    if not lines:
        covered = len(report.raised)
        lines.append(
            f"Every error path the spec mandates has a test: {covered} exception "
            f"type(s) raised, {covered} asserted, across {report.test_count} test(s)."
        )

    lines.append(
        f"Not measured here: statement coverage. This spec's code carries "
        f"{report.handlers} except handler(s), and whether a test reaches one "
        f"cannot be read from the text. Requirement coverage is a different "
        f"number from statement coverage and does not predict it."
    )
    return "\n".join(lines)
