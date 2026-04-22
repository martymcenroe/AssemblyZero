# 0927 - New Repo: Human Steps Checklist

**Category:** Runbook / Operational Procedure
**Version:** 4.1
**Last Updated:** 2026-04-22

---

## Purpose

The human steps when creating a new repo. Most of the work is automated by `new_repo_setup.py` — it creates the local scaffold, GitHub repo, branch protection, workflow files, initial push, and (with `--cerberus-pem`) the Cerberus secrets deploy.

The human handles only what the script genuinely can't: supplying a classic PAT for privileged operations (workflow push + branch protection), downloading the Cerberus `.pem` from the browser, and revoking the Cerberus key when done.

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

### 1. Run the setup script with env-scoped classic PAT (preferred)

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
env GH_TOKEN=$(gpg -d ~/.secrets/classic-pat.gpg) \
  poetry run python tools/new_repo_setup.py {name} [--public] [--license mit] [--cerberus-pem PATH]
```

**Why `env VAR=VALUE command` instead of `export`:**
- The variable is scoped to the single command's process tree
- When the script exits, `GH_TOKEN` ceases to exist — no `unset` to forget
- Never touches `gh auth` storage, so the classic PAT isn't left sitting there for other agents

**What `GH_TOKEN` does:** the `gh` CLI documented behavior is to honor `GH_TOKEN` over whatever's in `gh auth` storage for the duration of the process. This is needed for the two remaining `gh`-backed privileged operations:

- the initial `git push` of the scaffold (via `gh repo create --source . --push`) — requires `workflow` scope because the push includes `.github/workflows/*.yml` files, which fine-grained PATs can't push.
- Cerberus secret-set (via `gh api`) — requires the `secrets` scope.

**Branch protection and repo settings no longer need `GH_TOKEN`.** After PR #1001 (Phase A of #964), those two REST calls decrypt the same gpg file inline via `tools/_pat_session.py` (per ADR-0216) and consume the PAT as a Python heap variable. The PAT never enters the env block for those calls. Net effect: the snoopable env-block exposure window shrank from ~90s (full privileged sequence) to ~5s (the git push only). Phase B — tracked in #1000 — will eliminate even the push window by deploying workflow files via the Contents API.

The script handles all of the following automatically:
- Local directory structure + all config files
- GitHub repo creation (forced lowercase) via `gh repo create --source . --push`
- Repo settings: wiki disabled, projects disabled, squash-only merge, delete branch on merge
- Branch protection: require PR (1 review), block force push, block deletion, enforce_admins, pr-sentinel check
- PR governance workflow (`auto-reviewer.yml` — pr-sentinel check comes from the Cloudflare Worker fleet-wide)
- `.unleashed.json`, `.claude/settings.json`, security hooks
- Initial commit and push
- Cerberus secrets deploy (if `--cerberus-pem` supplied)

The script prints a summary showing what succeeded and what failed.

### 2. Legacy fallback — `gh auth login` swap (if you haven't set up gpg)

If you haven't done the one-time gpg setup, you can still use the legacy two-paste swap:

```bash
gh auth login -h github.com -p https   # paste classic PAT

cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/new_repo_setup.py {name} [--public] [--license mit]

gh auth login -h github.com -p https   # paste fine-grained PAT back — do this immediately
```

**Risk:** if you forget the swap-back, classic-PAT access stays live in `gh auth` storage and any agent using the same storage inherits it. The env-scoped path in Step 1 avoids this entirely.

### 3. Security considerations for `GH_TOKEN` env var

While `GH_TOKEN` is in the env block, it is readable by same-user processes via OS APIs (`/proc/<pid>/environ` on Linux, `NtQueryInformationProcess` on Windows). Secret-guard hooks catch `echo $GH_TOKEN` / `printenv` patterns, but a subprocess making direct syscalls can snoop around the hook.

Post-Phase-A (#964 / PR #1001), that window is approximately **the 5 seconds of the initial git push** — not the full privileged sequence. Cerberus secret-set also uses `GH_TOKEN` briefly. The branch-protection and repo-settings calls no longer widen the window because they don't read `GH_TOKEN` at all.

Practical guidance:
- For the typical case, the ~5s window is small enough to not require special precautions.
- If you're especially cautious, run new-repo creation in a terminal where no other agent session is running.
- Phase B (#1000) will eliminate the window entirely by deploying workflow files via Contents API instead of git push.

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
| Auto-reviewer workflow file | Created by setup script in initial commit |
| Repo settings | Configured by setup script: wiki off, projects off, squash-only, delete-branch-on-merge |
| Branch protection | Configured by setup script: 1 review, enforce_admins, pr-sentinel check, strict=false |
| Directory structure + configs | Created by setup script |
| Cerberus secrets deploy | Handled by the script when `--cerberus-pem PATH` is passed |

The **per-repo human steps** are: supplying the classic PAT (via env-scoped GH_TOKEN or legacy swap), downloading the Cerberus `.pem`, revoking the Cerberus key when done, and optional wiki/domain setup.

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
