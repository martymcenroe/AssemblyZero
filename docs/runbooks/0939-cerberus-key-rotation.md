# 0939 - Cerberus Key Rotation and Consolidation

**Category:** Runbook / Operational Procedure
**Version:** 2.0
**Last Updated:** 2026-11-11

---

## Purpose

Rotate the Cerberus GitHub App's active private key across the fleet without breaking auto-approval mid-rotation. Also covers "consolidation" — collapsing N accumulated active keys down to 1.

Surfaced architectural finding (`unleashed#658`): no secret store returns a secret's VALUE, so direct "which key is in this secret" introspection is impossible. The only safe rotation pattern is **deploy → observe → revoke**: put the new key where it signs, see it work, and only then revoke the old one.

**Since Auto Review's retirement (#3663) the key signs in one place only: the pr-sentinel Worker.** The Worker approves each PR as Cerberus once its `issue-reference` check passes (Dependabot's excepted), with its own copy of the key. The per-repo `REVIEWER_APP_*` secrets are read by nothing (the readers were searched on #4724), so a rotation no longer touches them. The per-repo Cerberus health audit this runbook used to gate on (#1284) judged each repo by its Auto Review runs; with nothing reading a per-repo key there was nothing left for it to observe, and it is retired (#4723). The observation that remains is one Cerberus approval on one PR.

---

## Mental Model

A Cerberus App private key has three copies that matter:

1. **App-side public-half registration** — stored on the App settings page. Used by GitHub to verify JWTs signed by the corresponding private key.
2. **Operator-side encrypted blob** — `~/.secrets/cerberus-pem.gpg`. Offline copy enabling re-deploy without regenerating.
3. **The Worker's secret** — `CERBERUS_PRIVATE_KEY_B64` (with `CERBERUS_APP_ID`) in the pr-sentinel Worker, put there by `tools/cerberus_worker_key.py`. The bytes the Worker signs its JWT with before it approves a PR (`sentinel/src/cerberus.js`).

A fourth copy may linger: `REVIEWER_APP_PRIVATE_KEY` in a repo's Actions or Dependabot secrets, deployed when Auto Review still ran. Nothing reads it (#4724). A rotation leaves it holding the old key, and when the old key is revoked it becomes dead bytes, which breaks nothing. `tools/fleet_remove_cerberus_secrets.py` removes it from every repo (#4728; see the Tool Reference below), and nothing deploys it any more.

**The Worker holds ONE key.** It keeps K1 until you put K2 there.

**Revoking a key on the App page removes the public-half registration ONLY.** It does NOT touch the Worker's secret. If the Worker still holds that key, GitHub rejects its JWT, no installation token is issued, and Cerberus approves no PR in any repo: every PR sits at `mergeable_state: blocked`. **This is the failure mode the runbook is designed to prevent.**

The App supports **up to 25 active keys simultaneously**. So during a rotation, K1 and K2 are both valid until you explicitly revoke K1; mid-rotation is safe.

### Steady state

- 1 active key on the App page
- 1 encrypted blob at `~/.secrets/cerberus-pem.gpg`
- The Worker's `CERBERUS_PRIVATE_KEY_B64` holds that key's content

---

## The Rotation Procedure

Five steps. Step 3 is the safety gate; step 4 is the irreversible moment.

### Step 1: Generate K2 in the App page (browser)

1. https://github.com/settings/apps/cerberus-az → Private keys → Generate a private key
2. Browser downloads a `.pem` file (typically to `~/Downloads/` or wherever Save-As targets per runbook 0927 v6.4)
3. **Do NOT revoke K1 yet.** Both K1 and K2 are now active on the App.

### Step 2: Encrypt K2 + delete plaintext + put it in the Worker

Per runbook 0927 § Save-As recipe:

```bash
# Save the .pem outside Downloads/OneDrive to a known path, then:
gpg -c -o ~/.secrets/cerberus-pem.gpg ~/.secrets/cerberus.pem
rm ~/.secrets/cerberus.pem
```

**This OVERWRITES the K1 blob with K2.** Once done, you've lost the offline copy of K1 — that's fine, K1 still exists on the App side and in the Worker until steps 2 and 4.

Put K2 in the Worker. Run it yourself, in your own terminal, never through an agent: the key is decrypted into the process's heap (ADR-0216). From the AssemblyZero checkout:

```bash
poetry run python tools/cerberus_worker_key.py
```

Pinentry asks for the blob's passphrase. The script sets `CERBERUS_APP_ID` and `CERBERUS_PRIVATE_KEY_B64` on the Worker, prints `OK: <name> set` for each, and ends by listing the Worker's secret names. Note the time you ran it: step 3 needs an approval after it.

### Step 3: See Cerberus approve a PR — the safety gate

Open or push to any PR whose body passes `issue-reference` (landing any PR with the merge driver does this). Then read its reviews:

```bash
gh api repos/martymcenroe/{repo}/pulls/{N}/reviews --jq '.[] | select(.user.login == "cerberus-az[bot]") | "\(.state) \(.submitted_at)"'
```

Expected: an `APPROVED` line whose `submitted_at` (UTC) is later than step 2. That approval was signed with K2, so the Worker's key works.

**Do NOT proceed to step 4 without that approval.** No approval means the Worker is still on K1 or failed to sign; see Failure Recovery.

### Step 4: Revoke K1 on the App page (browser)

1. https://github.com/settings/apps/cerberus-az → Private keys
2. Click **Revoke** on K1 (the older key)
3. Confirm

After this step:
- App has only K2 active
- The Worker holds K2 and keeps approving; no break
- Any lingering per-repo `REVIEWER_APP_PRIVATE_KEY` that held K1 is now dead bytes, which nothing reads (#4724)

### Step 5: See Cerberus approve again to confirm nothing broke

Repeat step 3 on a PR opened or pushed after the revoke. An `APPROVED` line later than step 4 means the revoke broke nothing. None means the Worker was still on K1 (step 2 did not land): run step 2's `cerberus_worker_key.py` again, then step 3.

---

## The Consolidation Procedure

If you've accumulated N active keys on the App page (e.g., generated a fresh `.pem` for each of several past batches without revoking), consolidate to 1:

This is the same procedure as a single rotation. Steps 1–3 produce K_new, put it in the Worker and see Cerberus approve with it. Step 4 is the only difference: **revoke ALL the older keys at the same time**, not just one, every key on the App page EXCEPT K_new. Step 5 verifies nothing broke.

Net effect: App has only K_new active; the Worker and the encrypted blob hold only K_new.

---

## When to Rotate

| Trigger | Urgency |
|---|---|
| **Suspected key leak** | Immediate — leaked key + plaintext blob still on disk is the worst case |
| **Periodic hygiene** | Quarterly is reasonable; monthly is excessive for a solo-operator fleet |
| **App approaching 25-key limit** | Consolidation procedure (above) before the next batch creates a new key |
| **Operator-induced incident** | If a rotation went wrong (Cerberus stopped approving), the recovery IS a rotation — generate K_recovery, put it in the Worker, see Cerberus approve, revoke the broken intermediate |

---

## Failure Recovery

### No Cerberus approval after Step 2

- Confirm the PR's `issue-reference` check passed: the Worker approves only then, and never a Dependabot PR
- Confirm step 2 printed `OK: CERBERUS_PRIVATE_KEY_B64 set` and `OK: CERBERUS_APP_ID set`; if not, run it again
- The Worker logs why an approval failed, as `Cerberus approval for <owner>/<repo>#<N>: failed: ...` (`sentinel/src/webhook.js`); watch it with `npx wrangler tail` from `sentinel/` while you push to the PR again
- Do NOT proceed to step 4 until resolved

### Step 4 done, and Cerberus stops approving

- Means the Worker still held K1 at revoke time (step 2 did not land)
- Every PR's approval is broken until the Worker holds an active key
- Recovery: run `tools/cerberus_worker_key.py` again (the blob holds K2), then step 3
- This is why step 3 exists — it should catch this BEFORE step 4. Step 5 is the second chance.

### Operator wants to back out mid-rotation

- Between step 2 and step 4: free to back out. K1 is still active on the App, and the Worker works with either key. (Putting K1 back in the Worker requires the K1 blob; if step 2 already overwrote it, you'd need to regenerate K1 — impossible per GitHub's one-time-download for private keys. So in practice: don't back out after step 2 overwrote the blob; complete the rotation instead.)
- After step 4 (K1 revoked): can't go back. Forward is the only direction. If something breaks, generate K_recovery and re-rotate.

---

## Tool Reference

### `tools/cerberus_worker_key.py` (operator-run)

```bash
poetry run python tools/cerberus_worker_key.py
```

- Decrypts `~/.secrets/cerberus-pem.gpg` in-process (pinentry), converts the PEM to base64 PKCS#8 and pipes it to `wrangler secret put CERBERUS_PRIVATE_KEY_B64`; sets `CERBERUS_APP_ID` from `config/fleet-ids.json`
- The key never reaches argv, the environment, a file or the screen; the run ends by listing the Worker's secret names
- Issue: #3663

### `tools/fleet_remove_cerberus_secrets.py` (operator-run, not part of a rotation)

From the AssemblyZero checkout, in your own terminal (Ubuntu bash, or Git Bash on Windows). The first command is a dry run that lists every repo holding either secret and deletes nothing; the second deletes them.

```bash
poetry run python tools/fleet_remove_cerberus_secrets.py
poetry run python tools/fleet_remove_cerberus_secrets.py --apply
```

- Removes the per-repo `REVIEWER_APP_ID` and `REVIEWER_APP_PRIVATE_KEY`, in the Actions and the Dependabot scope, from every repo you own. Nothing reads them since Auto Review's retirement (#4724); the Worker signs with its own secrets, so removing them breaks nothing
- Touches no other secret; reads each deletion back; stops at the first failure with exit 1 and names it; a rerun skips the repos already clean
- ADR-0216-compliant (in-process classic PAT decryption, no env-block exposure). `--repo NAME` limits a run to one repo
- Issue: #4728. It replaces the per-repo deploy tool, which is retired, so nothing deploys these secrets again

---

## Related

- [`0927-new-repo-human-checklist.md`](0927-new-repo-human-checklist.md) — new-repo creation (Cerberus PEM gpg setup is documented there)
- [`0930-gpg-and-classic-pat-rotation.md`](0930-gpg-and-classic-pat-rotation.md) — sibling for the classic PAT
- ADR-0216 — in-process classic PAT pattern (`cerberus_worker_key.py` and `fleet_remove_cerberus_secrets.py` use it)
- unleashed#658 — architectural finding that motivated this runbook
- AZ wiki "Closing the Agent Self-Authorization Loop" — Cerberus architecture overview + failure-mode taxonomy
