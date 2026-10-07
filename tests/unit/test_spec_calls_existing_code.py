"""A spec names only code that exists, with the signatures it has (#3754, #3755).

boostgauge #2 run-issue2-024542 (2026-10-07): the spec imported
`boostgauge.renderer`, which exists nowhere, and called
`Telltale(duration=...)` against `Telltale.__init__(self, window,
decay_rate=None)` in a file the plan did not own. Both passed the completeness
gate; the implementer could only answer NO-EDIT until the green phase ran out.
"""

from __future__ import annotations

from pathlib import Path

from assemblyzero.workflows.implementation_spec.nodes.validate_completeness import (
    check_call_signatures_match,
    check_import_targets_exist,
)

TELLTALE = '''
class Telltale:
    def __init__(self, window: float | None, decay_rate: float | None = None) -> None:
        self.window = window

def format_age(seconds, *, precise=False):
    return str(seconds)

class Config:
    pass

def build(**options):
    return options
'''


def _repo(tmp_path: Path) -> Path:
    pkg = tmp_path / "src" / "boostgauge"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "telltale.py").write_text(TELLTALE, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "boostgauge"\npackages = [{ include = "boostgauge", from = "src" }]\n',
        encoding="utf-8",
    )
    return tmp_path


def _spec(code: str) -> str:
    return f"# Spec\n\n```python\n{code}\n```\n"


PLAN = [{"path": "src/boostgauge/telltale_group.py", "change_type": "Add"}]


# ---- #3755: keyword arguments against the real signature ----


def test_the_boostgauge_call_fails_and_names_the_real_signature(tmp_path):
    spec = _spec("from boostgauge.telltale import Telltale\nshort = Telltale(duration=60.0)\n")
    result = check_call_signatures_match(spec, PLAN, str(_repo(tmp_path)))
    assert not result["passed"]
    assert "duration" in result["details"]
    assert "window" in result["details"]


def test_the_real_keyword_and_a_positional_call_pass(tmp_path):
    spec = _spec(
        "from boostgauge.telltale import Telltale\n"
        "a = Telltale(window=60.0)\nb = Telltale(60.0)\nc = Telltale(None, decay_rate=0.5)\n"
    )
    assert check_call_signatures_match(spec, PLAN, str(_repo(tmp_path)))["passed"]


def test_a_function_with_a_wrong_keyword_fails(tmp_path):
    spec = _spec("from boostgauge.telltale import format_age\nformat_age(5, exact=True)\n")
    result = check_call_signatures_match(spec, PLAN, str(_repo(tmp_path)))
    assert not result["passed"]
    assert "exact" in result["details"]


def test_a_keyword_only_parameter_is_accepted(tmp_path):
    spec = _spec("from boostgauge.telltale import format_age\nformat_age(5, precise=True)\n")
    assert check_call_signatures_match(spec, PLAN, str(_repo(tmp_path)))["passed"]


def test_kwargs_and_classes_without_init_are_not_judged(tmp_path):
    spec = _spec(
        "from boostgauge.telltale import Config, build\n"
        "Config(anything=1)\nbuild(whatever=2)\n"
    )
    assert check_call_signatures_match(spec, PLAN, str(_repo(tmp_path)))["passed"]


def test_a_callee_the_plan_changes_is_not_judged(tmp_path):
    plan = PLAN + [{"path": "src/boostgauge/telltale.py", "change_type": "Modify"}]
    spec = _spec("from boostgauge.telltale import Telltale\nTelltale(duration=60.0)\n")
    assert check_call_signatures_match(spec, plan, str(_repo(tmp_path)))["passed"]


def test_an_aliased_import_is_followed(tmp_path):
    spec = _spec("from boostgauge.telltale import Telltale as T\nT(duration=60.0)\n")
    assert not check_call_signatures_match(spec, PLAN, str(_repo(tmp_path)))["passed"]


def test_an_unparseable_fence_is_left_to_its_own_check(tmp_path):
    spec = _spec("from boostgauge.telltale import Telltale\nTelltale(duration=60.0\n")
    assert check_call_signatures_match(spec, PLAN, str(_repo(tmp_path)))["passed"]


# ---- #3754: a missing submodule of a real package ----


def test_an_import_of_a_missing_submodule_fails_the_import_check(tmp_path):
    spec = _spec("from boostgauge.renderer import Renderer\n")
    result = check_import_targets_exist(spec, PLAN, str(_repo(tmp_path)))
    assert not result["passed"]
    assert "boostgauge.renderer" in result["details"]


def test_an_import_of_a_real_submodule_passes_the_import_check(tmp_path):
    spec = _spec("from boostgauge.telltale import Telltale\n")
    assert check_import_targets_exist(spec, PLAN, str(_repo(tmp_path)))["passed"]
