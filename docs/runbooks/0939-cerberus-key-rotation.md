# 0939 - Cerberus Key Rotation and Consolidation

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-05-25

---

## Purpose

Rotate the Cerberus GitHub App's active private key across the fleet without breaking auto-approval mid-rotation. Also covers "consolidation" — collapsing N accumulated active keys down to 1.

Surfaced architectural finding (`unleashed#658`): GitHub Apps' Actions Secrets API never returns secret VALUES, so direct "which key is in this secret" introspection is impossible. The only safe rotation pattern is **deploy → observe → revoke**, with the audit tool (`tools/audit_cerberus_health.py`, AZ#1284) as the safety gate between deploy and revoke.

---

## Mental Model

A Cerberus App private key has three independent copies:

1. **App-side public-half registration** — stored on the App settings page. Used by GitHub to verify JWTs signed by the corresponding private key.
2. **Operator-side encrypted blob** — `~/.secrets/cerberus-pem.gpg`. Offline copy enabling re-deploy without regenerating.
3. **Per-repo secret** — `REVIEWER_APP_PRIVATE_KEY` in each repo's Actions Secrets storage. The bytes the `auto-reviewer.yml` workflow reads at run time to sign JWTs.

**Each repo independently holds ONE key.** A repo deployed yesterday with K1 keeps K1 in its secret until you re-deploy K2 to overwrite it.

**Revoking a key on the App page removes the public-half registration ONLY.** It does NOT touch any per-repo secret. Every per-repo secret that held that key becomes useless because GitHub no longer accepts JWTs signed by it. **This is the failure mode the runbook is designed to prevent.**

The App supports **up to 25 active keys simultaneously**. So during a rotation, K1 and K2 are both valid until you explicitly revoke K1. Repos with K1 in their secret still work; repos with K2 also work; mid-rotation is safe.

### Steady state

- 1 active key on the App page
- 1 encrypted blob at `~/.secrets/cerberus-pem.gpg`
- Every repo's `REVIEWER_APP_PRIVATE_KEY` secret holds that key's content

---

## The Rotation Procedure

Five steps. Step 3 is the safety gate; step 4 is the irreversible moment.

### Step 1: Generate K2 in the App page (browser)

1. https://github.com/settings/apps/cerberus-az → Private keys → Generate a private key
2. Browser downloads a `.pem` file (typically to `~/Downloads/` or wherever Save-As targets per runbook 0927 v6.4)
3. **Do NOT revoke K1 yet.** Both K1 and K2 are now active on the App.

### Step 2: Encrypt K2 + delete plaintext + deploy fleet-wide

Per runbook 0927 § Save-As recipe:

```bash
# Save the .pem outside Downloads/OneDrive to a known path, then:
gpg -c -o ~/.secrets/cerberus-pem.gpg ~/.secrets/cerberus.pem
rm ~/.secrets/cerberus.pem
```

**This OVERWRITES the K1 blob with K2.** Once done, you've lost the offline copy of K1 — that's fine, K1 still exists on the App side and in every repo's secret until step 4.

Deploy K2 to the entire fleet:

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/deploy_cerberus_secrets.py \
    --cerberus-pem-gpg ~/.secrets/cerberus-pem.gpg --all
```

`--all` overwrites every repo's `REVIEWER_APP_PRIVATE_KEY` with K2. The script reports `OK` per repo. Any failures must be investigated before step 3.

### Step 3: Audit the fleet — the safety gate

```bash
poetry run python tools/audit_cerberus_health.py --days 7
```

Expected output:

- **`HEALTHY (N)`** — all repos with recent successful Auto Review runs. They authenticated against the App; the deployed key (now K2) works.
- **`UNCERTAIN (M)`** — recent failures. Must be investigated. Could be Mode A old caller format, transient, or — if the failure is new — your deploy didn't land. Common cause of NEW uncertainty: the deploy script reported OK but the repo's workflow hasn't been re-triggered since.
- **`UNKNOWN (K)`** — no recent non-dependabot runs. Either the repo is inactive (no PRs), or you need a synthetic trigger to verify K2 works.

**Do NOT proceed to step 4 until every repo is either HEALTHY or accounted for in your incident log.** For UNKNOWN repos: open a small synthetic PR (`No-Issue: cerberus rotation verification`), watch the Auto Review check, close the PR. For UNCERTAIN repos: diagnose the specific failure (Mode A → fix caller; persistent failure → escalate).

### Step 4: Revoke K1 on the App page (browser)

1. https://github.com/settings/apps/cerberus-az → Private keys
2. Click **Revoke** on K1 (the older key)
3. Confirm

After this step:
- App has only K2 active
- Every repo's `REVIEWER_APP_PRIVATE_KEY` holds K2's content
- Workflows continue to authenticate; no break

### Step 5: Re-audit to confirm nothing broke

```bash
poetry run python tools/audit_cerberus_health.py --days 1
```

Should show the same `HEALTHY` set as step 3. If anything moved from HEALTHY to UNCERTAIN immediately after the revoke, K1 was still in that repo's secret somehow (your deploy missed it) — re-run step 2 and step 3 for the affected repo.

---

## The Consolidation Procedure

If you've accumulated N active keys on the App page (e.g., generated a fresh `.pem` for each of several past batches without revoking), consolidate to 1:

This is the same procedure as a single rotation. Steps 1–3 produce K_new and verify every repo holds it. Step 4 is the only difference: **revoke ALL the older keys at the same time**, not just one. Step 5 verifies nothing broke.

```bash
# After step 3 confirms HEALTHY across the fleet against K_new:
# In the browser, revoke every key on the App page EXCEPT K_new.
# Then re-audit:
poetry run python tools/audit_cerberus_health.py --days 1
```

Net effect: fleet was using a mix of K1, K2, K3, ...; now all on K_new; App has only K_new active; encrypted blob holds only K_new.

---

## When to Rotate

| Trigger | Urgency |
|---|---|
| **Suspected key leak** | Immediate — leaked key + plaintext blob still on disk is the worst case |
| **Periodic hygiene** | Quarterly is reasonable; monthly is excessive for a solo-operator fleet |
| **App approaching 25-key limit** | Consolidation procedure (above) before the next batch creates a new key |
| **Operator-induced incident** | If a rotation went wrong (UNCERTAIN repos), the recovery IS a rotation — fix the broken ones, generate K_recovery, deploy, audit, revoke the broken intermediate |

---

## Failure Recovery

### Audit shows UNCERTAIN after Step 2 deploy

- Re-run `deploy_cerberus_secrets.py` for the specific repo: `--repo NAME`
- Re-run `audit_cerberus_health.py --repo NAME`
- If still UNCERTAIN: inspect the most recent Auto Review run via `gh run view --repo {repo} --log` and diagnose by failure signature (Mode A old caller format, missing scope, etc. — see AZ wiki Cerberus pipeline page)
- Do NOT proceed to step 4 until resolved

### Audit shows UNKNOWN after Step 2

- The repo has no recent Auto Review runs to observe; deploy succeeded but the new key is untested
- Trigger a synthetic PR: tiny diff, `No-Issue: cerberus rotation verification`, push, watch Auto Review check, close PR + delete branch when done
- Re-run audit; should flip to HEALTHY

### Step 4 done, but some repo immediately UNCERTAIN

- Means K1 was still active in that repo's secret at revoke time (your step-2 deploy missed it for some reason)
- The repo's auto-approval is broken until you re-deploy K2
- Recovery: `deploy_cerberus_secrets.py --cerberus-pem-gpg ~/.secrets/cerberus-pem.gpg --repo NAME`
- Re-audit
- This is why step 3 exists — it should catch this BEFORE step 4. Step 5's re-audit is the second chance.

### Operator wants to back out mid-rotation

- Between step 2 and step 4: free to back out. K1 is still active on App; some repos may have K2 in their secret; some may have K1. Both work. Re-deploy K1 with `--all` to restore uniformity. (Requires keeping the K1 blob; if step 2 already overwrote it, you'd need to regenerate K1 — impossible per GitHub's one-time-download for private keys. So in practice: don't back out after step 2 overwrote the blob; complete the rotation instead.)
- After step 4 (K1 revoked): can't go back. Forward is the only direction. If something breaks, generate K_recovery and re-rotate.

---

## Tool Reference

### `tools/audit_cerberus_health.py` (read-only)

```bash
poetry run python tools/audit_cerberus_health.py [--repo NAME] [--days N] [--include-not-deployed]
```

- Read-only fleet scan via `gh api`
- Classifies each repo: HEALTHY / UNCERTAIN / UNKNOWN / NOT_DEPLOYED
- Exit 1 if any UNCERTAIN — CI-friendly gate for rotation scripts
- No classic PAT, no pinentry, no secrets touched, no PRs opened
- Issue: #1284, PR #1285

### `tools/deploy_cerberus_secrets.py`

```bash
poetry run python tools/deploy_cerberus_secrets.py \
    --cerberus-pem-gpg ~/.secrets/cerberus-pem.gpg [--all | --repo NAME]
```

- Deploys the encrypted blob's key content to one or all repos as `REVIEWER_APP_PRIVATE_KEY` + `REVIEWER_APP_ID`
- ADR-0216-compliant (in-process classic PAT decryption, no env-block exposure)
- Reports per-repo OK/FAILED
- Issue lineage: AZ#1007 (in-process classic PAT migration), AZ#1254 (`--cerberus-pem-gpg` support)

---

## Related

- [`0927-new-repo-human-checklist.md`](0927-new-repo-human-checklist.md) — new-repo creation (Cerberus PEM gpg setup is documented there)
- [`0930-gpg-and-classic-pat-rotation.md`](0930-gpg-and-classic-pat-rotation.md) — sibling for the classic PAT
- ADR-0216 — in-process classic PAT pattern (deploy_cerberus_secrets uses it)
- unleashed#658 — architectural finding that motivated this runbook
- AZ wiki "Closing the Agent Self-Authorization Loop" — Cerberus architecture overview + failure-mode taxonomy
