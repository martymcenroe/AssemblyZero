#!/bin/bash
# post-plan-write.sh — PostToolUse hook for Edit|Write.
#
# Fires on every Write/Edit to any file. Filters by path: if the
# edited file is under ~/.claude/plans/*.md (but NOT under plans-archive/),
# invokes unleashed/src/plan_archiver.py to archive with versioning.
#
# Contract:
# - Reads hook JSON from stdin (tool_input.file_path is the edited file).
# - Always exits 0 — hook failures must NEVER block the tool call.
# - The archiver runs in --from-hook mode: quiet, always exits 0, writes
#   status JSON to ~/.claude/plans-archive/.last-archive.json.
#
# Fixes: unleashed #275, #276
# Canonical source: AssemblyZero/.claude/hooks/post-plan-write.sh
# ADR: docs/adrs/0215-claude-hook-locations.md

set -u

PLAN_ARCHIVER="/c/Users/mcwiz/Projects/unleashed/src/plan_archiver.py"

# Read hook input from stdin. jq is available on the user's machine per
# CLAUDE.md install.sh. If jq is missing or the JSON is malformed, exit 0.
INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Nothing to do if jq failed or there's no file_path
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Normalize backslashes to forward slashes for bash path matching
NORMALIZED=${FILE_PATH//\\//}

# Match ~/.claude/plans/*.md but exclude plans-archive/*
case "$NORMALIZED" in
    */.claude/plans/*.md)
        ;;
    *)
        exit 0
        ;;
esac

# Explicitly exclude archive dir (shouldn't match above but be safe)
case "$NORMALIZED" in
    */.claude/plans-archive/*)
        exit 0
        ;;
esac

# Skip hidden files (e.g. .plan-status.json — though the glob above
# should not match it anyway)
BASENAME=$(basename "$NORMALIZED")
case "$BASENAME" in
    .*) exit 0 ;;
esac

# Extract slug: strip directory and .md extension
SLUG="${BASENAME%.md}"

# Skip if plan_archiver.py is missing (e.g. unleashed moved or not yet deployed)
if [ ! -f "$PLAN_ARCHIVER" ]; then
    exit 0
fi

# Invoke archiver in hook mode. Always exit 0.
python "$PLAN_ARCHIVER" archive --slug "$SLUG" --from-hook >/dev/null 2>&1 || true

exit 0
