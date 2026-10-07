# ADR 0236: Every failure is loud, logged with details, stops dependent processing, and alerts the operator

**Status:** Accepted (the operator, 2026-10-06, in session `55a83d74-76d7-4ae2-8fce-20d30173a8fc`: "I accept ADR 0236 and ADR 0237.")
**Date:** 2026-10-06
**Deciders:** Operator
**Related:** ADR 0237 (Gemini only through agy), #3579, #3580, #3581, #3585, #2926, #2475, #2529

---

## Decision

**Every failure in AssemblyZero has four properties: it is loud, it is logged with details, it stops the processing that depends on it, and it alerts the operator. There are no fall-throughs, and no class of failure is carved out.**

The operator gave this rule in the supervising session on 2026-09-25 and has given it repeatedly before. He ruled the same day that every deliberate fall-through, all of the sites tagged `# fail-open:`, comes under the rule. This ADR records that ruling; it does not reopen it.

A **failure** is any point at which an operation does not produce what its caller needs in order to go on correctly. Examples: an exception, a non-zero return code, a missing file the step requires, an empty result where content was required, a model call that returns no verdict, a gate that cannot run, and a retry loop that runs out of attempts.

## The four properties, as tests one line of code can be held to

### 1. Loud

At the point of failure, the process the operator launched writes a message at level `ERROR` or higher to its standard error. The message names the failure in one line.

The following are not loud:
- a message at `DEBUG`, `INFO` or `WARNING`;
- a message written only to a file;
- a field set in state or in a report and printed nowhere;
- a reason string returned to a caller that may discard it.

### 2. Logged with details

The failure is recorded with these fields:
- **what** failed: the operation, in words;
- **where**: the module and function, plus the workflow, node or seat when there is one;
- **identity**: the repository, issue number and model spec when they apply;
- **cause**: the exception type and message, or the return code with its stderr;
- **consequence**: what stops because of it.

The record is written to standard error with the loud line. It is also appended to the alert log, `~/.assemblyzero/alerts.jsonl`, one JSON object per failure, and to the run's audit directory when the run has one.

### 3. Stops dependent processing

**Dependent processing** is anything that would consume the failed operation's output, or whose correctness assumes the operation ran. A gate that cannot run makes everything after it dependent, because a pass and a skip become indistinguishable.

So a failure stops in the following ways:
- **A graph node** returns an error that the graph routes to `HALT`, and the run exits non-zero.
- **A command-line tool** exits non-zero.
- **A loop over items** stops when one item fails, if anything the loop produces would include or be shaped by that item. The result of the loop counts here, so a report missing one row is dependent. No partial report is written.
- **A retry loop** that exhausts its attempts fails. It never ends in a skip.

**What is never allowed:**
- substituting a default value for the missing result;
- recording the step as "skipped" and continuing;
- treating "could not check" as "passed";
- any branch commented as best-effort.

**A note on handlers.** An exception handler is a failure path unless the value it produces is part of the function's declared contract, and every caller treats that value as a legitimate state rather than as success after failure.

For example, a lookup that documents "returns `None` when the key is absent" may catch the absence. But it may not catch a permission error and return the same `None`.

The step 3 check flags every handler; the sweep (#3581) judges each one in its ledger and records the verdict.

### 4. Alerts the operator

The failure site calls the alert path: one function, `assemblyzero.core.alert.alert_operator`, which #3580 builds on `assemblyzero/core/operator_notify.py`. It does four things:
- writes the loud line and the detail record to standard error;
- appends the record to `~/.assemblyzero/alerts.jsonl`;
- sends one email through SES v2 (us-east-1) to the operator's contact address (`OPERATOR_CONTACT` in `operator_notify.py`);
- shows a Windows toast when the host is Windows.

**Why email is the channel.** Email reaches the operator from Ubuntu as well as from Windows, and when he is not watching the terminal. The toast alone does not: it exists only on a Windows host.

**A failure to send the alert is itself a failure.** The alert path prints the undelivered record and the reason for the failed send to standard error, then raises. The process exits non-zero. The alert path never returns a reason string for the caller to discard.

**The channel is checked before work starts.** Every workflow run checks, before its first node, that the email sender is configured (`AZ_OPERATOR_EMAIL_FROM`) and that SES credentials resolve. A run whose alert channel cannot work refuses to start.

## What this retires

- **The `# fail-open:` tag convention.** It is withdrawn: no new tag may be written. #3581 brings each existing tag under the rule.
- **The fail-open baseline test** (`tests/unit/test_fail_open_audit.py` with `tests/fixtures/fail_open_baseline.json`). It treated a tagged site as a decision on record. Under this ADR, a tag is a violation on record.

**The replacement is the check #3580 adds.** It asserts that the tag count is zero. Until #3581 finishes, the remaining tags sit in that check's baseline, each entry naming #3581, and the baseline may only shrink.

The classifier in `assemblyzero/core/fail_open_audit.py` stays available as a tool for that check. Its categories describe where to look, not what is allowed.

- **`operator_notify.py`'s "non-fatal by construction."** Its docstring, and the two `fail-open:` handlers in `show_toast` and `send_email`, contradict property 4. #3581 brings them under the rule as part of building the alert path.

## The three evidence sites in #3579, judged

| Site | Loud | Logged | Stops | Alerts | Verdict |
|---|---|---|---|---|---|
| N7.5 adversarial review: `assemblyzero/workflows/testing/nodes/adversarial_node.py:148-179` records "skipped" for a missing client, an exhausted quota, a forbidden model, a downgrade or a timeout, logs at `WARNING`, and the run goes on | no | partly | no | no | Violates. #2926's change of transport is in place, but a review that cannot run still lets the run continue. |
| The `# fail-open:` sites: 130 tags in 50 files at `f29dbb17` (`git grep -o "fail-open:" -- 'assemblyzero/*.py' 'tools/*.py'`) | varies | varies | no, by definition | no | Violates, each one: a tag is a decision to continue after a failure. |
| An unknown provider in `get_provider` (`assemblyzero/core/llm_provider.py`) raises `ValueError`. The draft node returns `{"error_message": "Invalid drafter: ..."}` (`assemblyzero/workflows/requirements/nodes/generate_draft.py:398-399`). `route_after_generate_draft` sends any error to `HALT` (`assemblyzero/workflows/requirements/graph.py:182`), and `tests/unit/test_finalize_repair_routing.py` asserts that route. `HALT` saves state and prints a recovery plan (`assemblyzero/core/halt_node.py`) | yes | yes | yes | no | Violates property 4 only: `halt_node.py` calls no alert path. |

## Consequences

- **Failures that used to pass quietly now stop runs.** Every failure stops its run and reaches the operator's inbox. Runs will stop more often until #3581 has turned each silent continuation into a fix or a true contract.
- **Every workflow needs a working email path on the machine that runs it.** That means `AZ_OPERATOR_EMAIL_FROM`, and SES credentials on Ubuntu as well as on Windows. A machine without them cannot start a run.
- **The `HALT` node becomes a caller of the alert path.** Every graph's halt then alerts without each node calling it separately.
- **The rule is enforced by code, not convention.** #3580 writes the standard under `docs/standards/` citing this ADR, and adds the `ast` check in the unit tier. #3581 sweeps every tracked file in `assemblyzero/` and `tools/` until that check's baseline is empty and the tag count is zero.

## Provenance

The operator gave the rule in the supervising session `238abf52-9bc1-4653-b664-4051b8942d47` on 2026-09-25 at about 9:05 AM Central. This ADR was drafted on 2026-10-06 under the #3585 work order, and states the operator's rules from that order verbatim in substance.
