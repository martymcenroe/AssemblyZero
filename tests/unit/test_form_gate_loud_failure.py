"""The form check's launcher preflight under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/form_gate.py``. A form check that could
not run used to print "could not be checked" and let the roll proceed, and a
crash in the discrimination or scope extension vanished without a word. Each
is now an ERROR line and an alert, and the preflight refuses: the launcher
already returns 91 on a refusal. The form check's own findings keep the
operator's 2026-08-12 ruling: only a malformed decision table refuses.
"""
from __future__ import annotations

import inspect
import logging

from assemblyzero.workflows.requirements import form_gate
from tests.unit.test_form_gate import GOOD_ISSUE

LOGGER = "assemblyzero.workflows.requirements.form_gate"


def _fetch(bodies, seen=None):
    def fetch(_repo_root, issue):
        if seen is not None:
            seen.append(issue)
        if issue not in bodies:
            raise RuntimeError(f"no such issue #{issue}")
        return (f"issue {issue}", bodies[issue])
    return fetch


def _crash(message):
    def crash(*_a, **_k):
        raise RuntimeError(message)
    return crash


def _errors(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]


class TestTheIssueRead:
    def test_149_an_issue_that_cannot_be_fetched_alerts_and_refuses(
        self, tmp_path, operator_alerts, caplog
    ):
        with caplog.at_level(logging.ERROR, logger=LOGGER):
            text, refuse = form_gate.check_form_at_preflight(tmp_path, [7], _fetch({}))
        assert refuse is True
        assert "no such issue #7" in text
        assert any("no such issue #7" in m for m in _errors(caplog))
        assert len(operator_alerts) == 1
        assert operator_alerts[0]["issue"] == 7
        assert "RuntimeError: no such issue #7" in operator_alerts[0]["cause"]

    def test_153_an_empty_body_alerts_and_refuses(self, tmp_path, operator_alerts):
        text, refuse = form_gate.check_form_at_preflight(
            tmp_path, [7], _fetch({7: "   \n"})
        )
        assert refuse is True
        assert "empty" in text
        assert len(operator_alerts) == 1
        assert "empty" in operator_alerts[0]["cause"]


class TestTheExtensions:
    def test_162_a_discrimination_crash_is_loud_and_refuses(
        self, tmp_path, monkeypatch, operator_alerts, caplog
    ):
        monkeypatch.setattr(form_gate, "check_discrimination", _crash("disc boom"))

        with caplog.at_level(logging.ERROR, logger=LOGGER):
            text, refuse = form_gate.check_form_at_preflight(
                tmp_path, [7], _fetch({7: GOOD_ISSUE})
            )
        assert refuse is True
        assert "disc boom" in text
        assert any("disc boom" in m for m in _errors(caplog))
        assert len(operator_alerts) == 1
        assert "RuntimeError: disc boom" in operator_alerts[0]["cause"]

    def test_169_a_scope_crash_is_loud_and_refuses(
        self, tmp_path, monkeypatch, operator_alerts, caplog
    ):
        monkeypatch.setattr(form_gate, "check_scope_coverage", _crash("scope boom"))

        with caplog.at_level(logging.ERROR, logger=LOGGER):
            text, refuse = form_gate.check_form_at_preflight(
                tmp_path, [7], _fetch({7: GOOD_ISSUE})
            )
        assert refuse is True
        assert "scope boom" in text
        assert any("scope boom" in m for m in _errors(caplog))
        assert len(operator_alerts) == 1

    def test_170_no_fail_open_tag_remains(self):
        assert "fail-open" not in inspect.getsource(form_gate)


class TestTheRefusal:
    def test_193_an_errored_item_refuses_in_render(self, operator_alerts):
        item = form_gate.IssueForm(issue=7, error="the issue could not be read")
        text, refuse = form_gate.render([item])
        assert refuse is True
        assert "could not be checked" in text
        assert "BLOCKED" in text

    def test_the_first_failure_stops_the_loop(self, tmp_path, operator_alerts):
        """No partial report: the issue after a failed one is not checked."""
        seen: list[int] = []
        _text, refuse = form_gate.check_form_at_preflight(
            tmp_path, [7, 8], _fetch({8: GOOD_ISSUE}, seen=seen)
        )
        assert refuse is True
        assert seen == [7]
        assert len(operator_alerts) == 1

    def test_a_good_issue_still_proceeds_without_an_alert(self, tmp_path, operator_alerts):
        """Kept: a form check that ran and found nothing malformed proceeds."""
        _text, refuse = form_gate.check_form_at_preflight(
            tmp_path, [7], _fetch({7: GOOD_ISSUE})
        )
        assert refuse is False
        assert operator_alerts == []
