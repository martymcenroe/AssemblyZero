#!/bin/bash
# Secret File Guard Hook (Read/Write/Edit)
#
# BLOCK: Read, Write, and Edit tool calls targeting secret files.
#
# The Bash secret-guard.sh only covers shell commands. Agents bypass it by
# using Read() to inspect secrets or Write() to render them in the permission
# prompt (the leak happens at prompt-render time, before user approval).
#
# Input: hook JSON on stdin; field depends on the tool (see below)
# Matched tools: Read, Write, Edit (via settings.json PreToolUse matchers)
#
# Incident: 2026-03-09 — career agent wrote API key via Write(.dev.vars),
# exposing it in the permission prompt and session transcript.

set -e

# Grep uses .tool_input.path; Read/Write/Edit use .tool_input.file_path
# Input arrives as JSON on stdin. It used to arrive in CLAUDE_TOOL_INPUT_*, which
# the harness no longer sets -- so this hook received an empty string, hit the
# guard below, and exited 0 while the config still read as protected (#301).
# Read stdin ONCE: a second `cat` in the same process gets nothing.
_hook_json=$(cat)
file_path=$(printf '%s' "$_hook_json" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
if [ -z "$file_path" ]; then
    file_path=$(printf '%s' "$_hook_json" | jq -r '.tool_input.path // empty' 2>/dev/null)
fi

# Skip empty paths
if [ -z "$file_path" ]; then
    exit 0
fi

# Normalize: extract just the filename (handle both Windows and Unix paths)
filename=$(basename "$file_path")

# Also get the full path lowercased for pattern matching
file_path_lower=$(echo "$file_path" | tr '[:upper:]' '[:lower:]')

# ---------------------------------------------------------------------------
# Pattern 1: Secret dotfiles (.env, .env.*, .dev.vars)
# ---------------------------------------------------------------------------
if [[ "$filename" == ".env" ]] ||
   [[ "$filename" =~ ^\.env\. ]] ||
   [[ "$filename" == ".dev.vars" ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret File Guard" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $CLAUDE_TOOL_NAME($file_path)" >&2
    echo "" >&2
    echo "Secret files (.env, .env.*, .dev.vars) must never be read," >&2
    echo "written, or edited by Claude — session transcripts and" >&2
    echo "permission prompts capture content in plaintext." >&2
    echo "" >&2
    echo "For Write: the secret is leaked the moment the permission" >&2
    echo "prompt renders, BEFORE the user can approve or deny." >&2
    echo "" >&2
    echo "To update secrets: tell the user to run the command in their" >&2
    echo "own terminal, or use a deployment script that reads from env." >&2
    echo "" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Pattern 2: AWS credentials
# ---------------------------------------------------------------------------
if [[ "$file_path_lower" =~ \.aws/(credentials|config) ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret File Guard" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $CLAUDE_TOOL_NAME($file_path)" >&2
    echo "" >&2
    echo "AWS credential files must never be accessed by Claude." >&2
    echo "Use boto3 or os.environ.get() in Python instead." >&2
    echo "" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Pattern 3: Files with secret/credential/token in the name
# ---------------------------------------------------------------------------
filename_lower=$(echo "$filename" | tr '[:upper:]' '[:lower:]')
if [[ "$filename_lower" =~ secret ]] ||
   [[ "$filename_lower" =~ credential ]] ||
   [[ "$filename_lower" =~ private.key ]] ||
   [[ "$filename_lower" =~ \.pem$ ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret File Guard" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $CLAUDE_TOOL_NAME($file_path)" >&2
    echo "" >&2
    echo "Files with 'secret', 'credential', or 'private.key' in the name" >&2
    echo "are presumed to contain sensitive material." >&2
    echo "" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Pattern 4: Grep glob targeting secret files
# Issue #714 bypass #14: Grep(path=".dev.vars") or Grep(glob=".env*")
# ---------------------------------------------------------------------------
grep_glob=$(printf '%s' "$_hook_json" | jq -r '.tool_input.glob // empty' 2>/dev/null)
if [ -n "$grep_glob" ]; then
    grep_glob_lower=$(printf '%s' "$grep_glob" | tr '[:upper:]' '[:lower:]')
    if [[ "$grep_glob_lower" =~ \.env ]] ||
       [[ "$grep_glob_lower" =~ \.dev\.vars ]] ||
       [[ "$grep_glob_lower" =~ \.dev\. ]]; then
        echo "" >&2
        echo "========================================" >&2
        echo "BLOCKED: Secret File Guard" >&2
        echo "========================================" >&2
        echo "" >&2
        echo "REJECTED: $CLAUDE_TOOL_NAME(glob=$grep_glob)" >&2
        echo "" >&2
        echo "Grep glob pattern targets secret files." >&2
        echo "" >&2
        exit 2
    fi
fi

# No violations, allow tool call
exit 0
