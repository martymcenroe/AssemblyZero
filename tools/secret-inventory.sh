#!/bin/bash
# Secret Inventory Tool
#
# PURPOSE: Find all secret-containing files in ~/Projects/
# SAFETY:  Outputs FILE PATHS ONLY — never prints secret values.
#
# IMPORTANT: This script must be run by the HUMAN in their own terminal.
# An AI agent must NEVER execute this script — file paths in the output
# reveal the attack surface, and any bugs could leak secret values into
# an agent's session transcript.
#
# Usage:
#   chmod +x tools/secret-inventory.sh
#   ./tools/secret-inventory.sh > docs/security/secret-inventory.md
#
# The output is a markdown-formatted inventory suitable for committing
# (it contains NO secret values, only paths and metadata).

set -euo pipefail

PROJECTS_DIR="$HOME/Projects"
DIVIDER="---"

# Ensure we never accidentally search dangerous directories
EXCLUDE_DIRS=(
    "$HOME/OneDrive"
    "$HOME/AppData"
    "$HOME/.aws"  # Credentials dir — skip content search, just note existence
    "node_modules"
    ".git"
    "__pycache__"
    ".venv"
    "venv"
)

build_exclude_args() {
    local args=""
    for dir in "${EXCLUDE_DIRS[@]}"; do
        args="$args --exclude-dir=$dir"
    done
    echo "$args"
}

build_find_excludes() {
    local args=""
    for dir in "${EXCLUDE_DIRS[@]}"; do
        args="$args -not -path */$dir/*"
    done
    echo "$args"
}

echo "# Secret File Inventory"
echo ""
echo "Generated: $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "Scope: $PROJECTS_DIR"
echo ""
echo "## 1. Files Matching Secret Name Patterns"
echo ""
echo "| Path | Pattern | Gitignored |"
echo "|------|---------|------------|"

# Filename patterns that indicate secrets
FILE_PATTERNS=(
    "*.env"
    ".env.*"
    "*.dev.vars"
    "*.vars"
    "*credentials*"
    "*secret*"
    "*.pem"
    "*.key"
)

check_gitignored() {
    local filepath="$1"
    local dir
    dir=$(dirname "$filepath")

    # Walk up to find a git repo
    local check_dir="$dir"
    while [ "$check_dir" != "/" ] && [ "$check_dir" != "$HOME" ]; do
        if [ -d "$check_dir/.git" ]; then
            cd "$check_dir"
            if git check-ignore -q "$filepath" 2>/dev/null; then
                echo "Yes"
            else
                echo "**NO**"
            fi
            return
        fi
        check_dir=$(dirname "$check_dir")
    done
    echo "N/A (no repo)"
}

for pattern in "${FILE_PATTERNS[@]}"; do
    # Use find to locate files matching the pattern, excluding dangerous dirs
    while IFS= read -r filepath; do
        [ -z "$filepath" ] && continue
        # Skip node_modules, .git, etc.
        case "$filepath" in
            */node_modules/*|*/.git/*|*/__pycache__/*|*/.venv/*|*/venv/*) continue ;;
        esac
        gitignored=$(check_gitignored "$filepath")
        echo "| \`$filepath\` | \`$pattern\` | $gitignored |"
    done < <(find "$PROJECTS_DIR" -name "$pattern" -type f 2>/dev/null)
done

echo ""
echo "$DIVIDER"
echo ""
echo "## 2. Files Containing Token Patterns (paths only)"
echo ""
echo "Searched for: \`ghp_\`, \`github_pat_\`, \`sk-\`, \`AKIA\`, \`aws_secret_access_key\`, \`aws_access_key_id\`"
echo ""
echo "| Path | Matched Pattern |"
echo "|------|-----------------|"

# Content patterns — search for TOKEN PREFIXES only, output file paths only
TOKEN_PATTERNS=(
    "ghp_"
    "github_pat_"
    "sk-"
    "AKIA"
    "aws_secret_access_key"
    "aws_access_key_id"
)

for pattern in "${TOKEN_PATTERNS[@]}"; do
    while IFS= read -r filepath; do
        [ -z "$filepath" ] && continue
        case "$filepath" in
            */node_modules/*|*/.git/*|*/__pycache__/*|*/.venv/*|*/venv/*) continue ;;
            *.md) continue ;;  # Skip documentation (contains examples, not real secrets)
        esac
        echo "| \`$filepath\` | \`$pattern\` |"
    done < <(grep -rl --include='*' --exclude-dir=node_modules --exclude-dir=.git \
        --exclude-dir=__pycache__ --exclude-dir=.venv --exclude-dir=venv \
        --exclude='*.md' \
        "$pattern" "$PROJECTS_DIR" 2>/dev/null || true)
done

echo ""
echo "$DIVIDER"
echo ""
echo "## 3. AWS Credentials Check"
echo ""
if [ -f "$HOME/.aws/credentials" ]; then
    echo "- \`~/.aws/credentials\` exists (DO NOT cat this file)"
else
    echo "- \`~/.aws/credentials\` not found"
fi
if [ -f "$HOME/.aws/config" ]; then
    echo "- \`~/.aws/config\` exists"
else
    echo "- \`~/.aws/config\` not found"
fi

echo ""
echo "$DIVIDER"
echo ""
echo "## 4. Remediation Checklist"
echo ""
echo "For each finding above:"
echo "- [ ] Verify the file is in \`.gitignore\`"
echo "- [ ] Check git history: \`git log --all --full-history -- <path>\`"
echo "- [ ] If found in git history: rotate the secret immediately"
echo "- [ ] Add path to agent prohibition lists (CLAUDE.md, GEMINI.md, CHATGPT.md)"
echo "- [ ] Consider moving to a secrets manager (AWS SSM, 1Password CLI)"
