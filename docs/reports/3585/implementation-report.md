# Implementation Report: the requirements workflow's graph and nodes under standard 0034 (#3585 step 5)

The rule is ADR 0236 and standard 0034. This branch, `3585-requirements-nodes`, covers the graph of `assemblyzero/workflows/requirements/` and the nodes assigned to it, in order of harm: one commit per module, each site fixed and tested against ledger 0908. The support modules are on `3585-requirements-support`. When the two branches meet, both carry this file and its sibling, and each keeps its own sections.

## Modules

### nodes/finalize.py (20 ledger rows: 17 fixed here, 2 fixed by #3767, 1 compliant)

- **Every failure is said and halts.** Each one goes through one helper, which writes an ERROR line to stderr and to the log and sets `error_message`. `route_after_finalize` sends that to HALT (#3864), and HALT alerts.
- **Nothing outward happens after a precondition fails.**
  - The issue workflow checks the audit_dir before it files the issue (145).
  - The LLD workflow checks the issue number (532), the audit_dir (653), the draft (535) and an APPROVED review status (798) before it writes anything.
  - An LLD that is not APPROVED used to be saved with its durable copy, which a rebuild restores first (#3764), then logged complete and quietly left unlanded. It now halts with nothing saved.
- **Issue filing names what it was filing.**
  - A draft with no title names the repo and the draft (112).
  - A gh failure names the repo, the title, gh's exit code and its stderr (126); a timeout names the repo and the title (140); a missing gh names the repo (142).
  - A URL without an issue number halts naming the URL (136); it used to file as issue 0.
- **The landing.**
  - A failed commit or landing keeps `commit_error`, which the orchestrator reads (#3740), and adds `error_message` (261).
  - A landing that leaves no durable copy halts, naming the copy and the PR (247).
  - The completion record is now written last, so a failed landing is never logged complete.
- **The rest.**
  - A malformed `max_iterations` raises (450).
  - A missing declared idea halts after filing (673). An undeclared idea is quiet.
  - The lineage move halts when the audit_dir is gone (787).
  - The fail-open tag at 573 is deleted.
  - The exhausted repair budget (487) was already routed by #3864 and is now said at ERROR.
- **`validate_lld_final` fails on empty content.** It returned no errors, which is a pass. It lives in `finalize.py`, not in `verdict_schema.py`.
- **The gate registry.** `lld.finalize.issue_creation` now covers `_finalize_issue`'s two new halt sites.

## Loud-failure compliance (standard 0034)

| Site (file:line) | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| `finalize.py` `_finalize_issue`, `_save_lld_file`, `_commit_and_push_files`, `_cleanup_source_idea`, the lineage move in `finalize` | ERROR line on stderr and in the log, via `_fail` | the message names the repo, the issue, the path or URL, and the cause | `error_message`, which `route_after_finalize` sends to HALT | HALT calls `alert_operator` |
| `finalize.py` `_finalize_repair_budget` | the ValueError's traceback | names the bad value | raises out of the node | not alerted at the site: the orchestrator's `except Exception` in `run_lld_stage` records a failed stage without an alert (outside this branch) |
| `finalize.py` `validate_lld_final` | the ValueError's traceback | says the content is empty | raises; its one caller halts on an empty draft first | through that caller's HALT |

## New defects found, not fixed here

- `assemblyzero/workflows/orchestrator/stages.py:719` reads `final_verdict` and `review_verdict` from the requirements sub-graph. Neither is a key of `RequirementsWorkflowState`, and finalize sets neither, so the verdict is always empty. With the lld gate enabled, an APPROVED LLD would be classed blocked.
- `finalize.py` `_commit_and_push_files` checks the durable copy only when the driver returns a PR URL. A landing that returns a commit and no URL leaves `final_lld_path` naming the removed worktree copy.
