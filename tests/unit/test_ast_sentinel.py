"""Unit tests for AST Sentinel logic (Issue #600)."""

from __future__ import annotations

import sys
import textwrap
from io import StringIO
from unittest.mock import patch
from pathlib import Path

import pytest

from assemblyzero.utils.ast_sentinel import (
    SentinelError,
    SentinelResult,
    SymbolSentinel,
    analyze_file,
    analyze_source,
    main,
)

def _analyze(code: str) -> SentinelResult:
    return analyze_source(textwrap.dedent(code))

def _error_names(result: SentinelResult) -> list[str]:
    return [e.name for e in result.errors]

class TestHappyPath:
    def test_010_import_and_use(self):
        result = _analyze("""\
            import os
            os.path.join("a", "b")
        """)
        assert result.ok

    def test_010_from_import(self):
        result = _analyze("""\
            from os.path import join
            join("a", "b")
        """)
        assert result.ok

    def test_010_aliased_import(self):
        result = _analyze("""\
            import numpy as np
            np.array([1, 2, 3])
        """)
        assert result.ok

class TestMissingImport:
    def test_020_missing_import(self):
        result = _analyze("json.dumps({})")
        assert not result.ok
        assert "json" in _error_names(result)

class TestLocalScope:
    def test_050_function_args(self):
        result = _analyze("""\
            def foo(a):
                return a
        """)
        assert result.ok

class TestComprehensions:
    def test_060_list_comp(self):
        result = _analyze("[x for x in [1,2]]")
        assert result.ok

class TestWalrus:
    def test_070_walrus(self):
        result = _analyze("if (x := 10): print(x)")
        assert result.ok

class TestStarImports:
    def test_080_star_import(self):
        result = _analyze("from typing import *")
        assert not result.ok
        assert "*" in _error_names(result)

class TestTypeChecking:
    def test_100_type_checking(self):
        result = _analyze("""\
            from typing import TYPE_CHECKING
            if TYPE_CHECKING:
                import os
            def foo():
                print(os.path)
        """)
        assert result.ok

class TestExtraCoverage:
    def test_async_function(self):
        result = _analyze("async def foo(x): return x")
        assert result.ok

    def test_function_annotations(self):
        result = _analyze("def foo(x: int) -> str: return str(x)")
        assert result.ok

    def test_match_statement(self):
        # Point and x are undefined
        result = _analyze("""\
            match x:
                case [1, y]: print(y)
                case Point(px, py): print(px)
        """)
        assert "x" in _error_names(result)
        assert "Point" in _error_names(result)

    def test_except_handler(self):
        result = _analyze("""\
            try: pass
            except Exception as e: print(e)
        """)
        assert result.ok

    def test_cli_main(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("print(undefined_var)", encoding="utf-8")
        assert main([str(f)]) == 1
        
        f2 = tmp_path / "good.py"
        f2.write_text("x = 1; print(x)", encoding="utf-8")
        assert main([str(f2)]) == 0

    def test_analyze_file_io_error(self):
        result = analyze_file("non_existent_file_999.py")
        assert not result.ok
        assert result.errors[0].name == "<io>"

    def test_syntax_error(self):
        result = _analyze("if x:")
        assert not result.ok
        assert result.errors[0].name == "<syntax>"
        
    def test_async_for_with(self):
        # y and ctx are undefined
        result = _analyze("""\
            async def foo():
                async for x in y: pass
                async with ctx as z: pass
        """)
        assert "y" in _error_names(result)
        assert "ctx" in _error_names(result)

    def test_global_nonlocal(self):
        result = _analyze("""\
            x = 1
            def foo():
                global x
                print(x)
        """)
        assert result.ok
