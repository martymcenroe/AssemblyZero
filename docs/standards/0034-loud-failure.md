# Standard 0034: Loud Failure

**Status:** Active
**Decision:** ADR 0236 (every failure is loud, logged with details, stops dependent processing, and alerts the operator; Accepted 2026-10-06)
**Enforced by:** `tests/unit/test_loud_failure_check.py`, through `assemblyzero/core/loud_failure_check.py` and `tools/audit_loud_failure.py`
**Related:** #3580 (this standard), #3581 (the sweep), #3728 (the alert path)

---

## The rule

A failure is any point at which an operation does not produce what its caller needs to go on correctly. Every failure has four properties. There are no fall-throughs and no carve-outs. The `# fail-open:` tag is withdrawn and is never written.

Apply the four properties to each `except`, each returned error, each ignored return code and each retry loop, one line at a time.

### 1. Loud

The process the operator launched writes one line at `ERROR` or higher to standard error, at the point of failure.

Non-compliant:

```python
except TimeoutError as e:
    logger.warning("[ADV] call failed, skipping: %s", e)
```

Compliant:

```python
except TimeoutError as e:
    logger.error("[ADV] adversarial review failed: %s", e)
    raise
```

### 2. Logged with details

The record says what failed, where (module and function, plus workflow, node or seat), the identity (repository, issue, spec), the cause (exception type and message, or return code and stderr) and the consequence (what stops). `alert_operator` writes that record to standard error, to `~/.assemblyzero/alerts.jsonl` and to the email.

Non-compliant:

```python
return {"error_message": "failed"}
```

Compliant:

```python
return {"error_message": f"[N1] drafter {spec} failed: {type(e).__name__}: {e}"}
```

### 3. Stops dependent processing

Dependent processing is anything that would consume the failed output, or whose correctness assumes the step ran. A gate that cannot run makes everything after it dependent.

- **A node** returns an error, and the graph routes it to `HALT`. The router reads `error_message`; an unconditional edge out of a node that can return an error is a violation.
- **A tool** exits non-zero.
- **A loop** writes no partial result.
- **A retry loop** that runs out ends in a failure, never a skip.

Non-compliant:

```python
graph.add_edge(N0B_ANALYZE_CODEBASE, N0C_ANALYZE_REQUIREMENTS)  # N0b can return error_message
```

```python
except Exception:
    return {"adversarial_verdict": "skipped"}
```

Compliant:

```python
graph.add_conditional_edges(N0B_ANALYZE_CODEBASE, route_after_analyze_codebase,
                            {N0C_ANALYZE_REQUIREMENTS: N0C_ANALYZE_REQUIREMENTS, HALT: HALT})

def route_after_analyze_codebase(state):
    if state.get("error_message"):
        return HALT
    return N0C_ANALYZE_REQUIREMENTS
```

### 4. Alerts the operator

The failure reaches `assemblyzero.core.alert.alert_operator`, either directly or through the `HALT` node, which calls it (#3724). If the alert itself cannot be delivered, `AlertDeliveryError` is raised and the process exits non-zero; nothing returns a reason string for a caller to drop. A workflow refuses to start when `check_alert_channel()` fails (#3729).

Non-compliant:

```python
reason = send_email(...)
if reason:
    logger.info(reason)  # the operator is never told, and neither is anyone else
```

Compliant:

```python
except OSError as e:
    alert_operator(what="write the audit record", where="tools/x.py main",
                   cause=f"{type(e).__name__}: {e}", consequence="the run exits 1")
    raise
```

## What the check enforces

`tests/unit/test_loud_failure_check.py` runs in the unit tier and fails on three kinds of site the parser can see:

| Kind | What it is |
|---|---|
| `swallowed_handler` | A bare `except`, or `except Exception` / `BaseException`, whose own body neither raises nor calls `alert_operator`. |
| `fail_open_tag` | A `# fail-open:` comment. |
| `unrouted_error` | A graph node that returns a non-empty `error_message` where the graph does not route it to a halt node. |

The sites present when the check was written are in `tests/fixtures/loud_failure_baseline.json`, each naming #3581. A new site fails the build. A fixed site must leave the baseline, and `BASELINE_CEILING` in the test only goes down. The sweep (#3581) brings the baseline to empty.

The check is a floor, not the standard. A narrow handler (`except ValueError`) that swallows a real failure breaks the standard as surely as a broad one; the sweep's line-by-line reading, recorded in its ledger, is what finds those.

## Reporting

Every implementation report states compliance: which failure paths the change adds or touches, and for each one, how it meets all four properties. Template: `docs/templates/0103-implementation-report-template.md`.
