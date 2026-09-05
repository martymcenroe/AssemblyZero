"""#2839: a spec-defined subclass's surface includes what it inherits.

Run 15 resumed (`run-issue4-040403`, 2026-09-05) spent a completeness
iteration on `api_symbols_exist` flagging `UNICODE_STRING.from_buffer_copy`,
`self.generic_visit(node)` and `visitor.visit(tree)` -- ctypes.Structure's
classmethod and ast.NodeVisitor's methods, on classes the spec defined as
their subclasses. The check recorded the classes by name and never read
their bases, so their instances were judged against the target repo's
symbols, where nothing inherited from the standard library can be found.
"""

from __future__ import annotations

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    detect_unknown_method_calls,
)

# The target repo's gathered symbols: nothing from ctypes or ast is in here.
TARGET = {"WindowsCollector", "collect", "start", "stop", "Gauge", "render"}


def _spec(code: str) -> str:
    return f"## 6. Implementation\n\n```python\n{code}\n```\n"


class TestRun15sThreeCalls:
    def test_a_ctypes_structure_subclass_inherits_from_buffer_copy(self):
        spec = _spec(
            "import ctypes\n"
            "class UNICODE_STRING(ctypes.Structure):\n"
            "    _fields_ = [('Length', ctypes.c_ushort)]\n"
            "us = UNICODE_STRING.from_buffer_copy(buffer, offset + 56)\n"
        )
        assert detect_unknown_method_calls(spec, set(TARGET)) == {}

    def test_a_node_visitor_subclass_inherits_visit_and_generic_visit(self):
        spec = _spec(
            "import ast\n"
            "class SweepVisitor(ast.NodeVisitor):\n"
            "    def visit_Call(self, node):\n"
            "        self.generic_visit(node)\n"
            "visitor = SweepVisitor()\n"
            "visitor.visit(tree)\n"
        )
        assert detect_unknown_method_calls(spec, set(TARGET)) == {}

    def test_a_bare_imported_base_resolves_through_its_import(self):
        spec = _spec(
            "from ctypes import Structure, c_ushort\n"
            "class S(Structure):\n"
            "    _fields_ = [('n', c_ushort)]\n"
            "s = S.from_buffer_copy(b)\n"
        )
        assert detect_unknown_method_calls(spec, set(TARGET)) == {}

    def test_an_aliased_module_resolves(self):
        spec = _spec(
            "import ctypes as c\n"
            "class S(c.Structure):\n"
            "    pass\n"
            "S.from_buffer_copy(b)\n"
        )
        assert detect_unknown_method_calls(spec, set(TARGET)) == {}


class TestWhatStaysFlagged:
    def test_a_typo_on_the_inherited_name_is_still_flagged(self):
        spec = _spec(
            "import ctypes\n"
            "class UNICODE_STRING(ctypes.Structure):\n"
            "    pass\n"
            "us = UNICODE_STRING.from_buffer_cpy(buffer, 56)\n"
        )
        assert set(detect_unknown_method_calls(spec, set(TARGET))) == {"from_buffer_cpy"}

    def test_self_method_the_class_neither_defines_nor_inherits_is_flagged(self):
        spec = _spec(
            "import ast\n"
            "class SweepVisitor(ast.NodeVisitor):\n"
            "    def visit_Call(self, node):\n"
            "        self.render_all(node)\n"
            "        self.generic_visit(node)\n"
        )
        assert set(detect_unknown_method_calls(spec, set(TARGET))) == {"render_all"}

    def test_a_class_with_no_foreign_base_is_judged_as_before(self):
        """#1527's founding true positive: pydantic's method on a plain class."""
        spec = _spec(
            "class Gauge:\n"
            "    def render(self):\n"
            "        return 1\n"
            "g = Gauge()\n"
            "g.model_dump()\n"
        )
        assert set(detect_unknown_method_calls(spec, set(TARGET))) == {"model_dump"}

    def test_self_call_inside_a_plain_class_is_judged_as_before(self):
        spec = _spec(
            "class Gauge:\n"
            "    def render(self):\n"
            "        return self.model_dump()\n"
        )
        assert set(detect_unknown_method_calls(spec, set(TARGET))) == {"model_dump"}


class TestForeignBasesAbstain:
    def test_a_third_party_base_the_checker_cannot_resolve_abstains(self):
        spec = _spec(
            "from pydantic import BaseModel\n"
            "class Config(BaseModel):\n"
            "    name: str\n"
            "cfg = Config(name='x')\n"
            "cfg.model_dump()\n"
        )
        assert detect_unknown_method_calls(spec, set(TARGET)) == {}

    def test_a_spec_defined_base_passes_its_inheritance_down(self):
        spec = _spec(
            "import ast\n"
            "class Base(ast.NodeVisitor):\n"
            "    pass\n"
            "class Leaf(Base):\n"
            "    def visit_Name(self, node):\n"
            "        self.generic_visit(node)\n"
        )
        assert detect_unknown_method_calls(spec, set(TARGET)) == {}

    def test_self_root_attribute_calls_are_not_the_classs(self):
        """`self.root.x()` keys on `root`, whoever owns it -- unchanged by #2839."""
        spec = _spec(
            "import tkinter as tk\n"
            "class App:\n"
            "    def __init__(self):\n"
            "        self.root = tk.Tk()\n"
            "        self.root.attributes('-topmost', True)\n"
        )
        assert detect_unknown_method_calls(spec, set(TARGET)) == {}
