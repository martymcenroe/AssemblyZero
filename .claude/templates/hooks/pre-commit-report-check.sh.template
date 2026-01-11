#!/bin/bash
# Pre-Commit Hook: Enforce Report Existence (PRE-COMMIT GATE)
#
# BLOCK: git commit on feature branches without reports
# ALLOW: commits on main (documentation only), commits with existing reports
#
# Environment: $CLAUDE_TOOL_INPUT_COMMAND contains the bash command

set -e

command="$CLAUDE_TOOL_INPUT_COMMAND"

# Only check git commit commands
if [[ ! "$command" =~ ^git[[:space:]]+commit ]]; then
    exit 0
fi

# Get current branch
branch=$(git branch --show-current 2>/dev/null || echo "unknown")

# On main branch, allow all commits (docs only per worktree isolation)
if [ "$branch" = "main" ]; then
    exit 0
fi

# Extract issue ID from branch name (format: {ID}-description)
issue_id=$(echo "$branch" | grep -oE '^[0-9]+' || echo "")

if [ -z "$issue_id" ]; then
    echo "" >&2
    echo "WARNING: Branch name doesn't start with issue ID" >&2
    echo "Branch: $branch" >&2
    echo "Expected format: {IssueID}-description (e.g., 45-feature-name)" >&2
    echo "" >&2
    echo "Allowing commit, but please follow naming conventions." >&2
    exit 0
fi

# Check if reports exist
report_dir="docs/reports/$issue_id"
impl_report="$report_dir/implementation-report.md"
test_report="$report_dir/test-report.md"

missing=""

if [ ! -f "$impl_report" ]; then
    missing="$missing\n  - $impl_report"
fi

if [ ! -f "$test_report" ]; then
    missing="$missing\n  - $test_report"
fi

if [ -n "$missing" ]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Missing reports for issue #$issue_id" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "PRE-COMMIT GATE requires these reports before commit:" >&2
    echo -e "$missing" >&2
    echo "" >&2
    echo "Create reports first:" >&2
    echo "  docs/reports/$issue_id/implementation-report.md" >&2
    echo "  docs/reports/$issue_id/test-report.md" >&2
    echo "" >&2
    echo "See CLAUDE.md § 'PRE-COMMIT GATE' for requirements." >&2
    echo "" >&2
    exit 1
fi

# Reports exist, allow commit
exit 0
