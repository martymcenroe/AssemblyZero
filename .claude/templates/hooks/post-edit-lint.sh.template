#!/bin/bash
# Post-Edit Hook: Active Security Linting
#
# Runs linters IMMEDIATELY after file edits, not at pre-commit.
# This creates a tight feedback loop where the AI fixes errors
# before moving to the next file.
#
# Environment: $CLAUDE_TOOL_INPUT_FILE_PATH contains the edited file path

file="$CLAUDE_TOOL_INPUT_FILE_PATH"

# Skip if file doesn't exist (was deleted)
if [ ! -f "$file" ]; then
    exit 0
fi

# JavaScript/TypeScript files: Run ESLint with security plugins
case "$file" in
    *.js|*.jsx|*.mjs|*.cjs)
        echo "[Hook] Running ESLint on: $file" >&2
        npx eslint "$file" --config eslint.config.mjs
        exit_code=$?
        if [ $exit_code -ne 0 ]; then
            echo "" >&2
            echo "[Hook] ESLint FAILED. Fix the issues above before continuing." >&2
        fi
        exit $exit_code
        ;;
    *.ts|*.tsx)
        echo "[Hook] Running ESLint on: $file" >&2
        npx eslint "$file" --config eslint.config.mjs
        exit_code=$?
        if [ $exit_code -ne 0 ]; then
            echo "" >&2
            echo "[Hook] ESLint FAILED. Fix the issues above before continuing." >&2
        fi
        exit $exit_code
        ;;
esac

# Python files: Run Ruff with Bandit rules
case "$file" in
    *.py)
        echo "[Hook] Running Ruff on: $file" >&2
        poetry run ruff check "$file"
        exit_code=$?
        if [ $exit_code -ne 0 ]; then
            echo "" >&2
            echo "[Hook] Ruff FAILED. Fix the issues above before continuing." >&2
        fi
        exit $exit_code
        ;;
esac

# Other file types: No lint needed
exit 0
