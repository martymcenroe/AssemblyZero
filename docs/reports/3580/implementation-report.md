# Implementation Report: the loud-failure standard and its check (#3580)

## What was built

- **`docs/standards/0034-loud-failure.md`**, the standard. It cites ADR 0236, and gives the four properties with one non-compliant and one compliant example each, in this codebase's terms: the `HALT` routing, `alert_operator`, and the report section.
- **`assemblyzero/core/loud_failure_check.py`**, the check, built on `ast` and `tokenize` with no pattern matching. It finds three kinds of site:
  - `swallowed_handler`: a bare `except`, or `except Exception` / `BaseException` (alone or in a tuple), whose own body neither raises nor calls `alert_operator`. A `raise` inside a nested function does not count.
  - `fail_open_tag`: a `# fail-open:` comment token. A string that only names the marker is not a tag.
  - `unrouted_error`: a node whose function returns a dict with a non-empty `error_message`, where the graph has no conditional edge out of it, or a router on it that does not both read `error_message` and return a halt node's name.
- **How the graphs are read.** Each workflow graph is built, and its nodes and branches are read from LangGraph's own builder. Each node is unwrapped through `narrated`'s `__wrapped__` to its function. A halt node is recognised by being `create_halt_node`'s, whatever the graph named it; the orchestrator calls its `"terminal"`. `GRAPH_BUILDERS` lists all six graphs, including `death/hourglass.py`, and a test fails if a module that builds a `StateGraph` is missing from that list.
- **Stable keys.** Findings are keyed by path, enclosing function, kind and ordinal, so an unrelated line move changes no key.
- **`tools/audit_loud_failure.py`**: a report, `--check`, and `--write-baseline`. The last refuses to add any site the current baseline lacks.
- **`tests/fixtures/loud_failure_baseline.json`**: every site present today, each naming #3581.
- **`WORKFLOW.md`** gains a "Loud Failure (standard 0034)" section.
- **The report templates** gain a loud-failure compliance section: `docs/templates/0103-implementation-report-template.md` and `.claude/templates/reports/implementation-report.md.template`.
- **The retired tag advice is corrected.** `tools/audit_fail_open.py` told readers to clear a finding by writing a tag, in its docstring and its printed advice, and `assemblyzero/core/fail_open_audit.py` described the convention as current. Both now say ADR 0236 withdrew it.

## The baseline

335 sites on `main` at `c51dbe84`: 200 `swallowed_handler`, 131 `fail_open_tag`, 4 `unrouted_error`. Five of the tags landed on `main` after ADR 0236 was accepted, in other PRs, before this check existed to refuse them; they are filed as #3767. `git grep -o "fail-open:"` counts four more than the tags; those four are inside string literals in the old audit (its own marker constant and docstrings), which are not tags.

The four `unrouted_error` sites are real:
- **N0b `analyze_codebase` and N4c `augment_tests`** leave on unconditional edges, so the next node runs on a failed input before any router sees the error.
- **N6 `finalize_spec`** also has no conditional edge.
- **N3 `validate_completeness`'s router** never reads `error_message`, so a failed N3 retries through N2 as though validation had merely failed.

## Not done here, with reasons

- **`tests/unit/test_fail_open_audit.py` and its baseline stay.** ADR 0236 retires them in favour of this check, but the older audit's categories (vacuous pass, warned return, unmet precondition) reach sites this check does not. Removing it before #3581 has read those sites would lose coverage, so it stays until the sweep's ledger covers them; #3581 retires it.
- **The `HALT` node's alert call is #3724, and the start-up channel check is #3729.** Both build on #3728, which landed.
