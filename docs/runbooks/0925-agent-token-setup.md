# 0925 - Runbook: Agent Token Setup (Fine-Grained PATs)

## Purpose

Create and manage restricted GitHub Fine-Grained Personal Access Tokens (PATs) for AI agents (Claude Code, Gemini CLI, etc.). Agents get enough permission to do their work but cannot bypass branch protection, force-push, or perform admin actions.

## Why Fine-Grained PATs

| Concern | Classic PAT | Fine-Grained PAT |
|---------|-------------|-------------------|
| Scope granularity | Coarse (repo, admin:org) | Per-repo, per-permission |
| Admin bypass | `repo` scope includes admin | Admin is a separate toggle |
| Branch protection | Can bypass with `--admin` | Cannot bypass (no admin scope) |
| Token visibility | No audit trail | GitHub shows last-used, permissions |
| Expiration | Optional | Mandatory (max 1 year) |

## Attribution Model

Agents use the **owner's git identity** for attribution (green squares) but a **restricted token** for API access:

```
Git identity (authorship):   martymcenroe <mcwizard1@gmail.com>
API identity (authorization): Fine-Grained PAT with limited scope
```

This means:
- Commits show as Marty's contributions on GitHub
- The token cannot bypass branch protection or perform admin actions
- If leaked, blast radius is limited to the scoped permissions

## Creating a Fine-Grained PAT

### Step 1: Navigate to Token Settings

1. Go to https://github.com/settings/tokens?type=beta
2. Click **Generate new token**

### Step 2: Configure Token Metadata

| Field | Value |
|-------|-------|
| Token name | `claude-code-restricted` (or `gemini-restricted`, etc.) |
| Expiration | 90 days (rotate quarterly) |
| Description | Restricted agent token for Claude Code / Gemini |

### Step 3: Set Repository Access

Select **Only select repositories** and add:
- `martymcenroe/AssemblyZero`
- `martymcenroe/gh-link-auditor`
- `martymcenroe/Aletheia`
- `martymcenroe/Talos`
- (add others as needed)

### Step 4: Set Permissions

**Repository permissions (Read and Write):**

| Permission | Access | Why |
|------------|--------|-----|
| Contents | Read and Write | Push commits, read files |
| Pull requests | Read and Write | Create/merge PRs |
| Issues | Read and Write | Create/close/comment issues |
| Metadata | Read-only | Required (auto-enabled) |

**Repository permissions (DO NOT GRANT):**

| Permission | Why NOT |
|------------|---------|
| Administration | Would allow bypassing branch protection |
| Actions | Agents should not modify CI/CD |
| Environments | No deployment access |
| Pages | No site publishing |
| Secrets | Agents must never access repo secrets |
| Webhooks | No webhook management |
| Workflows | No workflow file modification |

**Account permissions:** Leave all at **No access**.

### Step 5: Generate and Store

1. Click **Generate token**
2. Copy the token (starts with `github_pat_`)
3. Store it in the project `.env` file:

```
GITHUB_TOKEN=github_pat_xxxxxxxxxxxx
```

4. **DO NOT** paste the token into a terminal, chat, or any file that gets committed

### Step 6: Configure gh CLI

Run this command yourself (not through an agent):

```bash
echo "github_pat_xxxxxxxxxxxx" | gh auth login --with-token
```

Verify:
```bash
gh auth status
```

Expected output includes:
```
Token: github_pat_****
Token scopes: (none required for fine-grained PATs)
```

## Verification Checklist

After creating the token, verify these constraints hold:

### Should WORK

```bash
# Read repo contents
gh api repos/martymcenroe/gh-link-auditor/contents/README.md --repo martymcenroe/gh-link-auditor

# Create an issue
gh issue create --repo martymcenroe/gh-link-auditor --title "test" --body "test"

# Create a PR (from a branch)
gh pr create --repo martymcenroe/gh-link-auditor --title "test" --body "test"

# Merge a PR (respects branch protection)
gh pr merge NUMBER --squash --repo martymcenroe/gh-link-auditor
```

### Should FAIL

```bash
# Admin merge bypass -- MUST fail with 403
gh pr merge NUMBER --admin --repo martymcenroe/gh-link-auditor

# Delete branch protection -- MUST fail
gh api -X DELETE repos/martymcenroe/gh-link-auditor/branches/main/protection --repo martymcenroe/gh-link-auditor

# Access repo secrets -- MUST fail
gh api repos/martymcenroe/gh-link-auditor/actions/secrets --repo martymcenroe/gh-link-auditor
```

### Should BLOCK (via secret-guard hook)

These are blocked by the `secret-guard.sh` hook, not the token itself:

```bash
# These commands are blocked before execution
cat .env              # Blocked: Category A (secret file read)
echo $GITHUB_TOKEN    # Blocked: Category C (secret var dereference)
printenv GITHUB_TOKEN # Blocked: Category B (secret var dump)
```

## Token Rotation

### Schedule

| Token | Rotation | Reminder |
|-------|----------|----------|
| `claude-code-restricted` | Every 90 days | GitHub emails 7 days before expiry |
| `gemini-restricted` | Every 90 days | Same |

### Rotation Procedure

1. Create new token (follow steps above)
2. Update `.env` in each project
3. Re-run `gh auth login --with-token` with new token
4. Verify with checklist above
5. Revoke old token at https://github.com/settings/tokens?type=beta

## Incident Response

### Token Leaked in Transcript

If a token appears in a Claude Code session transcript:

1. **Immediately revoke** the token at https://github.com/settings/tokens?type=beta
2. Create a new token following this runbook
3. Check GitHub audit log for unauthorized activity: https://github.com/settings/security-log
4. The fine-grained scope limits blast radius — the attacker cannot:
   - Bypass branch protection
   - Access secrets
   - Modify CI/CD
   - Delete repos

### Token Expired

1. GitHub sends email 7 days before expiry
2. Follow rotation procedure above
3. Agents will get 401 errors until token is replaced

## Defense in Depth Summary

This token is one layer in a three-layer defense:

| Layer | What | Protects Against |
|-------|------|------------------|
| 1. `secret-guard.sh` hook | Blocks `cat .env`, `printenv`, `echo $TOKEN` | Secret leakage to transcripts |
| 2. Fine-Grained PAT (this runbook) | Limits token permissions | Blast radius if token leaks |
| 3. `settings.local.json` Read deny | Blocks Read tool on `.env*` | Agent reading secret files |

## Related Documents

- `docs/standards/0003-agent-prohibited-actions.md` — Agent safety rules
- `.claude/hooks/secret-guard.sh` — Bash hook blocking secret leaks
- `docs/runbooks/0905-gemini-credentials.md` — Gemini credential management
- `docs/runbooks/0900-runbook-index.md` — Runbook index
- AssemblyZero #595 — Tracking issue
- AssemblyZero #663 — Secret-guard hook issue

## History

| Date | Change |
|------|--------|
| 2026-03-07 | Initial runbook created |
