#!/bin/bash
# gemini-model-check.sh - Detect Gemini model downgrades
# AssemblyZero Core Tool - Available to all child projects
#
# Usage: ./tools/gemini-model-check.sh "prompt text" [required-model]
#
# This script uses gemini-retry.py for automatic retry with exponential backoff.
# If Gemini downgrades to a lower model, the script aborts.
#
# Exit codes:
#   0 - Success (correct model used)
#   1 - Gemini CLI failed to execute / max retries exceeded
#   2 - Quota exhausted (429 error - not retryable)
#   3 - Model downgrade detected
#
# Environment variables (passed to gemini-retry.py):
#   GEMINI_RETRY_MAX         Max retry attempts (default: 20)
#   GEMINI_RETRY_BASE_DELAY  Initial delay in seconds (default: 30)
#   GEMINI_RETRY_MAX_DELAY   Max delay cap in seconds (default: 600)

set -euo pipefail

# Parse arguments
PROMPT="$1"
REQUIRED_MODEL="${2:-gemini-3-pro-preview}"

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$(dirname "$SCRIPT_DIR")/../tools"

# Check if gemini-retry.py exists
if [[ -f "$TOOLS_DIR/gemini-retry.py" ]]; then
  # Use retry wrapper for automatic backoff on capacity errors
  result=$(python "$TOOLS_DIR/gemini-retry.py" --prompt "$PROMPT" --model "$REQUIRED_MODEL" 2>&1) || {
    exit_code=$?
    echo "ERROR: Gemini retry failed after max attempts" >&2
    echo "$result" >&2
    exit $exit_code
  }
  # gemini-retry.py returns the response directly on stdout
  echo "$result"
  exit 0
fi

# Fallback: direct invocation (no retry)
echo "WARNING: gemini-retry.py not found, using direct invocation" >&2
result=$(gemini -p "$PROMPT" \
  --model "$REQUIRED_MODEL" \
  --output-format json 2>&1) || {
  echo "ERROR: Gemini CLI failed to execute" >&2
  echo "$result" >&2
  exit 1
}

# Check for 429 quota errors in raw output
if echo "$result" | grep -qE "429|Resource exhausted|quota"; then
  echo "ERROR: Quota exhausted (429 error)" >&2

  # Try to extract quota reset time if available
  reset_time=$(echo "$result" | grep -oP "reset.*?(\d{4}-\d{2}-\d{2})" | head -1 || echo "Unknown")
  echo "Next reset: $reset_time" >&2

  exit 2
fi

# Extract JSON portion (skip any non-JSON prefix like "Loaded cached credentials.")
json_output=$(echo "$result" | sed -n '/{/,$p')

# Parse models used from JSON stats
models_json=$(echo "$json_output" | jq -r '.stats.models // {}' 2>/dev/null) || {
  echo "ERROR: Failed to parse JSON response" >&2
  echo "Raw output:" >&2
  echo "$result" >&2
  exit 1
}

# Check for model downgrades
downgrade=false
models_used=()

while IFS= read -r model; do
  # Trim any trailing whitespace/CR/LF
  model=$(echo "$model" | tr -d '\r\n')

  models_used+=("$model")

  # Check if this model is NOT one of the allowed models
  # Allow: gemini-3-pro-preview, gemini-3-pro (stable), or the explicitly required model
  if [[ "$model" != "$REQUIRED_MODEL" && "$model" != "gemini-3-pro" && "$model" != "gemini-3-pro-preview" ]]; then
    echo "ERROR: Model downgrade detected!" >&2
    echo "Required: $REQUIRED_MODEL" >&2
    echo "Actually used: $model" >&2
    downgrade=true
  fi
done < <(echo "$models_json" | jq -r 'keys[]')

if [ "$downgrade" = true ]; then
  echo "All models used: ${models_used[*]}" >&2
  exit 3
fi

# Success - output positive model verification to stderr (for capture/logging)
echo "---GEMINI-MODEL-VERIFIED---" >&2
echo "Model: ${models_used[*]}" >&2
echo "Stats.models:" >&2
echo "$models_json" | jq -c '.' >&2
echo "---END-VERIFICATION---" >&2

# Extract and output response only (no JSON wrapper) to stdout
response=$(echo "$json_output" | jq -r '.response')
echo "$response"

exit 0
