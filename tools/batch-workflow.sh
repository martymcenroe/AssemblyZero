#!/usr/bin/env bash
#
# batch-workflow.sh - Run AssemblyZero workflows on multiple issues sequentially
#
# Usage: batch-workflow --type <issue|lld|impl> [options] <issues>
#
# Examples:
#   batch-workflow --type impl 272 273 274
#   batch-workflow --type lld --gates auto 100,101,102
#   batch-workflow --type issue --yes --continue-on-fail 50 51 52
#
# Options:
#   --type <type>       Workflow type: issue, lld, impl (required)
#   --gates <mode>      Gate mode: none, draft, verdict, all (default: none)
#   --yes               Auto-approve prompts
#   --continue-on-fail  Continue to next issue if one fails
#   --all <label>       Fetch all open issues with this GitHub label
#   --repo <owner/repo> GitHub repo (default: auto-detect from git remote)
#   --dry-run           Show commands without executing
#   --help              Show this help
#
# Issues can be comma-separated (272,273,274) or space-separated (272 273 274)
# Or use --all <label> to auto-fetch issues (e.g., --all needs-lld)
#

set -euo pipefail

# Configuration
AGENTOS_ROOT="/c/Users/mcwiz/Projects/AssemblyZero"
LOG_DIR="$AGENTOS_ROOT/logs/batch"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Defaults
WORKFLOW_TYPE=""
GATES="none"
YES_FLAG=""
CONTINUE_ON_FAIL=false
DRY_RUN=false
ALL_LABEL=""
REPO=""
ISSUES=()

# Track results
declare -A RESULTS
TOTAL=0
PASSED=0
FAILED=0
START_TIME=$(date +%s)

usage() {
    head -30 "$0" | grep -E "^#" | sed 's/^# //' | sed 's/^#//'
    exit 0
}

log() {
    echo -e "${CYAN}[$(date +%H:%M:%S)]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[$(date +%H:%M:%S)] ✓${NC} $*"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)] ✗${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)] !${NC} $*"
}

# Parse comma-separated or space-separated issues into array
parse_issues() {
    local input="$*"
    # Replace commas with spaces, then split
    input="${input//,/ }"
    for issue in $input; do
        # Strip whitespace and validate it's a number
        issue=$(echo "$issue" | tr -d '[:space:]')
        if [[ "$issue" =~ ^[0-9]+$ ]]; then
            ISSUES+=("$issue")
        elif [[ -n "$issue" ]]; then
            log_warn "Skipping invalid issue number: $issue"
        fi
    done
}

# Get the workflow command for a given type and issue
get_command() {
    local type="$1"
    local issue="$2"
    local cmd=""
    local gates_value="$GATES"

    case "$type" in
        issue)
            cmd="poetry run python tools/run_issue_workflow.py --brief $issue"
            # issue workflow: none, draft, verdict, all
            ;;
        lld|requirements)
            cmd="poetry run python tools/run_requirements_workflow.py --type lld --issue $issue"
            # requirements workflow uses different format: draft,verdict | draft | verdict | none
            # Map 'all' to 'draft,verdict' for this workflow
            if [[ "$gates_value" == "all" ]]; then
                gates_value="draft,verdict"
            fi
            ;;
        impl|implementation)
            cmd="poetry run python tools/run_implement_from_lld.py --issue $issue"
            # impl workflow: none, draft, verdict, all
            ;;
        *)
            log_error "Unknown workflow type: $type"
            exit 1
            ;;
    esac

    # Add gates flag
    cmd="$cmd --gates $gates_value"

    # Add yes flag if specified
    if [[ -n "$YES_FLAG" ]]; then
        cmd="$cmd --yes"
    fi

    # Add repo flag if specified
    if [[ -n "$REPO" ]]; then
        cmd="$cmd --repo $REPO"
    fi

    echo "$cmd"
}

# Run a single workflow
run_workflow() {
    local issue="$1"
    local cmd
    cmd=$(get_command "$WORKFLOW_TYPE" "$issue")
    local log_file="$LOG_DIR/${TIMESTAMP}_${WORKFLOW_TYPE}_${issue}.log"

    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log "Starting $WORKFLOW_TYPE workflow for issue #$issue"
    log "Command: $cmd"
    log "Log file: $log_file"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if $DRY_RUN; then
        log_warn "DRY RUN - would execute: $cmd"
        RESULTS[$issue]="skipped"
        return 0
    fi

    # Run with unbuffered output, tee to log file
    local exit_code=0
    (
        cd "$AGENTOS_ROOT"
        PYTHONUNBUFFERED=1 $cmd 2>&1 | tee "$log_file"
    ) || exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "Issue #$issue completed successfully"
        RESULTS[$issue]="passed"
        ((PASSED++))
    else
        log_error "Issue #$issue failed with exit code $exit_code"
        RESULTS[$issue]="failed"
        ((FAILED++))

        # Show prominent error block with last 20 lines of output
        echo ""
        echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║                    FAILURE DETAILS                         ║${NC}"
        echo -e "${RED}╠════════════════════════════════════════════════════════════╣${NC}"
        echo -e "${RED}║${NC} Issue:     #$issue"
        echo -e "${RED}║${NC} Exit code: $exit_code"
        echo -e "${RED}║${NC} Log file:  $log_file"
        echo -e "${RED}╠════════════════════════════════════════════════════════════╣${NC}"
        echo -e "${RED}║${NC} Last 20 lines of output:"
        echo -e "${RED}╠════════════════════════════════════════════════════════════╣${NC}"
        # Show last 20 lines, indented
        if [[ -f "$log_file" ]]; then
            tail -20 "$log_file" | while IFS= read -r line; do
                echo -e "${RED}║${NC}   $line"
            done
        else
            echo -e "${RED}║${NC}   (no log file found)"
        fi
        echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
        echo ""

        if ! $CONTINUE_ON_FAIL; then
            log_error "Stopping due to failure (use --continue-on-fail to keep going)"
            return 1
        fi
    fi

    return 0
}

# Print summary
print_summary() {
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    local hours=$((duration / 3600))
    local minutes=$(((duration % 3600) / 60))
    local seconds=$((duration % 60))

    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                    BATCH WORKFLOW SUMMARY                  ║${NC}"
    echo -e "${BLUE}╠════════════════════════════════════════════════════════════╣${NC}"
    printf "${BLUE}║${NC} %-58s ${BLUE}║${NC}\n" "Type: $WORKFLOW_TYPE"
    printf "${BLUE}║${NC} %-58s ${BLUE}║${NC}\n" "Duration: ${hours}h ${minutes}m ${seconds}s"
    printf "${BLUE}║${NC} %-58s ${BLUE}║${NC}\n" "Total: $TOTAL | Passed: $PASSED | Failed: $FAILED"
    echo -e "${BLUE}╠════════════════════════════════════════════════════════════╣${NC}"

    for issue in "${ISSUES[@]}"; do
        local status="${RESULTS[$issue]:-unknown}"
        local icon=""
        local color=""
        case "$status" in
            passed)  icon="✓"; color="$GREEN" ;;
            failed)  icon="✗"; color="$RED" ;;
            skipped) icon="○"; color="$YELLOW" ;;
            *)       icon="?"; color="$NC" ;;
        esac
        printf "${BLUE}║${NC} ${color}${icon}${NC} Issue #%-51s ${BLUE}║${NC}\n" "$issue"
    done

    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

    # Write summary to log file
    local summary_file="$LOG_DIR/${TIMESTAMP}_summary.txt"
    {
        echo "Batch Workflow Summary"
        echo "======================"
        echo "Type: $WORKFLOW_TYPE"
        echo "Date: $(date)"
        echo "Duration: ${hours}h ${minutes}m ${seconds}s"
        echo "Total: $TOTAL | Passed: $PASSED | Failed: $FAILED"
        echo ""
        echo "Results:"
        for issue in "${ISSUES[@]}"; do
            echo "  #$issue: ${RESULTS[$issue]:-unknown}"
        done
    } > "$summary_file"
    log "Summary written to: $summary_file"

    # Desktop notification (if available)
    if command -v notify-send &> /dev/null; then
        notify-send "Batch Workflow Complete" "$PASSED passed, $FAILED failed"
    fi

    # Return non-zero if any failed
    [[ $FAILED -eq 0 ]]
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --type)
            WORKFLOW_TYPE="$2"
            shift 2
            ;;
        --gates)
            GATES="$2"
            shift 2
            ;;
        --yes)
            YES_FLAG="--yes"
            shift
            ;;
        --continue-on-fail)
            CONTINUE_ON_FAIL=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --all)
            if [[ -z "${2:-}" ]] || [[ "$2" == --* ]]; then
                log_error "--all requires a label argument"
                echo "Usage: --all <label> (e.g., --all needs-lld)"
                exit 1
            fi
            ALL_LABEL="$2"
            shift 2
            ;;
        --repo)
            REPO="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            # Assume remaining args are issues
            parse_issues "$1"
            shift
            ;;
    esac
done

# Auto-detect repo if not specified
if [[ -z "$REPO" ]]; then
    # Try to get repo from git remote
    REPO=$(git remote get-url origin 2>/dev/null | sed -E 's|.*github.com[:/]([^/]+/[^/.]+)(\.git)?$|\1|' || echo "martymcenroe/AssemblyZero")
fi

# If --all specified, fetch issues from GitHub
if [[ -n "$ALL_LABEL" ]]; then
    if [[ ${#ISSUES[@]} -gt 0 ]]; then
        log_warn "Both --all and explicit issues specified; using --all"
        ISSUES=()
    fi

    log "Fetching issues with label '$ALL_LABEL' from $REPO..."

    # Fetch issues using gh CLI
    issue_numbers=$(gh issue list --state open --label "$ALL_LABEL" --limit 100 --repo "$REPO" --json number --jq '.[].number' 2>/dev/null | sort -n | tr '\n' ' ')

    if [[ -z "$issue_numbers" ]]; then
        log_error "No issues found with label '$ALL_LABEL'"
        exit 1
    fi

    # Parse the fetched issues
    parse_issues "$issue_numbers"

    log "Found ${#ISSUES[@]} issues: ${ISSUES[*]}"
fi

# Validate required args
if [[ -z "$WORKFLOW_TYPE" ]]; then
    log_error "Missing required argument: --type"
    echo "Usage: batch-workflow --type <issue|lld|impl> [options] <issues>"
    exit 1
fi

if [[ ${#ISSUES[@]} -eq 0 ]]; then
    log_error "No issues specified"
    echo "Usage: batch-workflow --type <issue|lld|impl> [options] <issues>"
    exit 1
fi

# Validate gates value
valid_gates=("none" "draft" "verdict" "all")
gates_valid=false
for g in "${valid_gates[@]}"; do
    if [[ "$GATES" == "$g" ]]; then
        gates_valid=true
        break
    fi
done
if ! $gates_valid; then
    log_error "Invalid gates value: '$GATES'"
    echo "Valid options: none, draft, verdict, all"
    exit 1
fi

# Create log directory
mkdir -p "$LOG_DIR"

# Print header
TOTAL=${#ISSUES[@]}
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              AGENTOS BATCH WORKFLOW RUNNER                 ║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════╣${NC}"
printf "${BLUE}║${NC} %-58s ${BLUE}║${NC}\n" "Type: $WORKFLOW_TYPE"
printf "${BLUE}║${NC} %-58s ${BLUE}║${NC}\n" "Gates: $GATES"
printf "${BLUE}║${NC} %-58s ${BLUE}║${NC}\n" "Issues: ${ISSUES[*]}"
printf "${BLUE}║${NC} %-58s ${BLUE}║${NC}\n" "Total: $TOTAL"
printf "${BLUE}║${NC} %-58s ${BLUE}║${NC}\n" "Continue on fail: $CONTINUE_ON_FAIL"
printf "${BLUE}║${NC} %-58s ${BLUE}║${NC}\n" "Logs: $LOG_DIR"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

# Run workflows sequentially
for issue in "${ISSUES[@]}"; do
    run_workflow "$issue" || {
        if ! $CONTINUE_ON_FAIL; then
            print_summary
            exit 1
        fi
    }
done

print_summary
