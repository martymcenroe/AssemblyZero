# Babysit Protocol (The Perdita Protocol)

When the user says "babysit": run a workflow in the background, monitor its execution mechanically, and intervene only when the **Perdita Protocol** guardrails are triggered.

## The Perdita Shift (Mechanical Monitoring)

As of March 2026, babysitting has shifted from manual "human-watching-agent" to **Mechanical Safety Gates**. The agent is expected to babysit itself using the following rules:

1.  **Two-Strike Rule:** Maximum of 2 retries per file/node. If the second attempt fails, the workflow must **Halt and Plan**.
2.  **Surgical Context:** Retries must prune context (LLD + current file only) to conserve the $200/month Claude Pro Max token budget.
3.  **File Size Safety Gate:** Reject any 'Modify' operation that results in a >50% reduction in line count unless explicitly authorized.
4.  **Isolation:** Work only in isolated worktrees (`../AssemblyZero-{ID}`).

## Hard Rules

1. **ALWAYS redirect output to `/tmp/` file.** Use: `> /tmp/workflow-ISSUE.log 2>&1 &` and `echo "PID: $!"`.
2. **NEVER use the TaskOutput tool to monitor workflows.** Use `cat /tmp/workflow-ISSUE.log` instead.
3. **One workflow at a time** unless explicitly told otherwise.
4. **Token discipline is paramount.** Use surgical context pruning on all retries.
5. **When something produces no output, redirect to file FIRST.**
6. **Stay focused.** Don't propose parallel work while a babysit is in progress.

## Pipeline (LLD → Impl Spec → TDD)

All commands run from AssemblyZero. The `--repo` flag points to the target repo.

### Step 1 — LLD
```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
CLAUDECODE= PYTHONUNBUFFERED=1 poetry run python tools/run_requirements_workflow.py \
    --type lld --issue {NUMBER} --repo /c/Users/mcwiz/Projects/{TARGET_REPO} --yes \
    > /tmp/lld-{NUMBER}.log 2>&1
```

### Step 2 — Implementation Spec
```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
CLAUDECODE= PYTHONUNBUFFERED=1 poetry run python tools/run_implementation_spec_workflow.py \
    --issue {NUMBER} --repo /c/Users/mcwiz/Projects/{TARGET_REPO} \
    > /tmp/impl-spec-{NUMBER}.log 2>&1
```

### Step 3 — TDD Implementation
```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
CLAUDECODE= PYTHONUNBUFFERED=1 poetry run python tools/run_implement_from_lld.py \
    --issue {NUMBER} --repo /c/Users/mcwiz/Projects/{TARGET_REPO} \
    > /tmp/tdd-{NUMBER}.log 2>&1
```

## Monitoring (The Perdita Watch)

Watch logs and watch for: `[CIRCUIT]`, `[STAGNATION]`, `ERROR`, `FAILED`, tracebacks, >120s silence.

Two-strike rule applies per issue per phase.

## Done Criteria

- LLD: `docs/lld/active/LLD-{NUMBER}.md` exists with APPROVED verdict
- Impl Spec: spec exists under `docs/lld/drafts/` with APPROVED verdict
- TDD: tests pass, no regressions

## Closing Issues

Use `Closes #{NUMBER}` in commit message body — never `gh issue close`.
After push, verify issues show CLOSED on GitHub.

### Worktree Cleanup
Archival must happen BEFORE creating the PR. Inside your worktree, run:
```bash
poetry run python tools/archive_worktree_lineage.py --worktree . --issue {NUMBER} --main-repo .
git commit -m "chore: archive workflow lineage (Closes #{NUMBER})"
```
Submit the lineage as part of your feature PR.
