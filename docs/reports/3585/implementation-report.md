# Implementation Report: the requirements workflow under standard 0034 (#3585 step 5)

The rule is ADR 0236 and standard 0034. This package covers `assemblyzero/workflows/requirements/` in two halves, cut as two branches and assembled on `3585-requirements-landing`. The first half, `3585-requirements-nodes`, covers the graph and the nodes assigned to it, in order of harm. The second, `3585-requirements-support`, takes the support modules that the nodes call. Each half is one commit per module, each site fixed and tested against ledger 0908, and each keeps its own sections below.

## The graph and nodes (`3585-requirements-nodes`)

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

### nodes/validate_test_plan.py (3 ledger findings fixed; 2 compliant rows)

- **A telemetry record that cannot be made** alerts the operator and re-raises (139). It used to print "skipped".
- **A failing draft is preserved, or the run stops.**
  - No audit_dir halts at ERROR (154).
  - A write that fails alerts and re-raises (163).
  - Both used to be skipped as best-effort.
- **The gate registry:** `lld.input_precondition` covers the new halt site.

### nodes/ponder.py (2 ledger findings fixed; 1 compliant row)

- **A fixed draft that cannot be written back halts**, naming the path (73). The disk and the state used to diverge behind a warning.
- **The record of the fixes, if it cannot be written,** is said at ERROR and raised by `_save_fixes_to_lineage`, and the node halts (108). It was dropped without a word.
- **The gate registry:** `lld.input_precondition` covers the two new halt sites.

## Loud-failure compliance (standard 0034): the graph and nodes

| Site (file:line) | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| `finalize.py` `_finalize_issue`, `_save_lld_file`, `_commit_and_push_files`, `_cleanup_source_idea`, the lineage move in `finalize` | ERROR line on stderr and in the log, via `_fail` | the message names the repo, the issue, the path or URL, and the cause | `error_message`, which `route_after_finalize` sends to HALT | HALT calls `alert_operator` |
| `finalize.py` `_finalize_repair_budget` | the ValueError's traceback | names the bad value | raises out of the node | not alerted at the site: the orchestrator's `except Exception` in `run_lld_stage` records a failed stage without an alert (outside this branch) |
| `finalize.py` `validate_lld_final` | the ValueError's traceback | says the content is empty | raises; its one caller halts on an empty draft first | through that caller's HALT |
| `graph.py` `route_from_human_gate_draft`, `route_from_human_gate_verdict` | the gate's own ERROR line | the gate's message | an error routes to HALT | HALT calls `alert_operator` |
| `analyze_requirements.py` `analyze_requirements` (333, 561, 643, 727, 763) | the halt message, printed, then HALT's alert record on stderr | names the issue, the seat, the pairings and the cause | `requirements_unverified` or `error_message`, which `route_after_analyze_requirements` sends to HALT | HALT calls `alert_operator` |
| `analyze_requirements.py` `_provider_storm_active` (371) | ERROR line on stderr and in the log | the exception | re-raised out of the node | not alerted at the site (the orchestrator's catch, outside this branch) |
| `analyze_requirements.py` telemetry and filing beside a conflict (814, 825) | `alert_operator`'s ERROR line | names the repo, the issue and the cause | the conflict halt stands | `alert_operator` at the site |
| `ponder.py` `ponder_stibbons_node`, `_save_fixes_to_lineage` | ERROR line on stderr and in the log | names the path and the cause | `error_message`, which `route_after_ponder` (#3864) sends to HALT | HALT calls `alert_operator` |
| `validate_test_plan.py` telemetry (139), failed-draft write (163) | `alert_operator`'s ERROR line | names the issue, the repo or the file, and the cause | re-raised out of the node | `alert_operator` at the site |
| `validate_test_plan.py` no audit_dir (154) | ERROR line on stderr and in the log | names the iteration | `error_message`, which `route_after_validate_test_plan` sends to HALT | HALT calls `alert_operator` |
| `load_input.py` `_load_issue`, `_get_repo_name` | ERROR line on stderr and in the log, via `_loud` | names the issue, the repo, git's exit code and stderr | `error_message`, which `route_after_load_input` sends to HALT | HALT calls `alert_operator` |
| `human_gate.py` `_decide_verdict` | ERROR line on stderr and in the log | names the status, or the review count and the cap | `error_message`, which `route_from_human_gate_verdict` now sends to HALT | HALT calls `alert_operator` |
| `review.py` `review`, `_invoke_reviewer_with_feedback_schema`, `_build_target_repo_context`, `_update_draft_with_verdict` | ERROR line on stderr and in the log, via `_loud` | names the reviewer spec, the provider's cause, the target, the warnings | `error_message`, which `route_after_review` sends to HALT | HALT calls `alert_operator` |
| `analyze_codebase.py` `analyze_codebase`, `_unread_selected`, `_select_key_files`, `_search_for_file` | ERROR line on stderr and in the log, via `_loud` | names the repo, the file or listing, and the cause | `error_message`, which `route_after_analyze_codebase` sends to HALT before N0c | HALT calls `alert_operator` |
| `generate_draft.py` `generate_draft`, `_generate_best_of_n`, `build_revision_context` | ERROR line on stderr and in the log, via `_loud` | names the path, size, spec, files and cause | `error_message`, which `route_after_generate_draft` sends to HALT; a failed candidate alone does not stop the round, by design | HALT calls `alert_operator` |

## New defects found, not fixed here

- `assemblyzero/workflows/orchestrator/stages.py:719` reads `final_verdict` and `review_verdict` from the requirements sub-graph. Neither is a key of `RequirementsWorkflowState`, and finalize sets neither, so the verdict is always empty. With the lld gate enabled, an APPROVED LLD would be classed blocked.
- `finalize.py` `_commit_and_push_files` checks the durable copy only when the driver returns a PR URL. A landing that returns a commit and no URL leaves `final_lld_path` naming the removed worktree copy.

## The support modules (`3585-requirements-support`)

### nodes/validate_mechanical.py (14 ledger rows: 13 fixed, 1 compliant)

N1.5 sits in `nodes/`, but it was assigned to the support half.

- **A title the check cannot read blocks the draft** (571, 584). No H1, or an H1 with no issue number, is an ERROR naming the title the drafter must write; it was a warning, and the draft passed as if its issue had been checked. The dead `int()` handler on the title number is gone (548): group 1 is digits.
- **The base probe answers or raises** (1080, 1082). `_exists_on_base` asks `git ls-tree`, which answers on a base that resolves: an entry when the base ships the path, nothing when it does not. Git that cannot be run, a base that does not resolve and a directory that is not a repository raise `GitOperationError` with the rc and stderr; each used to read as "not shipped". An empty base branch is still a quiet "not shipped", since the run declared none.
- **A search or sentinel that crashes raises** (1056, 1513), after an ERROR line naming the file.
- **A lineage record that cannot be written stops the run** (1583, 1617, 1653, 1694, 1766). The five writes share `_save_errors_to_lineage`, which logs ERROR with issue, repo, draft and folder and re-raises. No lineage folder in the state is still quiet: the answer-key replay passes none.
- **A telemetry record that cannot be written alerts and raises** (1825).
- **Compliant, pinned** (1775): a blocked draft goes back to the drafter, and to HALT at the cap.
- **What the graph now receives.** N1.5 can raise where it returned. Nothing in the graph catches it; the one handler in `tools/run_requirements_workflow.py`'s `main` (PR #4282) prints `ERROR:`, alerts the operator and exits 1.
- **The mock drafter.** Its canned LLD (`assemblyzero/core/llm_provider.py`, `MockProvider.DEFAULT_RESPONSES["lld"]`) was titled `# Mock Feature: rehearsal LLD`, with no issue number, so a `--mock` LLD run was blocked at N1.5. On the landing branch it is titled `# 42 - Feature: Mock rehearsal LLD`, and `MockProvider.invoke` replaces the 42 with the issue the drafter's prompt names (the fixed `This LLD is for GitHub Issue #N` marker, or the skeleton's `unchanged from iteration 1. Issue #N` from the third draft on), so a `--mock` rehearsal of any issue clears N1.5. A prompt without either marker keeps the canned title, which N1.5 blocks on its mismatch. Pinned by `tests/unit/test_mock_lld_title.py` (4 tests; on the previous commit the two title tests fail).

### audit.py (14 ledger rows: 13 fixed, 1 compliant)

- **The repository structure is read or the node stops** (133, 150, 179). A repo that does not exist raises; a directory that cannot be listed is an ERROR line naming it, then re-raises. Both used to become placeholder text in the drafter's prompt, or a silently missing subtree. An empty repo is still described as one.
- **The lineage move alerts and raises** (333, 359) when the directory is missing or the move fails.
- **A context file the operator named is used or the node stops** (539, 558): outside the repo or missing raises ValueError saying which; unreadable is an ERROR line and re-raises.
- **The approval cache is read or nothing is written** (613, 646, 680, 683, 697). A file that cannot be read, is not a JSON object, or has a malformed `repos` field alerts and raises `LLDStatusCacheError`; since every save reads first, a broken file is no longer overwritten with an empty cache. The main-worktree lookup tells git's "not a git repository" (an answer) from a git failure (raised with rc and stderr), and the cache key no longer falls back to an unresolved path.
- **The review row is embedded or the finalize raises** (1183).
- **Compliant, pinned** (816).
- **Who now receives the raises (audit.py).** N0 `load_input`, N1 `generate_draft`, `finalize`, the implementation-spec and testing nodes that list the repo or move lineage, the orchestrator's settlement read, `speedrun/restore.py` and `tools/speedrun_roll.py`. The orchestrator's settlement write (`stages.py` line 229) still swallows a cache failure in a broad handler; the cache read alerts the operator before that.

### contract_fidelity.py (13 ledger rows, all fixed)

- **Report-only covers findings, never an audit that did not run.** A declared contract that is missing (376) or unreadable (864, 865), an issue that cannot be fetched (1094, 1095), a brief with no table or no section in play (1018), a reviewer that cannot be resolved (1030, 1031), a model call that fails (1052), and an answer that is not JSON (1060, 1061) or has no findings list (1069) each raise or come back NOT REACHED. The preflight alerts the operator with the issue and the cause, prints REFUSED and returns `refuse=True` (1115), without auditing the issues after it. A finding still prints and never refuses.
- **A repo that declares no contract** still pays nothing and is not refused. The preflight now asks the brief whether a contract is declared rather than matching an error string.
- **The launcher discards the flag.** `tools/speedrun_roll.py` line 3896 reads the result as `fidelity_text, _`, so the refusal is printed and alerted but the roll still launches until that line returns 91 on it, as the form check's does.

### precheck.py (10 ledger rows, all fixed in its tool)

- **The standalone pre-check alerts.** `precheck.py` already raised for every failed issue read and gate call, and returned an `error` status when no verdict came; `tools/check_requirements.py` exited 2 on both with no alert. It now alerts in its `PrecheckError` handler and, for an `error` status, writes an ERROR line on stderr and alerts. That also settles the tool's own ledger row (line 99). A conflict is the gate's verdict: it prints, exits 1 and alerts nobody.

### form_gate.py (6 ledger rows, all fixed)

- **A form check that could not run refuses the launch.** An issue that cannot be fetched (149), an empty body (153), and a crash in the discrimination (162) or scope (169, 170) extension each write an ERROR line, alert the operator and refuse; the loop stops at the first. They used to print "could not be checked" (or nothing, for a crashed extension) and proceed (193). The findings keep the operator's 2026-08-12 ruling: only a malformed decision table refuses.
- **The extensions refuse rather than re-raise.** The preflight's contract is `(text, refuse)` and the launcher returns 91 on it; a raise would reach the operator as a traceback instead of a refusal.
- **The unit suite reads no issue from GitHub.** `tests/unit/conftest.py` gains an autouse fixture that hands the launcher's form and contract preflights a prose issue when they are given the real reader, as the box-health bypass does for memory. Without it, 53 launcher tests were refused, since a test repo has no GitHub remote.

### best_of_n.py (5 ledger rows: 4 fixed, 1 compliant)

- **A gate that crashes on a candidate alerts and re-raises** (130, 131); it counted as one failure and the candidate could still win.
- **A candidate count that is not a number raises naming it** (179, 180); it silently meant one candidate. A number is still clamped into 1..5.
- **Every candidate unusable** stays `None` for the draft node to halt on (156, compliant).

### parsers/draft_updater.py (4 ledger rows, all fixed)

- **A resolution that cannot reach the approved draft raises naming it**: an empty draft (35), no Open Questions section (84), no matching question (105), a suggestions heading whose section cannot be read (271, which was an AttributeError). Each used to be a warning the review node only printed.
- **Idempotency is kept.** A question already marked resolved, and a question the verdict quotes struck through, are recognised before the raise; the existing #257 tests found both cases.
- **The review node still swallows these** (`nodes/review.py` `_update_draft_with_verdict`, a broad handler in the nodes half).

### verdict_summarizer.py (4 ledger rows: 3 fixed, 1 fixed in part)

- **A JSON verdict is read strictly** (64, 66, 105): text starting with `{` that is not JSON is an ERROR line and a ValueError; a JSON verdict without a `blocking_issues` list, or with an item lacking `description`, raises. They used to be read as prose or as "0 issues".
- **The status comes from an explicit verdict line** (109), so "NOT APPROVED" is no longer APPROVED. An entry with no verdict line stays UNKNOWN: the review node stores actionable feedback, usually a bullet list, in the history, so raising there would stop every revision. That half of the ledger's fix is a won't-do, pinned.

### git_operations.py (5 ledger rows: 4 fixed, 1 compliant)

- **The arc is fetched or the cut stops** (116). A fetch failure raises with git's stderr; no `origin`, and an origin without the branch, still fall back to the local base (#2684).
- **A reused LLD branch must descend from the arc** (180), checked with `git merge-base --is-ancestor` before any worktree is created. The two `worktree add` argument lists are unchanged.
- **The commit SHA is read from git** (265, 395) with `git rev-parse --short HEAD`, and raises when it cannot be; the summary-line parse returned "(root-commit)" for a first commit and "" when it did not parse.
- **The origin URL lookup** stays best-effort (330, compliant).

### ownership_check.py (3 ledger rows, all fixed) and the form verdict

- **An untagged owner row in a joinable table is a violation** (459); its criteria were skipped as "already reported" when nothing had reported them.
- **A form check that examined nothing of a part renders NOT CHECKED** (611, 627, and `form_check.py:821`): no variable table, owners named only in prose, no requirements section, or no table of the checked kind. `FormReport.not_checked` names each part, and the verdict line lists them. `FormReport.ok` still means "no violations", because the preflight and the tools read it that way; `tools/check_requirements_form.py` therefore still exits 0 on NOT CHECKED, which is reported for the parent.

### form_check.py, scope_coverage.py, step_budget.py, parsers/verdict_parser.py (8 ledger rows)

- **No requirements section** (form_check 388) is named in the NOT CHECKED verdict, not added as a violation: the fleet's one converted issue carries no such section and is ruled correct, and a violation would fail it. Won't-do for the violation, pinned.
- **Scope coverage** (467, 476): a vacuous report is no longer `ok`, and an alias naming a row the table lacks is a violation. Refusing the launch on a vacuous scope is a won't-do: the 2026-08-12 ruling keeps unconverted prose from refusing.
- **The step budget** (83, 159): a cap that is not a number raises; a spent budget is an ERROR line and an alert, since HALT never runs on that path.
- **The verdict parser** (76, 135): an empty verdict, and one whose status cannot be read, raise. The review node's broad handler still swallows them.

### config.py, discrimination_check.py, table_injection.py (4 ledger rows: 3 fixed, 1 compliant)

- **A WorkflowConfig validates itself when built** (122); its validator had no caller.
- **Discrimination coverage with no Acceptance Criteria section** is not `ok` (278).
- **A source table outside the body raises** (120) instead of being clamped into a partial "verbatim" injection. The append when there is no Section 3 stays (184, compliant).

---

# Implementation Report: the implementation-spec workflow under standard 0034 (#3585 step 5)

The rule is ADR 0236 and standard 0034. The module issues were deleted on 2026-10-30, so ledger 0908 names every site; line numbers are the ledger's, at `79e18ad1`. The package was swept in two halves and assembled on one branch.

## The first half: N3's route in `graph.py`, then `nodes/validate_completeness.py`, then `nodes/compile_manifest.py`

### graph.py: N3's errors reach HALT

`route_after_validation` keyed its halt on `completeness_cannot_check` alone, so `tools/audit_loud_failure.py` listed N3 as a node whose `error_message` no router sends to HALT. Its comment said `error_message` also carries a cap message on a grace revision that must still reach N2 (#2304). N3's code does not do that: it writes the cap message only when no grace is granted. The router now reads `error_message` first and halts on any value. A grace revision carries an empty `error_message`, so it still reaches N2. The `completeness_cannot_check` branch went, because `error_message` carries the same text; N3 still writes the field.

The ledger's two `graph.py` rows (265, an unknown human-gate decision; 513, N6's errors) were fixed by #3887 before this sweep reached the file. They are pinned by tests here.

Compliance: the one failure path touched is N3's error. It is loud (N3 prints an ERROR line for a check that cannot run), logged (the message names the check and the cause), stops (the router sends it to HALT), and alerts (HALT calls `alert_operator`).

Baseline: the entry `assemblyzero.workflows.implementation_spec.graph::N3_validate_completeness::unrouted_error::1` leaves.

### nodes/validate_completeness.py: a check that cannot run halts N3 (33 sites; 2 fixed earlier by #3767)

The checks run in `_run_checks`; the node calls it in one `try`. Every check that cannot run raises `CompletenessCannotCheck`, naming the check, its subject and the cause. The node's one handler prints `ERROR [N3] ...` to stderr and returns `completeness_cannot_check` and `error_message`, which is the registry's existing `validate_completeness::return 0`, so no gate row moves. A defect in the draft fails its check and is revised.

- **What N3 needs.** No repo root (1342, 1455, 1702), no LLD (1879), and an LLD with no criteria table or with untagged rows (1892) raise. Each used to pass as "skipping" or "not applicable".
- **The target environment.** `_target_env_python` and `_probe_target_env` (4380 to 4423) raise with the return code and stderr, instead of returning None. So the import check (1530) and the unbound-root probe (3873) halt when the environment cannot answer, instead of passing with a note or judging with no notice.
- **The repo layout.** A pyproject that exists and cannot be read or parsed (4167, 4288, 1988, 2050) raises naming the file, through one `_read_pyproject`; a missing one is still an answer. A root or `src/` that cannot be listed raises (4355), the declared-package read is no longer swallowed (4360), and `_first_party_tops_for` no longer turns a read failure into "no packages" (3890). A base pyproject that cannot be read raises instead of falling back to the checkout (2036), and a failed `git ls-tree` raises with stderr (1614).
- **Telemetry** (280) that cannot be recorded halts N3 with its type and message. It used to print a WARNING to stdout.
- **Draft defects fail their check.** No Section 10 (2194), with a complaint revision pinning reads as a demand to add. The implementation stage's extractor refusing the draft (2222), quoted. A Section 10 block that does not parse (2419), with the SyntaxError and Section 10's lines. A python fence that does not parse, in manifest traceability (2641), which now reads fences through `_scan_fences`.
- **Recorded, not silent.** An empty draft (132) joins the cap bookkeeping, so a halt at the cap carries a reason. A standard-library base this host cannot resolve (3439) is printed at ERROR and named in the symbol check's details; the methods it would lend still abstain. An extracted test function the draft does not hold (2083) raises.
- **Empty symbols** (3932) no longer skip the symbol check. Unparseable python still fails it. A call that needs the table raises in a repo that has Python packages, and is a finding in one that has none. A spec whose calls need no table passes, and its details say why.

Every `# fail-open:` tag in the module is gone.

Compliance: each failure path above is loud (an ERROR line on stderr from the node, or the check's own failed result for a draft defect), logged (the message names the check, the repo or file, and the cause), stops (N3's cannot-check return is routed to HALT; a draft defect is revised, and halts at the cap), and alerts (HALT calls `alert_operator`). The unresolved stdlib base (3439) is loud and logged, as the ledger asks; it stops nothing, because the check still runs and only that class's inherited methods abstain.

On real runs, N3 now halts where it used to pass: when the target repo's poetry environment cannot answer a probe (third-party imports, or calls on roots nothing in the spec binds), when the LLD's criteria cannot be joined, and when N1 gathered no symbols from a repo that has Python packages (a plan that modifies no existing .py file, with no base branch).

Not changed, reported: `base_tree.read_from_base` returns "" both when the file is absent and when git fails, so `_pyproject_for_run` cannot tell a base with no pyproject from a git failure. It still falls to the checkout on "". The `spec.completeness_cannot_check` row's notes in `gate_registry.py` still name only the unparseable-callee case.

Baseline: nine loud-failure entries leave (seven tags and two swallowed handlers).

### nodes/compile_manifest.py: N1b halts on a missing input, a failed filing alerts, N1c passes only a recorded absence (13 sites fixed, 2 WON'T DO)

What N1b needs and cannot get raises `ManifestCannotRun`. N1b halts through `_halt_manifest_cannot_run`, which prints `ERROR [N1b] ...` to stderr and returns "N1b assertion manifest cannot run: ..."; the existing router sends it to HALT, which alerts.

- **The contract** (54, 63, 66, 67): no repo root, a visual-gate declaration that cannot be loaded, a declared contract that is not a file, and a contract that cannot be read each raise. They used to compile without the contract, losing the cross-document hex check with a stdout line or none. No declaration is still an answer.
- **The lineage artifact** (155): an unset or missing `audit_dir`, or a write that fails, raises. It used to skip the manifest's lineage copy silently.
- **The must-resolve filing** (198, 199, 210, 211): no repo root, no issue number, or a filer that raises calls `alert_operator` with the cause and every criterion left unfiled. The halt on the uncompilable criteria stands. It used to file against "." and issue 0, and print a WARNING on failure.
- **Mock mode** (186, 188): N1b decides it and files nothing, as documented test-mode behaviour, with no early return.
- **N1c** (230, 231, 256) passes through only on an absence N1b recorded, and says why. No manifest and no record, or rows with no criteria list, is a finding through the existing GATE return. The fallback that re-derived criteria from the rows, which could only agree with them, is gone.

**WON'T DO: the abstain (89, and the abstain half of 230).** The ledger asks for at least an ERROR and an alert when the compiler abstains, meaning the LLD has tables and none in the criteria shape. Counted on 2026-10-30 over the 110 LLDs in this repository: 110 abstain, 0 compile, 0 have no tables. Only the #332 visual-criteria shape carries a binding column, so an alert there would fire on every non-visual run. The tags are gone; the comment states the contract and the count, the abstain still prints and travels forward on state, and the pass-through is pinned.

Compliance: each new failure path is loud (an ERROR line on stderr from N1b, or alert_operator's own line), logged (the message names the repo, the declared path or the audit dir, and the cause), stops (N1b's cannot-run return and N1c's findings route to HALT; a failed filing changes nothing because the run is already halting), and alerts (HALT calls `alert_operator`; the filing calls it directly).

**Shared files changed:** `assemblyzero/core/gate_registry.py` gains the row `spec.manifest_cannot_run` for the new halt site, citing the operator's 2026-10-06 ADR 0236 acceptance in `created_by`. `tests/fixtures/gate_registry_baseline.json` raises `halt_rows_per_stage.spec` from 20 to 21 in the same change, as the ratchet requires.

Baseline: seven loud-failure entries leave (five tags and two swallowed handlers).
## The second half: the nodes and helpers other than `graph.py`, `nodes/validate_completeness.py` and `nodes/compile_manifest.py`

Each site is the ledger row in `docs/audits/0908-loud-failure-sweep-ledger.md` named by file and line at `79e18ad1`.

### `workflows/implementation_spec/base_tree.py` (4 sites)

- **A failed fetch (41) and a base not on origin (45).** `base_ref` ignored the fetch's exit code, and when `origin/<base>` did not resolve it fell back to the local branch, which nothing fast-forwards (#2021). Both now raise `BaseTreeError` with the command, the exit code and git's stderr.
- **A git error read as absence (54, 63).** `exists_on_base` used `git cat-file -e`, which exits non-zero both for a missing path and for a ref git cannot read. It now asks `git ls-tree --full-tree`, which exits 0 with no output for a missing path and fails only for a git error, which raises. `read_from_base` returns `""` only for a path the base does not ship, and raises on any other failed `git show`.
- **`BaseTreeError`** is a `RuntimeError`, not an `OSError`, so no caller reads a git failure as a missing file.
- **Callers.** `analyze_codebase` catches it and halts (below). `validate_completeness.py` does not catch it yet; a git failure there now raises out of N3 rather than reading as absent.

### `workflows/implementation_spec/nodes/analyze_codebase.py` (23 sites, 1 compliant)

- **The node halts.** Every failure below reaches the node as `BaseTreeError` or the new `CodebaseReadError`, and the node returns an `error_message` of the form `[N1] analyze_codebase for issue #N: ...`, with an ERROR line on stderr. `route_after_analyze` already sends it to HALT, which alerts. The repo_root guard (110) was already compliant.
- **The plan's own files (118, 183, 196, 216, 261, 310).** An empty plan, a Modify or Delete target that is missing, not a file, unreadable or unparseable, and an unknown change type each used to pass with a WARNING on stdout and no content. They now halt, at the first file that fails. A file that does not parse is reported by interface_surface, which raises since #3779.
- **An Add whose directory does not exist yet** is still not a failure: the implementation creates it. The note is no longer a WARNING, and the `warnings` list is gone.
- **The context files (567, 627, 676, 734, 782, 831, 843, 871, 914).** A pattern file, CLAUDE.md, README, pyproject or planned file that exists and cannot be read or parsed raises naming it; it used to be dropped. An absent one still contributes nothing.
- **The base sweep (947, 959, 988, 1024, 1037, 1044, 1054).** A failed `git ls-tree` raises; the 200-file caps are gone; a file git cannot show raises (through `read_from_base`); a base file that does not parse raises, where it used to be regex-scraped.
- **The symbol gather (1127).** `gather_symbols` still names every file that did not parse; the node halts on the list, and `_extract_symbols_from_files` raises instead of returning a shorter list.
- **`core/gate_registry.py`.** The new `_halt` return is a halt site, added to the existing `spec.input_precondition` row. No row is added, so the ratchet is unchanged.

### `workflows/implementation_spec/nodes/finalize_spec.py` (9 rows)

Settled by #3887 and #3891 (PR #3901); unchanged here. Four rows no test reached are now pinned.

### `workflows/implementation_spec/nodes/generate_spec.py` (7 sites, 5 compliant)

- **Halts before the drafter is paid.** A template that cannot be loaded now names the node, the issue and the path (328). A missing lineage directory halts (662); it used to skip the save after the call. A revision whose verdict names nothing the pinning gate can read halts (747); pinning used to abstain and pass the revision unenforced. A prompt whose required parts exceed the budget halts (1436); it used to be cut off mid-content.
- **Halts after the call.** An empty draft halts (616); it used to be saved and sent to N3. A draft that cannot be saved halts (662).
- **The prompt budget (1416).** The builders now append named parts, and the budget drops optional parts whole. The instructions, the LLD, the binding manifest, the draft, the completeness errors and the review feedback are never dropped. The old trimmer re-split the joined text on `##` lines, so the LLD's, the template's and the draft's own sections, and the manifest, were dropped first.
- **The withdrawn tag (397).** Seat resolution, the preflight and the provider build share one handler, so a seat error is no longer held and raised again.
- **For a real run:** a revision whose verdict names no backticked span, quoted phrase, test name, manifest row, Section or line range now halts at N2, and a run with no lineage directory halts at N2 rather than N6.
- **`core/gate_registry.py`.** The new `_halt` return joins `spec.drafter_failed`; no row is added.

### `workflows/implementation_spec/nodes/load_lld.py` (7 sites, 3 compliant)

- **No repo_root (234)** halts; it used to read the working directory.
- **The Section 2.1 table (105, 165, 290).** An absent table, a change type no known spelling matches, and a table that lists no files each halt, naming the issue and the LLD's path. They used to read as no files, as "Add", and as a WARNING. Directory rows are skipped before their type is read.
- **Approval (196)** needs an explicit marker; the word APPROVED anywhere in the text no longer passes the gate. The LLD stage always writes `**Final Status:**`, so its LLDs are unaffected.
- **The read and the length guard (260, 266)** name the issue, the path, the exception type and the length; a file that is not UTF-8 is reported, where it raised past the node.
- **`core/gate_registry.py`.** The node's returns shift by the new guard and gain two; `spec.input_precondition` names 0 to 3 and `spec.lld_not_usable` 4 to 7. No row is added.

### `workflows/implementation_spec/nodes/review_spec.py` (7 sites, 10 compliant)

- **Halts before the reviewer is paid.** A draft under the minimum (334) used to be reviewed after a WARNING; one over the limit (338) was cut, and an APPROVED verdict on the part then stood for the whole. A call with no audit directory (432) dropped the verdict record. All three halt.
- **A verdict that cannot be recorded (432)** halts; it used to print a WARNING and go on. A set but absent directory is still created (#1889).
- **The LLD (641) is sent whole.** It used to be cut at 50,000 characters, so traceability was judged against part of it. A halt there would stop real runs, since LLDs in this repo reach 58,000 characters; the draft keeps its own limit.
- **A must-resolve filing that fails (558)** now alerts the operator with its cause; the halt is unchanged.
- **An empty reviewer response (771)** raises `StructuredContractError`; it was a BLOCKED verdict the reviewer never issued.
- **The withdrawn tag (203).** The template fallback moved into `_read_review`, whose handler re-raises, and the failure tuple is built by `_reviewer_failed`, so neither handler returns a stand-in result.
- **`core/gate_registry.py`.** The new `_halt` return joins `spec.review.empty_draft`; no row is added.

### `workflows/implementation_spec/criteria_coverage.py` (4 sites)

- **A row the check cannot read (171, 180)** raises `CriteriaTableError` naming it: the wrong number of cells, or neither a REQ tag nor an ID. Both used to be skipped, dropping the criterion from the count.
- **A check that cannot run (222, 237)** is no longer `ok`. With no criteria table, or untagged rows, the report still says why, but its caller set `passed=report.ok` and passed the gate unverified.
- **For the caller:** `validate_completeness.py` should raise `CompletenessCannotCheck` on a report that did not run, and on `CriteriaTableError`. As it stands, the failed check is sent to the drafter, who cannot tag the LLD.

### `workflows/implementation_spec/assertion_manifest.py` (1 site, 1 compliant, 1 not changed)

- **A fragment with no literal (325)** is a `CompileFailure` naming it, and its row contributes nothing partial; it used to be skipped while the row's other fragments compiled.
- **Abstention (259) is not changed.** The prescription was for the caller to halt on `abstained`, but every LLD carries the Section 2.1 table, so every LLD without a criteria decision table abstains. Halting there would halt every non-visual run.

### `workflows/implementation_spec/lineage_seed.py` (2 sites)

- **A lineage file that cannot be read (102)** raises `LineageReadError` naming it. It used to read as empty, so the run was skipped and its paid work replaced by an older seed or a fresh draw.
- **A verdict that cannot be read or is empty (140)** raises, where it was dropped from the review history and blinded the stagnation check.
- **Kept:** no prior run, a run with no verdict, and an empty newest draft still mean nothing to resume onto.

### `workflows/implementation_spec/revision_pinning.py` (2 sites)

- **A pinning merge that malfunctions (571, 583)** raises `PinningMergeError`: a merge that lost tests both inputs hold, or holds more copies of a test than either input. It used to emit the revision unenforced, so the round went through without pinning.
- **N2 halts on it**, at both places it pins a revision; no draft is saved.
- **Kept:** a revision that itself removed unnamed tests is still refused entire, emitting the previous draft.
- **`core/gate_registry.py`.** `spec.conservation_gate` names only that remaining site, with `emits` changed to its message; the ratchet does not move.

### `workflows/implementation_spec/nodes/retry_prompt_builder.py` (1 site, 2 compliant, 1 not changed)

- **A token estimate that fails (232)** logs an ERROR naming the exception and re-raises; it returned -1, which a caller could read as a count.
- **The tier-two fallback (174) is not changed.** Tier 2 prunes to save tokens; when the LLD has no section for the file, tier 1 sends the whole LLD, which loses nothing, and the result says it fell back.

### Four one-site modules

- **`error_path_coverage.py` (102).** A spec with no implementation fence is a check that cannot run, and is no longer `ok`; its caller recorded it as passed. A tests-only or docs-only spec now fails this check.
- **`review_progress.py` (73).** A `max_iterations` that is not an integer raises; it stood in a base cap of 3, so the run reviewed to a ceiling nobody set.
- **`nodes/human_gate.py` (146).** Reaching the gate while it is disabled is a misrouted graph and halts; it used to proceed to N5 as a "safety fallback".
- **`table_injection.py` (139).** A machine-owned decision-table block that holds no criteria table raises `DamagedInjectionError`; it used to read around the damage to every criteria table in the LLD. N2 checks it before the drafter is paid.
- **`core/gate_registry.py`.** The gate's new return makes the no-draft guard index 1; `spec.input_precondition` names both.

## Assembling the two halves

- **N3 halts on the second half's errors.** `base_tree` raises `BaseTreeError` and `criteria_coverage` raises `CriteriaTableError`; both reach N3 from inside its checks, where the first half caught only `CompletenessCannotCheck`, so they escaped N3 as a crash. N3's one handler now takes all three and names the type and cause of the two new ones. It returns through the same statement, so no halt site moves. Pinned by `tests/unit/test_spec_n3_assembly_routing.py` (3 tests).
- **WON'T DO: halting N3 on an error-path report that did not run.** The second half's notes asked for it. The report's only not-run cause (`error_path_coverage.py:131`) is a draft with no implementation code, which is a defect in the draft that the drafter can repair. N3 sends draft defects back for revision and halts at the cap, so this stays a failed check.
- **Two passing-spec tests** gained one raise-free implementation fence each: `test_implementation_spec_workflow.py::test_passing_validation_does_not_append` and `test_halt_legibility.py::test_a_pass_at_the_cap_records_nothing`. Each existed only in the first half's form, and the second half's error-path rule failed it. The full unit tier on the assembled branch found the second (1 failed, 12087 passed); both pass on main.
