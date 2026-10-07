"""The loud-failure check (ADR 0236, standard 0034, #3580).

Three kinds of site break the standard in a way a parser can see:

* ``swallowed_handler``: a bare ``except``, or ``except Exception`` /
  ``except BaseException`` (alone or in a tuple), whose body neither raises
  nor calls the alert path (``alert_operator``). A nested function's raise
  does not count: it is not this handler raising.
* ``fail_open_tag``: a ``# fail-open:`` comment. ADR 0236 withdrew the
  convention; every tag is a decision to continue after a failure.
* ``unrouted_error``: a workflow-graph node whose function returns a dict
  carrying a non-empty ``error_message``, where the graph does not send that
  error to ``HALT``: the node has no conditional edge, or a router on it
  neither reads ``error_message`` nor can return ``HALT``.

Python is read with ``ast`` and ``tokenize``, never a pattern. Graphs are read
from the builders LangGraph itself holds, so a graph's wiring is what it is at
runtime, not what a reader of its source guesses.

Each finding has a stable key (path, enclosing function, kind, ordinal) that
survives unrelated line moves, so the baseline does not churn on every edit.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import io
import textwrap
import tokenize
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

KIND_HANDLER = "swallowed_handler"
KIND_TAG = "fail_open_tag"
KIND_UNROUTED = "unrouted_error"

TAG_MARKER = "fail-open:"
ALERT_FUNCTION = "alert_operator"
ERROR_KEY = "error_message"
HALT_NODE = "HALT"
BROAD_EXCEPTIONS = {"Exception", "BaseException"}

#: Every workflow graph: (module, builder function). A closed list; a new
#: graph is added here, and test_every_graph_module_is_listed fails until it is.
GRAPH_BUILDERS: tuple[tuple[str, str], ...] = (
    ("assemblyzero.workflows.requirements.graph", "create_requirements_graph"),
    ("assemblyzero.workflows.implementation_spec.graph", "create_implementation_spec_graph"),
    ("assemblyzero.workflows.orchestrator.graph", "create_orchestration_graph"),
    ("assemblyzero.workflows.testing.graph", "build_testing_workflow"),
    ("assemblyzero.workflows.janitor.graph", "build_janitor_graph"),
    ("assemblyzero.workflows.death.hourglass", "create_hourglass_graph"),
)


@dataclass(frozen=True)
class Finding:
    key: str
    path: str
    line: int
    kind: str
    detail: str


# ---------------------------------------------------------------------------
# Handlers and tags (one source file at a time)
# ---------------------------------------------------------------------------


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    names = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(n, ast.Name) and n.id in BROAD_EXCEPTIONS for n in names)


def _own_nodes(body: list[ast.stmt]):
    """Every node in ``body`` except a nested def, lambda or class and its contents."""
    nested = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
    stack: list[ast.AST] = [s for s in body if not isinstance(s, nested)]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(c for c in ast.iter_child_nodes(node) if not isinstance(c, nested))


def _handled(handler: ast.ExceptHandler) -> bool:
    for node in _own_nodes(handler.body):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name == ALERT_FUNCTION:
                return True
    return False


def _scopes(tree: ast.AST) -> list[tuple[int, int, str]]:
    """(first line, last line, qualname) for every function and class."""
    spans: list[tuple[int, int, str]] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}{child.name}"
                spans.append((child.lineno, child.end_lineno or child.lineno, name))
                visit(child, name + ".")
            else:
                visit(child, prefix)

    visit(tree, "")
    return spans


def _scope_of(spans: list[tuple[int, int, str]], line: int) -> str:
    inner = [s for s in spans if s[0] <= line <= s[1]]
    return max(inner, key=lambda s: s[0])[2] if inner else "<module>"


def scan_source(path: str, source: str) -> list[Finding]:
    """Handler and tag findings for one file. Raises SyntaxError on bad source."""
    tree = ast.parse(source)
    spans = _scopes(tree)
    raw: list[tuple[int, str, str, str]] = []  # (line, scope, kind, detail)

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and _is_broad(node) and not _handled(node):
            caught = "bare except" if node.type is None else f"except {ast.unparse(node.type)}"
            raw.append((node.lineno, _scope_of(spans, node.lineno), KIND_HANDLER,
                        f"{caught} neither raises nor calls {ALERT_FUNCTION}"))

    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.COMMENT and TAG_MARKER in tok.string:
            line = tok.start[0]
            raw.append((line, _scope_of(spans, line), KIND_TAG, tok.string.strip()[:120]))

    raw.sort()
    ordinals: Counter = Counter()
    findings: list[Finding] = []
    for line, scope, kind, detail in raw:
        ordinals[(scope, kind)] += 1
        key = f"{path}::{scope}::{kind}::{ordinals[(scope, kind)]}"
        findings.append(Finding(key, path, line, kind, detail))
    return findings


# ---------------------------------------------------------------------------
# Graph routing
# ---------------------------------------------------------------------------


class UnreadableGraphFunction(RuntimeError):
    """A node or router whose source cannot be read, so it cannot be judged."""


def _function_tree(fn: Callable) -> tuple[ast.AST, str, int]:
    """The AST, path and first line of the function behind a node or router.

    A function whose source cannot be read stops the check (ADR 0236): skipping
    it would pass a node the check never looked at.
    """
    fn = getattr(fn, "func", fn)  # functools.partial / RunnableCallable
    fn = inspect.unwrap(fn)
    try:
        source = textwrap.dedent(inspect.getsource(fn))
        path = inspect.getsourcefile(fn) or ""
        line = inspect.getsourcelines(fn)[1]
    except (OSError, TypeError) as exc:
        raise UnreadableGraphFunction(f"cannot read the source of {fn!r}: {exc}") from exc
    return ast.parse(source), path, line


def returns_error(tree: ast.AST) -> bool:
    """A ``return {..., "error_message": <non-empty>, ...}`` anywhere in it."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            for k, v in zip(node.value.keys, node.value.values, strict=True):
                is_error_key = isinstance(k, ast.Constant) and k.value == ERROR_KEY
                is_empty = isinstance(v, ast.Constant) and v.value in ("", None)
                if is_error_key and not is_empty:
                    return True
    return False


def routes_error_to_halt(tree: ast.AST, halt_names: set[str]) -> bool:
    """The router reads ``error_message`` and can return a halt node's name."""
    reads = any(isinstance(n, ast.Constant) and n.value == ERROR_KEY for n in ast.walk(tree))
    halts = any(
        isinstance(n, ast.Return) and (
            (isinstance(n.value, ast.Constant) and n.value.value in halt_names)
            or (isinstance(n.value, ast.Name) and n.value.id == HALT_NODE)
        )
        for n in ast.walk(tree)
    )
    return reads and halts


def _is_halt_node(runnable: Any) -> bool:
    """The node is ``create_halt_node``'s, whatever name the graph gave it."""
    fn = inspect.unwrap(getattr(runnable, "func", runnable))
    return getattr(fn, "__qualname__", "").startswith("create_halt_node.")


def scan_graphs(repo_root: Path, builders=GRAPH_BUILDERS) -> list[Finding]:
    findings: list[Finding] = []
    for module_name, fn_name in builders:
        graph = getattr(importlib.import_module(module_name), fn_name)()
        builder = getattr(graph, "builder", graph)
        halt_names = {n for n, s in builder.nodes.items() if _is_halt_node(s.runnable)}
        for node_name, spec in builder.nodes.items():
            if node_name in halt_names:
                continue
            tree, src, line = _function_tree(spec.runnable)
            if not returns_error(tree):
                continue
            branches = builder.branches.get(node_name, {})
            routers = [_function_tree(b.path)[0] for b in branches.values()]
            if branches and all(routes_error_to_halt(r, halt_names) for r in routers):
                continue
            why = "no conditional edge" if not branches else "a router does not send error_message to HALT"
            rel = Path(src).resolve().relative_to(repo_root.resolve()).as_posix() if src else module_name
            key = f"{module_name}::{node_name}::{KIND_UNROUTED}::1"
            findings.append(Finding(key, rel, line, KIND_UNROUTED,
                                    f"node {node_name} returns {ERROR_KEY}; {why}"))
    return findings


# ---------------------------------------------------------------------------
# The whole tree
# ---------------------------------------------------------------------------


def scan(repo_root: Path, files: list[str]) -> list[Finding]:
    """Every finding in ``files`` (repo-relative) plus every graph."""
    findings: list[Finding] = []
    for rel in files:
        source = (repo_root / rel).read_text(encoding="utf-8-sig")
        findings.extend(scan_source(rel, source))
    findings.extend(scan_graphs(repo_root))
    return sorted(findings, key=lambda f: f.key)


def as_baseline(findings: list[Finding], issue: int) -> dict[str, Any]:
    return {
        "issue": issue,
        "count": len(findings),
        "entries": {
            f.key: {"issue": issue, "line": f.line, "kind": f.kind, "detail": f.detail}
            for f in findings
        },
    }
