"""The error-path check's complaint is one pinning can read (#2875).

boostgauge #4, `run-issue4-190442`, spec stage, three revisions, one check
left unresolved every round:

    - OSError: raised once by the spec's own code, and no test uses pytest.raises(OSError)

The draft already tested it as `try: ... assert False / except OSError:`.
Round 3 converted that to `pytest.raises(OSError)`; pinning refused the
change -- `locked content the verdict did not name` -- because the message
named the exception bare and `named_tokens` reads backticked spans. The
#2555 deadlock, one more check.

`check_error_paths_have_tests` is on the addressability sweep's uncovered
list, so this module drives the message's own renderer and the real pinning
functions, on the shape of the run's draft.
"""

from __future__ import annotations

from assemblyzero.workflows.implementation_spec.error_path_coverage import (
    ErrorPathReport,
    format_report,
)
from assemblyzero.workflows.implementation_spec.revision_pinning import (
    demands_additions,
    enforce_pinning,
    named_tokens,
)

PREVIOUS = """\
## 10. Test Plan

```python
def test_oserror_propagation_on_fail(monkeypatch):
    # OSError handling - propagates NtQuerySystemInformation failure
    collector = WindowsCollector({})
    monkeypatch.setattr(collector, "_query", lambda: (-1, 0))
    try:
        collector.collect()
        assert False, "Expected OSError"
    except OSError:
        pass


def test_composite_is_the_max():
    assert compute_composite({"conpty": 15.0}) == (50.0, "conpty")
```
"""

REVISED = PREVIOUS.replace(
    """    try:
        collector.collect()
        assert False, "Expected OSError"
    except OSError:
        pass
""",
    """    with pytest.raises(OSError):
        collector.collect()
""",
)


def _message() -> str:
    return format_report(ErrorPathReport(ran=True, raised={"OSError": 1}, untested=["OSError"]))


class TestTheMessageCarriesAnAddress:
    def test_the_exception_and_the_demanded_form_are_backticked(self):
        message = _message()

        assert "`OSError`" in message
        assert "`pytest.raises(OSError)`" in message

    def test_named_tokens_reads_both(self):
        tokens = named_tokens("", [_message()])

        assert "oserror" in tokens
        assert "pytest.raises(oserror)" in tokens

    def test_the_header_still_reads_as_a_demand_to_add(self):
        """The new-test case keeps #2560's exemption: the header is unchanged."""
        assert demands_additions([_message()]) is True


class TestPinningPassesTheConversion:
    def test_the_try_except_to_pytest_raises_change_is_not_refused(self):
        tokens = named_tokens("", [_message()])

        result = enforce_pinning(PREVIOUS, REVISED, current_tokens=tokens)

        assert result.refusals == (), result.refusals
        assert "with pytest.raises(OSError):" in result.text
        assert 'assert False, "Expected OSError"' not in result.text

    def test_an_unrelated_locked_line_is_still_refused(self):
        """The unlock is the named test's, not the whole draft's."""
        tokens = named_tokens("", [_message()])
        tampered = PREVIOUS.replace(
            'assert compute_composite({"conpty": 15.0}) == (50.0, "conpty")',
            'assert compute_composite({"conpty": 15.0}) == (99.0, "conpty")',
        )

        result = enforce_pinning(PREVIOUS, tampered, current_tokens=tokens)

        assert result.refusals, "the untouched test's assertion must stay locked"
        assert "(50.0," in result.text

    def test_the_bare_message_was_the_defect(self):
        """Pinned: with the pre-#2875 wording the same conversion is refused."""
        bare = (
            "1 exception type(s) the spec raises have no test asserting them. "
            "Section 10 owes each a test:\n"
            "  - OSError: raised once by the spec's own code, and no test uses "
            "pytest.raises(OSError)"
        )
        tokens = named_tokens("", [bare])

        result = enforce_pinning(PREVIOUS, REVISED, current_tokens=tokens)

        assert result.refusals, "the bare wording names nothing, so the change is locked"
