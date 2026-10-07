#!/usr/bin/env python3
"""Send one real test alert to the operator through the alert path (#3728).

Proves the channel ADR 0236 names works on the machine it runs on: the sender
resolves, AWS credentials resolve, and SES accepts the message. Exits 0 when
the alert was delivered, 1 with the reason on standard error when it was not.

    poetry run python tools/send_test_alert.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from assemblyzero.core.alert import AlertDeliveryError, alert_operator, check_alert_channel  # noqa: E402


def main() -> int:
    try:
        sender = check_alert_channel()
        alert_operator(
            what="test alert (no failure occurred)",
            where="tools/send_test_alert.py",
            cause="a deliberate test of the alert channel",
            consequence="none; this proves the channel delivers",
        )
    except AlertDeliveryError as exc:
        sys.stderr.write(f"test alert NOT delivered: {exc}\n")
        return 1
    print(f"test alert delivered from {sender}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
