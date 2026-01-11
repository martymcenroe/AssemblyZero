#!/bin/bash
# Pre-Edit Security Warning Hook
#
# WARN (not block): Alerts before editing files with known security patterns.
# Creates defense-in-depth: warn before edit → lint after edit.
#
# Based on: anthropics/claude-code security-guidance plugin
# Monitors 9+ security anti-patterns from OWASP guidance.
#
# Environment: $CLAUDE_TOOL_INPUT_FILE_PATH contains the target file path

file="$CLAUDE_TOOL_INPUT_FILE_PATH"

# Skip if file doesn't exist yet (new file creation)
if [ ! -f "$file" ]; then
    exit 0
fi

# Skip non-code files
case "$file" in
    *.md|*.txt|*.rst|*.adoc|*.gitignore|*.json|*.yaml|*.yml|*.toml)
        exit 0
        ;;
esac

warnings=""

# Function to add warning
add_warning() {
    local pattern="$1"
    local risk="$2"
    local guidance="$3"
    warnings="${warnings}
  - Pattern: ${pattern}
    Risk: ${risk}
    Guidance: ${guidance}"
}

# === JAVASCRIPT/TYPESCRIPT PATTERNS ===
case "$file" in
    *.js|*.jsx|*.ts|*.tsx|*.mjs|*.cjs)
        # XSS vectors (CRITICAL)
        if grep -q "innerHTML" "$file" 2>/dev/null; then
            add_warning "innerHTML" "XSS injection" "Use textContent or createElement instead"
        fi
        if grep -q "outerHTML" "$file" 2>/dev/null; then
            add_warning "outerHTML" "XSS injection" "Use DOM methods instead"
        fi
        if grep -q "document\.write" "$file" 2>/dev/null; then
            add_warning "document.write" "XSS injection" "Use DOM methods instead"
        fi
        if grep -q "insertAdjacentHTML" "$file" 2>/dev/null; then
            add_warning "insertAdjacentHTML" "XSS injection" "Use DOM methods with textContent"
        fi

        # Code execution (CRITICAL)
        if grep -qE "eval\s*\(" "$file" 2>/dev/null; then
            add_warning "eval()" "Arbitrary code execution" "Avoid eval; use JSON.parse for data"
        fi
        if grep -qE "new\s+Function\s*\(" "$file" 2>/dev/null; then
            add_warning "new Function()" "Arbitrary code execution" "Avoid dynamic function creation"
        fi

        # Message handling (browser extensions)
        if grep -q "onMessage" "$file" 2>/dev/null; then
            if ! grep -q "sender\.id" "$file" 2>/dev/null; then
                add_warning "onMessage without sender.id" "Message spoofing" "Always validate sender.id === chrome.runtime.id"
            fi
        fi

        # Dangerous APIs
        if grep -qE "localStorage\.(set|get)Item.*([\"']password|[\"']token|[\"']secret|[\"']api.?key)" "$file" 2>/dev/null; then
            add_warning "Secrets in localStorage" "Credential exposure" "Use chrome.storage.session or secure storage"
        fi
        ;;
esac

# === PYTHON PATTERNS ===
case "$file" in
    *.py)
        # Code execution (CRITICAL)
        if grep -qE "eval\s*\(" "$file" 2>/dev/null; then
            add_warning "eval()" "Arbitrary code execution" "Use ast.literal_eval for data parsing"
        fi
        if grep -qE "exec\s*\(" "$file" 2>/dev/null; then
            add_warning "exec()" "Arbitrary code execution" "Avoid exec; refactor to direct calls"
        fi

        # Command injection (CRITICAL)
        if grep -qE "os\.system\s*\(" "$file" 2>/dev/null; then
            add_warning "os.system()" "Command injection" "Use subprocess.run with shell=False"
        fi
        if grep -qE "subprocess.*shell\s*=\s*True" "$file" 2>/dev/null; then
            add_warning "subprocess shell=True" "Command injection" "Use shell=False with list args"
        fi

        # Deserialization (CRITICAL)
        if grep -qE "pickle\.(load|loads)" "$file" 2>/dev/null; then
            add_warning "pickle.load()" "Arbitrary code execution via deserialization" "Use JSON or validate source"
        fi
        if grep -qE "yaml\.load\(" "$file" 2>/dev/null; then
            if ! grep -q "Loader=" "$file" 2>/dev/null; then
                add_warning "yaml.load() without Loader" "Arbitrary code execution" "Use yaml.safe_load() instead"
            fi
        fi

        # SQL injection
        if grep -qE "execute\s*\(\s*[\"'].*%s" "$file" 2>/dev/null; then
            add_warning "SQL string formatting" "SQL injection" "Use parameterized queries"
        fi
        if grep -qE "execute\s*\(\s*f[\"']" "$file" 2>/dev/null; then
            add_warning "SQL f-string" "SQL injection" "Use parameterized queries"
        fi
        ;;
esac

# === SHELL PATTERNS ===
case "$file" in
    *.sh|*.bash)
        # Command injection vectors
        if grep -qE '\$\([^)]*\$' "$file" 2>/dev/null; then
            add_warning "Nested command substitution with variables" "Command injection" "Quote variables, validate input"
        fi
        if grep -qE 'eval\s+' "$file" 2>/dev/null; then
            add_warning "eval in shell" "Command injection" "Avoid eval; use direct commands"
        fi
        ;;
esac

# === HTML PATTERNS ===
case "$file" in
    *.html|*.htm)
        # Inline scripts (CSP violation for extensions)
        if grep -qE "<script[^>]*>" "$file" 2>/dev/null; then
            if grep -qE "<script[^>]*>[^<]+" "$file" 2>/dev/null; then
                add_warning "Inline script" "CSP violation (MV3)" "Move to external .js file"
            fi
        fi
        # Inline event handlers
        if grep -qE "on(click|load|error|mouseover)=" "$file" 2>/dev/null; then
            add_warning "Inline event handler" "CSP violation (MV3)" "Use addEventListener in external JS"
        fi
        ;;
esac

# Output warnings if any found
if [ -n "$warnings" ]; then
    echo "" >&2
    echo "========================================" >&2
    echo "SECURITY WARNING: Patterns detected" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "File: $file" >&2
    echo "" >&2
    echo "Detected patterns:$warnings" >&2
    echo "" >&2
    echo "Review security best practices" >&2
    echo "before modifying security-sensitive code." >&2
    echo "" >&2
    echo "This is a WARNING, not a block." >&2
    echo "Proceed with caution." >&2
    echo "" >&2
fi

# Always exit 0 (warning, not blocking)
exit 0
