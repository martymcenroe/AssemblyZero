"""The default-argument-binding audit must be able to fail (#2264).

An audit that has never caught anything is indistinguishable from one that
cannot. The positive fixtures below build the real trap in a temporary tree and
assert the audit finds it; the negative ones build each shape that LOOKS like
the trap and is not, because a check that cries wolf is a check people skip.

That distinction is the whole design. A first cut of this script matched on the
bare attribute name and reported seven suspects on the live tree, of which zero
were defects. This version reports the seven as nothing and finds a real one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import audit_default_arg_patches as audit_mod  # noqa: E402


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A miniature repo the audit can be pointed at."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "t").mkdir()
    monkeypatch.setattr(audit_mod, "ROOT", tmp_path)
    return tmp_path


def _write(tree, rel, body):
    path = tree / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The positive case: the audit CAN fail
# ---------------------------------------------------------------------------


class TestItCatchesTheRealTrap:
    """The #2192 shape, reconstructed: a default-bound collaborator, a caller
    that omits it, and a test that patches at module level."""

    def _build(self, tree):
        _write(tree, "pkg/mod.py", '''
def _default_runner(args):
    return "real"


def repo_slug(repo_root, runner=_default_runner):
    return runner(["git", "remote"])


def caller(repo_root):
    return repo_slug(repo_root)
''')
        _write(tree, "t/test_mod.py", '''
from unittest.mock import patch


def test_slug():
    with patch("pkg.mod._default_runner") as fake:
        fake.return_value = "stub"
        assert caller("x") == "stub"
''')

    def test_it_is_reported_as_a_finding(self, tree):
        self._build(tree)
        findings, _suspects = audit_mod.audit(("pkg",), ("t",))
        assert len(findings) == 1

    def test_the_finding_names_the_frozen_call_site(self, tree):
        self._build(tree)
        findings, _ = audit_mod.audit(("pkg",), ("t",))
        frozen = findings[0]["frozen_call_sites"]
        assert frozen[0]["function"] == "repo_slug"
        assert frozen[0]["parameter"] == "runner"
        assert frozen[0]["lines"]

    def test_the_command_exits_non_zero(self, tree, capsys):
        self._build(tree)
        monkey = audit_mod
        original_sources, original_tests = monkey.SOURCE_DIRS, monkey.TEST_DIRS
        monkey.SOURCE_DIRS, monkey.TEST_DIRS = ("pkg",), ("t",)
        try:
            code = audit_mod.main([])
        finally:
            monkey.SOURCE_DIRS, monkey.TEST_DIRS = original_sources, original_tests
        assert code == 1
        assert "VACUOUS" in capsys.readouterr().out

    def test_monkeypatch_setattr_is_caught_too(self, tree):
        _write(tree, "pkg/mod.py", '''
def _runner(a):
    return 1


def f(x, runner=_runner):
    return runner(x)


def caller(x):
    return f(x)
''')
        _write(tree, "t/test_mod.py", '''
def test_it(monkeypatch):
    monkeypatch.setattr(mod, "_runner", lambda a: 2)
''')
        findings, _ = audit_mod.audit(("pkg",), ("t",))
        assert len(findings) == 1


# ---------------------------------------------------------------------------
# The negative cases: everything that looks like the trap and is not
# ---------------------------------------------------------------------------


class TestItDoesNotCryWolf:
    def test_an_explicit_call_site_is_not_a_finding(self, tree):
        """The `sentinel_migrate.AUDIT_CSV` shape: captured as a default, but
        every caller passes it, so the patch is live."""
        _write(tree, "pkg/mod.py", '''
AUDIT_CSV = "real.csv"


def find_outliers(audit_csv=AUDIT_CSV):
    return audit_csv


def main():
    return find_outliers(AUDIT_CSV)
''')
        _write(tree, "t/test_mod.py", '''
def test_it(monkeypatch):
    monkeypatch.setattr(mod, "AUDIT_CSV", "fake.csv")
''')
        findings, suspects = audit_mod.audit(("pkg",), ("t",))
        assert findings == []
        assert len(suspects) == 1

    def test_a_name_captured_in_a_DIFFERENT_module_is_not_a_finding(self, tree):
        """The `builtins.print` shape: the audit's first cut matched the bare
        name and reported four of these."""
        _write(tree, "pkg/other.py", '''
def logs(x, log=print):
    return log(x)


def caller(x):
    return logs(x)
''')
        _write(tree, "pkg/mod.py", '''
def unrelated(x):
    print(x)
''')
        _write(tree, "t/test_mod.py", '''
from unittest.mock import patch


def test_it():
    with patch("builtins.print"):
        pass
''')
        findings, _ = audit_mod.audit(("pkg",), ("t",))
        assert findings == []

    def test_a_module_constant_read_in_the_body_is_not_a_finding(self, tree):
        """The `MERGEABLE_TIMEOUT_S` shape: read from module scope at call
        time, so the patch is live."""
        _write(tree, "pkg/mod.py", '''
TIMEOUT = 900


def wait():
    return TIMEOUT
''')
        _write(tree, "t/test_mod.py", '''
def test_it(monkeypatch):
    monkeypatch.setattr(mod, "TIMEOUT", 1)
''')
        findings, suspects = audit_mod.audit(("pkg",), ("t",))
        assert findings == []
        assert suspects == []

    def test_a_literal_default_is_not_the_trap(self, tree):
        """A literal cannot be rebound by a module-level patch."""
        _write(tree, "pkg/mod.py", '''
def f(x, retries=3):
    return retries


def caller(x):
    return f(x)
''')
        _write(tree, "t/test_mod.py", '''
def test_it(monkeypatch):
    monkeypatch.setattr(mod, "retries", 9)
''')
        findings, _ = audit_mod.audit(("pkg",), ("t",))
        assert findings == []

    def test_a_keyword_argument_at_the_call_site_clears_it(self, tree):
        _write(tree, "pkg/mod.py", '''
def _runner(a):
    return 1


def f(x, runner=_runner):
    return runner(x)


def caller(x):
    return f(x, runner=_runner)
''')
        _write(tree, "t/test_mod.py", '''
def test_it(monkeypatch):
    monkeypatch.setattr(mod, "_runner", lambda a: 2)
''')
        findings, suspects = audit_mod.audit(("pkg",), ("t",))
        assert findings == []
        assert len(suspects) == 1

    def test_a_module_nothing_patches_is_not_reported(self, tree):
        _write(tree, "pkg/mod.py", '''
def _runner(a):
    return 1


def f(x, runner=_runner):
    return runner(x)


def caller(x):
    return f(x)
''')
        _write(tree, "t/test_mod.py", "def test_nothing():\n    assert True\n")
        findings, suspects = audit_mod.audit(("pkg",), ("t",))
        assert findings == []
        assert suspects == []


# ---------------------------------------------------------------------------
# The live tree
# ---------------------------------------------------------------------------


class TestTheToolDoesNotContainTheDefectItHunts:
    """The audit's own first cut had the bug. `audit(source_dirs=SOURCE_DIRS)`
    captured the constant at definition time, so a test patching the module
    constant was testing nothing -- and the positive fixture above failed for
    that reason rather than for the reason it was written. Pinned so it cannot
    come back."""

    def test_the_entry_points_resolve_their_directories_at_call_time(self):
        import inspect

        for function in (audit_mod.audit, audit_mod.scan_sources):
            for name, parameter in inspect.signature(function).parameters.items():
                if name.endswith("_dirs"):
                    assert parameter.default is None, (
                        f"{function.__name__}({name}=...) captures a value at "
                        "definition time -- the very trap this script hunts"
                    )

    def test_patching_the_module_constants_actually_takes_effect(self, tree, monkeypatch):
        _write(tree, "pkg/mod.py", '''
def _runner(a):
    return 1


def f(x, runner=_runner):
    return runner(x)


def caller(x):
    return f(x)
''')
        _write(tree, "t/test_mod.py", '''
def test_it(monkeypatch):
    monkeypatch.setattr(mod, "_runner", lambda a: 2)
''')
        monkeypatch.setattr(audit_mod, "SOURCE_DIRS", ("pkg",))
        monkeypatch.setattr(audit_mod, "TEST_DIRS", ("t",))
        findings, _ = audit_mod.audit()
        assert len(findings) == 1, "the module-level patch did not take effect"


class TestTheLiveTreeIsClean:
    def test_no_vacuous_patches_on_main(self):
        """The #2264 blast-radius answer, kept honest by re-running.

        Settled by experiment 2026-08-15: the two `sentinel_migrate.AUDIT_CSV`
        patches are live (`main` calls `find_outliers(AUDIT_CSV)` explicitly --
        pointing the module attribute at a nonexistent path raises), the four
        `builtins.print` patches target a module with no callable defaults, and
        `MERGEABLE_TIMEOUT_S` is read from module scope in the body. Zero
        vacuous tests.
        """
        findings, _suspects = audit_mod.audit()
        assert findings == [], (
            "a test patches a name its target captures as a default, and a "
            f"call site omits it: {findings}"
        )
