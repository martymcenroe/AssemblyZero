"""api_symbols_exist on bases that are not classes but carry `__mro_entries__` (#4690).

`typing.TypedDict` and `typing.NamedTuple` are functions on current Python.
They hand a subclass its real base through PEP 560's `__mro_entries__`. The
check called them unresolvable, printed an ERROR, left every inherited method
unjudged, and passed the spec anyway.
"""

from __future__ import annotations

import importlib

import pytest

vc = importlib.import_module(
    "assemblyzero.workflows.implementation_spec.nodes.validate_completeness"
)


def _fence(body: str) -> str:
    return f"```python\n{body}\n```\n"


TYPED_DICT = _fence(
    "from typing import TypedDict\n\n"
    "class OutageDict(TypedDict):\n"
    "    turns_active: list\n\n"
    "def read(outage: OutageDict) -> list:\n"
    "    o = OutageDict(turns_active=[1])\n"
    "    o.setdefault('turns_active', [])\n"
    "    return o.copy()\n"
)

NAMED_TUPLE = _fence(
    "from typing import NamedTuple\n\n"
    "class Point(NamedTuple):\n"
    "    x: int\n\n"
    "def show() -> dict:\n"
    "    p = Point(x=1)\n"
    "    return p._asdict()\n"
)


class TestT1APep560BaseResolves:
    @pytest.mark.parametrize("dotted", ["typing.TypedDict", "typing.NamedTuple"])
    def test_the_base_resolves_to_a_class(self, dotted):
        resolved = vc._resolve_stdlib_class(dotted)
        assert isinstance(resolved, type), resolved

    def test_a_typed_dict_probe_carries_dicts_methods(self):
        resolved = vc._resolve_stdlib_class("typing.TypedDict")
        assert {"setdefault", "copy", "items"} <= set(dir(resolved))

    def test_a_named_tuple_probe_carries_asdict(self):
        resolved = vc._resolve_stdlib_class("typing.NamedTuple")
        assert "_asdict" in set(dir(resolved))

    @pytest.mark.parametrize("spec", [TYPED_DICT, NAMED_TUPLE], ids=["TypedDict", "NamedTuple"])
    def test_the_check_passes_with_no_error(self, spec, capsys):
        check = vc.check_api_symbols_exist(spec, ["unrelated"], "")
        assert check["passed"], check["details"]
        assert "ERROR" not in check["details"]
        assert "ERROR" not in capsys.readouterr().err


class TestT4AForeignBaseStillAbstains:
    def test_a_third_party_base_abstains_silently(self, capsys):
        """#2839 kept: a foreign base is not the checker failing."""
        spec = _fence(
            "from pydantic import BaseModel\n\n"
            "class M(BaseModel):\n"
            "    def go(self):\n"
            "        self.model_frobnicate()\n"
        )
        check = vc.check_api_symbols_exist(spec, ["unrelated"], "")
        assert check["passed"], check["details"]
        assert "ERROR" not in capsys.readouterr().err


class TestADerivedClassInheritsTheBlindness:
    def test_a_subclass_of_a_blind_class_cannot_check_either(self, capsys):
        spec = _fence(
            "import ctypes\n\n"
            "class Thing(ctypes.NoSuchBase):\n"
            "    pass\n\n"
            "class Child(Thing):\n"
            "    def go(self):\n"
            "        self.frobnicate_later()\n"
        )
        with pytest.raises(vc.CompletenessCannotCheck) as raised:
            vc.check_api_symbols_exist(spec, ["unrelated"], "")
        assert "frobnicate_later" in str(raised.value)
