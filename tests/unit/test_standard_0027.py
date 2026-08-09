"""Standard 0027 exists and keeps its load-bearing clauses (#2143).

String-level pins, same style as the standard-0026 pins in
test_speedrun_roll_follow.py: the clauses that implementation issues #2144,
#2145 and #2146 build against must not drift out from under them.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STANDARD = REPO_ROOT / "docs" / "standards" / "0027-idempotent-rolls.md"


def _text() -> str:
    return STANDARD.read_text(encoding="utf-8")


def test_the_standard_exists():
    assert STANDARD.is_file()


def test_the_two_obligations_and_the_bound_are_stated():
    text = _text()
    assert "Preserve, then restore" in text
    assert "Janitor on entry" in text
    assert "cleanliness never destroys evidence" in text


def test_refusal_is_reserved_for_unproven_authorship():
    assert "cannot prove it authored" in _text()


def test_the_implementation_issues_are_named():
    text = _text()
    for issue in ("#2144", "#2145", "#2146"):
        assert issue in text, f"standard must point at its implementation gap {issue}"
