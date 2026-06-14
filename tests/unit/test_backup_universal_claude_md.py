"""Pin tests for tools/backup_universal_claude_md.py.

Issue: #1380 — replace `git worktree remove --force` with the no-force
`_try_remove_worktree` helper at both call sites (pre-run leftover
cleanup + finally-block cleanup).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

TOOL_PATH = (
    Path(__file__).parent.parent.parent / "tools" / "backup_universal_claude_md.py"
)


def _find_subprocess_calls(tree: ast.AST) -> list[tuple[int, list[str]]]:
    """Return [(lineno, [string-arg, ...]), ...] for every Call node whose
    arguments include literal strings — covers both `_git("worktree", ...)`
    and `subprocess.run(["git", ...])` forms.
    """
    found: list[tuple[int, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        literals: list[str] = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                literals.append(arg.value)
            elif isinstance(arg, ast.List):
                for elt in arg.elts:
                    if (isinstance(elt, ast.Constant)
                            and isinstance(elt.value, str)):
                        literals.append(elt.value)
        if literals:
            found.append((node.lineno, literals))
    return found


class TestNoForceFlagInWorktreeCalls:
    """#1380: --force must never reach a git worktree subprocess call."""

    def test_no_force_arg_passed_to_worktree_call(self):
        """No Call node has both 'worktree' and '--force' as string args."""
        tree = ast.parse(TOOL_PATH.read_text(encoding="utf-8"))
        for lineno, literals in _find_subprocess_calls(tree):
            if "worktree" in literals and "--force" in literals:
                pytest.fail(
                    f"Banned: subprocess call at line {lineno} passes both "
                    f"'worktree' and '--force'. Use _try_remove_worktree() "
                    f"instead (no-force helper). Args: {literals}"
                )

    def test_helper_function_is_defined(self):
        """_try_remove_worktree must exist and not pass --force itself."""
        tree = ast.parse(TOOL_PATH.read_text(encoding="utf-8"))
        helper_funcs = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_try_remove_worktree"
        ]
        assert len(helper_funcs) == 1, (
            "_try_remove_worktree helper missing — the no-force replacement "
            "for `git worktree remove --force` (#1380)"
        )
        # Walk just the helper's body and confirm no --force string literal
        for node in ast.walk(helper_funcs[0]):
            if (isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and node.value == "--force"):
                pytest.fail(
                    "_try_remove_worktree contains a '--force' string literal "
                    "— the helper exists to AVOID --force; it must not use it."
                )
