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

---

# Implementation Reports: the testing workflow under standard 0034 (#3585 step 5)

The package was swept in five batches from `fc1b2b0f` and merged on one branch. Each batch's report follows whole, under its own title, in merge order: C (the graph and three nodes), B (the implementation subpackage), D (the remaining nodes), E (runners, templates and top-level modules), A (checkpoints, verify_phases and cleanup).

---

# Implementation Report: the testing graph and three of its nodes under standard 0034 (#3585 step 5, batch C)

The rule is ADR 0236 and standard 0034. This branch, `3585-testing-graph`, is batch C of the testing workflow's sweep: `assemblyzero/workflows/testing/graph.py` with its routers, and the nodes `load_lld.py`, `augment_tests.py` and `e2e_validation.py`. One commit per module, each ledger 0908 row fixed and tested, or kept and pinned. The other batches of the testing workflow are on their own branches. When the branches meet, each keeps its own sections of this file and its sibling.

## Modules

### graph.py (15 ledger rows: 14 fixed, 1 fixed earlier by #3725 and pinned)

- **Every stop a router decides reaches HALT (232, 245, 318, 355, 438, 447, 451, 471, 478, 488, 513).** The iteration caps, the cost budget, the spent coverage attempts, a BLOCKED plan under the strict policy or out of revisions, an exhausted scaffold that named no reason, and a route a node did not name each ended the run at END, which writes no halt bundle and alerts no one; the stage then read the empty `error_message` as a pass. Each condition now lives in one `_stop_after_*` function. The router consults it and routes to HALT. The node in front of the router is wrapped by `_records_its_stop`, which applies the same function to the node's result and records the reason as `error_message` at ERROR on stderr, so HALT's alert carries it.
- **auto_mode no longer hides a failed gate (217, 227).** `--review none`, the default, sets `auto_mode`, under which an N1 error was ignored and a BLOCKED test plan was walked past to N2. Any error now halts; a BLOCKED plan is revised under auto as under the default policy and halts when the revisions are spent.
- **A failed checkpoint stops the run (128).** The wrapper printed the error and carried on. It now writes an ERROR line naming the checkpoint, node, worktree and issue, and raises `CheckpointFailed` from the cause. Both callers of the graph alert on it, so it does not alert a second time.
- **The adversarial review's halt is pinned (557).** #3725 already routes N7.5's recorded reason to HALT.
- **Structure.** The edge maps of N1, N2.5, N3, N5 and N6 lose their `end` entries, which nothing can take now, and `testing/atlas.py` follows. The gate registry names the twelve new halt sites; three new impl rows (`impl.coverage_augment_spent`, `impl.budget.cost`, `impl.route_unrecognised`) cite the operator's ruling of 2026-10-06, and the impl ratchet in `tests/fixtures/gate_registry_baseline.json` goes from 44 to 47.

### nodes/load_lld.py (18 ledger rows: 10 fixed, 8 compliant and pinned)

- **N0 stops on every input it cannot build from (896, 1001, 1146, 1182, 1224).** A spec with no APPROVED marker, no Section 10 test plan in the LLD or the spec, no requirements, or no files to implement, and in issue-only mode a body with no test plan or no files, each halts at N0 naming the source. Each used to be a warning or nothing, and the run spent its reviews before a later gate, or nothing, stopped it. `extract_files_to_modify` raises when there is no table or the table names no file; it returned an empty list.
- **An LLD that cannot be read or rebuilt halts (324, 325, 1164).** A rebuild from refs that raises is said at ERROR and raised as `LLDRebuildFailed`, and the fail-open tag is gone; an LLD found and unreadable halts naming the path and cause. Both used to print a WARN and go on with the spec standing in for the LLD. A clean miss is still the quiet answer for absence.
- **Section 10's reason is never hidden (202, 1180).** `extract_spec_test_functions` returns the reason beside the empty suite when Section 10 fails the structure rule, so "no executable functions" and "no test plan" read differently. It does not raise, because the spec workflow's completeness checks call it on drafts. N0 records each source's reason and prints the LLD's when the spec's Section 10 serves instead. The rule now lives in `spec_structure_error`, so neither path catches an exception.
- **Kept and pinned (835, 969, 972, 977, 983, 1099, 1136, 1142).** The ADR 0207 default target, and the halts the ledger found compliant.
- **Structure.** The halts go through `_halt_spec_unusable` and `_halt_input_unreadable`, registered under the existing rows `impl.lld_not_usable` and `impl.input_precondition`; no row is added. The `requirements_empty_reason` state key is no longer written.

### nodes/augment_tests.py (26 ledger rows: 25 fixed, 1 compliant and pinned)

- **Every failure of N4c halts (347, 537, 554, 581, 593, 613, 645, 650, 671, 721, 734, 755, 761).** No test file, a report that names no uncovered line, an unreadable test file, no audit dir, no seat, a failed or empty model call, generation attempts spent, a vetting run that executed nothing, a repair that cannot be made, and no added test passing each used to return to N5 with an empty `error_message`, and N5 sent the same shortfall back. Each now halts with its cause, through `_halt_augment_cannot_run` (the node's machinery failed) or `_halt_augment_spent` (an allowance is spent), which `route_after_augment` sends to HALT. A reply with no code is a rejected attempt, revised like an import problem.
- **Nothing it reads is skipped (101, 106, 134, 209, 218, 223).** A malformed range in a coverage report raises `CoverageRangeUnreadable`, and an unreadable source raises its `OSError`; the node halts on either before any model call. `_read_lines` reads its ranges through `_line_numbers`, so there is one parser.
- **Broken invariants raise (317, 318, 389, 390, 735).** An addition that does not parse raises `AugmentInvariantBroken`, and the node restores the suite and re-raises. `_without_named_tests` raises on source that does not parse. The three fail-open tags are gone.
- **A dropped test is said at ERROR (701).** The passing additions are kept, as #2902 designed, and the node returns to N5 with them; the tests still dropped after the repair pass are counted in one ERROR line.
- **The suite left on disk always passes.** Before any halt after vetting, the file is what was there plus only the additions that ran and passed.
- **Kept and pinned (142).** The fallback to bare lines for a source that does not parse.
- **Structure.** A new registry row, `impl.coverage_augment_cannot_run`, cites the operator's ruling of 2026-10-06, and the impl ratchet goes from 47 to 48; the spent halt joins `impl.coverage_augment_spent`.

### nodes/e2e_validation.py (13 ledger rows: 10 fixed, two of them in part; 3 compliant and pinned)

- **A run that cannot be made halts with its cause (182, 188, 291).** A timeout or a runner that cannot start raises `E2ERunFailed` naming the ceiling, the command and the cause; both returned code -1 with a fixed string. An unset or absent audit dir halts before the run; an unset one used to write the results into the working directory.
- **The sandbox stubs stop claiming success (210, 231, 300).** The safety check and the cleanup raise `NotImplementedError` instead of reporting "safe" and "cleaned", so a run given a sandbox repo halts before any test runs. A cleanup that reports failure halts with its error.
- **Only exit 1 is a test failure (331, 334).** Exit 2, 3, 4 and any other code halt, naming the code's meaning, the issue and the output tail. Exit 2 and unknown codes used to loop to N4 as test failures.
- **E2E files that collect nothing halt (313, 337, in part).** A run whose E2E or integration files collect no marked test halts naming the files. A run with no such file and no marked test still goes to finalize, with a line saying there was nothing to validate: the orchestrator never sets `skip_e2e`, so halting there would stop every orchestrated run on a target without E2E tests after its green phase. Whether such a run is a failure is the operator's decision; the halt is one line. Files are now judged by their path inside the repository, not the whole path.
- **Kept and pinned (45, 394, 417).** The advisory pass count, the circuit breaker and the retry cap.
- **Structure.** The new halts join the existing registry row `impl.e2e_error`; no row is added.

## Compliance

Every failure path above meets the four properties of standard 0034: it writes an ERROR line on stderr naming what failed and its subject, it stops what depends on it (a HALT route, or a raise the entry point owns), and it alerts the operator, through HALT or through the caller's handler.


---

# Implementation Report: the testing workflow's implementation subpackage under standard 0034 (#3585 step 5, batch B)

The rule is ADR 0236 and standard 0034. This batch takes the ledger 0908 rows for `assemblyzero/workflows/testing/nodes/implementation/`, module by module. Each site is fixed or recorded as a won't-do with its reason, and each has a test named by its ledger line at the ledger's base `79e18ad1`.

## Modules

### orchestrator.py (28 rows), with `ImplementationError` in claude_client.py

- **Every `raise ImplementationError` is loud where it is raised** (239, 270, 301, 316, 344, 357, 933, 946, 1146). The raises are unchanged, so the halt-site walker and the gate registry still match them. The exception's constructor writes `ERROR [N4] FATAL: Failed to implement <file>: <reason>` to stderr. The runner, `tools/run_implement_from_lld.py`, alerts on it with the file, reason, repo and issue, and exits 1. An alert at each raise as well would send two for one failure.
- **A read N4 depends on stops N4** (589, 819, 912, 1016, 1065, 1120). The test files for the prompt, the Modify base, the edit script's base, an unattributed file's text, a test file left after a failed patch, and the spec suite each went to an empty string on a read error. `_read_or_stop` writes an ERROR line naming the file and what it was for, and re-raises.
- **`came_from_base` answers only what git answered** (439). Exit 1 is untracked. Any other exit, such as 128 outside a repository, is an ERROR line with git's stderr and a `CalledProcessError`; it used to read as "untracked", which resumes past a base file.
- **Every fallback alerts** (117, 125, 135, and edit_script_fix.py 497, 503, 507). An edit script that raised, met an API error, came back as a whole file, had no blocks, had blocks that did not apply, or emptied the file now alerts with the file, the cause, the repo, the issue and the consequence, then falls back as before. `try_edit_script_fix` takes `repo` and `issue`.
- **The batch path alerts** (693, 704, 717): once when the batch call fails, and once per batch for the files its response could not supply or that failed validation. Those files are then generated on their own, as before.
- **559, 572: won't do.** Both return an `error_message` that `route_after_implement` sends to HALT, which alerts. Pinned.
- The four `# fail-open:` tags are gone (913, 1017, 1066, 1121).

Callers: `assemblyzero/workflows/orchestrator/stages.py` turns any exception from the testing graph into a failed stage result, and `tools/orchestrate.py` exits 1 on it without an alert. That is the orchestrator's entry point, outside this batch.

### keep_passing_tests.py (7 rows)

- **A contract that cannot be decided stops** (98, 172, 214). A prior text, revised text, spec suite or plan file that does not parse is an ERROR line naming the side and the file, then SyntaxError. Each used to return its input unchanged. The functions take an optional path for the line; N4 passes it.
- **A passing test is never dropped without a word** (134). When a revision removes the class that held a passing test, the tests are named in an ERROR line and a ValueError.
- The three `# fail-open:` tags are gone (99, 173, 215).

Callers: N4 lets the raises reach the runner, which alerts. N5's `_align_plan_files_with_the_spec` (verify_phases.py, another batch) does not pass the paths, so its ERROR line names the side but not the file.

### parsers.py (6 rows)

- **The conftest option check (#2547) no longer passes when it cannot compare** (142, 197, 212). An ancestor conftest that does not parse or cannot be read, or a directory on the walk that cannot be resolved, is an ERROR line naming it, and the exception propagates. Each used to end the comparison and pass.
- The three `# fail-open:` tags are gone (143, 198, 213).

Callers: `validate_code_response` is called by N4's retry loop and batch path; neither catches, so the runner alerts.

### edit_script_fix.py (5 rows)

- **Attribution by test body (#2861) does not guess around a file it cannot read** (273, 303). A planned Python file or a failing test's file that cannot be read or does not parse is an ERROR line naming it, and the exception propagates. A file that is not on disk, or not Python, is still an answer: it defines or uses nothing.
- **497, 503, 507** are fallbacks the orchestrator takes; it alerts on them (see orchestrator.py above).
- The two `# fail-open:` tags are gone.

### deprecated.py (4 rows)

No run calls these batch-mode helpers; they keep the standard while they exist.

- **A read the batch prompt needs stops** (58, 87): an ERROR line naming the file, and the read error propagates.
- **No invented paths** (190): a code block that names no file is an ERROR line and a ValueError; it used to be written as `implementation_N.py`.
- **No partial write** (218): an entry with no path or no content is refused before anything is written.

### claude_client.py (4 rows)

- **A timeout override that cannot be used raises** (61, 64). `AZ_FILE_TIMEOUT_FLOOR` or `AZ_FILE_TIMEOUT_CAP` set to something that is not a positive whole number is an ERROR line naming the variable and value, then ValueError, as `AZ_LLM_IDLE_TIMEOUT` does since #3780. Unset or empty is the default.
- **A provider exception is an ERROR line** (270) naming its type, the seat and the file, and the returned error carries the type. It is still returned as the call's error, which is the function's contract: the retry loop raises after its budget and the runner alerts.
- **250: won't do.** Compliant: a model that is not a provider spec is a non-retryable error the retry loop raises on. Pinned.
- `ImplementationError` writes its ERROR line at construction (see orchestrator.py above).

### import_validator.py (3 rows)

- **The import gate (#842) does not judge on what it could not read** (85, 119). Installed-package metadata that cannot be read, or a `pyproject.toml` that cannot be read or does not parse, is an ERROR line naming it, and the exception propagates. Reading the second as "no dependencies" had flagged every third-party import. No `pyproject.toml` still declares nothing.
- **Code that does not parse does not pass** (229): it is a failed verdict carrying the syntax error, with an ERROR line. In a run, `validate_code_response` checks syntax first.

Callers: N4's validation and, for the pyproject reader, `scaffold_tests.py` (another batch); neither catches.

### routing.py (1 row)

- **62: won't do.** Compliant: a file path that is not a string raises TypeError naming its type. Pinned.

### prompts.py (1 row)

- **The Modify prompt is never built without the file** (153). A Modify file that cannot be read is an ERROR line naming it, and the read error propagates; the model used to be asked to modify a file it was never shown.

### context.py (1 row)

- **A Python file that does not parse is said aloud** (40). The summary for later files still carries its first 50 lines, now with an ERROR line naming the file and the syntax error. The summary is context, not a gate, so it goes on. A file that is not Python is summarized by its head, quietly. The prompt builder passes the path.

## Compliance (standard 0034)

| Failure path | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| `ImplementationError` raised in N4 | ERROR line at construction | file and reason; the runner's alert adds repo and issue | the run exits 1 | the runner |
| A read N4 depends on fails | ERROR line naming file and purpose | exception type and message | the read error propagates | the runner |
| `git ls-files` cannot answer | ERROR line with stderr | exit code and stderr | `CalledProcessError` | the runner |
| An edit-script or batch fallback | `alert_operator` writes the ERROR record | what, where, cause, consequence, repo, issue | the fallback is the designed recovery | `alert_operator` |
| The test contract cannot be decided | ERROR line naming side, file, line | syntax error or lost tests | SyntaxError or ValueError | the runner |


---

# Implementation Report: the testing workflow's remaining nodes under standard 0034 (#3585 step 5, batch D)

The rule is ADR 0236 and standard 0034. This branch, `3585-testing-nodes`, is batch D of the testing workflow's sweep: the nodes under `assemblyzero/workflows/testing/nodes/` that no other batch owns. One commit per module, each ledger 0908 row fixed and tested, or kept and pinned. The other batches of the testing workflow are on their own branches. When the branches meet, each keeps its own sections of this file and its sibling.

## Modules

### nodes/validate_tests_mechanical.py (11 ledger rows: 5 fixed, 6 compliant and pinned)

- **An unreadable helper halts (522, 523).** A helper file beside the tests that the tests import from, and that cannot be read or parsed, raises `HelperSourceUnreadable` naming the file, the imported name and the cause. N2.5 returns it through `_halt_validation_cannot_run`: an ERROR line on stderr and an `error_message` that `route_after_validate` sends to HALT, which alerts. It used to drop the helper silently, and the test that relied on it was refused with a message that never named the file. The ledger's "record it as a validation error" was not taken: the assertion check cannot follow into the file, so it cannot run, as with an unreadable test file (#3081), and regenerating the scaffold cannot repair a file the scaffolder did not write.
- **A placeholders-only suite is named at ERROR (676).** When every generated test fails unconditionally and the spec ships no test bodies, the node writes an ERROR line on stderr naming the issue and every placeholder. When the suite otherwise passes and goes on to the red phase, nothing stops the run there (#386, #2331), so the node also alerts the operator. When the suite is rejected for other errors, the rejection routes back to the scaffolder or, out of attempts, to HALT, which alerts, so the node does not alert a second time.
- **An exhausted run never ends quietly (1043).** `should_regenerate` returns "escalate" only when state carries the node's `error_message`, which reaches HALT. Out of moves with no recorded reason, the legacy fallback for resumed state or a carried escalate whose reason is gone, it writes an ERROR line and raises `ScaffoldExhausted` with `DETERMINISTIC FAILURE` and the reason. It used to return "escalate", which `route_after_validate` maps to `end`, and the run ended as if nothing failed. The raise leaves the graph, and `tools/run_implement_from_lld.py` prints it at ERROR and alerts.
- **The tags are gone (500, 523).** `imported_helper_sources` has no handler for unparseable test text any more: it asks `count_stub_tests` whether the text holds a test function, and parses only when it does, so the syntax error is reported once, by `validate_test_structure`.
- **Kept and pinned (101, 418, 499, 557, 963, 975).** The parse answers that say "nothing here" for text whose syntax error another check reports, now documented in their docstrings, and the two budget halts, which already reach HALT.
- **Where the raises go.** `HelperSourceUnreadable` is handled by the node and also reaches `assemblyzero/speedrun/answer_key.py`, which has no handler, so the answer key stops on an unreadable neighbour. `ScaffoldExhausted` is raised inside graph execution and reaches the entry point's handler. In `assemblyzero/workflows/testing/graph.py`, `route_after_validate` still maps "escalate" to `end`; that return is now reached only with `error_message` set, which the router sends to HALT first.

### nodes/scaffold_tests.py (11 ledger rows: 9 fixed, 2 compliant and pinned)

- **No Section 10 raises (105).** `parse_lld_test_section` raises ValueError naming the headings it looked for. It returned no scenarios, which read the same as an empty test plan.
- **No `assert True` (325, 342).** Where no assertion can be derived from a scenario's expected behaviour, the generated test is `assert False` with a "TDD RED" message naming that behaviour. `assert True` passed with no implementation at all, so a scaffold no one replaced read as green.
- **Bodies that do not parse halt N2 (787, 788).** `unbound_names` raises `ScaffoldImportError` naming the line of the emitted file and the parser's message; `_scaffold_python_tests` returns it as `error_message`, routed to HALT, before anything is written. It used to repair nothing and leave the refusal to N2.5, which then regenerated a transcription that comes out byte for byte the same.
- **A finder that raises halts N2 (833, 834).** A name `importlib`'s finder raises on is reported with the test that uses it and the cause, by the same route.
- **A missing audit directory halts N2 (1069, 1199).** `_require_audit_dir` runs before either scaffold writes anything: a state naming no directory, or one that is not a directory, raises FileNotFoundError, and N2 halts through `_halt_scaffold_framework`. The single-pytest path now catches ValueError and OSError into that halt, as the multi-framework path already did. An unset `audit_dir` used to be `Path("")`, the working directory, so the scaffold's audit copy landed wherever the run was started.
- **Kept and pinned (435, 1153).** An unsupported framework raises; no scenarios is the GUARD halt.
- **Where the raises go.** `parse_lld_test_section` and the assertion generator have no caller outside the tests. `ScaffoldImportError`'s new causes also reach `implementation_spec/nodes/validate_completeness.py`, which already catches it and fails its Section 10 check with the message.

### nodes/review_test_plan.py (7 ledger rows: 2 fixed, 5 fixed in the node and waiting on the router)

- **The prompt is AssemblyZero's, and a missing one raises (156).** `load_review_prompt` read `docs/skills/0706c-Test-Plan-Review-Prompt.md` under the TARGET repository's root, where it never is, and a missing file became a built-in default prompt without a word: every review of another repository's plan ran on a prompt nobody maintained. It now reads this checkout's file (`projects_root.REPO_ROOT`) and raises FileNotFoundError naming the path; the default prompt is deleted. The raise reaches the entry point, which alerts.
- **A BLOCKED verdict sends real feedback or is rejected (710).** The schema-required rationale was never read, so a JSON BLOCKED verdict with no blocking issues sent the reviser "See full verdict for details." The feedback is now the summary and blocking issues, else the Required Changes section or numbered list, else the rationale. A BLOCKED verdict naming none of them is rejected through the existing "Test-plan reviewer response rejected" return, which halts.
- **Every error is an ERROR line on stderr (428, 489, 553, 579, 609).** The GUARD block, an unresolvable reviewer, a failed call, an unexpected error (now named with its type) and an unusable verdict each write `ERROR [N1]` on stderr and return `error_message` as before.
- **The router half is batch C's.** `route_after_review` in `graph.py` (line 218) sends an error to HALT only when `auto_mode` is off: `if error and not auto_mode`. It must be `if error`. Until then, those five errors continue to N2 under `auto_mode`.
- **Halt sites unchanged.** The five error returns keep their order, so the gate registry needs no change; the line-579 broad handler and its loud-failure baseline entry stay for that reason.

### nodes/document.py (7 ledger rows: 5 fixed, 2 kept and pinned)

- **An artifact that cannot be written stops N8 (292, 308, 338, 350).** The wiki page, runbook, c/p docs and README steps each printed "SKIPPED" on stdout and went on, the c/p step with a partial list. Each now raises `DocumentationError` naming the issue, the artifact and the cause, after an ERROR line on stderr. N8 has no route to HALT and returns no `error_message`, so the raise reaches the run's entry point, which reports it and alerts.
- **A missing README raises (182).** When N8 decides a README needs a feature entry and there is no README.md, `update_readme` raises FileNotFoundError naming it. It returned False, printed as "no update needed".
- **Kept: no Features section (215).** A README that keeps no feature list has none to add to. Five READMEs in the Projects tree have a Features section and AssemblyZero's has none, while N8 decides to update one from LLD keywords; raising would stop most runs that reach N8. It is left unchanged and said as that, no longer as "no update needed".
- **Kept: no wiki sidebar (289).** `update_wiki_sidebar` returns False for a wiki with no `_Sidebar.md` or a page already listed, both absences; `generate_wiki_page` makes the wiki directory itself, so a repository with no wiki gets a page and no sidebar. The result is now checked and said, and a sidebar that cannot be read or written raises and is no longer swallowed.

### nodes/mechanical_hooks.py (5 ledger rows: 1 fixed, 4 compliant and pinned)

- **A staging that fails halts (108).** After a successful hook, `git add .` ran with `check=False` and its return code was never read, so a staging that failed went on to the tests as if the hook's output were in the tree. Its exit code is read now: non-zero, or git that cannot start, halts through `_halt` with the directory, the exit code or exception, and git's stderr.
- **Every halt is an ERROR line (74, 91, 98).** `_halt` now also writes the reason at ERROR on stderr; the unreadable config, the hook that cannot start and the hook that fails were already halts and are pinned.
- **Kept (70).** No `.unleashed.json` is no hook.

### nodes/revise_test_plan.py (4 ledger rows: 4 compliant and pinned)

- **Pinned, and said where they happen (226, 246, 266, 307).** No requirements, an invalid revisor spec, a failed revision call and a short plan at the revision cap each record a reason that `route_after_revision` sends to HALT. Each now also writes an ERROR line on stderr, naming the spec where there is one. The docstring said these route "to END"; it says HALT now.

### nodes/finalize.py (4 ledger rows: 4 fixed)

- **No test counts, no report (152).** A green-phase output with no passed, failed or error count was reported as 0 of 0 tests passed, and the run as COMPLETE. N7 now raises `FinalizeError` naming the issue and the head of the output, before the report is written or anything archived.
- **A file to archive that is missing raises (46).** `archive_file_to_done` raises FileNotFoundError naming it when it is in neither active/ nor done/. One already in done/ with no copy in active/ is the file an earlier pass of N7 archived, and its done/ path is returned, so a resumed N7 does not fail on its own work.
- **A move that fails raises (74).** `FinalizeError` names the source, the destination and the cause, after an ERROR line; it was an ERROR naming the file only, and the run went on to COMPLETE.
- **Failures are no longer "skipped" (216).** The skipped list held failures nothing read. They raise now; the list holds only files with nothing to archive, and N7 prints it.
- **Why a raise.** `route_after_finalize` does send `error_message` to HALT, but N7 has no registered halt site and the gate registry is not this batch's file. The raise reaches the entry point, which alerts.

### nodes/adversarial_validator.py (3 open ledger rows: 3 compliant and pinned)

- **Pinned (114, 227, 251).** A file that does not compile is an error and makes the result invalid. The mock and assertion scans answer "nothing found" for source that does not parse because their only caller runs them after `compile` accepted the file; their docstrings now say so. Lines 63 and 79 were fixed in #3725.

### nodes/completeness_gate.py (1 open ledger row: compliant and pinned)

- **Pinned (119).** Zero requirements is a BLOCK whose `error_message` routes to HALT. The refusal is now an ERROR line on stderr instead of a stdout print. The gate's other rows were fixed in #3811.

## Compliance

Every failure path above meets the four properties of standard 0034: it writes an ERROR line on stderr naming what failed and its subject, it stops what depends on it (a HALT route, or a raise the entry point owns), and it alerts the operator, through HALT, through the entry point's handler, or from the node when nothing stops.


---

# Implementation Report: the testing workflow's runners, templates and top-level modules under standard 0034 (#3585 step 5)

The rule is ADR 0236 and standard 0034. This branch, `3585-testing-runners`, is batch E of the testing workflow's sweep: the runners, the runner registry, the exit-code router, the framework detector, the coverage report, the audit helpers, the path and symbol validators, the knowledge patterns and the three documentation templates under `assemblyzero/workflows/testing/`. One commit per module, each site fixed and tested against ledger 0908. The other batches of the testing workflow are on their own branches. When the branches meet, each keeps its own sections of this file and its sibling.

## Modules

### runners/jest_runner.py (7 ledger rows: 6 fixed, 1 compliant and pinned)

- **A run nobody can read raises.** A run whose stdout carries no JSON report (110), or whose report does not parse (124), raises `RunnerError` after an ERROR line on stderr and in the log. The message names the framework, the project directory, the exit code and the head of both streams.
- **The fallback is gone (169).** It read zero failures and zero errors at exit 0, so a run nobody could read was judged as one where nothing failed. The only result the runner builds without a report is a failed typecheck's, now `_typecheck_failed_result`, which always carries one failure and one error.
- **package.json is read or refused (57, 58).** `_has_typecheck_script` decides whether a Vitest project declares a typecheck. No package.json declares none, quietly. One that cannot be read, does not parse, or is not an object with an object of scripts raises `RunnerError` naming the file, and no suite runs. The fail-open tag and its handler are deleted.
- **npx missing is loud (33).** The constructor prints an ERROR line naming the framework and the project directory, then raises the EnvironmentError every caller already turns into a halt.
- **Kept (72).** A typecheck that exits non-zero is the run's answer and comes back as a failing result.
- **New in `base_runner.py`** for every runner: `RunnerError`, `loud()` and `output_head()`.
- **Where the raise goes.** `nodes/verify_phases.py` calls `run_tests` in N3, N5 and the full-suite gate. None of them catches `RunnerError`, so it ends the run through `tools/run_implement_from_lld.py main`, which prints it at ERROR, alerts the operator and exits 1. Catching it beside `CoverageReportError` and returning it as `error_message` would end the run at HALT instead, with its saved state; that file belongs to another batch.

### runners/base_runner.py (4 ledger rows: 4 fixed)

- **A test command that did not run raises.** A timeout (129), a missing command (132) or another OS error (135) raises `RunnerError` naming the framework, the command, the working directory and the cause, after an ERROR line. They came back as exit code -1 with the cause where stderr would be, and the runners parsed that as a run, so a suite that never started read as one that failed.
- **No scenarios is not 0% (96).** `compute_scenario_coverage` with no scenarios raises ValueError after an ERROR line. It returned 0.0 with a WARNING, which the green phase read as a measured 0%.
- **Where the raises go.** Both reach `nodes/verify_phases.py`, which catches neither, so each ends the run through the entry point's handler, which alerts. Catching them in N5 and returning them as `error_message` would end the run at HALT instead.

### runners/pytest_runner.py (2 ledger rows: 2 fixed)

- **The exit code is read (45).** 0 and 1 are finished runs, read from the summary line. Any other code raises `RunnerError` after an ERROR line, naming the code, what pytest means by it (interrupted or stopped at collection, internal error, usage error, no tests collected) and the head of the output. Those runs used to come back as counts read off their output, mostly zero.
- **No coverage table is not 0% (57).** `coverage_percent` is None, not measured, when the output carries no TOTAL row, as the Jest runner reports it since #4246.
- **No caller swallows it.** Nothing in `assemblyzero/` or `tools/` calls `PytestRunner.run_tests`; the phases run pytest through `run_pytest`.

### runners/playwright_runner.py (2 ledger rows: 2 fixed)

- **A run nobody can read raises.** No JSON report (91), a report that does not parse (104), or a report whose suites are not the shape Playwright writes raises `RunnerError` after an ERROR line, naming the project, the exit code and the head of both streams.
- **The fallback is gone.** It read zero failures and zero errors at exit 0.
- **Where the raise goes.** As for the Jest runner: N3, N5 and the full-suite gate do not catch it, so the run ends through the entry point's handler, which alerts.

### runner_registry.py (1 ledger row: fixed)

- **An unknown framework raises (117).** `resolve_framework` raises `UnknownFrameworkError`, a ValueError, after an ERROR line, naming the value and the four frameworks. It returned None, the same answer as no framework, and `framework_ownership.run_frameworks` reads None on a one-framework run as pytest.
- **No framework named is still None, quietly.** No config, no `framework` key, or a key holding None is the pytest default every caller documents.
- **Where the raise goes.** `run_frameworks` does not catch it, and its four callers catch only `TestFileOwnershipError`, so the run ends through the entry point's handler, which alerts. Wrapping it in `TestFileOwnershipError` in `run_frameworks` would end it at HALT instead; that file belongs to another batch.

### exit_code_router.py (4 ledger rows: 4 fixed)

- **The unused router is deleted (47, 60, 68, 71).** `route_by_exit_code` sent a red phase that passed, an interrupted or broken pytest, a timeout and an unknown code to a plain end, never to HALT. Nothing called it: the routing that runs is inline in `nodes/verify_phases.py` on the same constants (see #2690). The ledger allowed routing to HALT or deletion; deletion leaves no second copy with silent ends to wire in, and changes no route.
- **What verify_phases reads stays.** The constants, `describe_exit_code` and `describe_run_outcome` are unchanged.

### framework_detector.py (3 ledger rows: 3 fixed)

- **Two raises are now loud.** An unreadable package.json (215) and a `test_dirs` declaration naming no framework (252) raised with nothing said where they failed. Each now prints an ERROR line first. The path resolver's read of the same package.json, added by #4237 after the ledger's base, does the same.
- **A missing project is not pytest (273).** `detect_framework_dirs` with a project root that is empty or not a directory raises `FrameworkResolutionError` naming it, after an ERROR line. It returned no frameworks, which the callers read as pytest at the root. A project that exists and declares nothing is still the quiet empty answer.
- **Where the raises go.** N0 catches ValueError on all three paths and halts, and HALT alerts; provisioning turns ValueError into `ProvisioningError` naming the worktree.

### coverage_report.py (2 ledger rows: both compliant, pinned)

- **Unchanged, by design.** No TOTAL row (137) and a table that leaves out the target (143) are each a reading in the state ABSENT, with no percentage and a message naming what was sought and what the report held. That is the module's contract (#2637). N5 stops on it, and N4c returns it as an error that its router sends to HALT. The new tests pin the contract.

### audit.py, the testing workflow's (3 ledger rows: 2 fixed, 1 left for the verify_phases batch)

- **A missing audit directory raises (121).** `next_file_number` raises FileNotFoundError naming it, after an ERROR line. It answered 1, as if the directory were empty. Every caller checks or creates the directory first.
- **A lost audit event raises (280).** `log_workflow_execution` raises `WorkflowAuditError` naming the workflow, the event, the issue, the log and the cause, after an ERROR line, when the log's directory cannot be made or the line cannot be appended. It logged a WARNING and went on. The run ends through its entry point's handler, which alerts.
- **No coverage table still reads 0.0 (320).** `nodes/verify_phases.py`, another batch's file, compares and records the value as a number, so None would raise there. The fix needs that file first; a strict xfail records the open site. N5 already catches the absence with `coverage_report.read_coverage` before it decides a route.

### path_validator.py (3 ledger rows: 2 fixed, 1 compliant and pinned)

- **Every failed context file is said (164, 177).** A rejection, or a read that fails, is an ERROR line naming the file and the cause. The read handler names OSError and UnicodeDecodeError where it caught every exception.
- **No partial context.** When any file fails, no content comes back, only the errors. The one caller, `tools/run_implement_from_lld.py`, already refuses to start on any error, and its handler alerts.
- **Kept (65).** A file that cannot be statted is a rejection with its reason.

### symbol_validator.py (3 ledger rows: 3 fixed)

- **A check that cannot run raises.** A module of the target's own that cannot be read or parsed (71, 152), and a test source that does not parse (137), raise `SymbolCheckError`, a ValueError, naming the file and the cause after an ERROR line. They returned None or an empty list, the same answer as "every import resolves".
- **Not the repository's own is still quiet.** An import from the standard library or a third-party package is not this check's to make.
- **Where the raise goes.** N4c (`nodes/augment_tests.py`) does not catch it, so the run ends through the entry point's handler, which alerts. Catching it at N4c's two calls and returning it as `error_message` would end the run at HALT instead.

### knowledge/patterns.py (2 ledger rows: 2 fixed)

- **The knowledge base is read or refused.** A missing types.yaml (24) raises FileNotFoundError naming it. One that cannot be read, does not parse, or holds no `test_types` mapping (30) raises `KnowledgeBaseError`, a ValueError. Each comes after an ERROR line.
- **The stand-in is deleted.** Both failures fell back, silently, to a shorter inline copy of the definitions that differed from the file. It existed only for those failures.
- **Where the raise goes.** N0 and N1 read the knowledge base outside any handler, so a broken install ends the run at the first node, through the entry point's handler, which alerts.

### templates/runbook.py (3 ledger rows: 3 fixed)

- **No invented sections.** An LLD with no prerequisites (172), no procedure (200) or no verification steps (210) raises ValueError naming the feature, the issue and every missing section, after an ERROR line and before anything is written. The template wrote invented ones in their place, and the runbook read as written from the LLD.
- **The caller still swallows it.** N8 (`nodes/document.py`) catches every exception from the runbook and prints "SKIPPED" on stdout. That handler is its own ledger row, `document.py:308`, in another batch.
- **A defect that row's fix will expose.** The section patterns allow one digit before a heading, so "## 10. Verification" and "## 2.2 Dependencies" are not found. On such an LLD the runbook now raises where it used to be invented.

### templates/wiki_page.py (2 ledger rows: 2 fixed)

- **No placeholder overview (120).** An LLD with no overview raises ValueError naming the feature, the issue and the headings searched, after an ERROR line and before anything is written.
- **A missing sidebar is said (169).** `update_wiki_sidebar` raises FileNotFoundError naming `_Sidebar.md`, after an ERROR line. It returned False, the same answer as "already linked", and N8 ignored it. False now means only "already linked".
- **The caller still swallows both.** N8 catches every exception from the wiki step and prints "SKIPPED" on stdout: ledger rows `document.py:289` and `document.py:292`, in another batch.

### templates/cp_docs.py (2 ledger rows: 2 fixed)

- **No invented commands (137, 159).** An LLD that shows no command raises ValueError naming the tool, the issue and what was searched, after an ERROR line and before anything is written. The CLI document carried an invented reference row and usage block, neither of them the tool's.
- **The caller still swallows it.** N8 catches every exception from the c/p docs and prints "SKIPPED": ledger row `document.py:338`, in another batch. The CLI document is written first, so no prompt document is written without it.


---

# 3585 - Implementation Report: loud failure in the testing workflow, batch A

## 1. Metadata

| Field | Value |
|-------|-------|
| **Issue** | #3585 (step 5, the #3581 sweep); module issue #3810 for `checkpoints.py` |
| **LLD** | None: the work order is #3585, and each site's prescription is its row in `docs/audits/0908-loud-failure-sweep-ledger.md` |
| **Test Report** | `docs/reports/3585/test-report.md` |
| **Implementer** | Claude Opus 5.5 via Claude Code |
| **Date** | 2026-10-31 |
| **Branch** | `3585-testing-verify` |

## 2. Summary

Batch A brings four modules of the testing workflow under ADR 0236 and standard 0034: every failure is loud, logged with details, stops what depends on it, and alerts the operator. Each module is one commit. The ledger's line numbers are from commit `79e18ad1`.

### 2.1 `assemblyzero/workflows/testing/checkpoints.py` (#3810, 14 rows fixed)

`commit_checkpoint`, `record_measurement` and `read_measurement` used to be best-effort: every git failure printed "(non-fatal)" to stdout and returned False or None, which callers read as "nothing to commit" or "no measurement". Each failure now writes one ERROR line to stderr, logs it, and raises `CheckpointError` naming the worktree or commit, the git command, its exit code and git's stderr. Only exit 1 of `git diff --cached --quiet` reads as staged, and only git's "no note found" (exit 1, nothing on stdout) reads as an unmeasured commit. A note is parsed field by field, so a corrupt note and numbers that do not convert are both live, named failures. The three `# fail-open:` tags are gone.

The module alerts no one itself; the caller that can stop does. N5 now notes its measurement through `_note_measurement` in `verify_phases.py`, which turns `CheckpointError` into N5's halt; `route_after_green` sends it to HALT, which alerts. The halt site is the new gate `impl.measurement_not_noted`, and the impl halt-row ratchet rises from 44 to 45.

### 2.2 `assemblyzero/workflows/testing/nodes/verify_phases.py` (33 rows fixed, 18 compliant rows pinned)

Every step N3 and N5 depend on raises `PhaseStepError` after an ERROR line: pytest that times out, cannot start or lacks pytest-cov for a coverage run; a red marker, test file, spec suite or audit directory that cannot be read or written; a snapshot, restore, dropping removal or visual sample that fails; a failed `git status`; a coverage target nothing names (the hard-coded default is gone) or that lies outside the repository; a runner that crashed or exited non-zero with no failure; an unknown coverage_type; a passing leg with no coverage figure; a critical skipped test. The two entry points turn it into one registered halt, gate `impl.phase_step_failed` (impl ratchet 46). A run with no framework, or naming an unknown one, halts through `FrameworkLegError`; a full suite whose exit contradicts its parse halts at the gate. A state with no `audit_dir` still writes no trail (only a direct call omits it); a named directory that is gone halts.

### 2.3 `assemblyzero/workflows/testing/nodes/cleanup_helpers.py` (4 fixed, 2 compliant)

A failed `git worktree list` raises `CalledProcessError`; only git's not-found message for this branch reads as already deleted; an unreadable lineage artifact or an unparsable coverage figure raises `LineageReadError`.

### 2.4 `assemblyzero/workflows/testing/nodes/cleanup.py` (N9, 8 fixed)

Every N9 failure writes an ERROR line and raises `CleanupError`, because N9's edge to END is unconditional; N9 reads the declared keys (`coverage_achieved`, `coverage_target`, `workflow_status`) and refuses when one, or `repo_root`, is absent; `route_after_document` raises when N8 leaves no issue_number. The graph changes that would let N8 and N9 route to HALT instead belong to `graph.py`.

## 3. Files Created

| File | Description |
|------|-------------|
| `tests/unit/test_checkpoints_loud_failure.py` | One test per ledger site, the kept behaviours, and N5's halt on a note it cannot write |
| `tests/unit/test_verify_phases_loud_failure.py` | One test per site, kept behaviours, and the 18 compliant rows (69 tests) |
| `tests/unit/test_cleanup_helpers_loud_failure.py` | One test per site and the two compliant rows (10 tests) |
| `tests/unit/test_cleanup_loud_failure.py` | One test per site and the kept behaviours (12 tests) |

## 4. Files Modified

| File | Description |
|------|-------------|
| `assemblyzero/workflows/testing/checkpoints.py` | `CheckpointError`; every git failure raises after an ERROR line; field parser for the note |
| `assemblyzero/workflows/testing/nodes/verify_phases.py` | `_note_measurement`: a note N5 cannot write is N5's halt |
| `assemblyzero/core/gate_registry.py` | Gate `impl.measurement_not_noted` |
| `tests/fixtures/gate_registry_baseline.json` | impl halt rows 44 to 45 |
| `tests/unit/conftest.py` | Autouse stand-in for the name N5 calls through (`verify_phases.record_measurement`); N5's unit tests measure fake runs in plain directories |
| `tests/unit/test_tdd_checkpoints.py`, `tests/unit/test_impl_resume_prefers_best_measured.py`, `tests/unit/test_impl_lands_through_driver.py` | Tests that asserted the retired best-effort behaviour now assert the raise |

## 5. Deviations from the ledger

None for `checkpoints.py`. Two defects found and not fixed (not ledger sites): `record_measurement` still returns False for a path that is not a directory, and `orchestrator/stages.py::_best_measured_attempt` reads every grave as unmeasured when `target_repo` is "".

## 6. Compliance with standard 0034

| Failure path | Loud | Logged | Stops | Alerts |
|---|---|---|---|---|
| A checkpoint commit fails (any git step, timeout, missing worktree) | ERROR line on stderr | `logger.error` and the exception message: worktree, command, exit code, stderr | `CheckpointError` raised | By the caller: the standalone finish's entry-point handler; the graph's checkpoint wrapper is batch C's row `graph.py:128` |
| N5's measurement note cannot be written | ERROR line on stderr | as above, plus the note | N5 returns `error_message`, routed to HALT | HALT alerts |
| A measurement note cannot be read or is corrupt | ERROR line on stderr | commit, repository, note text | `CheckpointError` raised out of the impl stage | The orchestrator entry point's handler |

---

# Joining the batches

The five branches were merged on `21e32f12` in the order C, A, B, D, E. Merge conflicts were the two report files (each batch's report kept whole), `gate_registry_baseline.json` (regenerated from the tree, never merged by hand) and `test_spec_stage_pair.py` (batch D's assertions, which the joined code needs, with batch C's sentence in the docstring). Four places where one batch's change met another's were fixed:

- **An unknown framework.** Batch E made the runner registry raise `UnknownFrameworkError` where it answered None, so batch A's N3 check never saw None and crashed. `run_frameworks` now wraps it in `TestFileOwnershipError`, which N2 to N5 already halt on, naming the framework (#4311).
- **N8 and its templates.** Batch E's templates refuse to invent a section the LLD lacks; batch D's N8 raises naming the artifact. Both stand. They disagreed on a wiki with no `_Sidebar.md`: E raised, D kept it as a legitimate absence (row 289; `generate_wiki_page` makes the wiki directory itself, and most repositories have no sidebar). `update_wiki_sidebar` now returns None for no sidebar and False for already linked, so the two answers E wanted told apart are told apart, D's absence stays quiet, and N8 names each.
- **Checkpoints on a target that ignores `data/`.** Batch A made a failed `git add` raise and batch C made the checkpoint wrapper raise instead of swallowing. Joined, every checkpoint in a repository that ignores `data/` halted: the exclusion pathspecs `:!data/lineage` and `:!data/hourglass` name ignored paths, and `git add` exits 1 for that although `-A` never stages an ignored file. Only the excluded paths a repository does not ignore are now excluded (`git check-ignore`; a check that fails raises).
- **Tests built on the old silences.** Seven N8 tests gained LLDs with the sections the templates need; three loop-cap rolls gained a real git worktree; one staging test's fake git now says the internal dirs are not ignored.

Left as follow-ups, each already loud, stopping and alerting through the entry point: N8 and N9 halting through HALT rather than by raising (#4308), `RunnerError` in N3, N5 and the full-suite gate (#4309), `PhaseStepError` and `SymbolCheckError` in N4c (#4310). Ledger row `audit.py:320` stays open behind a strict xfail (#4312).

---

# Implementation Report: run-path modules outside the workflow packages under standard 0034 (#3585 step 5)

The rule is ADR 0236 and standard 0034. This branch takes the modules a workflow run passes through outside the three workflow packages: `workflows/narration.py`, `utils/`, `workflows/telemetry/` and `telemetry/`, `visual_gate/`, `hooks/` and `speedrun/`. Each module's ledger 0908 sites are fixed and tested, highest harm first: failures a run reads as success before failures that lose a record.

## Scope

A module is in scope when a run imports it. The import chain was read with `ast` from the three runners (`tools/run_requirements_workflow.py`, `tools/run_implement_from_lld.py`, `tools/run_implementation_spec_workflow.py`) and the three graph builders, following imports at module level and inside functions.

Not in this branch, because no run reaches them:
- utils: `github_metrics_client.py`, `markdown_inventory.py`, `metrics_aggregator.py`, `metrics_config.py`, `metrics_models.py`;
- telemetry: `telemetry/__main__.py`, `telemetry/sync.py`;
- visual_gate: `bundle.py`, `floor.py`, `gate.py`, `modify.py`, `server.py`, imported only inside the orchestrator's visual stage, which no runner runs (`run_implement_from_lld.py` takes only `impl_pr_body_path` from `orchestrator/stages.py`);
- speedrun: `answer_key.py`, `archive.py`, `box_health.py`, `emergency_stop.py`, `golden_disasters.py`, `healing.py` (imported only inside `factory_report.build_report`), `prompt_ranking.py`, `replay.py`, `roll_blockers.py`, `successes.py`, `timing.py`.

## Modules

### speedrun/requirements_status.py (3 sites)

The ledger exists so a roll whose requirements gate proceeded without a verdict cannot read as a verified roll. Losing a record, or a line of the ledger, hides that banner.

- **A record that cannot be written alerts and raises** (65). `record_unverified` used to return False, which its caller ignored. It now alerts with the ledger path and the cause and re-raises the `OSError` or `ValueError`.
- **A ledger line that cannot be read alerts and raises** (88, 90). A line that is not JSON, or is JSON but not an object, raises `ValueError` naming the file and line, after an alert. It used to be skipped.
- An absent ledger stays the quiet `[]`: no run has proceeded without a verdict.

Callers that still swallow the raise: `workflows/requirements/nodes/analyze_requirements.py` `_record_unverified` prints a WARNING; `tools/orchestrate.py` and `tools/speedrun_roll.py` `_requirements_unverified_lines` catch any exception around the read. Neither file is in this branch.

Compliance: each failure path writes an ERROR line through `alert_operator`, records what, where, cause and consequence, alerts, and raises.

### utils/ast_sentinel.py (2 sites)

- **A file that does not parse raises** (472). `analyze_source` raises `SentinelCannotRun` naming the file, the line and the syntax error, chained from the `SyntaxError`. It used to return a `<syntax>` finding, which the mechanical validator filed as the advisory "symbol '<syntax>' may not be imported".
- **A file that cannot be read raises** (498). `analyze_file` raises `SentinelCannotRun` for an `OSError` or `UnicodeDecodeError`, naming the path. It used to return an `<io>` finding.
- An undefined name is still a finding in the result; only "could not check" moved to a raise.

Caller that still swallows the raise: `workflows/requirements/nodes/validate_mechanical.py` `run_ast_sentinel_on_modify_files` catches `Exception` and logs at DEBUG (its own loud-failure baseline entry). Until it is fixed, a broken file goes from an advisory warning to nothing.

Compliance: the raise carries what and where (the file) and the cause; stopping and alerting fall to the caller, which is in the requirements package.

### utils/lld_verification.py (1 site; 1 compliant row)

- **The path check always runs** (307). `run_verification_gate` validated the LLD path only when a `project_root` was passed; without one the security check was skipped and the gate went on to pass the file. It now always calls `validate_lld_path`, which uses the current directory when no root is given, as its docstring says.
- The `ValueError` handler at 282 already raises `LLDVerificationError`; the ledger marks it compliant and it is unchanged.

No caller in `assemblyzero/` or `tools/` calls `run_verification_gate`; `utils/__init__.py` re-exports it.

### utils/lld_path_enforcer.py (1 site, won't do)

- **No Section 2.1 stays an empty spec** (97, won't do). The ledger asks for a raise. On a real implementation run the content passed in is the implementation spec (`load_lld` stores it under `lld_content`), whose files table is `## 2. Files to Implement`; it has no Section 2.1 by design. The implementation node adds every path of that table to the allowed set itself. A raise would halt every implementation run, so the empty answer is the contract. The docstring now says so, and a test pins it.

### utils/codebase_reader.py (7 sites)

The reader builds the codebase context the requirements drafter works from. A file it selected that could not be read used to come back empty and was dropped from the batch, so the draft was built on a partial context with nothing said.

- **A file that cannot be stat'd, resolved or read raises** (152, 171, 201) `CodebaseReadError` naming the file and the cause. `read_files_within_budget` stops on it instead of dropping the file.
- **A symlink that escapes the repo raises** (164), naming the link and where it resolves, and none of the content. It was a WARNING and an empty result.
- **A text file that is not valid in its encoding raises** (198). Binary extensions are still skipped before the read; a file that reaches the read was taken to be text.
- **A `pyproject.toml` or `package.json` that does not parse raises** (340, 369), naming the file. It read as `{}`, and a broken `pyproject.toml` silently fell through to `package.json`.
- Kept quiet, by contract and in the docstrings: a file that does not exist, is not a regular file, has a binary extension or matches a sensitive pattern, and a repo with no config file.

Caller: `workflows/requirements/nodes/analyze_codebase.py` has no handler around these calls, so the raise leaves the node uncaught; it is not routed to HALT. Baseline: the two `parse_project_metadata` handler entries leave.

### speedrun/convergence.py (5 sites) and the one consumer line in factory_report.py (802)

- **A record that cannot be appended alerts and raises** (90, 91). `_append` returned False, which every caller ignored, so the factory report fell back to the banner for that run. It now alerts with the store path, the event, stage and node, and the cause, then raises. `record_stage_enter`, `record_node_enter` and `record_terminal` return True only once the line is on disk. A follow-up commit moves the store-path computation inside the alerted region: a root the path cannot be built from (a NUL byte) raised unalerted in the first version.
- **A line that is not a record alerts and raises** (185, 186, 195). `read_records` counted such a line, and its one consumer, `factory_report.apply_records` (802), threw the count away, so the report stated numbers from a store it had not fully read. It now alerts and raises `ValueError` naming the store and the line. The count only ever carried those lines, so it is gone: `read_records` returns the list of records, and `apply_records` takes the list.
- An absent store is still the quiet `[]`.
- The two `# fail-open:` tags are gone.

Callers that still swallow the raise: `workflows/narration.py` `_record_entry` (fixed in the next commit); `workflows/orchestrator/graph.py` `_record_stage_entry` and `_record_terminal` catch `Exception` and return. The operator is alerted before either swallows.

Baseline: three entries leave (`_append`'s handler and tag, `read_records`'s tag).

### workflows/narration.py (4 sites; 1 compliant row)

`narrated()` wraps every node of all three graphs, so each of these ran on every node of every run.

- **A node with no atlas entry fails the graph build** (64). It printed a plain line once and the run went on. `narrated()` now raises `ValueError` naming the node and the stage at wrap time; `test_graph_atlas.py` already holds every real graph to a complete atlas.
- **A narration line that cannot be built or printed alerts and raises** (114). A broken atlas entry, a state that raises, or a closed stdout was dropped with a bare `pass` and the node ran. Now the node does not run.
- **A convergence record that cannot be written stops the node** (160). The store alerts and raises; the wrap no longer swallows it, and adds no second alert. The `# fail-open:` tag is gone.
- **A call-recording context that cannot be set alerts and raises** (181). It was swallowed, so the node's model calls were recorded against the node before it. The tag is gone.
- The `TypeError` handler in `_gate_is_off` (55) is the documented "unknown gate" answer; the ledger marks it compliant and a test pins it.
- Kept, and documented: a state with no `repo_root` records nothing.

Defect found, not fixed (outside the ledger rows): the requirements workflow's state has no `repo_root` key (it carries `target_repo`), and no requirements node sets one. So `_record_entry` returns at its first check on every LLD node, and the LLD stage writes no `node.enter` records at all.

Baseline: five entries leave (`narrated._wrapped`'s handler; `_record_entry`'s handler and tag; `_set_call_context`'s handler and tag).

### speedrun/prompt_telemetry.py (4 sites)

The store is where the rate of drafter validation failures is computed; each of these made the rate read lower than it was.

- **A failure with an empty detail is counted** (130), under the fingerprint `<stage>:<check>:empty-detail`, with the raw text kept. It returned None and wrote nothing.
- **A write that fails alerts and raises** (152), naming the store, the fingerprint and the cause. It printed through `log=print` and returned None. The `log` parameter only carried that message and is gone; `record_failure` always returns the record.
- **A store that exists but cannot be read alerts and raises** (180). An absent store is still `[]`, now by an existence check.
- **A line that is not a JSON object alerts and raises** (188), naming the line. It was skipped uncounted.

Callers that still swallow the raise: the three requirements nodes that record (`analyze_requirements.py`, `validate_mechanical.py`, `validate_test_plan.py`) and `orchestrator/stages.py` `_record_spec_convergence_failure` catch `Exception` and print or warn, so the halt they record is unchanged; the operator has been alerted first. The two readers, `factory_report.build_report` and `tools/prompt_failure_report.py`, let it out.

### workflows/telemetry/hallucination_log.py (3 sites)

The log is the baseline every invented-API detection is measured against.

- **An audit directory that was given but does not exist alerts and raises** `FileNotFoundError` (105). It was skipped silently. `None` still means "no such sink for this run".
- **A sink write that fails alerts and raises** (114, 123), naming the sink, the path and the cause. Each printed a WARNING to stdout and went on.
- Both sinks are always attempted; each failure alerts; the first is raised.

Caller that still swallows the raise: `workflows/implementation_spec/nodes/validate_completeness.py` wraps `_record_hallucination_telemetry` in `except Exception` and prints a WARNING, so the gate's verdict is unchanged; the operator has been alerted first.

Defect found, not fixed: a cold import of `assemblyzero.workflows.telemetry` (or of `hallucination_log`) fails with a circular import: `hallucination_log` imports `workflows.requirements.audit` at module level, which reaches `validate_completeness`, which imports the half-initialised telemetry package. A run imports the graphs first, so it never meets this; the new test file imports `validate_completeness` first for the same reason.

### visual_gate/config.py (2 sites)

- **A declared gate with no `renderer_cmd` is refused at load** (77). It got an empty command, which failed only at render time. Absent and empty both raise `ValueError` naming the key and the file.
- **A declared gate with no `separation_floor` is refused at load** (79). It got 0, which silently turned the palette-floor guardrail off, so a Modify that should have been refused passed. An explicit 0 is the repo's declared choice and still loads.
- No declaration file is still no gate (`None`).

Callers: `orchestrator/stages.py` `run_visual_stage` already turns a `ValueError` into a failed, non-transient stage result. `implementation_spec/nodes/compile_manifest.py` `_contract_text` catches `Exception`, prints, and compiles without the contract (a `# fail-open:` site of its own). `requirements/contract_fidelity.py` `resolve_contract` lets it out.

### utils/retry.py (1 site)

- **Giving up is an ERROR on stderr and in the log** (220). When `with_retry` stops (retries exhausted, or a failure not worth retrying) it still returns the last failed `LLMCallResult`, which is the declared contract every caller routes to HALT. What changed is how it says so: the halt line went to stdout and the log record was INFO. It now also writes `ERROR [RETRY] <call> failed after N attempt(s) [<class>]: <cause>; <reason>` to stderr and logs it at ERROR.

Callers: `workflows/testing/nodes/review_test_plan.py` and `revise_test_plan.py` return the failure as `error_message`; their routing to HALT is the testing package's.

### utils/process.py (2 sites)

`kill_process_tree` ends a timed-out model call and everything it spawned, so the drain after it does not block on a grandchild holding the pipes (the #1874 hang).

- **A `taskkill` that fails raises** (33). Its exit code was never read. Now 0 and 128 ("not found") are quiet; any other code raises `ProcessTreeKillError` with the code and stderr.
- **A kill the OS refuses, or a `taskkill` that times out, raises** (41). Every `OSError` and the timeout were swallowed as "already dead". Now only `ProcessLookupError` is quiet; the rest raise `ProcessTreeKillError` naming the pid and the cause, after an ERROR line on stderr and in the log.

Callers: `core/llm_provider.py` (`_kill_process_tree`, on the idle and wall timeouts and the storm probe) and `core/gemini_client.py` (the agy timeout). Neither catches it: a tree that survived its kill now ends the call loudly instead of reporting a clean timeout.

### utils/workflow_timeout.py (1 site)

- **The timeout alerts before it exits** (74). The timer printed a banner to stderr and called `os._exit(42)`, never reaching `alert_operator`, so a run that died on its wall clock told nobody away from the console. The handler is now `WorkflowTimeout._expire`: banner, then `alert_operator` with the limit, the workflow and the issue, then `os._exit(42)` in a `finally`, so the process still exits when the alert cannot be delivered.
- `WorkflowTimeout` takes optional `issue` and `workflow` keywords for the alert. The three runners do not pass them yet (they are not in this branch), so the alert says "workflow unnamed" until they do.

### telemetry/cost.py (1 site)

- **An unpriced model has no estimate, not a free one** (73). `estimate_cost` returned 0.0 with a WARNING, so the call record of an unpriced model read exactly like a call that cost nothing. It now returns None, the ledger's second option ("return None that callers must handle"). The record field `cost_usd_estimate` is already `Optional[float]`, the one caller (`InstrumentedCall.__exit__`) stores the value as given, and a sum that meets None raises instead of counting it as zero.

### utils/speedrun.py (3 sites)

The speed-run record is opt-in (`--speedrun`), and when it is on it is the durable cross-attempt record.

- **A lap split that cannot be written alerts and raises** (144), naming the file, the issue and the attempt. It was a WARNING.
- **A run-log entry that cannot be appended alerts and raises** (320). It was a WARNING.
- **A malformed run-log line alerts and raises** `ValueError` naming the log and the line (335). It was skipped with a WARNING, so the summary counted fewer attempts than the log holds.

Callers: the runners' `_finalize_speedrun` (`tools/run_requirements_workflow.py`, `tools/run_implement_from_lld.py`) and `tools/speedrun_summarize.py` do not catch.

### telemetry/store.py (4 sites)

- **A call record that cannot be written alerts and raises** (71). `CallStore.write` swallowed every exception at WARNING and the record was lost.
- **A corrupt line in a day's file alerts and raises** (88), naming the file and the line. It was skipped at WARNING.
- **A `calls-*.jsonl` file whose name holds no date alerts and raises** (114). It was skipped silently.
- **A corrupt line met by `query` alerts and raises** (127). It was skipped silently.
- A disabled store, and a day with no file, stay quiet.

Callers: `InstrumentedCall.__exit__` writes through it; its one user is `assemblyzero/nodes/anthropic_provider.py`, which no run reaches. Baseline: `CallStore.write`'s handler entry leaves.

### telemetry/emitter.py (9 sites: 7 fixed, 2 won't do, and 1 compliant row)

Every runner imports `emit`, `flush` and `track_tool`, and two register `flush` with `atexit`; graph routers and implementation nodes call `emit`. The module was fire-and-forget: every failure was a bare `pass` or a silent `None`.

- **A credentials file that exists but cannot be loaded raises** `TelemetryConfigError` (68), on every emit and flush, with an ERROR line each time and one alert per process. The cause names the exception type and the path, never the file's contents. Nothing is cached on failure.
- **An event the buffer cannot take alerts and raises** (84). It was dropped with a bare `pass`.
- **A failed DynamoDB write is an ERROR line, and the event is buffered** (151), with one alert per process: an outage fails every emit, and one email says so.
- **An event that cannot be built alerts and raises** (156). The outer `pass` is gone.
- **A buffered event that fails to upload stays buffered** (192), with an ERROR line naming the file and line, and one alert per process.
- **A buffer file that cannot be read or rewritten alerts and raises** (200), saying how many events were uploaded before it. The outer `pass` around the whole flush is gone (203).
- **Won't do, 54: no credentials file is local-only mode.** Every event is kept in the buffer, so nothing is lost, and the opt-out is `ASSEMBLYZERO_TELEMETRY=0`. An alert here would send one email per process from every machine without upload credentials, and would put an extra alert into whichever unit test emits first. Documented in the docstring and pinned.
- **Won't do, 171: `flush` with no client returns 0.** In local-only mode nothing was uploaded, so 0 is the true count; a raise would fail every runner's `atexit` flush on such a machine. Pinned. The sync CLI that prints "No buffered events to sync." on that 0 is `telemetry/sync.py`, which no run imports.
- The `track_tool` handler (237) re-raises; the ledger marks it compliant.

Callers: nothing catches the new raises, so a broken credentials file or a buffer that cannot take an event now stops the tool at its first emit. Baseline: seven entries leave.

### telemetry/actor.py (2 sites, loud but not raised)

`detect_github_user` labels every telemetry event.

- **`gh`'s exit code is read** (34). A non-zero exit was scanned anyway and fell through to "unknown". It now writes `ERROR [TELEMETRY] GitHub user not detected (gh auth status exited N)` to stderr, never `gh`'s output, and records "unknown".
- **`gh` missing or timing out is an ERROR line** (48), naming the exception type, instead of a bare `pass`. The handler is narrowed to `OSError` and `SubprocessError`.
- **`gh` is no longer asked for the token.** The call was `gh auth status --show-token`; the username line does not need it.
- **Not raised and not alerted, deliberately.** "unknown" is the label the docstring declares. Every `emit` calls this, and CI runs the unit tier with no `gh` login and with telemetry on, so a raise would fail every test that emits there, and an alert would land in whichever test emits first. Baseline: the handler entry leaves.

### speedrun/restore.py (4 sites)

`restore_artifact` rebuilds a missing pipeline input from the refs; the implementation run's `find_lld_path` calls it before concluding an LLD is absent.

- **A failing `git for-each-ref` raises** `RestoreError` with the command, the return code and stderr (46, 83). It returned no refs, so the search silently covered fewer of them.
- **A path outside the repo raises `ValueError`** (140). It was a tagged `return False`; the tag is gone.
- **A `git show` that fails for any reason but absence raises** `RestoreError` (150). Absence is a closed list of git's own messages: the ref does not exist, or the path is not on it. Those still move the search to the next ref.
- `False` now means only that no source holds the file.

Callers: `workflows/testing/nodes/load_lld.py` `find_lld_path` catches `Exception` around it and prints a WARN (a `# fail-open:` site of the testing package). `tools/speedrun_roll.py` (`_restore_artifact`, `_graveyard_leavings_refs`) lets it out. Baseline: the tag entry leaves.

### speedrun/must_resolve.py (18 sites, and 1 compliant row)

A requirements conflict halts the run and files a must-resolve question that the next launch refuses on. Every failure in that path printed a line to stdout and nothing more, and several read as success.

- **The halt is still never changed; every filing failure now alerts.** A new `_filing_failed` helper writes an ERROR line to the run log, calls `alert_operator` with what, where (the gate), the repository, the source issue, the cause and the consequence, and returns the failed result. That covers no GitHub remote (451), a recurrence comment that fails (465), an issue create that fails after the label retry (498), and a conflict with nothing to rule on (411, action still `rejected`).
- **A failed dedupe query is a failed filing, never "no existing issue"** (355, 359). `_find_existing` raises the new `MustResolveError` for a non-zero exit, an answer that is not JSON, or one that is not a list of issues; the filer files nothing, because filing without the check could duplicate an open question.
- **The label's own failure is reported** (372). `_ensure_label` returns gh's answer; when the retried create still fails, the cause names both exit codes and both stderrs. A label failure followed by a successful create is not reported: the created issue carries the label, which proves it exists.
- **An issue created with no number is a failure** (503): alert, nothing written to the ledger, the output named in the cause.
- **A ledger line that cannot be written is a failure** (443, 473, 509, 613). `record_filed` raises `OSError` naming the ledger (it returned False, which every call ignored) and `ValueError` for a call with neither a number nor a suppression reason; `file_must_resolve` alerts with the issue number and returns a failed result that still carries the number.
- **The ledger reads as empty only when it is absent** (630, 639). One that cannot be read alerts and re-raises; a line that is not JSON, not an object, or has a number that is not a whole number alerts and raises `ValueError` naming `path:line`. A line with no number (a suppressed replay filing) is still left out by contract.
- **The launch gate refuses when it cannot run** (527, 535, 539). `open_must_resolve_issues` keeps its `(issues, error)` contract and alerts on every error (no remote, gh failing, an answer that is not JSON or not a list). Its direct caller, `tools/speedrun_roll.py` at the launch gate, now prints BLOCKED and returns 91 where it warned and launched. `check_prereqs` already refused on the error; the run summary already says the list could not be read.
- **One conflict's filing raising alerts** (721) and is recorded failed; the remaining conflicts are still filed.
- 176 is compliant: `_default_runner` models a missing binary as exit 127, which every caller checks.

Callers that still swallow: `workflows/requirements/nodes/analyze_requirements.py` (around `file_all_conflicts`), `workflows/implementation_spec/nodes/review_spec.py` and `compile_manifest.py` (around `file_must_resolve`) catch `Exception` and print a WARNING. After this change only an undeliverable alert or a runner exception reaches them; the filing failures alert before they return. Those files are other branches' work.

Unit isolation: `tests/unit/conftest.py` gains `_must_resolve_gate_answers_offline`, which rebinds `speedrun_roll.open_must_resolve_issues` to "GitHub answered, nothing open". Twenty-three tests drive `speedrun_roll.main()` on a repository with no GitHub remote and relied on the gate warning and launching. The fixture follows the existing box-health bypass beside it.

Compliance: every failure path writes an ERROR line through `alert_operator` with what, where, identity, cause and consequence; the filer's halt is unchanged by contract, and the launch gate stops the launch. Baseline: the `file_all_conflicts` handler entry leaves.

### speedrun/factory_report.py (14 sites)

The factory report replaces "whichever kill happened most recently" with counts, and several of its readers made those counts wrong in a direction nobody could see. A run only reaches `classify_cause`, which is unchanged; the rest is `tools/factory_report.py`, and `scan_run_log` is also used by `tools/replay_run.py`.

- **The withdrawn tags are gone** from `parse_since` (496), `_parse_ts` (511), `scan_run_log` (631, 647), `scan_run_logs` (764), `_under` (852), `_parse_halted_at` (928) and `read_halt_bundles` (972). Where a tag excused a loop that tried two formats, the format is now chosen by the space that only the timestamp form has, so one parse decides and its own error names the input; `parse_since` still raises for an unparseable window.
- **A record that cannot be placed in the window alerts and raises** (529). `_in_window` takes a `source` naming the store and record, and with a window asked for, a timestamp that is not a date raises `ValueError` naming both. It used to keep the record in every window and count it nowhere. With no window, nothing is dated.
- **A run log that cannot be stat'd or read alerts and re-raises** (630, 646). An unstattable log was kept in every window and filed undated; an unreadable one carried `unreadable=True`, which nothing printed, and counted as a killed run. The `unreadable` field is deleted.
- **A path that cannot be resolved alerts and re-raises** (851). It read as "outside this repo" and dropped the halt. Containment is now `is_relative_to`, so "outside" is only ever an answer.
- **A halt bundle that cannot be read, is not JSON, or is not an object alerts and raises** (971, 976), naming the file. A bundle whose date cannot be read under a window does the same.
- **A bundle whose stamp is not ISO-8601 is still counted as unplaced, and now alerts** (928). `_parse_halted_at` raises; `attribute_bundles` counts the bundle unplaced, its declared place in the coverage figure, and calls `alert_operator` with the bundle's path.
- A repo with no runs directory still has no runs, documented and pinned: `build_report` records the absence and the report prints NO for that store.

Callers: `tools/factory_report.py` `main` and `tools/replay_run.py` do not catch, so a short count now ends either tool with a traceback after the alert. Neither is on a run path.

Compliance: each failure path alerts with what, where, cause and consequence (the report stops rather than print a short count) and raises, except 928, which alerts and keeps its declared count. Baseline: eight tag entries leave.

### speedrun/preserved.py (4 sites)

The archiver bundles every branch this ledger names. Committed before `worktrees.py` and `leavings.py`, because their ledger rows (295, 312) turn on this module raising.

- **A record that cannot be written raises naming the ledger** (97). `record_preserved` returned False, which both writers ignored, so a branch could be preserved and never reach the archive's record. It now raises `OSError` naming the branch and the ledger, and `ValueError` for an empty branch. The two writers alert: the raise-and-let-the-caller-alert shape, since each caller has already put the work on the branch and alerts with the worktree or the files it was preserving.
- **A ledger that exists but cannot be read alerts and re-raises** (115). It read as no preservations. Absence (no file) is still the quiet `[]`, by an existence check, so a directory where the file must be is no longer read as absence.
- **A line that is not JSON, not an object, or names no branch alerts and raises** `ValueError` naming `path:line` (124, 127). Such a line used to be skipped.

Callers: `assemblyzero/speedrun/archive.py` (`recorded_for`, `claimed_by_other_run`) and `factory_report.build_report` read the ledger and do not catch. The two writers are the next two sections.

Compliance: the reader alerts with what, where, cause and consequence and raises; the writer raises with the path and cause to callers that alert.

### speedrun/worktrees.py (13 sites)

The sweep runs at every launch and moves or removes the pipeline's worktrees. A run reaches only the path helpers (`pipeline_worktree_path`); the sweep is `tools/speedrun_roll.py`'s.

- **A worktree list git cannot give alerts and raises before anything moves** (97). `registered_worktrees` returned an empty set, which made every pipeline worktree look unregistered, so the sweep would have relocated each one as an orphan. It now raises the new `WorktreeSweepError` with the exit code and stderr.
- **A status that fails alerts** (136). The worktree is still treated as dirty and preserved, never discarded.
- **ReadOnly clearing raises instead of clearing part of a tree** (223, 229, 236). A tree that cannot be listed, a path that cannot be stat'd, and a chmod that fails log at ERROR and re-raise. Off Windows, where `os.stat` has no `st_file_attributes`, there is nothing to clear and the answer is 0, decided once rather than by an `AttributeError` per path.
- **Every entry the sweep cannot finish alerts** through the new `_sweep_failed`: a failed `git add -A` (274, which used to be ignored, so the commit could preserve less than the tree held), a removal that fails after preserving (300), an orphan that cannot be relocated (315), and a clean worktree that cannot be removed (344). Each is still returned as a problem entry and the sweep goes on to the next worktree.
- **A graveyard push that fails keeps the worktree and alerts** (286). The branch exists only in this checkout, so the content is not yet preserved against the checkout going.
- **A branch the ledger cannot record alerts, and the entry is a problem** (295). It is recorded even when the push failed, because the local branch holds the content either way.
- **With no log, every line goes to stderr** (330); it went to a no-op.
- **An unexpected OSError alerts and re-raises** (351), naming the worktree the sweep stopped at.

Callers: `tools/speedrun_roll.py` at launch catches `Exception` around the sweep and writes SWEEP FAILED (continuing); every failure above alerts before that. `restore_repo` in the same file calls `registered_worktrees` from the roll's `finally`, so a worktree list that fails there now raises out of it, after the alert.

Compliance: each failure path alerts with what, where, repository, cause and consequence; the list failure and the unexpected OSError stop the sweep, the per-worktree failures stop that worktree's handling and keep its content. Baseline: no loud-baseline entries existed for this module.

### speedrun/leavings.py (6 sites, and 1 compliant row)

The file janitor preserves pipeline-authored untracked files on a pushed graveyard branch and then clears them, at launch and at exit.

- **A `git status` that fails alerts and raises** the new `LeavingsError` with its exit code and stderr, in `untracked_files` (180, which read it as "no untracked files") and in `classify_dirt` (213, which passed it off as one line of operator dirt).
- **With no log, every line goes to stderr** (247); it went to a no-op.
- **A preservation step that fails alerts** (263): read-tree, add, write-tree, commit-tree, branch or push. Every file still stays in place.
- **A branch the preserved-branch ledger cannot record alerts** (312). The files are still cleared, because the pushed branch holds them.
- **A file that cannot be removed alerts** (321), naming the file and the branch that holds its content.
- 349 is compliant and pinned: `rmdir` of a directory that still holds something is the pruning's stop condition.

Callers: in `tools/speedrun_roll.py`, the launch janitor catches `Exception` and writes JANITOR FAILED (continuing), after the alert; the baseline `untracked_files` read before the first roll does not catch, so a status that fails stops the launch; `restore_repo` (in the roll's `finally`) does not catch either. `tools/speedrun_new_attempt.py` (`check_preconditions`, and `main` under `--apply`) lets the raise out.

Compliance: each failure path alerts with what, where, repository, cause and consequence; a status failure stops what reads it, a preservation failure clears nothing, and a removal failure leaves that file. Baseline: no loud-baseline entries existed for this module.

### telemetry/cascade_events.py (4 sites)

The cascade detector's event log, for measuring its accuracy. Every run imports it (`telemetry/__init__`), but nothing in `assemblyzero/` or `tools/` calls `get_cascade_stats`, and `log_cascade_event` is called only by `hooks/cascade_action.py`.

- **An event that cannot be written logs at ERROR and raises** `OSError` naming the log (72). It was a plain print and the event was lost. Its one caller alerts with the session id (next section).
- **A log line that is not JSON or not an object raises** `ValueError` naming `path:line` (152). It was skipped, so the stats undercounted.
- **With a window, a timestamp that is not a timezone-aware ISO-8601 instant raises** naming the line (161), including a naive one, whose comparison used to raise a `TypeError` that was swallowed with the rest.
- **A log that cannot be read logs at ERROR and re-raises** (170). It returned partial or zero stats with a WARNING.
- An absent log is still zero stats, and with no window no timestamp is read.

Compliance: each failure is an ERROR log line or a raise naming the log and line; the write's caller alerts. No alert at the reader, as the ledger's fixes ask: it has no caller in the codebase to route one through.

### hooks/cascade_action.py, cascade_detector.py, cascade_patterns.py (8 sites, and 1 compliant row)

The cascade detector blocks auto-approval of output that offers to start the next task. Every run imports these modules (`telemetry/__init__` -> `cascade_events` -> `hooks`), but nothing in `assemblyzero/` or `tools/` calls `detect_cascade_risk`, `load_user_patterns` or `handle_cascade_detection`. The detector's config path, its per-call config read, and pattern CP-024 are open issues of their own (#4277, #4276, #4275) and are unchanged.

- **A block whose telemetry cannot be recorded alerts, and still blocks** (cascade_action 64). The handler was a bare `pass`. It now calls `alert_operator` with the session id, the action and the cause; the alert import is lazy, like the telemetry import beside it, because `hooks/__init__` imports this module.
- **A pattern whose regex does not compile raises** (cascade_detector 81) the new `CascadePatternError`, naming the pattern and the regex error. It was skipped "silently", so detection ran with fewer patterns and could allow what the missing one exists to block.
- **A user pattern config that cannot be used raises** `CascadePatternError` (cascade_patterns 221, 228, 237, 245, 247, 252): one that cannot be read or is not JSON, is not an object, has a `patterns` field that is not a list, or holds an entry that is not an object, lacks a required key, or has a regex that does not compile. Each named the config or the entry in a WARNING, or nothing, and returned the defaults alone, so the operator's overrides vanished.
- 214 is compliant and pinned: an absent config is no user patterns. A config with `"enabled": false` is too, by the same reasoning.

Compliance: the block handler alerts with what, where, cause and consequence; the detector and the loader raise naming the pattern or config, which stops detection. No alert at those two: the ledger's fixes say raise, and they have no caller in the codebase. Baseline: the `handle_cascade_detection` handler entry leaves.
