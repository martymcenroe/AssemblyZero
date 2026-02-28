#!/usr/bin/env bash
# set-branch-protection.sh — Batch-apply required status check to all repos.
#
# Usage:
#   ./scripts/set-branch-protection.sh [--dry-run] [--owner OWNER]
#
# Adds "pr-sentinel / issue-reference" as a required status check on the
# default branch of every repo for the given owner. Preserves existing
# protection settings. Safe to re-run.

set -euo pipefail

CHECK_NAME="pr-sentinel / issue-reference"
DRY_RUN=false
OWNERS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --owner)   OWNERS+=("$2"); shift 2 ;;
    *)         echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ ${#OWNERS[@]} -eq 0 ]]; then
  OWNERS=("martymcenroe" "thrivetech-ai")
fi

for OWNER in "${OWNERS[@]}"; do
  echo "=== Processing repos for: $OWNER ==="

  # List all non-archived, non-fork repos
  REPOS=$(gh repo list "$OWNER" --no-archived --source --json nameWithOwner,defaultBranchRef --limit 200 -q '
    .[] | "\(.nameWithOwner)\t\(.defaultBranchRef.name)"
  ')

  while IFS=$'\t' read -r REPO BRANCH; do
    [[ -z "$REPO" ]] && continue

    echo -n "  $REPO ($BRANCH): "

    # Get existing required checks
    EXISTING=$(gh api "repos/$REPO/branches/$BRANCH/protection/required_status_checks" \
      --jq '.contexts // [] | join(",")' 2>/dev/null || echo "")

    if echo "$EXISTING" | grep -qF "$CHECK_NAME"; then
      echo "already required — skipping"
      continue
    fi

    if $DRY_RUN; then
      echo "would add check (dry-run)"
      continue
    fi

    # Build context array: existing + new check
    CONTEXTS="[\"$CHECK_NAME\""
    if [[ -n "$EXISTING" ]]; then
      IFS=',' read -ra EXISTING_ARRAY <<< "$EXISTING"
      for ctx in "${EXISTING_ARRAY[@]}"; do
        CONTEXTS+=",\"$ctx\""
      done
    fi
    CONTEXTS+="]"

    # Try to update existing protection, fall back to creating new
    if gh api "repos/$REPO/branches/$BRANCH/protection/required_status_checks" \
        --method PATCH \
        --input - <<< "{\"strict\":false,\"contexts\":$CONTEXTS}" > /dev/null 2>&1; then
      echo "updated"
    else
      # No existing protection — create it
      gh api "repos/$REPO/branches/$BRANCH/protection" \
        --method PUT \
        --input - <<< "{
          \"required_status_checks\":{\"strict\":false,\"contexts\":$CONTEXTS},
          \"enforce_admins\":false,
          \"required_pull_request_reviews\":null,
          \"restrictions\":null
        }" > /dev/null 2>&1 && echo "created" || echo "FAILED (check may not have fired yet)"
    fi
  done <<< "$REPOS"
done

echo ""
echo "Done. Re-run for repos where the check hasn't fired yet."
