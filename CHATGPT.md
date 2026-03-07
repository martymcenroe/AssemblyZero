# ChatGPT / Codex Operational Protocols - AssemblyZero

## 1. Core Rules

**Read `CLAUDE.md` in this repository.** Those rules apply to ALL agents:
- Path format rules (Windows paths for file tools, Unix paths for shell)
- Dangerous path avoidance (`~/OneDrive`, `~/AppData`)
- Safety rules (destructive commands only within `~/Projects/`)
- Two-Strike Rule, Definition of Done
- PR issue references mandatory

---

## 2. AssemblyZero Context

**Project:** AssemblyZero
**Repository:** martymcenroe/AssemblyZero
**Project Root (Windows):** `C:\Users\mcwiz\Projects\AssemblyZero`
**Project Root (Unix):** `/c/Users/mcwiz/Projects/AssemblyZero`

This is the **framework repository**. Standards defined here apply to all projects.

---

## 3. Codex Execution Model

OpenAI Codex runs in a **sandboxed container** with:
- Internet access disabled (no outbound network)
- Isolated filesystem (cloned repo snapshot)
- `AGENTS.md` as the primary instruction file (Codex reads this automatically)

The sandbox may limit filesystem access to the repo clone. The prohibitions below are **defense in depth** — they apply even if the sandbox prevents some access patterns.

---

## 4. Secret Protection (Mandatory)

**Session transcripts capture all stdout in plaintext.** Secrets printed during a session are irrevocably exposed. The following categories are NEVER permitted.

### Category A: Secret File Reads

**NEVER** run `cat`, `head`, `tail`, `less`, `more`, `bat`, `view`, `vim`, or `python -c "open(...)"` on:
- `.env`, `.env.*`, `.dev.vars`
- `~/.aws/credentials`, `~/.aws/config`
- Any file matching `*secret*`, `*credential*`, `*token*`, `*.pem`, `*.key`

**Safe alternative:** Use `os.environ.get('VAR_NAME')` in Python to access secrets programmatically without printing them.

### Category B: Environment Dumps

**NEVER** run these commands standalone:
- `env`, `printenv`, `set` (no args), `export -p`
- `printenv GITHUB_TOKEN` (or any secret variable name)

**Allowed:** `env VAR=val cmd`, `set -e`, `set -x`, `export MY_VAR=hello`, `printenv PATH`

### Category C: Secret Variable Dereference

**NEVER** output or dereference these variables in commands:
- `$GITHUB_TOKEN`, `$GH_TOKEN`
- `$AWS_SECRET_ACCESS_KEY`, `$AWS_SESSION_TOKEN`, `$AWS_ACCESS_KEY_ID`
- `$OPENAI_API_KEY`, `$ANTHROPIC_API_KEY`
- `$CLOUDFLARE_API_TOKEN`, `$CF_API_TOKEN`
- `$NPM_TOKEN`, `$DOCKER_PASSWORD`
- `$DATABASE_URL`, `$DB_PASSWORD`
- `$SECRET_KEY`, `$PRIVATE_KEY`

**Example violations:** `echo $GITHUB_TOKEN`, `curl -H "Authorization: $AWS_SECRET_ACCESS_KEY"`

### Category D: CLI Credential Dumps

**NEVER** run these commands:
- `gh auth token` — prints GitHub PAT to stdout
- `gh auth status --show-token` — embeds token in status output
- `aws configure get aws_secret_access_key` (or `aws_session_token`, `aws_access_key_id`)
- `aws sts get-session-token` — dumps temporary credentials
- `aws ssm get-parameter --with-decryption` — dumps secrets from Parameter Store

**Safe alternatives:** Use `boto3.client('sts')` or `os.environ.get()` in Python. Use `gh auth status` without `--show-token`.

### If You Need a Secret Value

1. Ask the user to provide it in their own terminal
2. Use `os.environ.get()` in a Python script (value stays in-process, never hits stdout)
3. **NEVER** print, echo, or cat a secret — even "just to check"

---

## 5. Execution Rules

- **One Step at a Time:** Verify paths and content before changing them.
- **No Placeholders:** Commands must be copy-paste ready.
- **Check First:** Read files before modifying them.
- **Python:** Use `poetry run python` for execution, `poetry add` for dependencies.
