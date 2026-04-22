# 0927 - New Repo: Human Steps Checklist

**Category:** Runbook / Operational Procedure
**Version:** 5.2
**Last Updated:** 2026-04-22

---

## Purpose

The human steps when creating a new repo. Most of the work is automated by `new_repo_setup.py` — it creates the local scaffold, GitHub repo, branch protection, workflow files, initial push, and (with `--cerberus-pem`) the Cerberus secrets deploy.

Post-#1000 + #1007 (both landed 2026-04-22), the script needs **no environment-variable prefix**, even when `--cerberus-pem` is used. The classic PAT stays encrypted at rest (`~/.secrets/classic-pat.gpg`), the script decrypts it inline only when a specific API call needs admin/workflow/secrets scope, and the PAT lives only in the Python process heap — never in the env block.

The human handles only what the script genuinely can't: the one-time gpg encryption of the classic PAT, the gpg passphrase prompt (per gpg-agent cache window), downloading the Cerberus `.pem` from the browser, and revoking the Cerberus key when done.

---

## One-time setup (do this once, reuse forever)

**Encrypt your classic PAT with gpg** so you never paste it interactively again:

```bash
# Generate a classic PAT at https://github.com/settings/tokens with scopes:
#   repo + workflow + admin:repo_hook
# Copy the token to your clipboard, then encrypt it by piping from the
# clipboard (NOT echo — echo puts the token in shell history and argv):
cat /dev/clipboard | gpg -c -o ~/.secrets/classic-pat.gpg
#   macOS:  pbpaste | gpg -c -o ~/.secrets/classic-pat.gpg
#   Linux:  xclip -selection clipboard -o | gpg -c -o ~/.secrets/classic-pat.gpg
# You'll be prompted for a passphrase — remember it; you'll enter it once per shell session.
```

This is the canonical form documented by `tools/_pat_session.py`. The clipboard pattern keeps the secret out of shell history and out of the process argv table.

**Tighten gpg-agent caching (optional but recommended):**

```bash
mkdir -p ~/.gnupg
echo 'default-cache-ttl 0' >> ~/.gnupg/gpg-agent.conf
echo 'max-cache-ttl 0' >> ~/.gnupg/gpg-agent.conf
gpgconf --kill gpg-agent
```

With `default-cache-ttl 0`, gpg prompts for the passphrase every decryption (instead of caching for ~10 minutes). Your choice on the ergonomics-vs-security tradeoff.

---

## Checklist

### 1. Run the setup script (bare — no env prefix needed)

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/new_repo_setup.py {name} [--public] [--license mit] [--cerberus-pem PATH]
```

gpg-agent will prompt for your passphrase once per cache window (controlled by `~/.gnupg/gpg-agent.conf`) and the script handles the rest.

**Before using `--cerberus-pem`**, download the `.pem`:

1. Go to <https://github.com/settings/apps/cerberus-az> → **Private keys**
2. Click **Generate a private key** — the browser downloads a `.pem` file (typically to `~/Downloads/`)
3. Pass that path to `--cerberus-pem`. Full walkthrough (including the revoke step) is in [Section 4](#4-deploy-cerberus-secrets-if-needed) below.

*Why you have to do this manually:* the GitHub App management API does not expose programmatic key generation or revocation — both are browser-only.

**What the script does under the hood (post-#1000 + #1007):**

| Step | Operation | Auth path |
|------|-----------|-----------|
| 12 | Local initial commit — non-workflow files only | (local git) |
| 13 | Create GitHub repo + push initial commit | `gh auth` (fine-grained PAT is sufficient because the push contains no workflow-file changes) |
| 14 | Star the repo | `gh auth` (fine-grained PAT) |
| 15 | **Upload `.github/workflows/*` via Contents API** | In-process classic PAT via `classic_pat_session()` — PAT stays in Python heap |
| 16 | `git pull --rebase` to sync local with the Contents-API commits | `gh auth` (read-only) |
| 17 | **Configure repo settings (wiki/projects/merge strategy)** via PATCH | In-process classic PAT |
| 18 | **Configure branch protection** via PUT | In-process classic PAT |
| — | **Cerberus secrets** (if `--cerberus-pem` passed): sealed-box encrypt + PUT | In-process classic PAT (#1007) |

Steps in **bold** require classic-PAT scopes. The PAT never enters the env block or subprocess argv — privileged calls share a `classic_pat_session()`, and gpg-agent caches the passphrase across sessions, so you'll typically see the prompt at most once per shell.

The script handles all of the following automatically:
- Local directory structure + all config files
- GitHub repo creation (forced lowercase) + initial push of non-workflow files
- Workflow file upload via Contents API (one PUT per file)
- Repo settings: wiki disabled, projects disabled, squash-only merge, delete branch on merge
- Branch protection: require PR (1 review), block force push, block deletion, enforce_admins, pr-sentinel check
- PR governance workflow (`auto-reviewer.yml` — pr-sentinel check comes from the Cloudflare Worker fleet-wide)
- `.unleashed.json`, `.claude/settings.json`, security hooks
- Cerberus secrets deploy (if `--cerberus-pem` supplied)

The script prints a summary showing what succeeded and what failed.

### 2. Emergency fallback — `gh auth login` swap (legacy; should never be needed)

All privileged paths now route through in-process classic PAT (#964 + #1000 + #1007). The `gh auth login` swap is retained only as a break-glass fallback if `classic_pat_session()` itself fails (e.g., missing `~/.secrets/classic-pat.gpg` or broken gpg-agent):

```bash
gh auth login -h github.com -p https   # paste classic PAT

cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/new_repo_setup.py {name} [--public] [--license mit] [--cerberus-pem PATH]

gh auth login -h github.com -p https   # paste fine-grained PAT back — do this immediately
```

**Risk:** if you forget the swap-back, classic-PAT access stays live in `gh auth` storage and any agent using the same storage inherits it.

### 3. Env-block exposure — historical note

Pre-#1000, the runbook required `env GH_TOKEN=$(gpg -d ~/.secrets/classic-pat.gpg) poetry run ...` to give the initial git push `workflow` scope. While `GH_TOKEN` was in the env block, it was readable by same-user processes via OS APIs (`/proc/<pid>/environ` on Linux, `NtQueryInformationProcess` on Windows).

After #1000, the script no longer needs `GH_TOKEN` for the git push — workflow files are deployed via Contents API with an in-process classic PAT instead, and the initial push contains no workflow changes (so fine-grained PAT suffices).

Net effect: **no `GH_TOKEN` env-block exposure for a plain invocation**. The only time `GH_TOKEN` might still appear in env is if the user passes `--cerberus-pem` AND their fine-grained PAT lacks `Actions: write` — a narrow edge case not applicable to most runs.

### 4. Deploy Cerberus secrets (if needed)

The auto-reviewer needs two secrets per repo: `REVIEWER_APP_ID` and `REVIEWER_APP_PRIVATE_KEY`. Without them, PRs pass pr-sentinel but don't get auto-approved.

**Skip this step if** you've deployed Cerberus secrets since the last time you created a repo (the new repo may already be covered).

Two ways to do this: **preferred** (integrated into `new_repo_setup.py`) or **fallback** (standalone fleet-wide script).

#### Preferred: pass `--cerberus-pem PATH` to `new_repo_setup.py`

When you invoke `new_repo_setup.py` with the flag, the script handles steps 3-5 below automatically after the repo is created:

1. Go to https://github.com/settings/apps/cerberus-az > Private keys
2. Click **Generate a private key** — browser downloads a `.pem` file
3. Run the setup script with the flag (re-using the same invocation if this is the first time):
   ```bash
   cd /c/Users/mcwiz/Projects/AssemblyZero
   poetry run python tools/new_repo_setup.py MyNewRepo --cerberus-pem /c/Users/mcwiz/Downloads/THE-FILE.pem
   ```
   The script deploys both secrets to ONLY the new repo, verifies they landed via `gh api`, then deletes the `.pem`.
4. Go to https://github.com/settings/apps/cerberus-az > Private keys
5. Click **Revoke** on the key you just generated (browser-only — the GitHub App management API does not expose programmatic revocation).

#### Fallback: standalone fleet-wide script

Use this path if the new repo was already created (without the flag) or if you want to deploy to multiple repos at once.

1. Go to https://github.com/settings/apps/cerberus-az > Private keys
2. Click **Generate a private key** — browser downloads a `.pem` file
3. Deploy to all repos:
   ```bash
   cd /c/Users/mcwiz/Projects/AssemblyZero
   poetry run python tools/deploy_cerberus_secrets.py /c/Users/mcwiz/Downloads/THE-FILE.pem
   ```
4. **Verify:** Look for `OK` next to your new repo name in the output.
5. **Delete the .pem file immediately:**
   ```bash
   rm /c/Users/mcwiz/Downloads/THE-FILE.pem
   ```
6. Go back to https://github.com/settings/apps/cerberus-az > Private keys
7. Click **Revoke** on the key you just generated.
   - The secrets are already stored in GitHub Actions — the .pem is never needed again.
   - Revoking prevents the key from being used if the file wasn't fully deleted.
   - **Note:** GitHub Apps require at least one active key. If only one exists, you cannot revoke it. File deletion (step 5) is your only protection.
8. **Done.** Secrets deployed, .pem deleted, key revoked.

**What happens without secrets:** PRs pass pr-sentinel but don't get auto-approved. You can merge manually via the GitHub UI until secrets are deployed.

### 5. Create wiki (if needed)

Skip this step if the repo doesn't need a wiki.

**Public repos:** Enable the wiki in Settings > Features > Wikis. The wiki inherits the repo's visibility. Create the first wiki page.

**Private repos (shadow wiki):** GitHub wikis inherit the repo's visibility — a private repo's wiki is also private. Create a separate public repo using the naming convention `{repo}-wiki`:

```bash
gh repo create martymcenroe/{name}-wiki --public --description "{Name} public wiki" --repo martymcenroe/{name}-wiki
```

Then initialize it with a Home page:
```bash
gh repo clone martymcenroe/{name}-wiki /c/Users/mcwiz/Projects/{name}-wiki
cd /c/Users/mcwiz/Projects/{name}-wiki
echo "# {Name} Wiki" > Home.md
git add . && git commit -m "docs: initialize wiki"
git push
```

---

## What's Automatic (No Human Action)

These all happen without any per-repo human intervention:

| Component | Why It's Automatic |
|-----------|-------------------|
| Cerberus-AZ app access | Fleet-wide installation ("All repositories") — new repos are covered instantly |
| pr-sentinel check (Cloudflare Worker) | Receives webhooks for all repos, authenticates with its own stored credentials |
| Auto-reviewer workflow file | Uploaded by setup script via Contents API (#1000) — in-process classic PAT |
| Repo settings | PATCHed by setup script — in-process classic PAT (#964 Phase A) |
| Branch protection | PUT by setup script — in-process classic PAT (#964 Phase A) |
| Directory structure + configs | Created by setup script |
| Cerberus secrets deploy | Handled by the script when `--cerberus-pem PATH` is passed |

The **per-repo human steps** are: entering the gpg passphrase (once per gpg-agent cache window), downloading the Cerberus `.pem` if `--cerberus-pem` is used, revoking the Cerberus key when done, and optional wiki/domain setup.

---

## Related Documents

- [0901 - New Project Setup](0901-new-project-setup.md) — Script reference and file details
- [0926 - Branch Protection Setup](0926-branch-protection-setup.md) — Manual branch protection steps (fallback if script fails)
- [0925 - Agent Token Setup](0925-agent-token-setup.md) — PAT permissions and rotation

---

## History

| Date | Change |
|------|--------|
| 2026-03-18 | Initial runbook created |
| 2026-03-18 | v1.1: Added Cerberus secrets deployment. App is fleet-wide but secrets are per-repo. |
| 2026-03-18 | v1.2: Expanded .pem walkthrough. Clarified multi-key support. Added revoke step. |
| 2026-04-05 | v1.3: Made wiki step conditional with public/private guidance. |
| 2026-04-05 | v2.0: Complete rewrite. Script now handles repo creation, branch protection, and workflow deployment. Human steps reduced to Cerberus secrets (fleet-wide) and wiki setup. |
| 2026-04-08 | v3.0: Added PAT switch protocol (steps 1/3). Expanded repo settings (projects, merge, delete-branch). Rewrote Cerberus section as numbered checklist with .pem lifecycle notes. Added shadow wiki creation steps. (#883) |
| 2026-04-18 | v4.0: Replaced interactive `gh auth login` swap with env-scoped `GH_TOKEN=$(gpg -d ...) poetry run ...` as preferred. Documented one-time gpg setup for at-rest PAT encryption. Legacy swap retained as fallback. Removed `pr-sentinel.yml` from automatic-component table (Worker-only after #938/#939). Documented `--cerberus-pem` flag as preferred Cerberus path (#940/#941). Added security note on env-var snooping via OS APIs. (#942) |
| 2026-04-22 | v4.1: Fixed unsafe one-time-setup command (`echo '...' \| gpg -c` → `cat /dev/clipboard \| gpg -c`, matching the canonical form in `tools/_pat_session.py`). Updated "What GH_TOKEN does" paragraph to reflect Phase A of #964 (PR #1001): branch protection + repo settings now use in-process classic PAT via `classic_pat_session()` and do not read `GH_TOKEN`; only the initial git push and Cerberus secret-set still do. Toned down the env-snooping mitigation note — window shrank from ~90s to ~5s. Added forward-reference to #1000 (Phase B will eliminate the remaining window). (#1004) |
| 2026-04-22 | v5.0: Phase B of #964 / #1000 landed. Invocation is now bare `poetry run python tools/new_repo_setup.py NAME [...]`; no `env GH_TOKEN` prefix required. Script splits step 13 into non-workflow initial commit (pushed via `git` with fine-grained PAT) + workflow upload via Contents API (PUT with in-process classic PAT) + `git pull` to sync. Env-block exposure of the classic PAT is eliminated for the common path. Cerberus secret-set (`--cerberus-pem`) still uses `gh auth` — bare works if your fine-grained PAT has `Actions: write`, else prepend `env GH_TOKEN=...` for that invocation. Demoted the "`gh auth login` swap" section to emergency-fallback. Replaced Section 3 (env-snooping mitigation) with a historical note. |
| 2026-04-22 | v5.1: #1007 — `tools/deploy_cerberus_secrets.py` migrated to in-process classic PAT (pynacl sealed-box encryption + REST API). `--cerberus-pem` invocation no longer needs `env GH_TOKEN` regardless of fine-grained PAT scope. `gh auth login` swap section updated to reflect it's now fully legacy (only relevant if `classic_pat_session` itself fails). Updated the under-the-hood table to include Cerberus secret-set on the in-process path. |
| 2026-04-22 | v5.2: #1009 — surfaced the Cerberus `.pem` download URL (`https://github.com/settings/apps/cerberus-az > Private keys`) next to the Step 1 invocation so users don't have to scroll to Section 4 to find it when they're about to run `--cerberus-pem`. |
