# Gemini Operational Protocols - AssemblyZero

## 1. Session Initialization (The Handshake)

## 2. Core Rules

**Read `CLAUDE.md` in this repository.** Those rules apply to ALL agents:
- Bash command rules (no &&, |, ;)
- Path format rules (Windows vs Unix)
- Worktree isolation rules
- Decision-making protocol

---

## 3. Execution Rules

- **Authority:** `docs/standards/0002-coding-standards.md` is the law for Git workflows.
- **One Step Per Turn:** Provide one distinct step, then wait for confirmation.
- **Check First:** Verify paths/content before changing them.
- **Copy-Paste Ready:** No placeholders. Use heredocs for new files.

---

## 4. AssemblyZero Context

**Project:** AssemblyZero
**Repository:** martymcenroe/AssemblyZero
**Project Root (Windows):** `C:\Users\mcwiz\Projects\AssemblyZero`
**Project Root (Unix):** `/c/Users/mcwiz/Projects/AssemblyZero`

This is the **framework repository**. Standards defined here apply to all projects.

---

## 5. Session Logging

At session end, append a summary to `docs/session-logs/YYYY-MM-DD.md`:
- **Day boundary:** 3:00 AM CT to following day 2:59 AM CT
- **Include:** date/time, model name (from handshake), summary, files touched, state on exit

---

## 6. You Are Not Alone

Other agents (Claude, human orchestrators) work on this project. Check `docs/session-logs/` for recent context before starting work.

---

## 7. Anti-Auto-Approve Protocol

**CRITICAL SAFETY RULE:** You are running in an environment with an **auto-approver** (automatically says "y" or "yes").

When proposing a **NEW MAJOR TASK** (e.g., starting a new Issue worktree, merging a PR, or destructive cleanup), you **MUST NOT** ask a Yes/No question.

**Protocol:**
1.  **Require Specific Input:** Ask the user to type a unique string to confirm.
2.  **Format:** "To proceed, please type: **'EXECUTE <TASK_ID>'**."
3.  **Reject Generics:** If the user (or auto-approver) replies "y", "yes", "go ahead", or "continue", you **MUST STOP** and repeat the request for the specific string.

---

## 8. The Perdita Protocol (Babysit Mode)

**Shorthand:** "Babysit <IssueID>"

When this command is issued, the agent operates in a high-autonomy, low-intervention mode governed by **Perdita X. Dream** (the watchful inner mind).

### 8.1 Core Principles
1.  **Isolation:** Always create a worktree `../AssemblyZero-{ID}` and branch `{ID}-fix`.
2.  **Two-Strike Rule:** Enforce `MAX_FILE_RETRIES=2` and `max_iterations=3` globally. No "trying one more time."
3.  **Mechanical Guardrails:** Every turn must be validated by non-LLM logic (e.g., File Size Safety Gate #587).
4.  **Surgical Context:** For retries, prune context to only the LLD + the failing file's current content to save tokens.
5.  **Halt-on-Stagnation:** If the same error occurs twice, or if `iteration_count` exceeds limits, the agent must **Halt and Plan**, saving a `recovery_plan.md` in the worktree.

### 8.2 Operational Steps
1.  **Initialize:** Create worktree and isolated branch.
2.  **Execute:** Run the relevant workflow tools (TDD, LLD, or Issue).
3.  **Monitor:** Watch the audit log (`workflow-audit.jsonl`) and cost budget.
4.  **Cleanup:** Finalize the issue only when tests are Green, LLD is moved to `done/`, and the worktree is deleted.

---

## 9. Secret Protection (Mandatory)

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
