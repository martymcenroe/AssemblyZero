"""Contract fidelity under standard 0034 (#3585).

Each test is named for its ledger line in
docs/audits/0908-loud-failure-sweep-ledger.md (base ``79e18ad1``), for
``assemblyzero/workflows/requirements/contract_fidelity.py``. The audit stays
report-only for its FINDINGS: a decision table the reviewer faults is printed
and the roll may go on. What changes is an audit that could not run. A
declared contract that is missing or unreadable, an issue that cannot be
fetched, a brief that cannot be assembled, a reviewer that cannot be resolved
or answers nothing usable: each raises or is not reached, and the preflight
alerts the operator and refuses. A repo that declares no contract still pays
nothing and is not refused.
"""
from __future__ import annotations

import inspect
import json
import logging
from pathlib import Path

import pytest

from assemblyzero.core.llm_provider import LLMCallResult
from assemblyzero.workflows.requirements import contract_fidelity as cf
from tests.unit.test_contract_fidelity import BODY_331, CONTRACT, TITLE_331

LOGGER = "assemblyzero.workflows.requirements.contract_fidelity"


def _declare(repo: Path, *, write_contract: bool = True) -> Path:
    design = repo / "docs" / "design"
    design.mkdir(parents=True, exist_ok=True)
    contract = design / "0002-aesthetic.md"
    if write_contract:
        contract.write_text(CONTRACT, encoding="utf-8")
    (design / "visual-gate.json").write_text(
        json.dumps({
            "issues": [331, 332],
            "renderer_cmd": ["true"],
            "contract": "docs/design/0002-aesthetic.md",
            "separation_floor": 85,
        }),
        encoding="utf-8",
    )
    return contract


@pytest.fixture
def repo(tmp_path):
    _declare(tmp_path)
    return tmp_path


def _result(success, response, error=None):
    return LLMCallResult(
        success=success, response=response, raw_response=response,
        error_message=error, provider="fake", model_used="fake-model",
        duration_ms=1, attempts=1,
    )


def _provider(monkeypatch, *results):
    answers = list(results)

    class _P:
        def invoke(self, **_kwargs):
            return answers.pop(0) if len(answers) > 1 else answers[0]

    import assemblyzero.core.llm_provider as llm

    monkeypatch.setattr(llm, "get_provider", lambda *_a, **_k: _P())


def _fetch(title=TITLE_331, body=BODY_331, seen=None):
    def fetch(_repo_root, issue):
        if seen is not None:
            seen.append(issue)
        return (title, body)
    return fetch


class TestTheContract:
    def test_376_a_declared_contract_that_is_missing_raises(self, tmp_path):
        contract = _declare(tmp_path, write_contract=False)

        with pytest.raises(FileNotFoundError) as raised:
            cf.resolve_contract(tmp_path, 331)
        assert str(contract) in str(raised.value)
        assert "visual-gate.json" in str(raised.value)

    def test_376_the_preflight_refuses_a_missing_contract(self, tmp_path, operator_alerts):
        _declare(tmp_path, write_contract=False)

        text, refuse = cf.check_contract_fidelity_at_preflight(tmp_path, [331], _fetch())
        assert refuse is True
        assert "FileNotFoundError" in text
        assert len(operator_alerts) == 1
        assert operator_alerts[0]["issue"] == 331

    def test_a_repo_declaring_no_contract_is_not_applicable(self, tmp_path, operator_alerts):
        """Kept: no declaration, nothing to audit, nothing spent, no refusal."""
        assert cf.resolve_contract(tmp_path, 331) is None
        text, refuse = cf.check_contract_fidelity_at_preflight(tmp_path, [331], _fetch())
        assert refuse is False
        assert "declares no binding contract" in text
        assert operator_alerts == []

    def test_an_issue_the_declaration_does_not_cover_is_not_applicable(
        self, repo, operator_alerts
    ):
        """Kept: the contract binds the issues it lists, and no others."""
        assert cf.resolve_contract(repo, 999) is None
        _text, refuse = cf.check_contract_fidelity_at_preflight(repo, [999], _fetch())
        assert refuse is False
        assert operator_alerts == []

    def test_864_an_unreadable_contract_raises_and_refuses(
        self, repo, monkeypatch, operator_alerts
    ):
        contract = repo / "docs" / "design" / "0002-aesthetic.md"
        real = Path.read_text

        def read_text(self, *args, **kwargs):
            if self == contract:
                raise PermissionError(13, "Permission denied", str(self))
            return real(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", read_text)

        with pytest.raises(PermissionError):
            cf.build_brief(repo, 331, TITLE_331, BODY_331)
        _text, refuse = cf.check_contract_fidelity_at_preflight(repo, [331], _fetch())
        assert refuse is True
        assert len(operator_alerts) == 1
        assert "PermissionError" in operator_alerts[0]["cause"]

    def test_865_1031_1061_1095_no_fail_open_tag_remains(self):
        for function in (
            cf.build_brief, cf.review_fidelity, cf.check_contract_fidelity_at_preflight,
        ):
            assert "fail-open" not in inspect.getsource(function)


class TestTheReview:
    def test_1018_a_brief_that_is_not_ready_refuses(self, repo, operator_alerts):
        text, refuse = cf.check_contract_fidelity_at_preflight(
            repo, [331], _fetch(body="Just prose, no decision table.\n")
        )
        assert refuse is True
        assert "NOT CHECKED" in text
        assert len(operator_alerts) == 1
        assert "no criteria table" in operator_alerts[0]["cause"]

    def test_1030_a_reviewer_that_cannot_be_resolved_raises(self, repo, operator_alerts):
        brief = cf.build_brief(repo, 331, TITLE_331, BODY_331)
        with pytest.raises(ValueError, match="no-such-provider"):
            cf.review_fidelity(brief, drafter_spec="no-such-provider:model")

        _text, refuse = cf.check_contract_fidelity_at_preflight(
            repo, [331], _fetch(), drafter_spec="no-such-provider:model"
        )
        assert refuse is True
        assert len(operator_alerts) == 1
        assert operator_alerts[0]["spec"] == "no-such-provider:model"

    def test_1052_a_failed_model_call_is_loud_and_refuses(
        self, repo, monkeypatch, operator_alerts, caplog
    ):
        _provider(monkeypatch, _result(False, None, error="provider storm"))
        brief = cf.build_brief(repo, 331, TITLE_331, BODY_331)

        with caplog.at_level(logging.ERROR, logger=LOGGER):
            review = cf.review_fidelity(brief, drafter_spec="fake:model")
        assert review.reached is False
        assert any(
            r.levelno == logging.ERROR and "provider storm" in r.getMessage()
            for r in caplog.records
        )

        _text, refuse = cf.check_contract_fidelity_at_preflight(
            repo, [331], _fetch(), drafter_spec="fake:model"
        )
        assert refuse is True
        assert len(operator_alerts) == 1
        assert "provider storm" in operator_alerts[0]["cause"]

    def test_1060_an_answer_that_is_not_json_raises(self, repo, monkeypatch):
        _provider(monkeypatch, _result(True, "the table looks fine to me"))
        brief = cf.build_brief(repo, 331, TITLE_331, BODY_331)

        with pytest.raises(ValueError, match="not JSON") as raised:
            cf.review_fidelity(brief, drafter_spec="fake:model")
        assert "the table looks fine" in str(raised.value)

    def test_1069_an_answer_with_no_findings_list_raises(self, repo, monkeypatch):
        _provider(monkeypatch, _result(True, json.dumps({"verdict": "fine"})))
        brief = cf.build_brief(repo, 331, TITLE_331, BODY_331)

        with pytest.raises(ValueError, match="no findings list") as raised:
            cf.review_fidelity(brief, drafter_spec="fake:model")
        assert "verdict" in str(raised.value)

    def test_an_empty_findings_list_is_a_real_answer(self, repo, monkeypatch, operator_alerts):
        """Kept: a reviewer that finds nothing has reached a verdict."""
        _provider(monkeypatch, _result(True, json.dumps({"findings": []})))
        _text, refuse = cf.check_contract_fidelity_at_preflight(
            repo, [331], _fetch(), drafter_spec="fake:model"
        )
        assert refuse is False
        assert operator_alerts == []


class TestThePreflight:
    def test_1094_an_issue_that_cannot_be_fetched_alerts_and_refuses(
        self, repo, operator_alerts
    ):
        def fetch(_r, _i):
            raise RuntimeError("no such issue")

        text, refuse = cf.check_contract_fidelity_at_preflight(repo, [331], fetch)
        assert refuse is True
        assert "no such issue" in text
        assert len(operator_alerts) == 1
        assert operator_alerts[0]["issue"] == 331
        assert "RuntimeError: no such issue" in operator_alerts[0]["cause"]

    def test_1094_the_first_failure_stops_the_loop(self, repo, monkeypatch, operator_alerts):
        """No partial report: the issue after a failed one is not audited."""
        _provider(monkeypatch, _result(False, None, error="provider storm"))
        seen: list[int] = []

        _text, refuse = cf.check_contract_fidelity_at_preflight(
            repo, [331, 332], _fetch(seen=seen), drafter_spec="fake:model"
        )
        assert refuse is True
        assert seen == [331]
        assert len(operator_alerts) == 1

    def test_1115_an_audit_not_reached_after_a_clean_one_refuses(
        self, repo, monkeypatch, operator_alerts
    ):
        _provider(
            monkeypatch,
            _result(True, json.dumps({"findings": []})),
            _result(False, None, error="quota exhausted"),
        )
        _text, refuse = cf.check_contract_fidelity_at_preflight(
            repo, [331, 332], _fetch(), drafter_spec="fake:model"
        )
        assert refuse is True
        assert len(operator_alerts) == 1
        assert operator_alerts[0]["issue"] == 332

    def test_findings_are_reported_and_do_not_refuse(self, repo, monkeypatch, operator_alerts):
        """Kept: the audit's findings are report-only (#2227, #2387); a defect
        in the issue is the operator's to fix, not a failure of the check."""
        _provider(monkeypatch, _result(True, json.dumps({"findings": [
            {"shape": "binding-no-row", "where": "§Bezel / Width",
             "contract_quote": "roughly 12–15% of the housing on each side",
             "why": "no row binds the ring's radial extent"},
        ]})))
        text, refuse = cf.check_contract_fidelity_at_preflight(
            repo, [331], _fetch(), drafter_spec="fake:model"
        )
        assert refuse is False
        assert cf.FIDELITY_MARKER in text
        assert operator_alerts == []
