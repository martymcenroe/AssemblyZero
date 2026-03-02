# Babysit Protocol

When the user says "babysit": run a workflow in the background, tail the output, watch for stalls/errors, intervene when needed.

## Hard Rules

1. **ALWAYS redirect output to `/tmp/` file.** Use: `> /tmp/workflow-ISSUE.log 2>&1 &` and `echo "PID: $!"`.
2. **NEVER use the TaskOutput tool to monitor workflows.** Use `cat /tmp/workflow-ISSUE.log` instead.
3. **One workflow at a time** unless explicitly told otherwise.
4. **Token discipline is paramount.** Diagnose before retrying.
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
    --issue {NUMBER} --repo /c/Users/mcwiz/Projects/{TARGET_REPO} --no-worktree \
    > /tmp/tdd-{NUMBER}.log 2>&1
```

## Monitoring

Tail logs and watch for: `[CIRCUIT]`, `[STAGNATION]`, `ERROR`, `FAILED`, tracebacks, >120s silence.

Two-strike rule applies per issue per phase.

Gemini down/blocked → stop, report, do not skip ahead.

## Done Criteria

- LLD: `docs/lld/active/LLD-{NUMBER}.md` exists with APPROVED verdict
- Impl Spec: spec exists under `docs/lld/drafts/` with Gemini APPROVED
- TDD: tests pass, no regressions

## Closing Issues

Use `Closes #{NUMBER}` in commit message body — never `gh issue close`.
After push, verify issues show CLOSED on GitHub.

## TDD Known Issues

- **Scaffold test syntax errors:** N2 sometimes generates scaffold tests with syntax errors. Delete `tests/test_issue_N.py` — real tests at `tests/unit/` work fine.
- **CLI_TIMEOUT is 600s.** Dynamic timeout via `compute_dynamic_timeout()` scales 300-600s based on prompt size.

## CLI Flags

Both workflow tools default to `--review none` (auto mode). The old `--gates` flag is a hidden deprecated alias.
