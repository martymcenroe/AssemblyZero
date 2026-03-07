#!/bin/bash
# Bash Command Gate Hook
#
# BLOCK: Bash commands containing banned patterns (&&, |, ;)
# These patterns trigger permission approval dialogs.
#
# When blocked, outputs a SUGGESTED FIX that Claude should use to retry.
#
# Environment: $CLAUDE_TOOL_INPUT_COMMAND contains the bash command

set -e

command="$CLAUDE_TOOL_INPUT_COMMAND"

# Skip empty commands
if [ -z "$command" ]; then
    exit 0
fi

violations=""
suggested_fix=""

# Check for cd at start followed by && (common pattern: cd /path && git ...)
if [[ "$command" =~ ^cd[[:space:]]+([^[:space:]&]+)[[:space:]]*\&\&[[:space:]]*git[[:space:]]+(.*) ]]; then
    path="${BASH_REMATCH[1]}"
    git_args="${BASH_REMATCH[2]}"
    violations="${violations}
  - Pattern: cd /path && git ...
    Issue: Chain operator triggers permission dialogs"
    suggested_fix="git -C $path $git_args"
fi

# Check for cd at start followed by && (other commands)
if [[ -z "$suggested_fix" ]] && [[ "$command" =~ ^cd[[:space:]]+([^[:space:]&]+)[[:space:]]*\&\&[[:space:]]+(.*) ]]; then
    path="${BASH_REMATCH[1]}"
    rest="${BASH_REMATCH[2]}"
    violations="${violations}
  - Pattern: cd /path && command
    Issue: Chain operator triggers permission dialogs"
    # Can't auto-fix non-git, but suggest the pattern
    suggested_fix="[Run command with absolute path: $path/... or use working directory]"
fi

# Check for && (chain operator) - generic
if [[ -z "$suggested_fix" ]] && [[ "$command" == *"&&"* ]]; then
    violations="${violations}
  - Found: &&
    Issue: Chain operator triggers permission dialogs
    Fix: Split into separate Bash calls"
    # Split suggestion
    IFS='&&' read -ra parts <<< "$command"
    suggested_fix="[SPLIT INTO PARALLEL BASH CALLS:]"
    for part in "${parts[@]}"; do
        trimmed=$(echo "$part" | xargs)
        if [ -n "$trimmed" ]; then
            suggested_fix="${suggested_fix}
  Bash call: $trimmed"
        fi
    done
fi

# Check for | (pipe) with common patterns
if [[ "$command" =~ (.+)\|[[:space:]]*(head|tail|grep|wc|sort) ]]; then
    base_cmd="${BASH_REMATCH[1]}"
    pipe_to="${BASH_REMATCH[2]}"
    violations="${violations}
  - Found: | $pipe_to
    Issue: Pipe operator triggers permission dialogs"
    case "$pipe_to" in
        head|tail)
            suggested_fix="[USE Read TOOL instead with limit/offset parameters]"
            ;;
        grep)
            suggested_fix="[USE Grep TOOL instead of piping to grep]"
            ;;
        *)
            suggested_fix="[USE dedicated tool or split into steps]"
            ;;
    esac
elif [[ "$command" == *"|"* ]]; then
    violations="${violations}
  - Found: |
    Issue: Pipe operator triggers permission dialogs"
    suggested_fix="[USE dedicated tools: Read (not cat|head|tail), Grep (not grep), Glob (not find|ls)]"
fi

# Check for ; (command separator)
if [[ -z "$suggested_fix" ]] && [[ "$command" == *";"* ]]; then
    violations="${violations}
  - Found: ;
    Issue: Command separator triggers permission dialogs"
    IFS=';' read -ra parts <<< "$command"
    suggested_fix="[SPLIT INTO PARALLEL BASH CALLS:]"
    for part in "${parts[@]}"; do
        trimmed=$(echo "$part" | xargs)
        if [ -n "$trimmed" ]; then
            suggested_fix="${suggested_fix}
  Bash call: $trimmed"
        fi
    done
fi

# Check for cd at start without && (standalone cd)
if [[ -z "$violations" ]] && [[ "$command" =~ ^cd[[:space:]] ]]; then
    violations="${violations}
  - Found: cd at start
    Issue: Directory change should use absolute paths or git -C"
    suggested_fix="[USE absolute paths or git -C /path instead]"
fi

# ---------------------------------------------------------------------------
# Destructive git operations (require explicit user approval)
# ---------------------------------------------------------------------------

# git push --force or --force-with-lease (any position in args)
if [[ "$command" =~ git[[:space:]].*push[[:space:]] ]] &&
   [[ "$command" =~ --force(-with-lease)?([[:space:]]|$) ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Destructive Git Operation" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "Force-push rewrites remote history." >&2
    echo "Ask the user for explicit approval before force-pushing." >&2
    echo "" >&2
    exit 1
fi

# git reset --hard
if [[ "$command" =~ git[[:space:]].*reset[[:space:]] ]] &&
   [[ "$command" =~ --hard([[:space:]]|$) ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Destructive Git Operation" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "git reset --hard destroys uncommitted work." >&2
    echo "Use 'git stash' or 'git revert' instead." >&2
    echo "If you truly need --hard, ask the user for explicit approval." >&2
    echo "" >&2
    exit 1
fi

# git branch -D (force delete)
if [[ "$command" =~ git[[:space:]].*branch[[:space:]] ]] &&
   [[ "$command" =~ [[:space:]]-D([[:space:]]|$) ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Destructive Git Operation" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "git branch -D force-deletes without merge check." >&2
    echo "Use 'git branch -d' (safe delete) instead." >&2
    echo "If the branch is truly unmerged and disposable, ask the user." >&2
    echo "" >&2
    exit 1
fi

# git clean -f (force clean untracked files)
if [[ "$command" =~ git[[:space:]].*clean[[:space:]] ]] &&
   [[ "$command" =~ -[a-zA-Z]*f ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Destructive Git Operation" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "git clean -f permanently deletes untracked files." >&2
    echo "Use 'git clean -n' (dry run) first, then ask the user." >&2
    echo "" >&2
    exit 1
fi

# If violations found, block the command and suggest fix
if [ -n "$violations" ]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Bash Command Gate Violation" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "Violations:$violations" >&2
    echo "" >&2

    if [ -n "$suggested_fix" ]; then
        echo "----------------------------------------" >&2
        echo "RETRY WITH:" >&2
        echo "$suggested_fix" >&2
        echo "----------------------------------------" >&2
        echo "" >&2
    fi

    echo "ACTION REQUIRED: Rewrite command and retry." >&2
    echo "DO NOT STOP. Fix the command and try again." >&2
    echo "" >&2
    exit 1
fi

# No violations, allow command
exit 0
