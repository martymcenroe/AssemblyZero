# Issue #148: fix: Cross-repo workflow invocation broken by poetry --directory

## Problem

When running the requirements workflow from a different project using `poetry run --directory`, the tool fails to detect the correct target repo.

**Reproduction:**
```bash
# From Aletheia directory
cd ~/Projects/Aletheia
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/run_requirements_workflow.py --type lld --issue 341 --gates none
```

**Error:**
```
[N0] Loading input (lld workflow)...
    ERROR: Issue #341 not found: GraphQL: Could not resolve to an issue or pull request with the number of 341. (repository.issue)
```

Issue #341 exists in Aletheia but the tool queries AgentOS instead.

## Root Cause

Poetry's `--directory` flag changes the working directory BEFORE running Python:

> The --directory (-C) option to change the working directory before executing any command.

So when `run_requirements_workflow.py` runs:
```python
result = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"],
    capture_output=True,
    text=True,
    timeout=10,
)  # No cwd specified!
```

The git command runs from AgentOS (poetry's --directory), not Aletheia (the user's original cwd).

## Current Workaround

Pass `--repo` explicitly:
```bash
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/run_requirements_workflow.py --type lld --issue 341 --gates none --repo /c/Users/mcwiz/Projects/Aletheia
```

## Proposed Solutions

### Option A: Capture original cwd via environment variable
Have the shell alias/function set `AGENTOS_TARGET_REPO=$PWD` before calling poetry.

### Option B: Wrapper script
Create a wrapper that captures cwd then invokes poetry:
```bash
#!/bin/bash
ORIGINAL_CWD=$(pwd)
poetry run --directory /c/Users/mcwiz/Projects/AgentOS python /c/Users/mcwiz/Projects/AgentOS/tools/run_requirements_workflow.py "$@" --repo "$ORIGINAL_CWD"
```

### Option C: Document the limitation
Update docs to always require `--repo` when running cross-repo.

## Affected Code

- `tools/run_requirements_workflow.py` lines 182-195 (`resolve_roots` function)
- `agentos/workflows/requirements/nodes/load_input.py` line 165 (uses `cwd=str(target_repo)`)

## Labels
bug, workflow, cross-repo