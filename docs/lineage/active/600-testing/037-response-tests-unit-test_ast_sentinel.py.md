```python
"""Unit tests for AST Sentinel logic (Issue #600).

Tests cover all scenarios from LLD-600 verification matrix:
- REQ-1: AST parsing via ast.parse and NodeVisitor
- REQ-2: Detect ast.Load without corresponding definition
- REQ-3: Structured error messages
- REQ-4: Fail gate on errors
- REQ-5: Recursive scope tracking (locals, comprehensions, walrus, global/nonlocal)
- REQ-6: Ban star imports
- REQ-7: TYPE_CHECKING block support
- REQ-8: sentinel: disable-line comment support
"""

from __future__ import annotations

import sys
import textwrap
from io import StringIO
from unittest.mock import patch

import pytest

from assemblyzero.utils.ast_sentinel import (
    SentinelError,
    SentinelResult,
    SymbolSentinel,
    analyze_file,
    analyze_source,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _analyze(code: str) -> SentinelResult:
    """Analyze dedented source code and return the result."""
    return analyze_source(textwrap.dedent(code))


def _error_names(result: SentinelResult) -> list[str]:
    """Extract just the symbol names from a result's errors."""
    return [e.name for e in result.errors]


# ---------------------------------------------------------------------------
# test_010 — Happy path valid AST Analysis (REQ-1)
# ---------------------------------------------------------------------------


class TestHappyPath:
    """REQ-1: Parse using ast.parse and NodeVisitor with no errors."""

    def test_010_import_and_use(self):
        """import os; os.path.join() produces no errors."""
        result = _analyze("""\
            import os
            os.path.join("a", "b")
        """)
        assert result.ok
        assert result.errors == []

    def test_010_from_import(self):
        """from os.path import join produces no errors."""
        result = _analyze("""\
            from os.path import join
            join("a", "b")
        """)
        assert result.ok

    def test_010_aliased_import(self):
        """import numpy as np — alias is the defined name."""
        result = _analyze("""\
            import numpy as np
            np.array([1, 2, 3])
        """)
        assert result.ok

    def test_010_builtins_always_available(self):
        """Built-in names like print, len, dict need no import."""
        result = _analyze("""\
            x = len([1, 2, 3])
            print(x)
            d = dict(a=1)
        """)
        assert result.ok


# ---------------------------------------------------------------------------
# test_020 — Missing import verified (REQ-2)
# ---------------------------------------------------------------------------


class TestMissingImport:
    """REQ-2: Detect ast.Load without corresponding definition."""

    def test_020_missing_import(self):
        """json.dumps({}) without import produces error for 'json'."""
        result = _analyze("""\
            json.dumps({})
        """)
        assert not result.ok
        assert "json" in _error_names(result)

    def test_020_multiple_missing(self):
        """Multiple undefined symbols each produce errors."""
        result = _analyze("""\
            foo(bar, baz)
        """)
        names = _error_names(result)
        assert "foo" in names
        assert "bar" in names
        assert "baz" in names

    def test_020_attribute_only_checks_root(self):
        """Only the root object needs to be defined, not attributes."""
        result = _analyze("""\
            import os
            os.path.join("a", "b")
        """)
        assert result.ok


# ---------------------------------------------------------------------------
# test_030 — Feedback to stderr (REQ-3)
# ---------------------------------------------------------------------------


class TestErrorMessages:
    """REQ-3: State specific error with symbol name and line number."""

    def test_030_error_message_format(self):
        """Error message includes symbol name and line number."""
        result = _analyze("""\
            json.dumps({})
        """)
        assert len(result.errors) >= 1
        err = result.errors[0]
        assert err.name == "json"
        assert err.line == 1
        assert "json" in err.message
        assert "1" in err.message
        assert "not imported" in err.message

    def test_030_format_errors_output(self):
        """format_errors() produces multi-line string for stderr."""
        result = _analyze("""\
            json.dumps({})
        """)
        formatted = result.format_errors()
        assert "Symbol 'json' used on line 1 but not imported." in formatted

    def test_030_sentinel_error_str(self):
        """SentinelError.__str__ returns the message."""
        err = SentinelError(name="foo", line=5, message="Symbol 'foo' used on line 5 but not imported.")
        assert str(err) == "Symbol 'foo' used on line 5 but not imported."


# ---------------------------------------------------------------------------
# test_040 — Mechanical validation fail (REQ-4)
# ---------------------------------------------------------------------------


class TestFailGate:
    """REQ-4: CLI exits 1 on errors, 0 on clean."""

    def test_040_exit_1_on_errors(self, tmp_path):
        """Bad file causes main() to return 1."""
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("json.dumps({})\n", encoding="utf-8")

        stderr_capture = StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = main([str(bad_file)])

        assert exit_code == 1
        assert "json" in stderr_capture.getvalue()

    def test_040_exit_0_on_clean(self, tmp_path):
        """Clean file causes main() to return 0."""
        good_file = tmp_path / "good.py"
        good_file.write_text("import os\nos.getcwd()\n", encoding="utf-8")

        exit_code = main([str(good_file)])
        assert exit_code == 0

    def test_040_syntax_error_returns_1(self, tmp_path):
        """Syntax error in file causes main() to return 1."""
        bad_file = tmp_path / "syntax.py"
        bad_file.write_text("def foo(\n", encoding="utf-8")

        stderr_capture = StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = main([str(bad_file)])

        assert exit_code == 1

    def test_040_unreadable_file_returns_1(self, tmp_path):
        """Non-existent file causes main() to return 1."""
        stderr_capture = StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = main([str(tmp_path / "nonexistent.py")])

        assert exit_code == 1


# ---------------------------------------------------------------------------
# test_050 — Local scope resilience (REQ-5)
# ---------------------------------------------------------------------------


class TestLocalScope:
    """REQ-5: Args and locals recognized within function scope."""

    def test_050_function_args_and_locals(self):
        """def foo(a): b = a; return b — no errors."""
        result = _analyze("""\
            def foo(a):
                b = a
                return b
        """)
        assert result.ok

    def test_050_nested_functions(self):
        """Nested function args don't leak to outer scope."""
        result = _analyze("""\
            def outer():
                x = 1
                def inner(y):
                    return x + y
                return inner
        """)
        assert result.ok

    def test_050_class_scope(self):
        """Class body defines names in its own scope."""
        result = _analyze("""\
            class Foo:
                x = 1
                y = x + 1
        """)
        assert result.ok

    def test_050_for_loop_target(self):
        """For-loop target variable is defined."""
        result = _analyze("""\
            items = [1, 2, 3]
            for item in items:
                print(item)
        """)
        assert result.ok

    def test_050_with_statement(self):
        """With-statement optional_vars defines name."""
        result = _analyze("""\
            import io
            with io.StringIO() as f:
                print(f)
        """)
        assert result.ok

    def test_050_except_handler(self):
        """Exception handler name is defined."""
        result = _analyze("""\
            try:
                pass
            except Exception as e:
                print(e)
        """)
        assert result.ok

    def test_050_tuple_unpacking(self):
        """Tuple unpacking defines all target names."""
        result = _analyze("""\
            a, b, c = 1, 2, 3
            print(a, b, c)
        """)
        assert result.ok

    def test_050_starred_assignment(self):
        """Starred assignment defines the starred name."""
        result = _analyze("""\
            first, *rest = [1, 2, 3, 4]
            print(first, rest)
        """)
        assert result.ok


# ---------------------------------------------------------------------------
# test_060 — Comprehensions (REQ-5)
# ---------------------------------------------------------------------------


class TestComprehensions:
    """REQ-5: Comprehension variables isolated in their own scope."""

    def test_060_list_comprehension(self):
        """[x for x in y] — 'x' defined inside comprehension scope."""
        result = _analyze("""\
            y = [1, 2, 3]
            result = [x for x in y]
        """)
        assert result.ok

    def test_060_nested_comprehension(self):
        """Nested comprehension variables are scoped."""
        result = _analyze("""\
            matrix = [[1, 2], [3, 4]]
            flat = [x for row in matrix for x in row]
        """)
        assert result.ok

    def test_060_dict_comprehension(self):
        """Dict comprehension defines key/value vars."""
        result = _analyze("""\
            items = [(1, 'a'), (2, 'b')]
            d = {k: v for k, v in items}
        """)
        assert result.ok

    def test_060_set_comprehension(self):
        """Set comprehension variables are scoped."""
        result = _analyze("""\
            items = [1, 2, 3]
            s = {x * 2 for x in items}
        """)
        assert result.ok

    def test_060_generator_expression(self):
        """Generator expression variables are scoped."""
        result = _analyze("""\
            items = [1, 2, 3]
            total = sum(x for x in items)
        """)
        assert result.ok

    def test_060_comprehension_with_filter(self):
        """Comprehension if-clause can reference the loop variable."""
        result = _analyze("""\
            items = [1, 2, 3, 4, 5]
            evens = [x for x in items if x % 2 == 0]
        """)
        assert result.ok


# ---------------------------------------------------------------------------
# test_070 — Walrus Operators (REQ-5)
# ---------------------------------------------------------------------------


class TestWalrusOperator:
    """REQ-5: Walrus operator := defines name in enclosing scope."""

    def test_070_walrus_in_if(self):
        """if (n := len(a)) > 1: print(n) — 'n' recognized."""
        result = _analyze("""\
            a = [1, 2, 3]
            if (n := len(a)) > 1:
                print(n)
        """)
        assert result.ok

    def test_070_walrus_in_while(self):
        """Walrus in while condition defines the name for the body."""
        result = _analyze("""\
            import io
            data = io.BytesIO(b"hello")
            while (chunk := data.read(2)):
                print(chunk)
        """)
        assert result.ok


# ---------------------------------------------------------------------------
# test_080 — Star imports banned (REQ-6)
# ---------------------------------------------------------------------------


class TestStarImports:
    """REQ-6: Star imports produce an explicit error."""

    def test_080_from_star_import(self):
        """from typing import * produces 'Star imports are not allowed'."""
        result = _analyze("""\
            from typing import *
        """)
        assert not result.ok
        assert any("Star imports are not allowed" in str(e) for e in result.errors)

    def test_080_star_import_error_details(self):
        """Star import error has correct name and line."""
        result = _analyze("""\
            from os.path import *
        """)
        star_errors = [e for e in result.errors if e.name == "*"]
        assert len(star_errors) == 1
        assert star_errors[0].line == 1


# ---------------------------------------------------------------------------
# test_090 — Global/Nonlocal tracking (REQ-5)
# ---------------------------------------------------------------------------


class TestGlobalNonlocal:
    """REQ-5: global/nonlocal statements don't produce false positives."""

    def test_090_global_declaration(self):
        """global x; x = 1 — no errors."""
        result = _analyze("""\
            def foo():
                global x
                x = 1
        """)
        assert result.ok

    def test_090_nonlocal_declaration(self):
        """nonlocal references enclosing scope without error."""
        result = _analyze("""\
            def outer():
                x = 0
                def inner():
                    nonlocal x
                    x = 1
                inner()
                return x
        """)
        assert result.ok

    def test_090_global_used_after_declaration(self):
        """Global var usable after declaration."""
        result = _analyze("""\
            x = 10
            def foo():
                global x
                print(x)
        """)
        assert result.ok


# ---------------------------------------------------------------------------
# test_100 — TYPE_CHECKING support (REQ-7)
# ---------------------------------------------------------------------------


class TestTypeChecking:
    """REQ-7: if TYPE_CHECKING: imports register symbols."""

    def test_100_type_checking_import(self):
        """if TYPE_CHECKING: from x import y — 'y' is registered."""
        result = _analyze("""\
            from __future__ import annotations
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                from collections import OrderedDict
            def foo() -> OrderedDict:
                pass
        """)
        assert result.ok

    def test_100_type_checking_multiple_imports(self):
        """Multiple imports under TYPE_CHECKING are all registered."""
        result = _analyze("""\
            from __future__ import annotations
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                from pathlib import Path
                from typing import Any
            def bar(x: Path) -> Any:
                pass
        """)
        assert result.ok


# ---------------------------------------------------------------------------
# test_110 — Ignore comments (REQ-8)
# ---------------------------------------------------------------------------


class TestDisableComment:
    """REQ-8: sentinel: disable-line suppresses errors on that line."""

    def test_110_disable_line_suppresses(self):
        """var # sentinel: disable-line — no error for undefined var."""
        result = _analyze("""\
            undefined_var  # sentinel: disable-line
        """)
        assert result.ok

    def test_110_disable_only_affects_that_line(self):
        """Disable comment only suppresses the specific line."""
        result = _analyze("""\
            foo  # sentinel: disable-line
            bar
        """)
        # foo should be suppressed, bar should still error
        names = _error_names(result)
        assert "foo" not in names
        assert "bar" in names


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


class TestAnalyzeFile:
    """Tests for analyze_file function."""

    def test_analyze_file_valid(self, tmp_path):
        """analyze_file works on a real file."""
        f = tmp_path / "test.py"
        f.write_text("import os\nos.getcwd()\n", encoding="utf-8")
        result = analyze_file(f)
        assert result.ok

    def test_analyze_file_errors(self, tmp_path):
        """analyze_file detects errors in a real file."""
        f = tmp_path / "test.py"
        f.write_text("json.dumps({})\n", encoding="utf-8")
        result = analyze_file(f)
        assert not result.ok
        assert "json" in _error_names(result)

    def test_analyze_file_not_found(self, tmp_path):
        """analyze_file returns error for non-existent file."""
        result = analyze_file(tmp_path / "nope.py")
        assert not result.ok
        assert result.errors[0].name == "<io>"


class TestSentinelResult:
    """Tests for SentinelResult data class."""

    def test_ok_when_empty(self):
        """SentinelResult.ok is True when no errors."""
        assert SentinelResult().ok

    def test_not_ok_with_errors(self):
        """SentinelResult.ok is False when errors exist."""
        result = SentinelResult(errors=[
            SentinelError(name="x", line=1, message="test"),
        ])
        assert not result.ok


class TestEdgeCases:
    """Additional edge-case coverage."""

    def test_decorator_usage(self):
        """Decorators are checked in the enclosing scope."""
        result = _analyze("""\
            import functools
            @functools.wraps
            def foo():
                pass
        """)
        assert result.ok

    def test_augmented_assignment(self):
        """Augmented assignment (+=) recognizes existing var."""
        result = _analyze("""\
            x = 0
            x += 1
        """)
        assert result.ok

    def test_annotated_assignment(self):
        """Annotated assignment defines the name."""
        result = _analyze("""\
            x: int = 5
            print(x)
        """)
        assert result.ok

    def test_async_function(self):
        """Async function definitions are handled."""
        result = _analyze("""\
            async def foo(x):
                return x
        """)
        assert result.ok

    def test_multiple_files_cli(self, tmp_path):
        """CLI handles multiple files."""
        good = tmp_path / "good.py"
        good.write_text("import os\nos.getcwd()\n", encoding="utf-8")
        bad = tmp_path / "bad.py"
        bad.write_text("undefined_thing\n", encoding="utf-8")

        stderr_capture = StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = main([str(good), str(bad)])

        assert exit_code == 1
        assert "undefined_thing" in stderr_capture.getvalue()

    def test_syntax_error_handled(self):
        """Syntax errors produce a SentinelError, not an exception."""
        result = _analyze("""\
            def foo(
        """)
        assert not result.ok
        assert result.errors[0].name == "<syntax>"

    def test_implicit_globals_no_errors(self):
        """__name__, __file__ etc. are always available."""
        result = _analyze("""\
            if __name__ == "__main__":
                print(__file__)
        """)
        assert result.ok

    def test_class_bases_checked(self):
        """Class bases are checked in enclosing scope."""
        result = _analyze("""\
            class Foo(UndefinedBase):
                pass
        """)
        assert not result.ok
        assert "UndefinedBase" in _error_names(result)

    def test_delete_no_false_positive(self):
        """del statement doesn't produce false positive."""
        result = _analyze("""\
            x = 1
            del x
        """)
        assert result.ok
```
