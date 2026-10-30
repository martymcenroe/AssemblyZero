"""test_plan_validator.py under standard 0034, one test per sweep site (#3801).

The test plan used to shrink without a word: a missing section, a section
with no rows, a malformed row and an unreadable ID all dropped out of it. Now
each is loud, and every unreadable part of Section 10 is an error violation.
Line numbers in the names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

from assemblyzero.core.validation import test_plan_validator as tpv

SECTION_3 = "## 3. Requirements\n\n1. The tool exits 1 on a bad flag.\n\n"
TABLE_HEAD = (
    "| ID | Scenario | Type | Input | Expected Output | Pass Criteria |\n"
    "|----|----------|------|-------|-----------------|---------------|\n"
)
GOOD_ROW = "| 010 | bad flag exits one (REQ-1) | Auto | --nope | exit 1 | rc == 1 |\n"


def _lld(section_10: str) -> str:
    return f"# LLD\n\n{SECTION_3}## 10. Verification & Testing\n\n{section_10}\n## 11. Risks\n"


class TestTheSectionsAreThere:
    def test_136_a_missing_section_3_is_loud(self, capsys):
        assert tpv.extract_requirements("# LLD\n\n## 2. Design\n\nText.\n") == []
        assert "ERROR [test plan] Section 3 (Requirements) heading not found" in capsys.readouterr().err

    def test_225_a_missing_section_10_is_loud_and_an_error(self, capsys):
        result = tpv.validate_test_plan(f"# LLD\n\n{SECTION_3}## 11. Risks\n")
        assert "Section 10 / 10.1 (Test Scenarios) not found" in capsys.readouterr().err
        assert any(
            v["check_type"] == "parse" and "Section 10 / 10.1" in v["message"]
            for v in result["violations"]
        )
        assert result["passed"] is False

    def test_237_a_section_10_with_no_rows_is_loud_and_an_error(self, capsys):
        problems: list[str] = []
        assert tpv.extract_test_scenarios(_lld("No table here, only prose.\n"), problems) == []
        assert any("no test-scenario table rows" in p for p in problems)
        assert "no test-scenario table rows" in capsys.readouterr().err


class TestNoRowDropsOutOfTheScenarioTable:
    def test_248_a_short_row_in_a_scenario_table_is_an_error(self):
        lld = _lld(TABLE_HEAD + GOOD_ROW + "| 020 | half a row |\n")
        result = tpv.validate_test_plan(lld)
        parse = [v for v in result["violations"] if v["check_type"] == "parse"]
        assert len(parse) == 1 and "2 cell(s)" in parse[0]["message"]
        assert result["passed"] is False

    def test_262_an_unreadable_id_in_a_scenario_table_is_an_error(self):
        lld = _lld(TABLE_HEAD + GOOD_ROW + "| TBD | later | Auto | x | y | z |\n")
        result = tpv.validate_test_plan(lld)
        parse = [v for v in result["violations"] if v["check_type"] == "parse"]
        assert len(parse) == 1 and "'TBD' is not a number" in parse[0]["message"]

    def test_another_table_in_section_10_is_not_read_as_scenarios(self):
        other = (
            "\n| Target | Value |\n|--------|-------|\n| Line coverage | 95% |\n"
            "| Notes | none |\n"
        )
        lld = _lld(TABLE_HEAD + GOOD_ROW + other)
        result = tpv.validate_test_plan(lld)
        assert [v for v in result["violations"] if v["check_type"] == "parse"] == []

    def test_a_clean_plan_has_no_parse_errors_and_passes(self, capsys):
        result = tpv.validate_test_plan(_lld(TABLE_HEAD + GOOD_ROW))
        assert [v for v in result["violations"] if v["check_type"] == "parse"] == []
        assert result["passed"] is True
        assert "ERROR" not in capsys.readouterr().err
