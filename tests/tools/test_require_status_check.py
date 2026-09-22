"""Unit tests for tools/require_status_check.py.

Issue #3447. The decision logic, which is the whole of this tool: when it
refuses, when it no-ops, and what it writes. The credential path is not
exercised -- that decrypt belongs to the operator, never to a test or an agent,
per the _pat_session operational rule -- so `run()` is called directly with a
placeholder string in place of the PAT.

The HTTP layer is replaced rather than mocked at the requests level, so a test
that expects "nothing written" fails loudly if a write is attempted.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

import require_status_check as rsc  # noqa: E402

PAT = "not-a-real-token"


def cfg(**overrides):
    args = ["--repo", "SomeRepo", "--context", "pytest"]
    for key, value in overrides.items():
        if value is True:
            args.append(f"--{key.replace('_', '-')}")
        elif value is not False:
            args.extend([f"--{key.replace('_', '-')}", str(value)])
    return rsc.parse_args(args)


@pytest.fixture
def no_writes(monkeypatch):
    """Any POST is a test failure unless the test opts in."""
    def explode(*_args, **_kwargs):
        raise AssertionError("add_context was called when nothing should be written")

    monkeypatch.setattr(rsc, "add_context", explode)


class TestRefusals:
    """Two repository states the tool stops on rather than improvising through."""

    def test_unprotected_branch_stops(self, monkeypatch, no_writes, capsys):
        monkeypatch.setattr(rsc, "read_protection", lambda *_: None)
        assert rsc.run(PAT, cfg(apply=True)) == 1
        assert "no branch protection at all" in capsys.readouterr().out

    def test_protection_without_status_checks_stops(self, monkeypatch, no_writes, capsys):
        monkeypatch.setattr(rsc, "read_protection", lambda *_: {"enforce_admins": {}})
        assert rsc.run(PAT, cfg(apply=True)) == 1
        assert "switched off" in capsys.readouterr().out

    def test_refusal_holds_even_with_apply(self, monkeypatch, no_writes):
        """--apply is not an override for a decision about the repository."""
        monkeypatch.setattr(rsc, "read_protection", lambda *_: None)
        assert rsc.run(PAT, cfg(apply=True)) == 1


class TestNoOp:
    def test_context_already_required_is_a_success_and_writes_nothing(
        self, monkeypatch, no_writes, capsys
    ):
        monkeypatch.setattr(
            rsc,
            "read_protection",
            lambda *_: {"required_status_checks": {"contexts": ["issue-reference", "pytest"]}},
        )
        assert rsc.run(PAT, cfg(apply=True)) == 0
        assert "already required" in capsys.readouterr().out


class TestDryRun:
    def test_dry_run_is_the_default_and_writes_nothing(
        self, monkeypatch, no_writes, capsys
    ):
        monkeypatch.setattr(
            rsc,
            "read_protection",
            lambda *_: {"required_status_checks": {"contexts": ["issue-reference"]}},
        )
        assert rsc.run(PAT, cfg()) == 0
        out = capsys.readouterr().out
        assert "DRY-RUN" in out
        # The operator has to be able to see what they are adding TO: the job
        # name vs workflow name trap is only catchable by reading this line.
        assert "issue-reference" in out


class TestApply:
    def test_apply_adds_the_context(self, monkeypatch, capsys):
        seen = {}

        def fake_add(pat, config):
            seen["context"] = config.context
            return ["issue-reference", config.context]

        monkeypatch.setattr(
            rsc,
            "read_protection",
            lambda *_: {"required_status_checks": {"contexts": ["issue-reference"]}},
        )
        monkeypatch.setattr(rsc, "add_context", fake_add)
        assert rsc.run(PAT, cfg(apply=True)) == 0
        assert seen["context"] == "pytest"
        assert "issue-reference" in capsys.readouterr().out

    def test_empty_contexts_list_is_not_treated_as_missing(self, monkeypatch):
        """`contexts: []` means checks are ON with none listed, which is a
        different state from checks being off, and must not hit the refusal."""
        monkeypatch.setattr(
            rsc, "read_protection", lambda *_: {"required_status_checks": {"contexts": []}}
        )
        monkeypatch.setattr(rsc, "add_context", lambda *_: ["pytest"])
        assert rsc.run(PAT, cfg(apply=True)) == 0


class TestArgs:
    def test_defaults(self):
        c = cfg()
        assert c.owner == "martymcenroe"
        assert c.branch == "main"
        assert c.apply is False

    def test_branch_is_overridable(self):
        assert cfg(branch="release").branch == "release"
