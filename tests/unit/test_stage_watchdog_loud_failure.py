"""stage_watchdog.py under standard 0034, the one sweep site (#3796).

A stage that runs six times its nominal was a stdout line, repeated every
tick, that nobody away from the terminal saw. The watchdog cannot stop the
stage (bounding a call is the provider's job), so the stall alerts the
operator, once per stage run, with the stage, the time and the ratio. An alert
that cannot be delivered is raised when the stage ends. Line numbers in the
names are ledger 0908's, at its base ``79e18ad1``.
"""
from __future__ import annotations

import time

import pytest

from assemblyzero.core import alert, operator_wait
from assemblyzero.core.stage_watchdog import StageWatchdog

#: Long enough for several ticks at the intervals below.
_TICKS = 0.25


class TestAStallAlerts:
    def test_139_a_stalled_stage_alerts_once(self, operator_alerts):
        with StageWatchdog("impl", nominal_seconds=0.001, interval=0.02):
            time.sleep(_TICKS)

        assert len(operator_alerts) == 1
        record = operator_alerts[0]
        assert "impl" in record["what"]
        assert "STALLED" in record["what"]
        assert "nominal" in record["cause"]
        assert "keeps running" in record["consequence"]
        assert record["where"] == "assemblyzero.core.stage_watchdog.StageWatchdog"

    # The watchdog's thread ends on the undelivered alert, by design.
    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_139_an_undelivered_alert_is_raised_when_the_stage_ends(self, monkeypatch):
        def undeliverable(**kwargs):
            raise alert.AlertDeliveryError("email: no sender configured")

        monkeypatch.setattr(alert, "alert_operator", undeliverable)

        with (
            pytest.raises(alert.AlertDeliveryError, match="no sender"),
            StageWatchdog("impl", nominal_seconds=0.001, interval=0.02),
        ):
            time.sleep(_TICKS)


class TestWhatIsNotAStall:
    def test_a_slow_stage_does_not_alert(self, operator_alerts, capsys):
        """Kept: SLOW is a louder line, not a failure."""
        with StageWatchdog("impl", nominal_seconds=10.0, interval=0.02) as watchdog:
            watchdog._start = time.monotonic() - 40  # 4x nominal: SLOW, not STALLED
            time.sleep(0.1)
        assert "SLOW, 4x nominal" in capsys.readouterr().out
        assert operator_alerts == []

    def test_a_stage_with_no_nominal_does_not_alert(self, operator_alerts):
        """Kept: no nominal, no verdict."""
        with StageWatchdog("triage", interval=0.02):
            time.sleep(0.1)
        assert operator_alerts == []

    def test_an_operator_wait_does_not_alert(self, operator_alerts):
        """Kept: elapsed time during an operator wait is his, not the stage's."""
        operator_wait.begin(url="http://localhost/visual", note="test")
        try:
            with StageWatchdog("impl", nominal_seconds=0.001, interval=0.02):
                time.sleep(0.1)
        finally:
            operator_wait.end()
        assert operator_alerts == []
