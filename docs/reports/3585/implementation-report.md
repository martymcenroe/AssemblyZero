# Implementation Report: the requirements workflow's graph and nodes under standard 0034 (#3585 step 5)

The rule is ADR 0236 and standard 0034. This branch, `3585-requirements-nodes`, covers the graph of `assemblyzero/workflows/requirements/` and the nodes assigned to it, in order of harm: one commit per module, each site fixed and tested against ledger 0908. The support modules are on `3585-requirements-support`. When the two branches meet, both carry this file and its sibling, and each keeps its own sections.

## Modules

### nodes/finalize.py (20 ledger findings: 18 fixed here, 2 by #3767; and 1 compliant row, pinned)

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

### graph.py (9 ledger rows: 7 fixed by #3864, 2 compliant, all pinned)

- **#3864 had already routed every ledger row to HALT.** Each is now pinned by a test named for its ledger line.
- **The two human-gate routers read only `next_node`.** A gate that stopped with an error and named a successor went on to that successor, or ended the run at END. Both routers now check `error_message` first and halt. The N4 revise cap in `human_gate.py` depends on this.

### nodes/generate_draft.py (11 ledger findings fixed; 8 compliant rows)

- **Nothing is spent before it can be recorded.** The audit_dir is checked first, before a seat, a template or a model (201, 233, 674). Without it, a draft or every best-of-N candidate was paid for and then not recorded in lineage.
- **Nothing is cut to fit.**
  - A prompt over the cap halts, naming its size and the cap (366).
  - `_truncate_prompt` is deleted (1155, 1160). It dropped sections and then hard-truncated.
- **Nothing is invented in place of what could not be read.**
  - A prior draft that cannot be read halts, naming its path and the exception (480). It used to be replaced in the system prompt by "(unable to read previous draft ...)".
  - A Tiphys refresh that fails raises `InterfaceRefreshError`, and the node halts on it (807). The broad handler that fell back to the stale N0b map is gone; `interface_surface` raises since #3779.
- **A failed best-of-N candidate is said** with its index, the drafter spec and the cause, and the round goes on (185).
- **The seat holder** is gone (345, tag deleted). A seat that will not resolve and a provider that cannot be built halt together as "Invalid drafter", before the preflight.
- **`validate_draft_structure`** blocks an empty draft (1186).
- **The gate registry:** the generate_draft sites are renumbered, and `lld.drafter_failed` covers the new preconditions.

### nodes/analyze_codebase.py (9 ledger findings: 8 fixed here, 1 by #3864; 1 compliant row)

- **N0b halts on anything it cannot read**, before N0c spends a model call:
  - no repo path (107), or a repo path that is not a directory (112);
  - a listing that fails (361, 375) or a search that fails (502); the three helpers raise where they passed, and the node halts on the raise;
  - a selected key file or related file that cannot be read (191, 268);
  - a Tiphys extraction that raises (285). The broad handler is gone; `interface_surface` raises since #3779.
- **Designed caps stay quiet or are named.**
  - A file left out to fit the token budget is named in the log.
  - A sensitive, binary or empty file is skipped quietly.
  - A repo with no Python files has an empty surface.
- **#3864 already halts an arc that cannot be cut** (153); it is pinned here.
- **The gate registry:** `lld.arc_unreadable` covers N0b's seven new halt sites.

## Loud-failure compliance (standard 0034)

| Site (file:line) | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| `finalize.py` `_finalize_issue`, `_save_lld_file`, `_commit_and_push_files`, `_cleanup_source_idea`, the lineage move in `finalize` | ERROR line on stderr and in the log, via `_fail` | the message names the repo, the issue, the path or URL, and the cause | `error_message`, which `route_after_finalize` sends to HALT | HALT calls `alert_operator` |
| `finalize.py` `_finalize_repair_budget` | the ValueError's traceback | names the bad value | raises out of the node | not alerted at the site: the orchestrator's `except Exception` in `run_lld_stage` records a failed stage without an alert (outside this branch) |
| `finalize.py` `validate_lld_final` | the ValueError's traceback | says the content is empty | raises; its one caller halts on an empty draft first | through that caller's HALT |
| `graph.py` `route_from_human_gate_draft`, `route_from_human_gate_verdict` | the gate's own ERROR line | the gate's message | an error routes to HALT | HALT calls `alert_operator` |
| `analyze_codebase.py` `analyze_codebase`, `_unread_selected`, `_select_key_files`, `_search_for_file` | ERROR line on stderr and in the log, via `_loud` | names the repo, the file or listing, and the cause | `error_message`, which `route_after_analyze_codebase` sends to HALT before N0c | HALT calls `alert_operator` |
| `generate_draft.py` `generate_draft`, `_generate_best_of_n`, `build_revision_context` | ERROR line on stderr and in the log, via `_loud` | names the path, size, spec, files and cause | `error_message`, which `route_after_generate_draft` sends to HALT; a failed candidate alone does not stop the round, by design | HALT calls `alert_operator` |

## New defects found, not fixed here

- `assemblyzero/workflows/orchestrator/stages.py:719` reads `final_verdict` and `review_verdict` from the requirements sub-graph. Neither is a key of `RequirementsWorkflowState`, and finalize sets neither, so the verdict is always empty. With the lld gate enabled, an APPROVED LLD would be classed blocked.
- `finalize.py` `_commit_and_push_files` checks the durable copy only when the driver returns a PR URL. A landing that returns a commit and no URL leaves `final_lld_path` naming the removed worktree copy.
