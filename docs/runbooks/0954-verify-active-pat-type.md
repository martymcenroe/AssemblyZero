# Runbook 0954: Verify Active PAT Type Non-Destructively

## Purpose
Operators frequently switch between a Fine-Grained (Limited) PAT and a Classic PAT depending on the required privileges (e.g., as governed by ADR-0216). This runbook documents how an operator can non-destructively verify which token is currently active in their system prompt.

## Background
- **Limited (Fine-Grained) PATs** are scoped strictly to specific repositories and lack high-risk privileges like `.github/workflows` modification (`workflow` scope).
- **Classic PATs** are broadly scoped and possess potentially dangerous permissions (e.g., `repo`, `workflow`, `admin:org`).

To avoid accidental destructive actions or triggering security alarms, it is crucial to confirm the active PAT type before executing scripts or API calls.

## Verification Methods

### Method 1: Check Token Prefix (Recommended)
GitHub intrinsically encodes the token type into the token prefix.

Run the following command:
```bash
gh auth status
```

In the output, examine the **Token:** line:
- If it starts with **`github_pat_`**, you are using a **Limited (Fine-Grained) PAT**.
- If it starts with **`ghp_`**, you are using a **Classic PAT**.

### Method 2: Inspect API Headers
If you need to programmatically or explicitly verify the actual OAuth scopes recognized by the GitHub API, you can inspect the HTTP headers returned by the `/user` endpoint.

Run the following command:
```bash
gh api /user -i | grep -i x-oauth-scopes
```

- **Classic PATs:** The command will output an `X-OAuth-Scopes:` header listing all active scopes.
  *Example:* `X-OAuth-Scopes: admin:repo_hook, repo, workflow`
- **Limited PATs:** The command will output nothing but the CORS `Access-Control-Expose-Headers` line. Fine-Grained PATs **do not** return the `X-OAuth-Scopes` header.

## Related Documents
- [ADR-0216: In-Process Classic PAT Decryption](../adrs/0216-in-process-classic-pat-decryption.md)
