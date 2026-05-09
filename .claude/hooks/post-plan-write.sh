#!/bin/bash
# post-plan-write.sh — PostToolUse hook for Edit|Write.
#
# Fires on every Write/Edit to any file. Filters by path: if the
# edited file is under ~/.claude/plans/*.md (but NOT already under a
# project subdir), relocates the file to ~/.claude/plans/<project>/*.md
# and invokes unleashed/src/plan_archiver.py to archive with versioning.
#
# #310: per-project plan storage. The relocation step is what physically
# scopes plans by project. After this hook runs, /handoff and /onboard
# only ever see plans inside the current project's subdir.
#
# Contract:
# - Reads hook JSON from stdin (cwd, tool_input.file_path).
# - Project derived from cwd (`git rev-parse --show-toplevel | basename`).
# - Always exits 0 — hook failures must NEVER block the tool call.
# - Skips already-migrated files (path already under plans/<project>/).
#
# Fixes: unleashed #275, #276, #310
# Canonical source: AssemblyZero/.claude/hooks/post-plan-write.sh
# ADR: docs/adrs/0215-claude-hook-locations.md

set -u

PLAN_ARCHIVER="/c/Users/mcwiz/Projects/unleashed/src/plan_archiver.py"

# Read hook input from stdin.
INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
HOOK_CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)

# Nothing to do if jq failed or there's no file_path.
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Normalize backslashes for bash path matching.
NORMALIZED=${FILE_PATH//\\//}

# Must be under ~/.claude/plans/.
case "$NORMALIZED" in
    */.claude/plans/*.md)
        ;;
    *)
        exit 0
        ;;
esac

# Explicitly exclude archive dir.
case "$NORMALIZED" in
    */.claude/plans-archive/*)
        exit 0
        ;;
esac

# Skip hidden files.
BASENAME=$(basename "$NORMALIZED")
case "$BASENAME" in
    .*) exit 0 ;;
esac

# Already under a project subdir? Pattern: .../plans/<project>/<slug>.md
# where <project> is one path component before the final .md file. We
# detect this by checking whether there's another component between
# ".claude/plans/" and the basename.
case "$NORMALIZED" in
    */.claude/plans/*/*.md)
        ALREADY_MIGRATED=1
        ;;
    *)
        ALREADY_MIGRATED=0
        ;;
esac

# Strip .md to get the slug.
SLUG="${BASENAME%.md}"

# Determine project: prefer git toplevel of HOOK_CWD; fall back to basename.
PROJECT=""
if [ -n "$HOOK_CWD" ]; then
    if PROJECT_PATH=$(git -C "$HOOK_CWD" rev-parse --show-toplevel 2>/dev/null); then
        PROJECT=$(basename "$PROJECT_PATH")
    else
        PROJECT=$(basename "$HOOK_CWD")
    fi
fi
# Fallback to current $PWD if hook input had no cwd.
if [ -z "$PROJECT" ]; then
    if PROJECT_PATH=$(git rev-parse --show-toplevel 2>/dev/null); then
        PROJECT=$(basename "$PROJECT_PATH")
    fi
fi

# If we still couldn't figure out a project, do nothing — better to leave
# the file at root for the migration script to sort than to invent a name.
if [ -z "$PROJECT" ]; then
    exit 0
fi

# Relocate the new plan into its project subdir (if not already there).
if [ "$ALREADY_MIGRATED" = "0" ]; then
    PROJECT_DIR=$(dirname "$NORMALIZED")/$PROJECT
    mkdir -p "$PROJECT_DIR" 2>/dev/null || true
    NEW_PATH="$PROJECT_DIR/$BASENAME"
    # Atomic rename — best-effort. Failure is non-fatal.
    mv -f "$NORMALIZED" "$NEW_PATH" 2>/dev/null || true
fi

# Skip if plan_archiver.py is missing.
if [ ! -f "$PLAN_ARCHIVER" ]; then
    exit 0
fi

# Invoke archiver in hook mode with --project. Always exit 0.
python "$PLAN_ARCHIVER" archive --slug "$SLUG" --project "$PROJECT" --from-hook >/dev/null 2>&1 || true

exit 0
