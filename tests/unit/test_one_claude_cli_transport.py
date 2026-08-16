"""One Claude CLI transport, and it kills on silence (#2406).

#2405 replaced the wall-clock timeout with an idle timeout in
`ClaudeCLIProvider.invoke` -- the transport the testing workflow and the
speedrun rolls actually use. A SECOND Claude CLI transport existed in
`assemblyzero/core/claude_client.py` and did not change:

    raise ClaudeClientError(f"Claude CLI timed out after {timeout}s")

It still killed on elapsed time, carrying the exact defect class #2405 removed:
a ceiling keyed to nothing observable, which gets overtaken every time the work
grows. #373, #2026 and #2405 are three occurrences of that class on the sibling
transport.

Reachability, confirmed mechanically before deleting:

    core/claude_client.py  <- nodes/fallback_provider.py  <- nothing

`call_with_fallback_instrumentation` was defined and never called outside its
own module; `nodes/__init__.py` imports only `check_type_renames` and
`smoke_test_node`. The one test that looked like a reference --
`test_fallback_provider_accepts_json_schema` -- is about `FallbackProvider` in
`llm_provider`, a different class entirely.

Two transports whose timeout semantics disagree is the kind of divergence that
reads as intentional once it has survived a few releases. These pin that there
is one.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


class TestTheDeadTransportIsGone:
    @pytest.mark.parametrize(
        "path",
        [
            "assemblyzero/core/claude_client.py",
            "assemblyzero/nodes/fallback_provider.py",
        ],
    )
    def test_the_module_no_longer_exists(self, path):
        assert not (ROOT / path).exists()

    def test_nothing_imports_it(self):
        """A leftover import would be an ImportError waiting for whoever
        wires it up next -- which is the trap this deletion is about.

        AST rather than text: the first cut matched substrings and flagged a
        COMMENT in `test_llm_instrumentation.py` explaining the deletion. A
        module named in prose is not a module imported, and a guard whose
        first finding is a false alarm gets switched off within a day.
        """
        dead = {
            "assemblyzero.core.claude_client",
            "assemblyzero.nodes.fallback_provider",
        }
        offenders: list[str] = []
        for directory in ("assemblyzero", "tools", "tests"):
            for py in (ROOT / directory).rglob("*.py"):
                try:
                    tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
                except (SyntaxError, OSError):
                    continue
                for node in ast.walk(tree):
                    named = None
                    if isinstance(node, ast.ImportFrom) and node.module:
                        named = node.module
                    elif isinstance(node, ast.Import):
                        named = next(
                            (a.name for a in node.names if a.name in dead), None
                        )
                    if named in dead:
                        offenders.append(
                            f"{py.relative_to(ROOT)}:{node.lineno}"
                        )
        assert offenders == [], offenders

    def test_the_implementation_stage_transport_is_untouched(self):
        """A DIFFERENT `claude_client` lives under the testing workflow and is
        very much alive. Deleting the core one must not have touched it."""
        module = importlib.import_module(
            "assemblyzero.workflows.testing.nodes.implementation.claude_client"
        )
        assert hasattr(module, "call_claude_for_file")


class TestTheSurvivingTransportKillsOnSilence:
    def test_it_has_an_idle_timeout(self):
        from assemblyzero.core.llm_provider import (
            IDLE_TIMEOUT_SECONDS,
            idle_timeout_seconds,
        )

        assert IDLE_TIMEOUT_SECONDS > 0
        assert idle_timeout_seconds() > 0

    def test_the_streaming_killer_is_the_idle_one(self):
        from assemblyzero.core import llm_provider

        assert hasattr(llm_provider, "_stream_with_idle_timeout")

    def test_a_wall_clock_kill_is_classified_as_deterministic(self):
        """#2423's gate depends on the transport distinguishing the two. If a
        second wall-clock transport reappeared without that classification,
        its kills would be re-paid."""
        from assemblyzero.core import retry_gate

        assert retry_gate.classify_failure("", timeout_kind="wall") == (
            retry_gate.CEILING_TIMEOUT
        )
        assert retry_gate.classify_failure("", timeout_kind="idle") == (
            retry_gate.IDLE_TIMEOUT
        )


class TestNoSecondWallClockTransportReappears:
    """The durable half. Deleting one is a fix; keeping one is a property."""

    #: Modules allowed to hold a `claude` subprocess timeout. The live
    #: transport uses it only as an outer backstop behind the idle watchdog.
    _ALLOWED = {
        "assemblyzero/core/llm_provider.py",
        "assemblyzero/workflows/testing/nodes/implementation/claude_client.py",
    }

    def test_only_known_modules_spawn_the_claude_cli(self):
        """Finds `subprocess` calls whose argv starts with a `claude` literal.

        AST rather than grep: a comment or a docstring mentioning the CLI is
        not a transport, and a guard whose first finding is a false alarm gets
        switched off within a day.
        """
        offenders: list[str] = []
        for py in (ROOT / "assemblyzero").rglob("*.py"):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
            except (SyntaxError, OSError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = getattr(func, "attr", None)
                if name not in ("run", "Popen", "check_output"):
                    continue
                if not node.args:
                    continue
                first = node.args[0]
                if not isinstance(first, ast.List) or not first.elts:
                    continue
                head = first.elts[0]
                spawns_claude = (
                    isinstance(head, ast.Constant)
                    and isinstance(head.value, str)
                    and "claude" in head.value.lower()
                )
                if spawns_claude:
                    rel = str(py.relative_to(ROOT)).replace("\\", "/")
                    if rel not in self._ALLOWED:
                        offenders.append(f"{rel}:{node.lineno}")
        assert offenders == [], (
            f"a Claude CLI is spawned outside the known transports: {offenders}. "
            "If that is deliberate, it needs the idle-timeout discipline "
            "(#2405) and the failure classification (#2423) before it ships."
        )

    def test_the_allowlist_is_not_stale(self):
        """A guard whose allowlist names files that no longer exist would pass
        while checking nothing."""
        for rel in self._ALLOWED:
            assert (ROOT / rel).exists(), rel
