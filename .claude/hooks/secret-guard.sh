#!/bin/bash
# Secret Guard Hook
#
# BLOCK: Bash commands that would leak secrets to stdout (captured in transcripts).
#
# Category A: Reading secret files (cat .env, less .aws/credentials, etc.)
# Category B: Environment dumps (printenv, env, set, export -p)
# Category C: Secret variable dereference (echo $GITHUB_TOKEN, etc.)
# Category D: CLI credential dump commands (gh auth token, aws configure get, etc.)
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
# Blocks: ANY command that references secret files as arguments.
# Covers: cat, less, more, head, tail, grep, rg, awk, sed, strings, xxd,
#         od, sort, wc, diff, cp, mv, python -c, ruby -e, etc.
#
# Strategy: Check if ANY secret file pattern appears anywhere in the command.
# This is intentionally broad — false positives are safer than false negatives.
# Issue #693: Agent bypassed old guard using `grep 'API_KEY' .dev.vars`
# ---------------------------------------------------------------------------

# Secret file patterns — match anywhere in the command arguments
secret_file_pattern='(^|[[:space:]/])(\.env|\.env\.[a-zA-Z0-9_]+|\.dev\.vars)([[:space:]]|$|")'
aws_creds_pattern='\.aws/(credentials|config)'

if [[ "$command" =~ $secret_file_pattern ]] ||
   [[ "$command" =~ $aws_creds_pattern ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - Secret File Access" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "Secret files (.env, .dev.vars, .aws/credentials) must never" >&2
    echo "be accessed via Bash — session transcripts capture all output." >&2
    echo "" >&2
    echo "This blocks ALL commands targeting secret files, not just cat/head." >&2
    echo "Agents have been observed using grep, awk, sed to bypass narrower guards." >&2
    echo "" >&2
    echo "Use os.environ.get() in Python to access secrets." >&2
    echo "" >&2
    exit 1
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

# ---------------------------------------------------------------------------
# Category D: CLI credential dump commands
# Blocks: gh auth token, aws configure get <secret>, etc.
# These tools have built-in "print my credential" subcommands that bypass
# env-var and file-read guards.
# ---------------------------------------------------------------------------

# gh auth token — prints active PAT to stdout
if [[ "$command" =~ (^|[;&|])[[:space:]]*gh[[:space:]]+auth[[:space:]]+token([[:space:]]|$) ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - CLI Credential Dump" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "'gh auth token' prints your GitHub PAT to stdout." >&2
    echo "Use resolve_github_token() in Python or gh auth login interactively." >&2
    echo "" >&2
    exit 1
fi

# gh auth status --show-token — token embedded in status output
if [[ "$command" =~ (^|[;&|])[[:space:]]*gh[[:space:]]+auth[[:space:]]+status ]] &&
   [[ "$command" =~ --show-token ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - CLI Credential Dump" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "'gh auth status --show-token' prints your GitHub PAT to stdout." >&2
    echo "Use 'gh auth status' without --show-token for safe status checks." >&2
    echo "" >&2
    exit 1
fi

# aws configure get <secret-key> — dumps individual AWS secrets
if [[ "$command" =~ (^|[;&|])[[:space:]]*aws[[:space:]]+configure[[:space:]]+get[[:space:]]+(aws_secret_access_key|aws_session_token|aws_access_key_id)([[:space:]]|$) ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - CLI Credential Dump" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "This prints an AWS credential to stdout." >&2
    echo "Use os.environ.get() or boto3 in Python instead." >&2
    echo "" >&2
    exit 1
fi

# aws sts get-session-token — dumps temporary credentials
if [[ "$command" =~ (^|[;&|])[[:space:]]*aws[[:space:]]+sts[[:space:]]+get-session-token([[:space:]]|$) ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - CLI Credential Dump" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "'aws sts get-session-token' dumps temporary credentials to stdout." >&2
    echo "Use boto3.client('sts') in Python instead." >&2
    echo "" >&2
    exit 1
fi

# aws ssm get-parameter --with-decryption — dumps secrets from Parameter Store
if [[ "$command" =~ (^|[;&|])[[:space:]]*aws[[:space:]]+ssm[[:space:]]+get-parameter ]] &&
   [[ "$command" =~ --with-decryption ]]; then
    echo "" >&2
    echo "========================================" >&2
    echo "BLOCKED: Secret Guard - CLI Credential Dump" >&2
    echo "========================================" >&2
    echo "" >&2
    echo "REJECTED: $command" >&2
    echo "" >&2
    echo "'aws ssm get-parameter --with-decryption' dumps secrets to stdout." >&2
    echo "Use boto3.client('ssm') in Python instead." >&2
    echo "" >&2
    exit 1
fi

# No violations, allow command
exit 0
