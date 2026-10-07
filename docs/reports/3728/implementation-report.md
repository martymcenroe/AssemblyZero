# Implementation Report: the operator alert path (#3728)

## What was built

- **`assemblyzero/core/alert.py`**, the one function ADR 0236 names. `alert_operator(what, where, cause, consequence, repo, issue, spec)`:
  - writes `ERROR [ALERT] ...` and the detail record to standard error;
  - sends one email through SES v2 (us-east-1) to `operator_notify.OPERATOR_CONTACT`;
  - shows a toast when the host is Windows;
  - appends the record to `~/.assemblyzero/alerts.jsonl`.

  The record's time is local with its offset, which is Central on the operator's machines.
- **Delivery failures are raised, never returned.**
  - A missing sender, a failed SES call, or a failed toast raises `AlertDeliveryError`.
  - The log append runs in a `finally`, so the record reaches the log even when the email does not, and a failed append raises too.
  - The outer handler prints `NOT DELIVERED` with the reason, and the earlier failure when there was one, then re-raises.
  - Every handler in the module raises, and `tools/audit_fail_open.py` finds no new site.
- **The sender is never in the code.** It comes from `AZ_OPERATOR_EMAIL_FROM`, then from `~/.assemblyzero/alert.json` (`{"email_from": ...}`).
- **`check_alert_channel()`** proves that a sender and AWS credentials resolve, without sending. #3729 wires it into every workflow's start-up.
- **`tools/send_test_alert.py`** sends one real test alert and exits non-zero when it is not delivered.
- **`tests/unit/conftest.py`** replaces the SES client and toast runner for the whole unit tier with a function that raises `RealAlertTransportReached`. It is a `BaseException`, so `alert_operator`'s handler cannot swallow it, and no unit test can email the operator.

## Proof of delivery

Sent from Ubuntu on 2026-10-06 at 11:01 PM Central, with the sender set for that command only:

```
ERROR [ALERT] test alert (no failure occurred) -- tools/send_test_alert.py: a deliberate test of the alert channel
time: 2026-10-06T23:01:09-05:00
...
test alert delivered from assemblyzero@martymcenroe.ai
```

`martymcenroe.ai` is a verified SES domain identity, and the account has production access (`sesv2 get-account`, `list-email-identities`, read on 2026-10-06).

## Not done here

- The persistent sender file on each machine is the operator's to write: the agent write guard refuses any path outside the Projects tree. The commands are in #3729.
- The start-up check in every workflow is #3729. The `HALT` node's call is #3724.

## Baseline

`tests/fixtures/fail_open_baseline.json` was regenerated because its denominator moved: one new file and 24 more sites examined. The frozen set is unchanged at 440 undeclared sites.
