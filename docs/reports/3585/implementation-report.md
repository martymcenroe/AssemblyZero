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
- **A mock issue run files nothing** (found by another agent, its own commit). `_finalize_issue` ran `gh issue create` whatever `config_mock_mode` said, so `--type issue --mock` filed a real GitHub issue. A mock run now never reaches the subprocess layer. It prints the issue it would have filed, records "NOT filed (mock run)" in the lineage, returns no URL or number, and leaves the source idea where it is.

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

### nodes/analyze_requirements.py (11 ledger findings: 10 fixed here, 1 by #3767; 3 compliant rows)

- **Nothing proceeds without a verdict.**
  - #2462's path, where every conflict the model reported lacked a divergence, used to proceed and record the unverified state. It now halts as REQUIREMENTS UNVERIFIED, naming the pairings, and files nothing (727, tag deleted).
  - `_record_unverified`, which swallowed a failed run_context and a failed write (399, 407), is deleted: nothing calls it now.
  - An empty issue body halts unverified (561, tag deleted).
  - A bad escalation seat halts unverified, naming it (643). It used to re-ask the model that had just timed out.
- **A finding that is not an object** makes the answer no verdict, which is retried and then halts (333). It was dropped, and a findings list could read as consistent.
- **A storm probe that raises** is said and raised (371). It read as "no storm".
- **The confirming ask's failure** is named in the conflict halt (763).
- **Beside a conflict halt,** a failed telemetry record (814) or must-resolve filing (825) alerts the operator, naming the repo and issue.
- **`_halt_unverified`** says when a halt was not retried, rather than claim a backoff that never ran.
- **The reproduced-conflict branch** (779, compliant by #3767) is written as an if/else. The fail-open audit read the `if not confirmed: return {}` shape as a vacuous pass once the two halts ahead of it stopped returning `{}`.

### nodes/review.py (9 ledger findings fixed; 4 compliant rows)

- **A failed reviewer call is reported with the provider's own cause** (101, 122). It is not re-asked, and not reported as an unreadable answer: a new `ReviewerCallError`.
- **Nothing is spent before it can be recorded.** The audit_dir is checked first, and the verdict is always saved (328).
- **The reviewer is grounded or the review does not run.**
  - A target that cannot be listed, or is not a directory, halts before the call (438). It used to be "structure could not be enumerated".
  - An empty target is said to be empty.
- **A REVISE without its Tier sections** breaks the reviewer contract and halts (306). It was silently BLOCKED and looped back.
- **An APPROVED draft whose resolutions cannot be applied stops** (553, 557, 560), through a new `DraftUpdateError`:
  - any update warning stops it;
  - a parser or updater that raises stops it;
  - the ImportError handler is gone.
- **`_parse_verdict_status`**, unused, is deleted (592); the verdict parser keeps its own.
- **The gate registry:** `lld.reviewer_failed` covers the new sites.

### nodes/human_gate.py (3 ledger findings fixed)

- **N4's own decision reads `lld_status` alone** when the gate is disabled (168) or in auto mode (186), through one helper:
  - APPROVED finalizes and BLOCKED revises;
  - any other status halts, naming it;
  - the word APPROVED anywhere in the verdict text, as in "NOT APPROVED", no longer finalizes.
- **Its revise loop stops at `max_iterations` reviews** (179). It used to run until GraphRecursionError. The halt reaches HALT because of the graph commit's change to the human-gate router.
- **A human at the prompt** still decides for himself, uncapped.
- **The gate registry:** `lld.reviewer_failed` covers N4's two new halt sites. No lld row fit better, and a new row would move the halt-row ratchet.

### nodes/load_input.py (3 ledger findings fixed; 5 compliant rows)

- **An issue with an empty or null body halts** before anything drafts from it (207).
- **The provenance is looked up, or the run stops.** `_get_repo_name` raises `RepoNameError` when git exits non-zero, with its stderr (334), or cannot be run (340). N0 halts on it before any lineage is written; a failed lookup used to fall through to "unknown/unknown".
- **A mock run looks nothing up.** It writes provenance `mock/<repo directory>`.
- **The gate registry:** `lld.input_precondition` covers the two new halt sites.

## Loud-failure compliance (standard 0034)

| Site (file:line) | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| `finalize.py` `_finalize_issue`, `_save_lld_file`, `_commit_and_push_files`, `_cleanup_source_idea`, the lineage move in `finalize` | ERROR line on stderr and in the log, via `_fail` | the message names the repo, the issue, the path or URL, and the cause | `error_message`, which `route_after_finalize` sends to HALT | HALT calls `alert_operator` |
| `finalize.py` `_finalize_repair_budget` | the ValueError's traceback | names the bad value | raises out of the node | not alerted at the site: the orchestrator's `except Exception` in `run_lld_stage` records a failed stage without an alert (outside this branch) |
| `finalize.py` `validate_lld_final` | the ValueError's traceback | says the content is empty | raises; its one caller halts on an empty draft first | through that caller's HALT |
| `graph.py` `route_from_human_gate_draft`, `route_from_human_gate_verdict` | the gate's own ERROR line | the gate's message | an error routes to HALT | HALT calls `alert_operator` |
| `analyze_requirements.py` `analyze_requirements` (333, 561, 643, 727, 763) | the halt message, printed, then HALT's alert record on stderr | names the issue, the seat, the pairings and the cause | `requirements_unverified` or `error_message`, which `route_after_analyze_requirements` sends to HALT | HALT calls `alert_operator` |
| `analyze_requirements.py` `_provider_storm_active` (371) | ERROR line on stderr and in the log | the exception | re-raised out of the node | not alerted at the site (the orchestrator's catch, outside this branch) |
| `analyze_requirements.py` telemetry and filing beside a conflict (814, 825) | `alert_operator`'s ERROR line | names the repo, the issue and the cause | the conflict halt stands | `alert_operator` at the site |
| `load_input.py` `_load_issue`, `_get_repo_name` | ERROR line on stderr and in the log, via `_loud` | names the issue, the repo, git's exit code and stderr | `error_message`, which `route_after_load_input` sends to HALT | HALT calls `alert_operator` |
| `human_gate.py` `_decide_verdict` | ERROR line on stderr and in the log | names the status, or the review count and the cap | `error_message`, which `route_from_human_gate_verdict` now sends to HALT | HALT calls `alert_operator` |
| `review.py` `review`, `_invoke_reviewer_with_feedback_schema`, `_build_target_repo_context`, `_update_draft_with_verdict` | ERROR line on stderr and in the log, via `_loud` | names the reviewer spec, the provider's cause, the target, the warnings | `error_message`, which `route_after_review` sends to HALT | HALT calls `alert_operator` |
| `analyze_codebase.py` `analyze_codebase`, `_unread_selected`, `_select_key_files`, `_search_for_file` | ERROR line on stderr and in the log, via `_loud` | names the repo, the file or listing, and the cause | `error_message`, which `route_after_analyze_codebase` sends to HALT before N0c | HALT calls `alert_operator` |
| `generate_draft.py` `generate_draft`, `_generate_best_of_n`, `build_revision_context` | ERROR line on stderr and in the log, via `_loud` | names the path, size, spec, files and cause | `error_message`, which `route_after_generate_draft` sends to HALT; a failed candidate alone does not stop the round, by design | HALT calls `alert_operator` |

## New defects found, not fixed here

- `assemblyzero/workflows/orchestrator/stages.py:719` reads `final_verdict` and `review_verdict` from the requirements sub-graph. Neither is a key of `RequirementsWorkflowState`, and finalize sets neither, so the verdict is always empty. With the lld gate enabled, an APPROVED LLD would be classed blocked.
- `finalize.py` `_commit_and_push_files` checks the durable copy only when the driver returns a PR URL. A landing that returns a commit and no URL leaves `final_lld_path` naming the removed worktree copy.
