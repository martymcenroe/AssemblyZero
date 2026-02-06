#!/usr/bin/env bash
#
# test_batch_workflow.sh - TDD tests for batch-workflow.sh
#
# Run: bash tests/test_batch_workflow.sh
#

set -uo pipefail
# Note: not using -e because we need to capture failures

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTOS_ROOT="$(dirname "$SCRIPT_DIR")"
BATCH_SCRIPT="$AGENTOS_ROOT/tools/batch-workflow.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    echo -e "${GREEN}PASS${NC}: $1"
    ((TESTS_PASSED++))
    ((TESTS_RUN++))
}

fail() {
    echo -e "${RED}FAIL${NC}: $1"
    echo "  Expected: $2"
    echo "  Got:      $3"
    ((TESTS_FAILED++))
    ((TESTS_RUN++))
}

# Extract command from dry-run output
get_command() {
    local output="$1"
    echo "$output" | grep "DRY RUN - would execute:" | sed 's/.*would execute: //'
}

echo "=============================================="
echo "TDD Tests for batch-workflow.sh"
echo "=============================================="
echo ""

# ==========================================
# TEST CATEGORY 1: Workflow Type Mapping
# ==========================================
echo "--- Category 1: Workflow Type Mapping ---"

# Test 1.1: --type lld maps to run_requirements_workflow.py with --type lld
output=$("$BATCH_SCRIPT" --type lld --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"run_requirements_workflow.py"* ]] && [[ "$cmd" == *"--type lld"* ]]; then
    pass "1.1: --type lld uses run_requirements_workflow.py with --type lld"
else
    fail "1.1: --type lld uses run_requirements_workflow.py with --type lld" \
         "run_requirements_workflow.py --type lld" "$cmd"
fi

# Test 1.2: --type impl maps to run_implement_from_lld.py
output=$("$BATCH_SCRIPT" --type impl --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"run_implement_from_lld.py"* ]]; then
    pass "1.2: --type impl uses run_implement_from_lld.py"
else
    fail "1.2: --type impl uses run_implement_from_lld.py" \
         "run_implement_from_lld.py" "$cmd"
fi

# Test 1.3: --type issue maps to run_issue_workflow.py
output=$("$BATCH_SCRIPT" --type issue --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"run_issue_workflow.py"* ]]; then
    pass "1.3: --type issue uses run_issue_workflow.py"
else
    fail "1.3: --type issue uses run_issue_workflow.py" \
         "run_issue_workflow.py" "$cmd"
fi

echo ""

# ==========================================
# TEST CATEGORY 2: Gates Mapping for LLD
# Valid: draft,verdict | draft | verdict | none
# ==========================================
echo "--- Category 2: Gates Mapping for LLD workflow ---"

# Test 2.1: --gates none passes through as none
output=$("$BATCH_SCRIPT" --type lld --gates none --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"--gates none"* ]]; then
    pass "2.1: LLD --gates none -> --gates none"
else
    fail "2.1: LLD --gates none -> --gates none" "--gates none" "$cmd"
fi

# Test 2.2: --gates draft passes through as draft
output=$("$BATCH_SCRIPT" --type lld --gates draft --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"--gates draft"* ]]; then
    pass "2.2: LLD --gates draft -> --gates draft"
else
    fail "2.2: LLD --gates draft -> --gates draft" "--gates draft" "$cmd"
fi

# Test 2.3: --gates verdict passes through as verdict
output=$("$BATCH_SCRIPT" --type lld --gates verdict --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"--gates verdict"* ]]; then
    pass "2.3: LLD --gates verdict -> --gates verdict"
else
    fail "2.3: LLD --gates verdict -> --gates verdict" "--gates verdict" "$cmd"
fi

# Test 2.4: --gates all maps to draft,verdict for LLD
output=$("$BATCH_SCRIPT" --type lld --gates all --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"--gates draft,verdict"* ]]; then
    pass "2.4: LLD --gates all -> --gates draft,verdict"
else
    fail "2.4: LLD --gates all -> --gates draft,verdict" "--gates draft,verdict" "$cmd"
fi

# Test 2.5: Default gates (none specified) should be 'none' for unattended
output=$("$BATCH_SCRIPT" --type lld --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"--gates none"* ]]; then
    pass "2.5: LLD default gates -> --gates none"
else
    fail "2.5: LLD default gates -> --gates none" "--gates none" "$cmd"
fi

echo ""

# ==========================================
# TEST CATEGORY 3: Gates Mapping for IMPL
# Valid: none | draft | verdict | all
# ==========================================
echo "--- Category 3: Gates Mapping for IMPL workflow ---"

# Test 3.1: --gates none passes through
output=$("$BATCH_SCRIPT" --type impl --gates none --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"--gates none"* ]]; then
    pass "3.1: IMPL --gates none -> --gates none"
else
    fail "3.1: IMPL --gates none -> --gates none" "--gates none" "$cmd"
fi

# Test 3.2: --gates all passes through (valid for impl)
output=$("$BATCH_SCRIPT" --type impl --gates all --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"--gates all"* ]]; then
    pass "3.2: IMPL --gates all -> --gates all"
else
    fail "3.2: IMPL --gates all -> --gates all" "--gates all" "$cmd"
fi

echo ""

# ==========================================
# TEST CATEGORY 4: --yes Flag
# ==========================================
echo "--- Category 4: --yes Flag ---"

# Test 4.1: --yes is passed to LLD workflow
output=$("$BATCH_SCRIPT" --type lld --yes --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"--yes"* ]]; then
    pass "4.1: LLD --yes is passed through"
else
    fail "4.1: LLD --yes is passed through" "--yes in command" "$cmd"
fi

# Test 4.2: --yes is passed to IMPL workflow
output=$("$BATCH_SCRIPT" --type impl --yes --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"--yes"* ]]; then
    pass "4.2: IMPL --yes is passed through"
else
    fail "4.2: IMPL --yes is passed through" "--yes in command" "$cmd"
fi

# Test 4.3: Without --yes, command has no --yes
output=$("$BATCH_SCRIPT" --type lld --dry-run 123 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" != *"--yes"* ]]; then
    pass "4.3: Without --yes flag, command has no --yes"
else
    fail "4.3: Without --yes flag, command has no --yes" "no --yes" "$cmd"
fi

echo ""

# ==========================================
# TEST CATEGORY 5: Issue Number Handling
# ==========================================
echo "--- Category 5: Issue Number Handling ---"

# Test 5.1: Issue number in command
output=$("$BATCH_SCRIPT" --type lld --dry-run 277 2>&1)
cmd=$(get_command "$output")
if [[ "$cmd" == *"--issue 277"* ]]; then
    pass "5.1: Issue 277 -> --issue 277"
else
    fail "5.1: Issue 277 -> --issue 277" "--issue 277" "$cmd"
fi

# Test 5.2: Comma-separated issues are split
output=$("$BATCH_SCRIPT" --type lld --dry-run 100,101,102 2>&1)
count=$(echo "$output" | grep -c "DRY RUN - would execute:")
if [[ "$count" -eq 3 ]]; then
    pass "5.2: Comma-separated 100,101,102 produces 3 commands"
else
    fail "5.2: Comma-separated 100,101,102 produces 3 commands" "3 commands" "$count commands"
fi

echo ""

# ==========================================
# TEST CATEGORY 6: Invalid Input Handling
# ==========================================
echo "--- Category 6: Invalid Input Handling ---"

# Test 6.1: Missing --type should error
output=$("$BATCH_SCRIPT" --dry-run 123 2>&1) || true
if [[ "$output" == *"Missing required argument: --type"* ]]; then
    pass "6.1: Missing --type produces error"
else
    fail "6.1: Missing --type produces error" "Missing required argument" "$output"
fi

# Test 6.2: No issues should error
output=$("$BATCH_SCRIPT" --type lld --dry-run 2>&1) || true
if [[ "$output" == *"No issues specified"* ]]; then
    pass "6.2: No issues produces error"
else
    fail "6.2: No issues produces error" "No issues specified" "$output"
fi

# Test 6.3: Invalid gates value 'auto' should error
output=$("$BATCH_SCRIPT" --type lld --gates auto --dry-run 123 2>&1) || true
if [[ "$output" == *"Invalid gates"* ]] || [[ "$output" == *"Valid options"* ]]; then
    pass "6.3: Invalid gates 'auto' produces error"
else
    fail "6.3: Invalid gates 'auto' produces error" "Invalid gates error" "$output"
fi

# Test 6.4: Invalid gates value 'foo' should error
output=$("$BATCH_SCRIPT" --type lld --gates foo --dry-run 123 2>&1) || true
if [[ "$output" == *"Invalid gates"* ]] || [[ "$output" == *"Valid options"* ]]; then
    pass "6.4: Invalid gates 'foo' produces error"
else
    fail "6.4: Invalid gates 'foo' produces error" "Invalid gates error" "$output"
fi

echo ""

# ==========================================
# TEST CATEGORY 7: --all <label> Feature
# ==========================================
echo "--- Category 7: --all <label> Feature ---"

# Test 7.1: --all with label fetches issues from GitHub
output=$("$BATCH_SCRIPT" --type lld --all needs-lld --dry-run 2>&1) || true
# Should show fetching message and have at least one issue
if [[ "$output" == *"Fetching issues with label"* ]] && [[ "$output" == *"needs-lld"* ]]; then
    pass "7.1: --all needs-lld shows fetching message"
else
    fail "7.1: --all needs-lld shows fetching message" "Fetching issues with label 'needs-lld'" "$output"
fi

# Test 7.2: --all produces commands for multiple issues
output=$("$BATCH_SCRIPT" --type lld --all needs-lld --dry-run 2>&1) || true
count=$(echo "$output" | grep -c "DRY RUN - would execute:" || true)
if [[ "$count" -gt 1 ]]; then
    pass "7.2: --all needs-lld produces multiple commands ($count issues)"
else
    fail "7.2: --all needs-lld produces multiple commands" ">1 commands" "$count commands"
fi

# Test 7.3: --all without label should error
output=$("$BATCH_SCRIPT" --type lld --all --dry-run 2>&1) || true
if [[ "$output" == *"--all requires a label"* ]] || [[ "$output" == *"No issues"* ]] || [[ "$output" == *"Missing"* ]]; then
    pass "7.3: --all without label produces error"
else
    fail "7.3: --all without label produces error" "error message" "$output"
fi

# Test 7.4: --all with non-existent label should error gracefully
output=$("$BATCH_SCRIPT" --type lld --all nonexistent-label-xyz --dry-run 2>&1) || true
if [[ "$output" == *"No issues found"* ]] || [[ "$output" == *"No issues"* ]]; then
    pass "7.4: --all with non-existent label shows no issues found"
else
    fail "7.4: --all with non-existent label shows no issues found" "No issues found" "$output"
fi

# Test 7.5: Cannot use both --all and explicit issues
output=$("$BATCH_SCRIPT" --type lld --all needs-lld --dry-run 123 2>&1) || true
if [[ "$output" == *"Cannot use --all with explicit issue"* ]] || [[ "$output" == *"mutually exclusive"* ]]; then
    pass "7.5: --all and explicit issues are mutually exclusive"
else
    # Alternative: it might just ignore the explicit issues and use --all
    # Let's check if it worked with --all (acceptable behavior)
    if [[ "$output" == *"Fetching issues with label"* ]]; then
        pass "7.5: --all takes precedence over explicit issues (acceptable)"
    else
        fail "7.5: --all and explicit issues conflict handling" "error or --all precedence" "$output"
    fi
fi

echo ""

# ==========================================
# TEST CATEGORY 8: --repo Flag
# ==========================================
echo "--- Category 8: --repo Flag ---"

# Test 8.1: Default repo is auto-detected or uses AssemblyZero
output=$("$BATCH_SCRIPT" --type lld --dry-run 123 2>&1) || true
cmd=$(get_command "$output")
# Should work without --repo specified
if [[ "$output" == *"Starting lld workflow"* ]]; then
    pass "8.1: Works without explicit --repo"
else
    fail "8.1: Works without explicit --repo" "workflow starts" "$output"
fi

# Test 8.2: --repo is passed to underlying workflow
output=$("$BATCH_SCRIPT" --type lld --repo martymcenroe/OtherRepo --dry-run 123 2>&1) || true
cmd=$(get_command "$output")
if [[ "$cmd" == *"--repo martymcenroe/OtherRepo"* ]]; then
    pass "8.2: --repo is passed to underlying workflow"
else
    fail "8.2: --repo is passed to underlying workflow" "--repo martymcenroe/OtherRepo" "$cmd"
fi

# Test 8.3: --repo is used for --all label fetch (check message)
output=$("$BATCH_SCRIPT" --type lld --repo martymcenroe/OtherRepo --all needs-lld --dry-run 2>&1) || true
if [[ "$output" == *"martymcenroe/OtherRepo"* ]] || [[ "$output" == *"No issues found"* ]]; then
    pass "8.3: --repo is used when fetching issues with --all"
else
    fail "8.3: --repo is used when fetching issues with --all" "repo in output or no issues" "$output"
fi

echo ""

# ==========================================
# SUMMARY
# ==========================================
echo "=============================================="
echo "SUMMARY: $TESTS_PASSED/$TESTS_RUN passed"
if [[ $TESTS_FAILED -gt 0 ]]; then
    echo -e "${RED}$TESTS_FAILED TESTS FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}ALL TESTS PASSED${NC}"
    exit 0
fi
