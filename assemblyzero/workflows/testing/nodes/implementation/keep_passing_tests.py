"""A passing test is the contract; a revision keeps it as written (#2905).

boostgauge #4, `run-issue4-042724` (2026-09-06 04:27): N4c had taken coverage
from 91 % to 99 % and left two of its thirteen tests failing. Fixing those
two, N4's edit script patched `tests/unit/test_collector.py` in iterations 2
and 4 (`Applied 2 edit(s); 97% preserved`, `Applied 3 edit(s); 98% preserved`)
and the patches rewrote assertions of tests that were passing: `test_req_13`
went from `pytest.raises(NotImplementedError)` to `pytest.raises(OSError)`,
req_9 and req_10 gained a `WindowsCollector(ntdll=mock)` the constructor never
had. Each per-file call sees only its file and the failure corpus (#2851), so
the test file's call could not know the implementation's call had added
`nt_query=` instead. The loop measured 49 -> 47 -> 48 of 51 and ran out at
the cap, three tests below where it started.

#2064's freeze holds the tests for the one iteration after a repeated failing
set; #2866 stops a *failed* patch from regenerating a test file. Neither speaks
to a patch that succeeds and changes a passing test. This does: in a revision,
every test that passed at the measurement the worktree reflects is kept byte
for byte -- decorators included -- and one the patch deleted comes back. The
failing tests, and any new ones, are the patch's to change. The implementation
conforms to the passing tests, never the reverse.
"""

from __future__ import annotations

import ast
import re
from typing import NamedTuple

#: A `-v` outcome line: `tests/unit/test_x.py::TestA::test_b[case] PASSED [ 12%]`.
_VERBOSE_PASSED = re.compile(r"^(?P<nodeid>\S+::\S+)\s+PASSED\b", re.MULTILINE)


def passing_test_names(pytest_output: str) -> set[str]:
    """Bare names of the tests a `-v` run reported PASSED.

    The same bare form `_extract_failed_test_names` uses for failures:
    `tests/unit/test_x.py::TestA::test_b[case] PASSED` -> `test_b`.
    """
    names: set[str] = set()
    for match in _VERBOSE_PASSED.finditer(pytest_output):
        leaf = match.group("nodeid").rsplit("::", 1)[-1]
        names.add(leaf.split("[", 1)[0])
    return names


class Kept(NamedTuple):
    source: str
    #: Tests whose edited text was replaced with their prior text.
    restored: list[str]
    #: Tests the edit had deleted, put back where they were.
    returned: list[str]


_Function = ast.FunctionDef | ast.AsyncFunctionDef


def _test_functions(tree: ast.Module) -> dict[str, tuple[_Function, ast.ClassDef | None]]:
    """Test functions by key: `name` at module level, `Class.name` in a class."""
    found: dict[str, tuple[_Function, ast.ClassDef | None]] = {}
    for node in tree.body:
        if isinstance(node, _Function) and node.name.startswith("test"):
            found[node.name] = (node, None)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, _Function) and item.name.startswith("test"):
                    found[f"{node.name}.{item.name}"] = (item, node)
    return found


def _span(node: ast.AST) -> tuple[int, int]:
    """1-based inclusive line span, decorators included."""
    first = min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])
    return first, node.end_lineno or node.lineno


def _text(lines: list[str], span: tuple[int, int]) -> str:
    return "\n".join(lines[span[0] - 1:span[1]])


def keep_passing_tests_as_written(before: str, after: str, passing: set[str]) -> Kept:
    """`after`, with every passing test's text taken from `before`.

    A passing test whose text the edit changed gets its prior text back in
    place. One the edit deleted is put back: at the end of the module, or at
    the end of its class when the class is still there (a class the edit
    removed takes its methods with it -- they are not re-homed).

    `after` is returned untouched when there is nothing to keep, or when
    either side does not parse: a file that does not parse is the syntax
    gate's finding, and a guess at its functions would be noise on top.
    """
    if not passing or before == after:
        return Kept(after, [], [])
    try:
        before_tree = ast.parse(before)
        after_tree = ast.parse(after)
    except SyntaxError:
        # fail-open: an unparseable side is reported by the syntax gate that
        # runs on the written file; this keeps nothing rather than guessing.
        return Kept(after, [], [])

    before_lines = before.splitlines()
    after_lines = after.splitlines()
    before_tests = _test_functions(before_tree)
    after_tests = _test_functions(after_tree)
    after_classes = {
        node.name: node for node in after_tree.body if isinstance(node, ast.ClassDef)
    }

    # Edits as (start_index, end_index_exclusive, replacement_lines), applied
    # bottom-up so earlier indices stay valid.
    edits: list[tuple[int, int, list[str]]] = []
    trailing: list[str] = []
    restored: list[str] = []
    returned: list[str] = []
    for key, (node, owner) in before_tests.items():
        if node.name not in passing:
            continue
        prior = _text(before_lines, _span(node))
        current = after_tests.get(key)
        if current is not None:
            span = _span(current[0])
            if _text(after_lines, span) != prior:
                edits.append((span[0] - 1, span[1], prior.splitlines()))
                restored.append(node.name)
            continue
        if owner is None:
            trailing.append(prior)
            returned.append(node.name)
            continue
        home = after_classes.get(owner.name)
        if home is None:
            continue
        end = home.end_lineno or home.lineno
        edits.append((end, end, ["", *prior.splitlines()]))
        returned.append(node.name)

    if not restored and not returned:
        return Kept(after, [], [])

    out = list(after_lines)
    for start, end, lines in sorted(edits, key=lambda e: e[0], reverse=True):
        out[start:end] = lines
    source = "\n".join(out)
    if trailing:
        source = source.rstrip("\n") + "\n\n\n" + "\n\n\n".join(trailing)
    if after.endswith("\n"):
        source = source.rstrip("\n") + "\n"
    return Kept(source, restored, returned)


def release_spec_twins(
    contract: set[str], spec_suite_source: str | None,
) -> tuple[set[str], set[str]]:
    """The contract without the names the spec suite defines, and those names (#2910).

    A plan-owned test file's `test_req_N` tests are copies of the spec's
    requirements: the LLD plans a unit file per module and the spec suite is
    generated from the same spec, which is the contract (#2709). On
    run-issue4-131639 the plan file's copy of `test_req_13` asserted
    `OSError` (run 39's rewrite) while the spec's asserted
    `NotImplementedError`; the copy passed first, #2905 held it while N4
    chased the spec's, and the loop ended at the cap raising neither. For a
    name both files carry, the spec's copy governs and the plan file's is
    the implementer's to change.
    """
    if not contract or not spec_suite_source:
        return set(contract), set()
    try:
        tree = ast.parse(spec_suite_source)
    except SyntaxError:
        # fail-open: a spec suite that does not parse is the scaffold gate's
        # finding; nothing is released and the #2905 keep stands as before.
        return set(contract), set()
    twins = {node.name for node, _ in _test_functions(tree).values()}
    released = set(contract) & twins
    return set(contract) - released, released


class Aligned(NamedTuple):
    source: str
    #: Tests whose text was replaced with the spec suite's copy.
    aligned: list[str]
    #: Import statements copied from the spec suite so those copies resolve.
    imports_added: list[str]


def align_spec_twins(plan_source: str, spec_source: str) -> Aligned:
    """`plan_source` with every module-level test the spec suite also defines
    carrying the spec's text (#2912).

    #2910 released a plan file's twin to the implementer; on run-issue4-135112
    the implementer still read the twin's failure -- `DID NOT RAISE OSError`
    -- as the implementation's fault and rewrote `make_collector` to raise
    `OSError`, which failed the spec's copy, which the hill-climb restored,
    twice. The twin is a copy of the spec's test by construction, so the
    honest state is the spec's text, and the verifier writes that state
    before it measures: a drifted copy is never measured, never reported,
    never chased.

    Module-level functions only: a method's indentation is not a function's,
    and the plan's `test_req_N` copies are module-level as the spec's are.
    Import statements the spec suite has and the plan file lacks (verbatim)
    are copied in after the plan file's imports, so a copied body resolves
    the names its own file resolved. Either side failing to parse aligns
    nothing: that is the syntax gate's finding.
    """
    if not spec_source or plan_source == spec_source:
        return Aligned(plan_source, [], [])
    try:
        plan_tree = ast.parse(plan_source)
        spec_tree = ast.parse(spec_source)
    except SyntaxError:
        # fail-open: an unparseable side is the syntax gate's finding; the
        # plan file is left exactly as it is and measured as it is.
        return Aligned(plan_source, [], [])

    plan_lines = plan_source.splitlines()
    spec_lines = spec_source.splitlines()
    spec_tests = {
        node.name: node for node, owner in _test_functions(spec_tree).values()
        if owner is None
    }

    edits: list[tuple[int, int, list[str]]] = []
    aligned: list[str] = []
    for node, owner in _test_functions(plan_tree).values():
        if owner is not None or node.name not in spec_tests:
            continue
        spec_text = _text(spec_lines, _span(spec_tests[node.name]))
        span = _span(node)
        if _text(plan_lines, span) != spec_text:
            edits.append((span[0] - 1, span[1], spec_text.splitlines()))
            aligned.append(node.name)
    if not aligned:
        return Aligned(plan_source, [], [])

    plan_imports = [
        node for node in plan_tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    present = set(plan_lines)
    imports_added = [
        _text(spec_lines, _span(node))
        for node in spec_tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and _text(spec_lines, _span(node)) not in present
    ]
    if imports_added:
        if plan_imports:
            at = max(node.end_lineno or node.lineno for node in plan_imports)
        elif (
            plan_tree.body
            and isinstance(plan_tree.body[0], ast.Expr)
            and isinstance(getattr(plan_tree.body[0], "value", None), ast.Constant)
            and isinstance(plan_tree.body[0].value.value, str)
        ):
            at = plan_tree.body[0].end_lineno or plan_tree.body[0].lineno
        else:
            at = 0
        edits.append((at, at, imports_added))

    out = list(plan_lines)
    for start, end, lines in sorted(edits, key=lambda e: e[0], reverse=True):
        out[start:end] = lines
    source = "\n".join(out)
    if plan_source.endswith("\n"):
        source = source.rstrip("\n") + "\n"
    return Aligned(source, aligned, imports_added)
