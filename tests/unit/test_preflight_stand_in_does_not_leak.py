"""The unit tier's transport stand-in ends with the test that set it (#4239).

`tests/unit/conftest.py` replaces `check_gemini_transport` for every unit
test. When it did so with `patch()`, a test that set the function again with
`monkeypatch` left the stand-in in place for the rest of the process: the
`patch()` context restored the real function first, then `monkeypatch`
restored the value it had saved, which was the stand-in. Every later test of
the real check then read a passing stand-in.

The two tests below run in file order. The first sets the check with
`monkeypatch` under the shared stand-in; the second turns the stand-in off and
asserts it gets the real function back.
"""

import pytest

from assemblyzero.core import preflight
from assemblyzero.core.preflight import check_gemini_transport as REAL_CHECK


def test_a_test_sets_the_check_again_with_monkeypatch(monkeypatch):
    assert preflight.check_gemini_transport is not REAL_CHECK
    monkeypatch.setattr(preflight, "check_gemini_transport", REAL_CHECK)


class TestTheNextTestGetsTheRealCheck:
    @pytest.fixture(autouse=True)
    def _bypass_gemini_preflight(self):
        """No stand-in for this class: the real function is what it reads."""
        yield

    def test_the_real_check_is_back(self):
        assert preflight.check_gemini_transport is REAL_CHECK
