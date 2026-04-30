# GPG + Classic PAT Rotation

Run all console commands in **Git Bash** on Windows. With `default-cache-ttl 0` set in `~/.gnupg/gpg-agent.conf` (per ADR-0216 / 2026-04-30 hardenings), every `gpg` call will pop a pinentry-w32 dialog — that is correct.

## What this rotates

1. The **GitHub classic PAT** itself (revokes old, generates new at github.com).
2. The **gpg passphrase** used to encrypt it (you'll choose a fresh one).

After this, any compromise of the previous gpg passphrase is mooted (it no longer protects a valid PAT), and any earlier PAT exfiltration is mooted (revoked at GitHub).

If you only want to rotate the gpg passphrase WITHOUT rotating the PAT, skip Sections 1 and 7. The same procedure works — the input plaintext is just the existing PAT instead of a new one.

---

## Section 1 — Generate a new GitHub classic PAT (web)

1. Open https://github.com/settings/tokens in your browser.
2. In the "Personal access tokens (classic)" list, find the existing classic PAT. **Don't delete it yet** — you delete it in Section 7 after the new one is in place.
3. Click **Generate new token (classic)**.
4. Note: pick a name, e.g. `Classic PAT YYYY-MM-DD rotation`.
5. Expiration: 90 days recommended. Avoid "No expiration."
6. Scopes: match the old token. For this fleet's typical use that's `repo` (full) and `workflow`. If you had any additional scopes (`admin:org`, `admin:repo_hook`, `delete_repo`, etc.) match them too — `gh` API operations will fail mysteriously if a scope is dropped.
7. Click **Generate token** at the bottom.
8. Token is shown ONCE on the next screen. Copy it to clipboard with the copy icon.

Leave the browser tab open. You'll come back to it in Section 7.

---

## Section 2 — Back up the current encrypted file

```
cp ~/.secrets/classic-pat.gpg ~/.secrets/classic-pat.gpg.bak-$(date +%Y-%m-%d)
```

If anything goes wrong in Sections 3–6, restore with:
```
cp ~/.secrets/classic-pat.gpg.bak-YYYY-MM-DD ~/.secrets/classic-pat.gpg
```

Section 8 deletes this backup after you've confirmed the rotation worked.

---

## Section 3 — Encrypt the new PAT to a new passphrase

The new PAT is on your clipboard from Section 1.8. Encrypt it to a fresh file:

```
cat /dev/clipboard | gpg --symmetric --cipher-algo AES256 -o ~/.secrets/classic-pat.gpg.new
```

Behavior:
- pinentry-w32 dialog pops up: **Enter the NEW passphrase**, then again for confirmation. Pick a strong one, distinct from the old. Memorize or record in your password manager.
- A new file `classic-pat.gpg.new` is written. The original `classic-pat.gpg` is untouched.

---

## Section 4 — Clear the clipboard

The new PAT plaintext is still on your clipboard. Wipe it:

```
powershell.exe -Command "Set-Clipboard -Value ''"
```

Verify:
```
cat /dev/clipboard
```
Should print nothing.

---

## Section 5 — Verify the new file decrypts

```
gpg --decrypt ~/.secrets/classic-pat.gpg.new > /dev/null
echo "exit: $?"
```

- pinentry prompts for the NEW passphrase.
- `exit: 0` = decrypt succeeded; rotation is good to commit.
- `exit: 2` = decrypt failed (wrong passphrase or corrupted file). STOP. Re-do Section 3 — do not proceed to Section 6.

---

## Section 6 — Atomic swap and end-to-end verification

```
mv ~/.secrets/classic-pat.gpg ~/.secrets/classic-pat.gpg.old
mv ~/.secrets/classic-pat.gpg.new ~/.secrets/classic-pat.gpg
```

End-to-end verification with the v3 tool:

```
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python -c "from tools._pat_session import classic_pat_session
with classic_pat_session() as p:
    print(f'OK len={len(p)} prefix={p[:4]}')"
```

- pinentry prompts for the NEW passphrase.
- Should print `OK len=40 prefix=ghp_` (classic PATs are 40 chars after `ghp_`, so total len = 44; if your PAT is `github_pat_...` it's a fine-grained PAT, length ~93 — but you generated a classic PAT, so expect `ghp_`).

If this prints `OK ...`, the rotation is fully working end-to-end.

---

## Section 7 — Revoke the OLD GitHub PAT (web)

1. Return to https://github.com/settings/tokens.
2. Find the OLD classic PAT (the one created BEFORE today). It will have an older "Last used" date than the one you just created.
3. Click **Delete** next to it. Confirm.

The old PAT is now revoked at GitHub. Even if it was exfiltrated at any point in the past, it cannot authenticate any further API calls.

---

## Section 8 — Securely delete old files

```
shred -uvz ~/.secrets/classic-pat.gpg.old
shred -uvz ~/.secrets/classic-pat.gpg.bak-YYYY-MM-DD
```

If `shred` isn't on your system (ships with Git for Windows / MSYS2 coreutils — should be there), fall back:
```
rm -f ~/.secrets/classic-pat.gpg.old ~/.secrets/classic-pat.gpg.bak-YYYY-MM-DD
```

`rm` doesn't overwrite the data; on a developer single-user machine that's typically acceptable since SSDs handle this through TRIM, but `shred` is the belt-and-suspenders move.

---

## After rotation — what changed

| | Before rotation | After rotation |
|---|---|---|
| Old gpg passphrase compromised? | Possibly — unknown, can't audit | Doesn't matter — it now decrypts a revoked PAT |
| Old PAT exfiltrated? | Possibly — unknown | Doesn't matter — revoked at GitHub |
| Current attack surface | Software-only design: heap-read on running scripts during the seconds PAT is in scope | Same. Phase 1 of #1016 (move gpg key to YubiKey) closes the at-rest gap structurally. |

## Sanity-check the next agent session

After this rotation, when an agent (Claude Code, Codex, Gemini) attempts to use a `classic_pat_session()` script:
- The user runs the script, not the agent (per `_pat_session.py` docstring + root `CLAUDE.md` gotchas section).
- pinentry prompts for the NEW passphrase. The OLD passphrase will fail.
- If anything tries to use the OLD PAT against GitHub it will fail with 401 — making any latent compromise immediately visible.

The rotation, combined with the existing TTL=0 + agent-must-not-run rules, makes a previously-undetectable potential compromise into a self-revealing one: the next time the old credential gets used (legitimately or otherwise), the failure surfaces.

## When to run this runbook

- Suspected compromise of either the gpg passphrase or the classic PAT.
- Periodic rotation hygiene (recommended: every 90 days, matching PAT expiration).
- After Phase 1 of #1016 (YubiKey migration) — the rotation procedure changes when the gpg key lives on hardware; this runbook should be updated then.
- After any incident where pinentry prompted for a passphrase that an agent or other-user-process could have observed.

## Related

- ADR-0216 — `docs/adrs/0216-in-process-classic-pat-decryption.md`
- `tools/_pat_session.py` — the v3 implementation; docstring documents TTL=0 mandate and agent-must-not-run rule
- Issue #1016 — Phase 1 of post-ADR-0216 hardening: move gpg key to YubiKey
- Root `CLAUDE.md` — "When `git push` Is Rejected For Workflow Scope" section + "Gotchas (learned the hard way 2026-04-30)" subsection
