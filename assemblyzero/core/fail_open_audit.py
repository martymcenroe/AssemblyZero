"""Enumerate every place the pipeline continues after something failed (#2475).

On 2026-08-16 the N0c requirements gate could not reach the governance model,
printed ``proceeding``, and the run went on to spend drafter budget with the
check skipped (#2474). This module answers the question that defect raises:
**where else does the pipeline continue after something failed?**

A pipeline that advances past a gate it could not run is untrustworthy at every
stage, because a green result becomes indistinguishable from a skipped one. That
is a systemic property, so it needs a systemic answer rather than a patch at the
one site that happened to surface.

Why a program and not a read-through
------------------------------------
A check that cannot be re-run is not a check. A human reading the tree once
produces a list that is stale on the next merge and unfalsifiable in the
meantime. This is an AST pass: it re-derives the answer from the code on every
run, so a newly-introduced fail-open is caught at the point it lands rather than
after the next incident.

What it classifies, and how
---------------------------
Every ``except`` handler in scope gets exactly one outcome, decided from the
handler body alone:

``propagates``
    Contains ``raise``, ``sys.exit``, or returns a value that signals an error
    (a dict carrying ``error_message``/``requirements_unverified``, or a call to
    something named ``*halt*``/``*fail*``). Fail-CLOSED. Not a finding.
``falls_through``
    No ``raise``, no exit, no ``return`` at all -- execution simply continues
    past the ``try``. Fail-OPEN, and the shape #2474 was.
``substitutes``
    Returns a value that does not signal an error, so the caller receives
    something indistinguishable from a real result. Fail-OPEN.

Two further shapes are reported in their own categories because the issue names
them and neither is an ``except`` handler:

``vacuous_pass``
    A branch guarded by an emptiness test that returns a success value -- the
    class already recorded on 2026-08-16, where a heading did not match, zero
    sentences were examined, and PASS was reported.
``warned_return``
    A neutral ``return`` preceded by a printed warning in the same block. This
    is N0c's own pre-#2474 shape: say something is wrong, then hand back the
    value that means everything is fine.

The column that matters
-----------------------
``visibility`` is the ranking key. A fail-open that leaves a visible mark is a
nuisance; a fail-open whose output is identical to the success path is what makes
results untrustworthy. ``silent`` means the site emits nothing at all -- no
print, no log, no warning -- so the run's output cannot be told from one where
the step succeeded. Those rank first, always.

Declaring a decision
--------------------
Some fall-throughs are correct: an advisory benchmark should not halt a run. The
goal is not to remove them but to make each one a decision on record rather than
an accident. Writing ``# fail-open: <reason>`` inside the handler (or on the line
above it) marks it as declared. Declared sites stay in the inventory -- they are
still fail-open and still counted -- but they are no longer *undeclared*, which
is what the CI gate acts on.

The reason text is not validated, deliberately. A marker whose reason is checked
by a program teaches people to write text that satisfies the program.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

#: Written inside a handler (or on the line above) to mark it a decision on
#: record. Deliberately not a ``noqa``-style code: the point is that a human
#: wrote a sentence about why continuing is correct here.
DECLARATION_MARKER = "# fail-open:"

#: Keys whose presence in a returned dict means "this is an error being
#: reported", not "here is your result". These are the pipeline's own halt
#: protocol -- reading them is reading our own contract, not scraping text.
ERROR_SIGNAL_KEYS = ("error_message", "requirements_unverified", "error_summary")

#: A returned call whose name contains one of these is reporting a failure
#: rather than substituting a result (``_halt_unverified``, ``_fail``, ...).
ERROR_CALL_SUBSTRINGS = ("halt", "fail", "abort", "raise_")

#: Names that emit something a human can see. A handler containing none of
#: these is SILENT, and a silent fall-through is the class that makes a run's
#: output indistinguishable from a successful one.
EMITTER_NAMES = ("print", "warn", "warning", "log", "error", "info", "debug",
                 "emit", "echo", "report")

#: Words that mark a printed string as an admission rather than progress
#: narration. Used only for the ``warned_return`` category.
WARNING_WORDS = ("warning", "skipped", "skipping", "proceeding", "unavailable",
                 "could not", "couldn't", "failed", "falling back", "fallback",
                 "ignored", "unverified")

#: Values that mean "nothing went wrong" when returned. A handler returning one
#: of these has substituted a real result with a neutral one.
_NEUTRAL_CONSTANTS = (True, None)

OUTCOME_PROPAGATES = "propagates"
OUTCOME_FALLS_THROUGH = "falls_through"
OUTCOME_SUBSTITUTES = "substitutes"

CATEGORY_HANDLER = "except_handler"
CATEGORY_VACUOUS_PASS = "vacuous_pass"
CATEGORY_WARNED_RETURN = "warned_return"
CATEGORY_UNMET_PRECONDITION = "unmet_precondition"

VISIBILITY_SILENT = "silent"
VISIBILITY_RECORDED = "recorded"
VISIBILITY_LOUD = "loud"

#: Rank order. ``silent`` first, because that is the column the issue calls the
#: important one: output identical to the success path.
_VISIBILITY_RANK = {
    VISIBILITY_SILENT: 0,
    VISIBILITY_RECORDED: 1,
    VISIBILITY_LOUD: 2,
}

#: Methods that put something INTO a structure. A handler doing this is
#: capturing the failure rather than dropping it -- the validator accumulator
#: pattern, ``except OSError as e: invalid_refs.append(f"cannot read: {e}")``,
#: which reads as silent to a naive scanner and is the opposite.
_RECORDING_METHODS = ("append", "add", "extend", "update", "insert",
                      "setdefault", "put", "write", "record")

#: Dict keys that carry a status back to the caller. A handler returning a dict
#: with one of these is reporting the failure in its own protocol rather than
#: pretending nothing happened -- ``{"returncode": -1, "stderr": "timed out"}``
#: is a failure report, even though it is not the graph's ``error_message``.
_STATUS_KEYS = ("returncode", "return_code", "exit_code", "status", "ok",
                "success", "failed", "error", "errors", "reason", "stderr",
                "message", "detail")
_CATEGORY_RANK = {
    CATEGORY_HANDLER: 0,
    CATEGORY_WARNED_RETURN: 1,
    CATEGORY_VACUOUS_PASS: 2,
    CATEGORY_UNMET_PRECONDITION: 3,
}


@dataclass
class Finding:
    """One site where execution continues after something failed."""

    path: str
    line: int
    qualname: str
    category: str
    outcome: str
    visibility: str
    what_fails: str
    what_happens: str
    spends_after: str
    declared: bool
    #: Which occurrence this is within its function, so two handlers in one
    #: function do not collapse onto the same key.
    index: int = 0
    #: Last line of the construct, used to spot two rules naming one site.
    end_line: int = 0

    @property
    def key(self) -> str:
        """Stable identity across edits that do not change the site.

        Deliberately excludes the line number. A baseline keyed on line numbers
        churns on every unrelated edit above it, and a baseline that churns is
        one people regenerate without reading -- which is the same failure as
        having no baseline.
        """
        return f"{self.path}::{self.qualname}::{self.category}::{self.index}"

    @property
    def distinguishable(self) -> str:
        """Can the run's final output be told from one where the step worked?

        ``maybe`` is deliberate. A handler that files the failure into a list
        has left evidence, but whether that list reaches the operator is a
        question about the caller, and asserting either way would be a guess
        dressed as a finding.
        """
        if self.visibility == VISIBILITY_SILENT:
            return "no"
        if self.visibility == VISIBILITY_RECORDED:
            return "maybe"
        return "yes"

    def sort_key(self) -> tuple:
        return (
            0 if not self.declared else 1,
            _VISIBILITY_RANK.get(self.visibility, 9),
            0 if self.spends_after == "yes" else 1,
            _CATEGORY_RANK.get(self.category, 9),
            self.path,
            self.line,
        )


@dataclass
class Coverage:
    """What was actually examined. Counted, never estimated."""

    files_scanned: int = 0
    files_unparseable: list[str] = field(default_factory=list)
    functions_scanned: int = 0
    handlers_examined: int = 0
    returns_examined: int = 0
    branches_examined: int = 0

    @property
    def sites_examined(self) -> int:
        return self.handlers_examined + self.returns_examined + self.branches_examined


def _call_name(node: ast.AST) -> str:
    """The dotted-ish name of a call target, lowercased, or ''."""
    if not isinstance(node, ast.Call):
        return ""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id.lower()
    if isinstance(func, ast.Attribute):
        return func.attr.lower()
    return ""


def _is_error_return(value: ast.AST | None) -> bool:
    """Does this returned value report a failure rather than substitute one?"""
    if value is None:
        return False
    if isinstance(value, ast.Dict):
        for key in value.keys:
            if isinstance(key, ast.Constant) and key.value in ERROR_SIGNAL_KEYS:
                return True
        return False
    name = _call_name(value)
    if name and any(s in name for s in ERROR_CALL_SUBSTRINGS):
        return True
    return False


def _visibility_of(node: ast.AST) -> str:
    """Can the run's output be told from one where the step succeeded?

    The ranking key, so its three values are ordered by how confidently the
    answer is no: nothing said at all, said into a structure, said out loud.
    """
    if _emits(node):
        return VISIBILITY_LOUD
    if _records(node):
        return VISIBILITY_RECORDED
    return VISIBILITY_SILENT


def _emits(node: ast.AST) -> bool:
    """Does this subtree print, log or otherwise say something?"""
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and any(
            e in _call_name(child) for e in EMITTER_NAMES
        ):
            return True
    return False


def _records(node: ast.AST) -> bool:
    """Does this handler capture the failure into a structure?

    An accumulating validator (``except OSError as e: invalid_refs.append(...)``)
    continues executing, so it is fail-open by outcome -- but its output is NOT
    identical to the success path, because the failure is now an entry the
    caller reports. Calling that silent would put the pipeline's most careful
    error handling at the top of a list titled "makes results untrustworthy",
    which is the fastest way to get a report ignored.

    Whether the structure actually reaches the output is not derivable here, so
    this earns ``recorded`` rather than ``loud`` and the report says maybe.
    """
    bound = getattr(node, "name", None) if isinstance(node, ast.ExceptHandler) else None

    for child in ast.walk(node):
        if isinstance(child, ast.Call) and _call_name(child) in _RECORDING_METHODS:
            return True
        if isinstance(child, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = getattr(child, "targets", None) or [child.target]
            if any(isinstance(t, ast.Subscript) for t in targets):
                return True
        if isinstance(child, ast.Return) and child.value is not None:
            # A returned dict carrying a status key is the function reporting
            # the failure through its own contract.
            if isinstance(child.value, ast.Dict) and any(
                isinstance(k, ast.Constant)
                and isinstance(k.value, str)
                and k.value.lower() in _STATUS_KEYS
                for k in child.value.keys
            ):
                return True
            # A returned value built from the caught exception carries the
            # failure with it, whatever shape it takes.
            if bound and any(
                isinstance(n, ast.Name) and n.id == bound
                for n in ast.walk(child.value)
            ):
                return True
    return False


def _emitted_strings(node: ast.AST) -> list[str]:
    """Every literal string inside emitter calls in this subtree, lowercased."""
    out: list[str] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if not any(e in _call_name(child) for e in EMITTER_NAMES):
            continue
        for piece in ast.walk(child):
            if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                out.append(piece.value.lower())
    return out


def _exits_hard(node: ast.AST) -> bool:
    """Does this subtree raise or exit the process?"""
    for child in ast.walk(node):
        if isinstance(child, ast.Raise):
            return True
        if isinstance(child, ast.Call) and _call_name(child) in ("exit", "_exit"):
            return True
    return False


def _returns_in(node: ast.AST) -> list[ast.Return]:
    return [c for c in ast.walk(node) if isinstance(c, ast.Return)]


def _is_neutral_value(value: ast.AST | None) -> bool:
    """Is this the value that means 'nothing went wrong'?"""
    if value is None:
        return True
    if isinstance(value, ast.Constant) and value.value in _NEUTRAL_CONSTANTS:
        return True
    if isinstance(value, ast.Dict) and not value.keys:
        return True
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)) and not value.elts:
        return True
    return False


#: Methods whose result is content rather than status, so ``not x.foo()`` is
#: still asking "is there anything here".
_CONTENT_METHODS = ("strip", "split", "splitlines", "keys", "values", "items",
                    "read", "readlines", "getvalue", "lower", "upper", "get")


def _is_success_value(value: ast.AST | None) -> bool:
    """Does returning this read as "I ran, and everything was fine"?

    Stricter than ``_is_neutral_value``: ``None`` is excluded. From a check, an
    empty COLLECTION reads as "I looked and found nothing wrong", which is
    indistinguishable from a clean result; ``None`` conventionally reads as "no
    answer", which a caller is expected to test. Counting both would inflate the
    report with every ``X | None`` helper in the tree.
    """
    if isinstance(value, ast.Constant) and value.value is True:
        return True
    if isinstance(value, ast.Dict) and not value.keys:
        return True
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)) and not value.elts:
        return True
    return False


def _is_emptiness_operand(node: ast.AST) -> bool:
    """Is ``not <node>`` asking "was there anything to examine"?

    Deliberately narrow. ``not result.success`` and ``not broken()`` are
    FAILURE tests, not emptiness tests, and calling them vacuous passes would
    put a false sentence -- "reported success having examined nothing" -- next
    to a real finding. A description that is wrong about why is worse than no
    finding, because it sends the reader to fix the wrong thing.
    """
    if isinstance(node, ast.Name):
        return True
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id == "len":
            return True
        if isinstance(func, ast.Attribute) and func.attr in _CONTENT_METHODS:
            return True
    return False


def _is_emptiness_test(test: ast.AST) -> bool:
    """``not rows``, ``len(x) == 0``, ``x == []`` -- 'there was nothing to check'."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _is_emptiness_operand(test.operand)
    if isinstance(test, ast.Compare) and len(test.comparators) == 1:
        left, op, right = test.left, test.ops[0], test.comparators[0]
        if not isinstance(op, (ast.Eq, ast.LtE, ast.Lt)):
            return False
        if _call_name(left) == "len" and isinstance(right, ast.Constant):
            return right.value == 0
        if isinstance(right, (ast.List, ast.Tuple, ast.Set)) and not right.elts:
            return True
        if isinstance(right, ast.Dict) and not right.keys:
            return True
    return False


def _looks_like_a_check(qualname: str) -> bool:
    """Is this function a gate, check or validator by name?

    Used only to decide whether an empty-input early return is worth reporting.
    A helper that returns True on empty input is ordinary; a VALIDATOR that
    does so has reported PASS having examined nothing.
    """
    tail = qualname.rsplit(".", 1)[-1].lower()
    return any(
        w in tail
        for w in ("check", "validate", "verify", "gate", "audit", "assert",
                  "review", "lint", "scan", "analyze", "analyse")
    )


class _Scanner(ast.NodeVisitor):
    """Walks one module, tracking the enclosing function for each site."""

    def __init__(self, path: str, source_lines: list[str], spends_after: str,
                 coverage: Coverage):
        self.path = path
        self.lines = source_lines
        self.spends_after = spends_after
        self.coverage = coverage
        self.findings: list[Finding] = []
        self._stack: list[str] = []
        self._counts: dict[tuple[str, str], int] = {}

    # -- bookkeeping -------------------------------------------------------

    @property
    def _qualname(self) -> str:
        return ".".join(self._stack) or "<module>"

    def _next_index(self, category: str) -> int:
        key = (self._qualname, category)
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key] - 1

    def _declared_at(self, node: ast.AST) -> bool:
        """Is there a ``# fail-open:`` marker on this site?

        Searched from the line above the site through its last line, so the
        marker can sit either as a lead-in comment or inside the body.
        """
        start = max(0, (node.lineno or 1) - 2)
        end = min(len(self.lines), getattr(node, "end_lineno", node.lineno) or node.lineno)
        return any(
            DECLARATION_MARKER in self.lines[i] for i in range(start, end)
        )

    def _visit_scope(self, node, name: str):
        self.coverage.functions_scanned += 1
        self._stack.append(name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node):  # noqa: N802 - ast API
        self._visit_scope(node, node.name)

    def visit_AsyncFunctionDef(self, node):  # noqa: N802 - ast API
        self._visit_scope(node, node.name)

    def visit_ClassDef(self, node):  # noqa: N802 - ast API
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    # -- the three categories ----------------------------------------------

    def visit_ExceptHandler(self, node):  # noqa: N802 - ast API
        self.coverage.handlers_examined += 1

        returns = _returns_in(node)
        if _exits_hard(node) or any(_is_error_return(r.value) for r in returns):
            outcome = OUTCOME_PROPAGATES
        elif returns:
            outcome = OUTCOME_SUBSTITUTES
        else:
            outcome = OUTCOME_FALLS_THROUGH

        if outcome != OUTCOME_PROPAGATES:
            self.findings.append(Finding(
                path=self.path,
                line=node.lineno,
                qualname=self._qualname,
                category=CATEGORY_HANDLER,
                outcome=outcome,
                visibility=_visibility_of(node),
                what_fails=self._exception_text(node),
                what_happens=self._describe(node, outcome),
                spends_after=self.spends_after,
                declared=self._declared_at(node),
                index=self._next_index(CATEGORY_HANDLER),
                end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
            ))

        self.generic_visit(node)

    def visit_If(self, node):  # noqa: N802 - ast API
        self.coverage.branches_examined += 1

        # Both shapes are "a check returned its all-clear without checking",
        # and they are reported apart because the CAUSE differs and a reader
        # fixes them differently. An emptiness test means there was nothing to
        # look at; any other negated guard means a precondition was not met.
        # Scoped to functions that are checks by name: an ordinary helper
        # returning early on empty input is ordinary code, and flagging it is
        # the noise that makes a report unreadable.
        if _looks_like_a_check(self._qualname) and not any(
            _is_error_return(r.value) for r in _returns_in(node)
        ):
            body_returns = [r for r in node.body if isinstance(r, ast.Return)]
            guard = node.test
            negated = isinstance(guard, ast.UnaryOp) and isinstance(guard.op, ast.Not)

            if body_returns and all(_is_success_value(r.value) for r in body_returns):
                category = what_fails = what_happens = None
                if _is_emptiness_test(guard):
                    category = CATEGORY_VACUOUS_PASS
                    what_fails = "there was nothing to examine"
                    what_happens = "reports success having examined nothing"
                elif negated:
                    category = CATEGORY_UNMET_PRECONDITION
                    what_fails = f"the precondition {ast.unparse(guard.operand)!r}"
                    what_happens = (
                        "returns the all-clear without running the check"
                    )

                if category:
                    emits = _emits(node)
                    self.findings.append(Finding(
                        path=self.path,
                        line=node.lineno,
                        qualname=self._qualname,
                        category=category,
                        outcome=OUTCOME_SUBSTITUTES,
                        visibility=VISIBILITY_LOUD if emits else VISIBILITY_SILENT,
                        what_fails=what_fails,
                        what_happens=what_happens,
                        spends_after=self.spends_after,
                        declared=self._declared_at(node),
                        index=self._next_index(category),
                        end_line=(
                            getattr(node, "end_lineno", node.lineno) or node.lineno
                        ),
                    ))

        self.generic_visit(node)

    def visit_Return(self, node):  # noqa: N802 - ast API
        self.coverage.returns_examined += 1
        self.generic_visit(node)

    def _describe(self, node: ast.ExceptHandler, outcome: str) -> str:
        """What happens instead of halting, in the terms the reader needs.

        `continue` is called out separately from a plain fall-through because
        it is a different failure: the item is DROPPED, and a loop that quietly
        drops items produces a short result that looks like a complete one.
        """
        if outcome == OUTCOME_SUBSTITUTES:
            return "returns a value the caller cannot tell from a real one"
        if any(isinstance(c, ast.Continue) for c in ast.walk(node)):
            return "drops this item and moves to the next; the result is short"
        if any(isinstance(c, ast.Break) for c in ast.walk(node)):
            return "stops the loop early and uses whatever it had"
        return "execution continues past the try"

    def _exception_text(self, node: ast.ExceptHandler) -> str:
        if node.type is None:
            return "any exception (bare except)"
        try:
            return ast.unparse(node.type)
        except Exception:  # noqa: BLE001
            # fail-open: this only names the exception type for the report. An
            # unparseable type expression costs a label, not a finding -- the
            # site is still counted, classified and ranked. Halting the whole
            # audit over a cosmetic string would be the worse trade.
            return "an exception"


def _warned_returns(tree: ast.AST, path: str, spends_after: str,
                    lines: list[str], coverage: Coverage) -> list[Finding]:
    """Neutral returns that follow a printed admission in the same block.

    N0c's own pre-#2474 shape: print that something could not be done, then
    return the value that means everything is fine. Detected separately from
    handlers because it is not inside one -- the failure was already caught and
    turned into a warning further up.
    """
    findings: list[Finding] = []
    counts: dict[str, int] = {}
    seen_lines: set[int] = set()

    for scope in ast.walk(tree):
        if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = scope.name
        for block in _statement_blocks(scope):
            warned = False
            for stmt in block:
                if isinstance(stmt, ast.Expr) and _emits(stmt):
                    if any(
                        w in s for s in _emitted_strings(stmt) for w in WARNING_WORDS
                    ):
                        warned = True
                    continue
                if isinstance(stmt, ast.Return) and warned:
                    # A nested function is walked both on its own and inside
                    # its parent's blocks, so the same return can be reached
                    # twice. One site, one finding.
                    if _is_neutral_value(stmt.value) and stmt.lineno not in seen_lines:
                        seen_lines.add(stmt.lineno)
                        idx = counts.get(name, 0)
                        counts[name] = idx + 1
                        findings.append(Finding(
                            path=path,
                            line=stmt.lineno,
                            qualname=name,
                            category=CATEGORY_WARNED_RETURN,
                            outcome=OUTCOME_SUBSTITUTES,
                            visibility=VISIBILITY_LOUD,
                            what_fails="named in the warning printed just above",
                            what_happens=(
                                "returns the value that means nothing went wrong"
                            ),
                            spends_after=spends_after,
                            declared=any(
                                DECLARATION_MARKER in lines[i]
                                for i in range(
                                    max(0, stmt.lineno - 4), min(len(lines), stmt.lineno)
                                )
                            ),
                            index=idx,
                        ))
                    warned = False
                elif not isinstance(stmt, ast.Expr):
                    warned = False
    return findings


def _statement_blocks(node: ast.AST) -> list[list[ast.stmt]]:
    """Every contiguous statement list in a subtree, so 'the same block' means it."""
    blocks: list[list[ast.stmt]] = []
    for child in ast.walk(node):
        for attr in ("body", "orelse", "finalbody"):
            value = getattr(child, attr, None)
            if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
                blocks.append(value)
    return blocks


def _spends_after(path: Path) -> str:
    """Is a failure here followed by stages that spend money?

    Answered structurally rather than guessed: a graph NODE that returns
    normally routes onward, and everything downstream of a node calls models.
    Anywhere else, the answer depends on the caller and is reported as unknown
    rather than asserted.
    """
    parts = [p.lower() for p in path.parts]
    if "nodes" in parts and "workflows" in parts:
        return "yes"
    return "unknown"


def scan_file(path: Path, root: Path, coverage: Coverage) -> list[Finding]:
    """Every fail-open site in one module."""
    try:
        # utf-8-sig, not utf-8: two files in this tree carry a UTF-8 BOM, and
        # plain utf-8 keeps it as a leading ﻿ that ast.parse rejects as a
        # non-printable character. Python's own import machinery strips it, so
        # the modules load fine and only a naive reader sees a syntax error --
        # which is how a scanner silently under-covers files that are perfectly
        # valid. utf-8-sig is identical to utf-8 when no BOM is present.
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        tree = ast.parse(source)
    except (OSError, SyntaxError, ValueError):
        # fail-open: one unreadable file must not cost the whole sweep. This is
        # only defensible because it is NOT silent -- the file is named in
        # `files_unparseable` and the report prints that count on its coverage
        # line, so an audit that examined less than it claims says so. That
        # line is what caught the UTF-8 BOM handled above.
        coverage.files_unparseable.append(str(path.relative_to(root)).replace("\\", "/"))
        return []

    coverage.files_scanned += 1
    lines = source.splitlines()
    rel = str(path.relative_to(root)).replace("\\", "/")
    spends = _spends_after(path)

    scanner = _Scanner(rel, lines, spends, coverage)
    scanner.visit(tree)
    warned = _warned_returns(tree, rel, spends, lines, coverage)

    # One site, one finding. `if not conflicts: print(WARNING); return {}` trips
    # the vacuous-pass rule on the `if` and the warned-return rule on the
    # `return`, and reporting it twice would inflate a count this audit asks
    # people to trust. The vacuous-pass reading is kept because it names the
    # cause (nothing was examined) rather than the symptom.
    covered = {
        (f.line, f.end_line) for f in scanner.findings
        if f.category in (CATEGORY_VACUOUS_PASS, CATEGORY_UNMET_PRECONDITION)
    }
    warned = [
        w for w in warned
        if not any(start <= w.line <= end for start, end in covered)
    ]
    return scanner.findings + warned


def scan(root: Path, subdirs: tuple[str, ...]) -> tuple[list[Finding], Coverage]:
    """Scan the pipeline. Returns findings ranked most-untrustworthy first."""
    coverage = Coverage()
    findings: list[Finding] = []
    for subdir in subdirs:
        base = root / subdir
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            findings.extend(scan_file(path, root, coverage))
    findings.sort(key=lambda f: f.sort_key())
    return findings, coverage
