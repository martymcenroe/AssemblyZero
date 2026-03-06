
import ast
import sys
import builtins
from dataclasses import dataclass, field

class SymbolSentinel(ast.NodeVisitor):
    def __init__(self, source_lines=None):
        self.scope_stack = [set()]
        self.errors = []
        self.source_lines = source_lines or []
    def _current_scope(self): return self.scope_stack[-1]
    def _define(self, name): self._current_scope().add(name)
    def _is_defined(self, name):
        if name in dir(builtins) or name in ['__name__', 'TYPE_CHECKING']: return True
        return any(name in scope for scope in reversed(self.scope_stack))
    def _push_scope(self): self.scope_stack.append(set())
    def _pop_scope(self): self.scope_stack.pop()
    
    def visit_ImportFrom(self, node):
        if any(a.name == '*' for a in node.names):
            self.errors.append('star')
    
    def visit_AsyncFunctionDef(self, node):
        print('DEBUG: VISITING ASYNC FN')
        self._define(node.name)
        self._push_scope()
        for b in node.body: self.visit(b)
        self._pop_scope()

    def visit_Match(self, node):
        print('DEBUG: VISITING MATCH')
        for case in node.cases:
            self._push_scope()
            for b in case.body: self.visit(b)
            self._pop_scope()

def test_coverage_manual():
    source = """
from math import *
async def foo(): pass
match x:
    case 1: pass
"""
    tree = ast.parse(source)
    v = SymbolSentinel()
    v.visit(tree)
    assert 'star' in v.errors
    # x is undefined, but we haven't implemented visit_Name in this mock
