# 0941 — Restore `gh` CLI auth using the fine-grained PAT (`llm-restricting`)

> **Version:** 1.0.2
> **Last updated:** 2026-05-29 10:40 PM Central
> **Applies to:** Operator workstation where `gh` CLI is the day-to-day GitHub interface. The standing fine-grained PAT for this fleet is named `llm-restricting`. Its declared purpose, taken from its GitHub settings page: *"Create and manage restricted GitHub Fine-Grained Personal Access Tokens (PATs) for AI agents (Claude Code, Gemini CLI, etc.). Agents get enough permission to do their work but cannot bypass branch protection, force-push, or perform admin actions."* Tokens with admin authority are out of scope here; that path is [ADR-0216](../adrs/0216-in-process-classic-pat-decryption.md)'s in-process classic PAT.
> **Fleet policy:** **OAuth is forbidden. Period.** `gh` runs on `llm-restricting` exclusively. If the browser-based `gh auth login` OAuth flow ever fires, that is a procedural error — see §3b.
> **Tracking issue:** TBD — file once `gh auth` is restored (see §9 change log)

## 1. The problem

You're here because `gh` stopped working — `gh auth status` says "the token in default is invalid," `git push` or `git fetch` against github.com pops the Git for Windows credential prompt, or both at the same time. This runbook restores `gh` auth using `llm-restricting`, the fleet's standing fine-grained PAT.

### 1a. The standing trigger: Windows 11 wipes Credential Manager

`gh` on this workstation stores its credential in Windows Credential Manager (the file at `%AppData%\GitHub CLI\hosts.yml` contains metadata only — no token). **Windows 11 updates wipe Credential Manager entries with depressing regularity.** When `gh` suddenly returns "invalid token" after a working session, the assumed cause is a Windows 11 update — not a token rotation at GitHub, not a network issue, not anything you did. Verify by:

- `cmdkey /list` (Git Bash: `cmd.exe //c "cmdkey /list"`) showing no github-related entry where one used to exist
- A recent Windows Update in the system event log (around the time `gh` started failing)
- `git fetch` against github.com prompting for credentials in the Git for Windows dialog (because Git Credential Manager's underlying github.com entry was wiped too)

That signature ⇒ Windows 11 wiped the cache. Re-loading `llm-restricting` via §3 is the recovery. No PAT regeneration is required if you have the existing token value available; if you don't, §3a covers regenerating it (which invalidates the prior value, so be deliberate).

### 1b. Why OAuth is forbidden here

`gh auth login` (the browser flow) defaults to OAuth. The "GitHub CLI" OAuth grant accumulates scopes over time — every `gh auth refresh -s <scope>` call adds one and the broader scope set persists on the grant until revoked. A grant that has been live for months can carry `delete_repo`, `admin:public_key`, `admin:project`, `user`, `admin:org`, and similar admin-equivalent scopes.

That grant lives silently in `gh`'s config and is selected for:

- Every `gh ...` CLI command
- Every `git push/fetch/clone` against `github.com`, because the global credential helper is `!'gh' auth git-credential` (confirm with `git config --global --get-all credential.https://github.com.helper`)

**No pinentry interaction is required to use it.** This bypasses the [ADR-0216](../adrs/0216-in-process-classic-pat-decryption.md) threat model. ADR-0216 puts admin-scope authority behind a GPG-encrypted classic PAT that requires the operator's passphrase per use. A broad-scope `gh` OAuth grant is a parallel channel with the same blast radius and **no per-use consent**. An agent running `gh repo delete`, `gh ssh-key delete`, or `gh api -X DELETE /repos/...` from its Bash tool would use this token silently. The mitigations (banned-commands list in `CLAUDE.md`, Bash-tool permission prompts, auto-classifier hooks) are instruction-level or approval-fatigue-prone — weaker than ADR-0216's pinentry gate.

This is why the fleet policy in the header is "OAuth is forbidden. Period." `llm-restricting` does the day-to-day work; ADR-0216's classic PAT (pinentry-gated, in-process) does the rare admin-scope work. There is no third channel.

## 2. Trade-offs to know before starting

- **Fine-grained PATs cannot fork arbitrary external repos.** `POST /repos/{owner}/{repo}/forks` requires writing into a target the PAT is not pinned to. Tools that fork third-party repos (e.g. `gh-link-auditor`'s `n6_submit_pr.py:_fork_repo`) require a classic PAT instead — they already do, per `gh-link-auditor/data/issue-body-least-priv-pat.md`.
- **Not every GitHub API endpoint supports fine-grained PATs yet.** Most do as of 2026; gaps surface as `403 Resource not accessible by personal access token`. Workaround: classic PAT for the specific call, via the ADR-0216 in-process pattern.
- **Tools that already use `_pat_session.classic_pat_session()` are unaffected.** They never read `gh`'s stored credential. This runbook only changes what `gh ...` and `git push/fetch` use.

## 2.5. Where the PAT lives long-term

`llm-restricting` lives in two places at most:

1. **At GitHub** — the master record. Its settings page (name, scope, expiry, repository access list) is at `https://github.com/settings/tokens?type=beta`, then click `llm-restricting` in the list. The token VALUE is shown only at creation or regeneration — never again afterward. GitHub itself is the source of truth for the slot; the value is recoverable from GitHub only by **regeneration** (which invalidates the prior value).
2. **On your workstation, optionally** — if you keep a local copy of the value (encrypted at rest, the same way `~/.secrets/classic-pat.gpg` holds the classic PAT), you can re-load `gh` from it without regenerating. If you don't keep a local copy, your recovery path is "regenerate at GitHub and load the new value." Both paths are supported by this runbook.

What the runbook does NOT prescribe: which of those two paths to use. Pick one and be consistent. The decision matters at recovery time, not at this moment, but the runbook's §3 splits accordingly.

What is NOT a long-term storage location: `gh`'s own config (gets wiped by Windows 11 updates — §1a), the transient `pat.txt` in §3c (gets `rm`'d at the end of §3c), a OneDrive-synced folder, a repo, or shell history. None of these survive what they need to survive.

## 3. Procedure

Three entry points, depending on how you keep `llm-restricting`'s value between operations (see §2.5):

- **You have the value in your local long-term storage** (encrypted file, password manager, etc.) — read it from there, skip §3a, go to §3b then §3c.
- **You do not have the value locally — `llm-restricting` is still the right token, but you need to regenerate it at GitHub to recover the value** — start at §3a (the "Regenerate token" button on the existing slot, not "Generate new token"). The regeneration keeps the name, scopes, and ID; only the value changes.
- **You are setting up `llm-restricting` for the first time** (new workstation, first use of this runbook, the slot doesn't exist on GitHub) — start at §3a using "Generate new token." Match the established scope set documented in §3a.7.

### 3a. Generate or regenerate the fine-grained PAT (skip if you already have the value locally)

1. Open `https://github.com/settings/tokens?type=beta` in an **incognito** browser window. (Incognito matters here because this page either displays the new value once, or the regeneration screen does — keeping that one-time-display out of normal browsing history reduces leak surfaces.)
2. **If `llm-restricting` already exists in the list:** click it, scroll to "Regenerate token," confirm. The new value is shown once.
3. **If you are creating from scratch:** click "Generate new token" → fine-grained. Continue with the rest of this section.
3. **Token name:** descriptive — e.g. `gh-cli-workstation-<hostname>`.
4. **Expiration:** 90 days is a reasonable default. Longer expirations defeat rotation discipline; shorter is fine if you don't mind redoing this runbook more often.
5. **Resource owner:** `martymcenroe`.
6. **Repository access:** "All repositories" matches the OAuth grant's account-wide reach. "Only select repositories" is tighter — choose the actual day-to-day set if you want narrower blast radius.
7. **Repository permissions** (minimum for `gh issue`, `gh pr`, `gh repo view`, `gh api`):
   - Contents: **Read and write**
   - Pull requests: **Read and write**
   - Issues: **Read and write**
   - Metadata: **Read** (mandatory; cannot be unchecked)
   - Workflows: **Read and write** (only if you push commits that touch `.github/workflows/*.yml`)
   - Administration: leave at **No access** (this is where `delete_repo` equivalents live)
8. **Account permissions:** leave all at "No access" unless you have a specific need.
9. Click "Generate token". The PAT is shown ONCE. Leave the page open in the browser tab — you'll consume it in §3c without copying it through the clipboard, ideally.

### 3b. Verify no `GitHub CLI` OAuth grant exists (mandatory)

Per fleet policy (header), OAuth is forbidden. This step confirms no OAuth grant exists server-side. Do it every time you run this runbook — it's the only place an OAuth grant can appear silently (e.g., if a stray `gh auth login` browser flow ever fired and was completed in a moment of confusion).

1. Open `https://github.com/settings/applications` in the same incognito window.
2. Look in the **Authorized OAuth Apps** list for "GitHub CLI."
3. If it exists, click **Revoke**. Do not proceed to §3c until the entry is gone.
4. If it does NOT exist, you are correctly in the fine-grained-PAT-only posture. Continue to §3c.

The server-side grant is what carries the broad scopes. Revoking it eliminates the bypass channel entirely. The OAuth grant has no legitimate use in this fleet — there is no scenario where it should be left in place.

### 3c. Load the PAT into `gh`

Retrieve the PAT from your long-term storage (§2.5) — `gpg --decrypt` if you store it the same way as the classic PAT, copy from your password manager, or read off the GitHub one-time-display page if you just created a new one in §3a. Then run the steps below.

Run from your terminal. **The agent should not run these.** The PAT value passes through your shell briefly; the agent has no need to see it.

```bash
# 1. Create a non-OneDrive staging path if it doesn't exist.
mkdir -p /c/Users/mcwiz/.secrets/staging

# 2. Read the PAT from stdin with terminal echo disabled.
#    Paste the PAT, press Enter. Nothing appears on screen.
read -rs pat

# 3. Write the PAT to a file via shell redirect.
#    The redirect captures printf's stdout into the file — nothing prints to the terminal.
printf '%s' "$pat" > /c/Users/mcwiz/.secrets/staging/pat.txt

# 4. Clear the shell variable.
unset pat

# 5. Load into gh. The path is in argv (acceptable); the value travels via stdin.
gh auth login --with-token -h github.com < /c/Users/mcwiz/.secrets/staging/pat.txt

# 6. Verify (without printing the token value).
#    gh auth status with no -t shows the account line + masked token.
#    Then gh api user --jq .login confirms the token is valid by hitting the API.
gh auth status
gh api user --jq .login

# 7. Delete the file from disk. Shell rm bypasses Recycle Bin.
rm /c/Users/mcwiz/.secrets/staging/pat.txt
```

### 3d. Clean the remaining surfaces

```bash
# Clipboard — if you copied the PAT from the GitHub page (instead of typing/pasting via read -rs),
# it's still in the OS clipboard until overwritten.
powershell.exe -NoProfile -Command "Set-Clipboard -Value \$null"

# Recycle Bin — insurance in case any path touched File Explorer's delete.
powershell.exe -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"
```

Two surfaces have no clean command-line clear and need a manual step if you used them:

- **Clipboard history** (the Win+V ring buffer, up to 25 entries):
  - Check whether it's enabled: Settings → System → Clipboard → "Clipboard history" toggle.
  - View the buffer: Win + V.
  - Clear: Settings → System → Clipboard → "Clear clipboard data" button, or click the trash icon next to individual items in the Win+V panel.
  - If it was off going into §3c, no action needed. If it was on and you copied the PAT through it, clear before continuing.
- **Browser download history** — only relevant if you downloaded (not copied) the PAT. Using incognito at §3a.1 avoids it.

## 4. Verification

Do NOT use `gh auth status -t` to verify — the `-t` flag prints the full token value to stdout, which lands in session transcripts and shell history. Use the masked-display + API-call combination instead:

```bash
gh auth status                          # masked token; shows account + token type prefix only
gh api user --jq .login                 # round-trip to GitHub; returns "martymcenroe" if valid
```

Expected output for `gh auth status`:

- `Logged in to github.com account martymcenroe`
- `Active account: true`
- `Token: github_pat_************` — **the `github_pat_` prefix is the load-bearing signal that you are on a fine-grained PAT.** If you instead see `gho_************` (OAuth) or `ghp_************` (classic), **STOP** — `llm-restricting` was not loaded, and you are violating the fleet policy. Go back to §3c and re-load.
- A `Token scopes:` line — fine-grained PATs don't expose classic scopes here; the line may be empty or absent. That's expected. Per-repo permissions are server-side.

Expected output for `gh api user --jq .login`: the single word `martymcenroe`. Anything else (401, 403, network error) means the token is loaded but rejected at the API.

Smoke tests (run against any repo `llm-restricting` is pinned to — per the screenshot the slot has "access to all repositories owned by you," so any martymcenroe/* repo works):

```bash
gh issue list --repo martymcenroe/Aletheia --limit 1
gh repo view martymcenroe/Aletheia --json name
git -C /c/Users/mcwiz/Projects/Aletheia fetch origin --dry-run
```

All three should succeed silently. If `gh issue list` returns `HTTP 401`/`403`, `llm-restricting`'s permissions don't cover the call — go back to GitHub, edit the token's permissions, and re-run §3c.

Negative test — confirm `llm-restricting` lacks admin authority by design. The token's User Permissions section is empty and Repository Administration is at "No access" (per the screenshot), so any destructive admin operation should fail at the API layer regardless of any agent rule or instruction. You do not need to actually run a destructive command to verify this; the screenshot is the verification.

## 5. Rollback

**There is no OAuth fallback in this fleet** — re-authorizing OAuth violates the header policy. If something breaks, the two legitimate paths are:

1. **`llm-restricting` is missing a permission** — open the token at `https://github.com/settings/tokens?type=beta`, click `llm-restricting`, edit Repository Permissions to add what's needed, then re-run §3c. The token value does not change on permission edits, so the local value you loaded is still good — but if you also regenerate the value at the same time, treat it as a §3a regeneration and re-do §3c with the new value.
2. **The failing operation genuinely needs admin-scope** — that's an ADR-0216 classic-PAT job by design, not a `gh` job. `llm-restricting`'s declared purpose is explicitly "agents cannot bypass branch protection, force-push, or perform admin actions." If the workflow needs to do one of those things, write a one-shot Python script that uses `with classic_pat_session() as pat:` and runs against the GitHub REST API directly, the same way the existing 23 ADR-0216 callers do. The agent observes the result; the operator runs the script.

If neither path applies — for example, a fine-grained PAT API gap that GitHub hasn't filled yet — file an issue describing the operation and what GitHub returned. Do not paper over it by re-authorizing OAuth.

## 6. Re-loading (the recurring case) and rotation (the periodic case)

This runbook gets used in two distinct rhythms.

### 6a. Re-loading after Windows 11 wipes Credential Manager — the recurring case

This is the dominant reason you'll see this runbook. Windows 11 updates invalidate or wipe Windows Credential Manager entries unpredictably. The `llm-restricting` value at GitHub is unchanged; the local credential is gone. Symptom signature:

- `gh auth status` returns "the token in default is invalid"
- `git fetch`/`git push` against `github.com` pops the Git for Windows credential prompt
- Both at roughly the same time
- A Windows Update happened on or shortly before that timestamp

**Recovery is just §3c** — re-load the same `llm-restricting` value from your local storage (if you keep one) or from a fresh regeneration (§3a, "Regenerate token" on the existing slot). No rotation paperwork required because the token at GitHub is the same one, with the same name, the same scopes, and the same expiry. Only `gh`'s local cache changed (it got wiped). Skip §3b's revoke step only if you've already confirmed no OAuth grant exists (it shouldn't, by policy).

If this happens often enough to be annoying, consider whether Windows Credential Manager is the right local store for this PAT in this environment. The alternative is keeping `llm-restricting`'s value in a GPG-encrypted file in `~/.secrets/` (same pattern as the classic PAT) and re-loading it into `gh` after each wipe — same number of steps, but the master copy outlives the wipe.

### 6b. Rotation — the periodic case

Separate from re-loading: `llm-restricting` also has a real expiry (per the screenshot, the current expiry is **Mon, Jun 22 2026**; default for new fine-grained PATs is 90 days). When it expires, GitHub stops honoring the value. When you regenerate it for any reason (scope change, suspected compromise, expiry), the value at GitHub changes — and the value needs updating in **two places**:

1. **Your local long-term storage** (encrypted file, password manager, etc., per §2.5), if you keep one. The old value is now invalid; replace it with the new one.
2. **`gh`'s loaded credential** — re-run §3c to overwrite. Verify via §4.

Order: regenerate at GitHub first, update local storage second, run §3c third. Doing §3c before updating local storage means the next wipe leaves you with no recoverable copy.

If you don't keep a local copy at all, your recovery is "regenerate at GitHub and load the new value" every time — fewer surfaces to keep in sync, but every re-load requires browser access at the moment.

## 7. Why not paste the PAT into a text editor (Sublime, VS Code, Notepad++)

The terminal `read -rs` + `printf > file` flow has two intermediate surfaces: the shell variable (process memory, cleared by `unset`) and the file (cleared by `rm`). A GUI editor adds three more:

- **Editor session persistence.** Sublime Text's Hot Exit (on by default) saves the full buffer of every open file — including saved files — into `%APPDATA%\Sublime Text\Local\Session.sublime_session` when the editor closes. The PAT persists in that file across restarts, well after you `rm pat.txt`. VS Code's hot exit (`workbench.editor.enableHotExit`) and Notepad++'s session restore behave similarly.
- **Recent files list.** Editors record the path and surface it on the next open. Harmless on its own, but a breadcrumb.
- **Auto-appended trailing newline.** Most editors append `\n` on save by default. `gh auth login --with-token` tolerates that; some fleet Python scripts that strip-compare a PAT don't.

The safe-Sublime sequence is five extra steps (`hot_exit: false`, `remember_open_files: false`, `ensure_newline_at_eof_on_save: false`, edit and save, then delete the two `*.sublime_session` files manually). The terminal flow doesn't need any of them.

## 8. Related documents

- [ADR-0216 — In-process classic-PAT decryption](../adrs/0216-in-process-classic-pat-decryption.md) — the threat model this runbook closes a gap in.
- [0930 — GPG and classic-PAT rotation](./0930-gpg-and-classic-pat-rotation.md) — rotating the classic PAT; orthogonal to this runbook's PAT.
- [0925 — Agent token setup](./0925-agent-token-setup.md) — Cerberus / GitHub App tokens, distinct from operator workstation PATs.
- [0936 — gh CLI aliases](./0936-gh-cli-aliases.md) and [0937 — gh CLI scripts](./0937-gh-cli-scripts.md) — what `gh` is used for day-to-day, i.e. what the loaded credential drives.
- Universal `C:/Users/mcwiz/Projects/CLAUDE.md` → "Secret-Handling Hygiene (Operator Recipes)" — the surface checklist this procedure was built against.
- `gh-link-auditor/data/issue-body-least-priv-pat.md` — worked example of why a tool that genuinely needs to fork external repos cannot use a fine-grained PAT and must stay on classic PAT.

## 9. Change log

| Version | Date | Change |
|---------|------|--------|
| 1.0.2 | 2026-05-29 10:40 PM Central | Reframe (still patch): runbook now reflects operator-confirmed ground truth. (1) Header retitled to "Restore `gh` CLI auth using the fine-grained PAT (`llm-restricting`)" — the standing PAT is named, its declared purpose is quoted from its GitHub settings page (AI-agent restricted, no admin / branch-protection bypass capability), and the fleet policy "OAuth is forbidden. Period." is stated up front. (2) §1 rewritten: §1a names Windows 11 wiping Credential Manager as the assumed #1 trigger for needing this runbook, with the symptom signature (`gh auth status` invalid + `git fetch` credential prompt + recent Windows Update); §1b retains the OAuth-bypass threat-model explanation as the WHY for the policy in (1). (3) §2.5 rewritten around the two real long-term storage choices (GitHub itself as master via regenerate-to-recover; optional encrypted local copy). (4) §3 intro now has three entry points (have value locally / regenerate at GitHub / first-time create) instead of two. (5) §3a step 2 added — regenerate vs create-new branch. (6) §3b converted from optional "Revoke OAuth (recommended)" to mandatory "Verify no OAuth grant exists" with explicit fleet-policy rationale. (7) §3c step 6 verification command switched from `gh auth status -t` (prints full token to stdout, transcript-toxic) to `gh auth status` + `gh api user --jq .login` (masked + round-trip). (8) §4 hardened — `github_pat_` prefix is now a load-bearing STOP gate; if `gho_` or `ghp_` appears, the operator is policy-violating and must re-run §3c. Smoke tests and negative-test framing reference `llm-restricting`'s actual screenshot-confirmed scope. (9) §5 Rollback no longer offers OAuth as a fallback — only "edit `llm-restricting`'s permissions and re-run §3c" or "pivot to ADR-0216 classic PAT for genuinely admin-scope operations." (10) §6 split into §6a Re-loading (the recurring Windows-11-wipe case, no rotation paperwork required) and §6b Rotation (the periodic expiry case, references the current expiry `Mon, Jun 22 2026` from the screenshot). Tracking issue still TBD. |
| 1.0.1 | 2026-05-29 10:05 PM Central | Patch: §3 split into "reuse existing" vs "create new" entry points so the lower-variability reuse path is explicit. §3a.1 incognito caveat clarified — only applies to the create-new path because reuse never visits the PAT one-time-display page. New §2.5 declares long-term PAT storage as a precondition the runbook does not prescribe (operator's existing pattern — GPG-encrypted file, password manager, etc.). New §3c lead-in tells the operator to retrieve the PAT from §2.5 storage. §3d expanded with how to check, view, and clear the Win+V clipboard-history ring buffer. New §6 covers rotation across both surfaces (long-term storage and `gh`'s loaded credential) and names the Windows Update–invalidated-token symptom that prompted the runbook. §7/§8/§9 renumbered (former §6/§7/§8). |
| 1.0.0 | 2026-05-29 9:49 PM Central | New runbook. Captures the gh-OAuth-bypass-of-ADR-0216 problem and the fine-grained-PAT replacement procedure. Tracking issue TBD — `gh auth` was 401 at runbook-write time (Windows Update apparently invalidated the token); file once §3c completes and `gh issue create` works again. |
