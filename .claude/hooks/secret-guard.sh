#!/bin/bash
# Secret Guard Hook
#
# BLOCK: Bash commands that would leak secrets to stdout (captured in transcripts).
#
# Category A: Reading secret files (cat .env, less .aws/credentials, etc.)
# Category B: Environment dumps (printenv, env, set, export -p)
# Category C: Secret variable dereference (echo $GITHUB_TOKEN, etc.)
#
# Environment: $CLAUDE_TOOL_INPUT_COMMAND contains the bash command

set -e

command="$CLAUDE_TOOL_INPUT_COMMAND"

# Skip empty commands
if [ -z "$command" ]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Category A: Secret file reads
# Blocks: cat/less/more/head/tail on .env*, .dev.vars, .aws/credentials
# ---------------------------------------------------------------------------

# Match: cmd [flags] <secret-file-pattern>
# Allow: cat README.md, head -n 5 main.py, etc.
if [[ "$command" =~ (^|[[:space:]])(cat|less|more|head|tail)([[:space:]]+-[a-zA-Z0-9]+)*[[:space:]]+(.*) ]]; then
    file_args="${BASH_REMATCH[4]}"
    if [[ "$file_args" =~ (^|[[:space:]])(\.env|\.env\.[a-zA-Z0-9_]+|\.dev\.vars) ]] ||
       [[ "$file_args" =~ \.aws/credentials ]] ||
       [[ "$file_args" =~ \.aws/config ]]; then
        echo "" >&2
        echo "========================================" >&2
        echo "BLOCKED: Secret Guard - Secret File Read" >&2
        echo "========================================" >&2
        echo "" >&2
        echo "REJECTED: $command" >&2
        echo "" >&2
        echo "Secret files must never be printed to stdout." >&2
        echo "Session transcripts capture all output in plaintext." >&2
        echo "" >&2
        echo "Use os.environ.get() in Python to access secrets." >&2
        echo "" >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Category B: Environment dumps
# Blocks: standalone printenv, env, set, export -p
# Also blocks: printenv SECRET_VAR (targeted secret dump)
# Allows: env VAR=val cmd, set -e, set -x, export MY_VAR=hello, printenv PATH
# ---------------------------------------------------------------------------

# Standalone "printenv" or "printenv" with a secret var name
if [[ "$command" =~ ^[[:space:]]*printenv[[:space:]]*$ ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - Env Dump" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "'printenv' dumps all environment variables including secrets." >&2
    echo "Use os.environ.get('VAR_NAME') in Python instead." >&2
    echo "" >&2
    exit 1
fi

# printenv with a specific secret variable
secret_vars="GITHUB_TOKEN|GH_TOKEN|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|AWS_ACCESS_KEY_ID|OPENAI_API_KEY|ANTHROPIC_API_KEY|CLOUDFLARE_API_TOKEN|CF_API_TOKEN|NPM_TOKEN|DOCKER_PASSWORD|DATABASE_URL|DB_PASSWORD|SECRET_KEY|PRIVATE_KEY"

if [[ "$command" =~ ^[[:space:]]*printenv[[:space:]]+(${secret_vars})([[:space:]]|$) ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - Secret Var Dump" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "This would print a secret to stdout (captured in transcripts)." >&2
    echo "Use os.environ.get() in Python instead." >&2
    echo "" >&2
    exit 1
fi

# Standalone "env" (no args or just flags) — but NOT "env VAR=val cmd"
if [[ "$command" =~ ^[[:space:]]*env[[:space:]]*$ ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - Env Dump" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "'env' dumps all environment variables including secrets." >&2
    echo "Use os.environ.get('VAR_NAME') in Python instead." >&2
    echo "" >&2
    exit 1
fi

# "set" without flags (dumps all shell variables) — but NOT "set -e", "set -x", etc.
if [[ "$command" =~ ^[[:space:]]*set[[:space:]]*$ ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - Shell Var Dump" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "'set' with no args dumps all shell variables including secrets." >&2
    echo "Use os.environ.get('VAR_NAME') in Python instead." >&2
    echo "" >&2
    exit 1
fi

# "export -p" (prints all exports)
if [[ "$command" =~ ^[[:space:]]*export[[:space:]]+-p([[:space:]]|$) ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - Export Dump" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "'export -p' dumps all exported variables including secrets." >&2
    echo "Use os.environ.get('VAR_NAME') in Python instead." >&2
    echo "" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Category C: Secret variable dereference in commands
# Blocks: echo $GITHUB_TOKEN, curl -H "Authorization: $AWS_SECRET_ACCESS_KEY"
# Allows: echo "hello", echo $HOME, normal variable usage
# ---------------------------------------------------------------------------

if [[ "$command" =~ \$(${secret_vars})([^a-zA-Z_]|$) ]] ||
   [[ "$command" =~ \$\{(${secret_vars})\} ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - Secret Var Dereference" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "This command would expand a secret variable to stdout." >&2
    echo "Session transcripts capture all output in plaintext." >&2
    echo "" >&2
    echo "Use os.environ.get() in Python to access secrets internally." >&2
    echo "" >&2
    exit 1
fi

# No violations, allow command
exit 0
