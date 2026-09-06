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
