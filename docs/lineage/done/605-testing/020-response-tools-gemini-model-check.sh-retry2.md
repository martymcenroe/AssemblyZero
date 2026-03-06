

```bash
#!/usr/bin/env bash
# gemini-model-check.sh — Verify Gemini and Claude model IDs across the codebase
# Usage: bash tools/gemini-model-check.sh

set -euo pipefail

EXPECTED_GEMINI="gemini-3.1"
EXPECTED_CLAUDE="claude-4.6"
EXIT_CODE=0

echo "=== Gemini Model Check ==="
echo "Expected Gemini model: ${EXPECTED_GEMINI}"
echo "Expected Claude model: ${EXPECTED_CLAUDE}"
echo ""

# Files to check
CONFIG_FILE="assemblyzero/core/config.py"
LLM_PROVIDER_FILE="assemblyzero/core/llm_provider.py"
ROTATE_FILE="tools/gemini-rotate.py"

check_file() {
    local file="$1"
    local pattern="$2"
    local label="$3"

    if [ ! -f "$file" ]; then
        echo "WARN: $file not found"
        return
    fi

    if grep -q "$pattern" "$file"; then
        echo "  OK: ${label} in ${file}"
    else
        echo "  FAIL: ${label} not found in ${file}"
        EXIT_CODE=1
    fi
}

echo "Checking Gemini model ID..."
check_file "$CONFIG_FILE" "$EXPECTED_GEMINI" "Gemini 3.1 default"
check_file "$LLM_PROVIDER_FILE" "$EXPECTED_GEMINI" "Gemini 3.1 mapping"
check_file "$ROTATE_FILE" "$EXPECTED_GEMINI" "Gemini 3.1 rotate"

echo ""
echo "Checking Claude model ID..."
check_file "$LLM_PROVIDER_FILE" "$EXPECTED_CLAUDE" "Claude 4.6 mapping"

echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "All model checks passed."
else
    echo "Some model checks failed. See above."
fi

exit $EXIT_CODE
```
