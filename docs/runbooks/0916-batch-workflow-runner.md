# 0916 - Batch Workflow Runner

## Purpose

Run AssemblyZero workflows on multiple issues sequentially without manual intervention. Designed for unattended operation - start it and walk away.

## Quick Reference

```bash
# Run LLD workflow on ALL issues with needs-lld label
batch-workflow --type lld --gates none --yes --all needs-lld

# Run implementation workflow on issues 272, 273, 274
batch-workflow --type impl --gates none 272 273 274

# Run LLD workflow on comma-separated issues
batch-workflow --type lld --gates none 100,101,102

# Run with continue even if some fail
batch-workflow --type impl --gates none --continue-on-fail 50 51 52

# Cross-repo: run for a different repository
batch-workflow --type lld --gates none --yes --repo martymcenroe/Aletheia --all needs-lld

# Dry run - see what would execute
batch-workflow --type lld --all needs-lld --dry-run
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--type <type>` | Workflow type (required): `issue`, `lld`, `impl` | - |
| `--gates <mode>` | Gate mode: `none`, `draft`, `verdict`, `all` | `none` |
| `--yes` | Auto-approve prompts (e.g., LLD regeneration) | off |
| `--continue-on-fail` | Continue to next issue if one fails | off |
| `--all <label>` | Fetch all open issues with this GitHub label | - |
| `--repo <owner/repo>` | GitHub repo for `--all` and workflow commands | auto-detect |
| `--dry-run` | Show commands without executing | off |
| `--help` | Show help | - |

**Gates values:**
- `none` - No human gates, fully automated
- `draft` - Stop for review after draft
- `verdict` - Stop for review after verdict
- `all` - All gates (mapped to `draft,verdict` for LLD workflow)

## Workflow Types

| Type | Script | Description |
|------|--------|-------------|
| `issue` | `run_issue_workflow.py` | Create issue from description |
| `lld` | `run_requirements_workflow.py` | Generate LLD from issue |
| `impl` | `run_implement_from_lld.py` | TDD implementation from LLD |

## Input Formats

Issues can be specified in multiple ways:

```bash
# Space-separated
batch-workflow --type impl 272 273 274

# Comma-separated
batch-workflow --type impl 272,273,274

# Mixed
batch-workflow --type impl 272,273 274 275,276

# Auto-fetch by label
batch-workflow --type lld --all needs-lld
```

## Cross-Repo Usage

By default, `--repo` is auto-detected from the git remote. To run workflows for a different repository:

```bash
# Run LLD workflow for Aletheia issues (from AssemblyZero directory)
batch-workflow --type lld --gates none --yes --repo martymcenroe/Aletheia --all needs-lld

# Run implementation for specific Talos issues
batch-workflow --type impl --gates none --repo martymcenroe/Talos 10,11,12

# Dry run to verify correct repo
batch-workflow --type lld --repo martymcenroe/Aletheia --all needs-lld --dry-run
```

The `--repo` flag affects:
- Issue fetching with `--all <label>`
- The `--repo` argument passed to underlying workflow scripts

## Output

### Console

Progress is displayed in real-time with colored status indicators:
- Green checkmark: Success
- Red X: Failed
- Yellow circle: Skipped (dry run)

### Logs

All output is logged to `$AGENTOS_ROOT/logs/batch/`:

```
logs/batch/
├── 20260204_143022_impl_272.log    # Individual issue logs
├── 20260204_143022_impl_273.log
├── 20260204_143022_impl_274.log
└── 20260204_143022_summary.txt     # Batch summary
```

### Summary

At completion, a summary shows:
- Total duration
- Pass/fail counts
- Per-issue status
- Path to summary file

## Recommended Patterns

### Full Pipeline (Unattended)

Run the complete pipeline for all issues with a label:

```bash
# 1. Generate LLDs for all issues needing them
batch-workflow --type lld --gates none --yes --continue-on-fail --all needs-lld

# 2. Implement all LLDs (would need a different label or explicit list)
batch-workflow --type impl --gates none --continue-on-fail 50 51 52 53 54
```

### Safe Mode (Stop on First Failure)

For critical work where you want to inspect failures:

```bash
batch-workflow --type impl --gates none 272 273 274
# Stops at first failure
```

### Maximum Automation

For overnight runs with maximum automation:

```bash
batch-workflow --type lld --gates none --yes --continue-on-fail --all needs-lld
```

### Dry Run Before Committing

Always preview what will run:

```bash
batch-workflow --type impl --dry-run 50 51 52
# Shows commands without executing
```

## Troubleshooting

### "No issues specified"

Ensure issues are provided after options:
```bash
# Wrong
batch-workflow 272 273 --type impl

# Correct
batch-workflow --type impl 272 273
```

### "Unknown workflow type"

Valid types are: `issue`, `lld`, `impl` (or `requirements`, `implementation`)

### Workflow Hangs

Individual workflow timeouts are handled by the workflow scripts themselves. If a workflow appears hung:
1. Check the log file in `logs/batch/`
2. Consider using `--gates none` to skip interactive gates

### API Rate Limits

For large batches, consider:
- Running during off-peak hours
- Using `--continue-on-fail` to handle transient failures
- Checking logs for rate limit errors

## Installation

The script is at `tools/batch-workflow.sh`. The alias is in `~/.bash_profile`:

```bash
alias batch-workflow='/c/Users/mcwiz/Projects/AssemblyZero/tools/batch-workflow.sh'
```

After editing `.bash_profile`, reload:
```bash
source ~/.bash_profile
```

## Related

- [0907 - Unified Requirements Workflow](0907-unified-requirements-workflow.md)
- [0909 - TDD Implementation Workflow](0909-tdd-implementation-workflow.md)
- [0904 - Issue Governance Workflow](0904-issue-governance-workflow.md)
