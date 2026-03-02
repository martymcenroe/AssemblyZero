# pr-sentinel

PR Issue-Reference Enforcer — a GitHub App on Cloudflare Workers.

Every PR must reference an open issue (`Closes #N`, `Fixes #N`, `Resolves #N`) or declare `No-Issue: <reason>`. The app creates a check run that blocks merge until the requirement is met.

## Deployment

| Resource | Value |
|----------|-------|
| Worker URL | `https://pr-sentinel.mcwizard1.workers.dev` |
| Platform | Cloudflare Workers |
| Account | `4fe1c5e241425c85d0f2c35c69fb45b8` (mcwizard1@gmail.com) |
| Check name | `pr-sentinel / issue-reference` |

## GitHub App

| Setting | Value |
|---------|-------|
| App name | `pr-sentinel-mm` |
| App ID | `2975092` |
| Private key | `/c/Users/mcwiz/Projects/pr-sentinel-mm.2026-02-28.private-key.pem` |

## Secrets (Wrangler)

The worker expects three secrets (set via `wrangler secret put`):

- `WEBHOOK_SECRET` — GitHub webhook HMAC secret
- `APP_ID` — GitHub App ID
- `PRIVATE_KEY_B64` — Base64-encoded PKCS#8 private key

## Branch Protection

`scripts/set-branch-protection.sh` batch-applies the required status check to all repos for the configured owners.

```bash
# Dry run (shows what would change)
./scripts/set-branch-protection.sh --dry-run --owner martymcenroe

# Apply
./scripts/set-branch-protection.sh --owner martymcenroe
```

## Architecture

```
src/
  index.js          — Entry point: /health and /webhook routes
  webhook.js        — HMAC-SHA256 signature verification + event dispatch
  auth.js           — GitHub App JWT generation + installation token exchange
  checks.js         — GitHub Checks API (create check runs)
  validate.js       — PR body regex validation (issue refs, No-Issue exemption)
  verify-issues.js  — Verify referenced issues exist and are open (not PRs, not closed)
```

## Development

```bash
npm test           # vitest
npm run deploy     # wrangler deploy
```
