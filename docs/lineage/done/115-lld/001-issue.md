# Issue #115: Auto-detect target repo from brief file path

## Problem

When running `run_issue_workflow.py` from the AgentOS directory with a brief located in another repo, the workflow defaults to filing the issue in the current working directory's repo instead of the repo containing the brief.

**Example:**
```bash
# Running from AgentOS directory
poetry run python tools/run_issue_workflow.py --brief /c/Users/mcwiz/Projects/RCA-PDF-extraction-pipeline/docs/briefs-temp/gfiat-fft-resampling.md --auto
```
This filed to `martymcenroe/AgentOS` instead of `martymcenroe/RCA-PDF-extraction-pipeline`.

## Proposed Solution

Infer the target repository from the brief file path by:
1. Walk up from the brief file path looking for a `.git` directory
2. Parse the git remote to determine the repo
3. Use this as the default instead of cwd

The `--repo` flag should still override this behavior.

## Workaround

Currently requires explicit `--repo` flag:
```bash
poetry run python tools/run_issue_workflow.py --brief /path/to/brief.md --repo /path/to/target/repo --auto
```

## Impact

Without this fix, issues can be filed to the wrong repository, requiring manual transfer via `gh issue transfer`.

---

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>