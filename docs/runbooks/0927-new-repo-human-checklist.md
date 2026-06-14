# 0927 - New Repo: Human Steps Checklist

**Category:** Runbook / Operational Procedure
**Version:** 6.8
**Last Updated:** 2026-05-26

---

## Purpose

The human steps when creating a new repo. Most of the work is automated by `new_repo.py` — it creates the local scaffold, GitHub repo, branch protection, workflow files, initial push, and (with `--cerberus-pem`) the Cerberus secrets deploy.

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

**Encrypt the Cerberus App private key** (recommended for any repeat use):

The first time you generate a Cerberus `.pem`, encrypt it and delete the plaintext immediately. After that, the encrypted blob is reusable across as many repo creations as you want against the same active App key. **Do NOT revoke the key after deploying** — every repo's `REVIEWER_APP_PRIVATE_KEY` Actions secret depends on it remaining active. Periodic key rotation is its own procedure — see [runbook 0939](0939-cerberus-key-rotation.md).

#### Hygiene surfaces (audit gate)

Any plaintext `.pem` passes through a finite set of surfaces between "downloaded from browser" and "encrypted at rest." Every surface is a potential leak vector. The recipe below names every surface it touches and the step that closes it.

| Surface | Risk | This recipe's mitigation |
|---|---|---|
| **Plaintext file on disk** | Same-user FS access; cloud-sync (OneDrive) could upload before local `rm` fires | Save-As directly to `~/.secrets/cerberus.pem` (sibling of where the encrypted blob will land; never synced anywhere). Do NOT route through `~/Downloads/` (often OneDrive-synced). |
| **Browser download history** | Filename + path persists after the file is deleted | Use private/incognito mode for the download, OR clear download history immediately after. |
| **Recycle Bin** | File Explorer delete (drag-to-trash or right-click) lands plaintext in Recycle Bin even after you "deleted" it | Use shell `rm`, not File Explorer. `Clear-RecycleBin -Force` as belt-and-suspenders. |
| **Clipboard** | If clipboard-pattern variant is used (see "Alternative" below), the PEM persists in the OS clipboard until overwritten. Windows clipboard-history (Win+V) caches up to 25 entries if enabled. | The Save-As recipe (preferred) avoids the clipboard entirely. If using the clipboard variant, clear with `Set-Clipboard -Value $null` and clear clipboard-history from Settings → System → Clipboard. |
| **Editor undo / hot-exit cache** | VS Code, Sublime, Notepad++ retain open buffers across restarts | Don't open the `.pem` in an editor. The Save-As recipe doesn't require it. |
| **gpg-agent passphrase cache** | Cached passphrase lets any same-user process silently decrypt the encrypted blob later | `default-cache-ttl 0` in `~/.gnupg/gpg-agent.conf` (per ADR-0216). Already covered in the "Tighten gpg-agent caching" subsection above. |

#### The recipe (Save-As pattern — preferred)

This pattern touches the fewest surfaces.

```bash
# 1. In browser at https://github.com/settings/apps/cerberus-az → Private keys
#    → Generate a private key. When the browser opens the Save-As dialog,
#    target ~/.secrets/cerberus.pem  (NOT ~/Downloads/; ~/.secrets is the
#    sibling of where the encrypted blob will land, owned by user, never
#    synced anywhere). Create the directory if needed: mkdir -p ~/.secrets

# 2. Encrypt and delete plaintext (shell rm, not File Explorer):
gpg -c -o ~/.secrets/cerberus-pem.gpg ~/.secrets/cerberus.pem
rm ~/.secrets/cerberus.pem

# 3. Belt-and-suspenders: empty Recycle Bin in case any tool routed through it:
powershell.exe -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"

# 4. Browser hygiene: open browser download history, find the .pem entry, delete it.
#    (Or use private/incognito for step 1 — no history entry is ever created.)
```

Surfaces touched: filesystem (briefly, outside `~/Downloads/`) + browser download history (none if incognito). No clipboard, no editor cache, no Recycle Bin (if shell `rm` is used; the `Clear-RecycleBin` is paranoia insurance).

#### Alternative: clipboard pattern (consistent with classic-PAT recipe)

If you prefer parity with the classic-PAT one-time-setup recipe above, the clipboard pattern works too — but touches more surfaces:

```bash
# 1. Browser downloads .pem (anywhere — Downloads is fine if you'll rm it shortly).
# 2. Open .pem in a text editor, Ctrl+A, Ctrl+C.
# 3. Pipe from clipboard:
cat /dev/clipboard | gpg -c -o ~/.secrets/cerberus-pem.gpg
# 4. CLEAR clipboard immediately:
echo -n "" | clip
#    OR powershell.exe -NoProfile -Command "Set-Clipboard -Value $null"
# 5. Close the editor; verify it doesn't preserve the file in recent-tabs.
# 6. Delete the downloaded .pem with shell rm:
rm ~/Downloads/cerberus.pem      # or wherever the browser saved it
# 7. Clear-RecycleBin (insurance) + clear browser download history.
```

Surfaces touched: filesystem + clipboard + editor cache + browser history. **Not recommended unless you specifically want classic-PAT recipe parity** — every additional surface is a step the operator might forget at 2am during an incident.

#### After encryption (both patterns)

The encrypted file lives at `~/.secrets/cerberus-pem.gpg` and is consumed via `cerberus_pem_session()` in `tools/_pat_session.py` (the parallel of `classic_pat_session()`, same ADR-0216 threat model). Decryption happens only inside the Python process's heap when `new_repo.py --cerberus-pem-gpg` runs — no plaintext PEM ever appears on disk after this one-time step (#1254).

#### Three independent copies of the key (read this once)

After encryption + deploy, the same key exists in three places:

1. **App-side public-half registration** — on https://github.com/settings/apps/cerberus-az → Private keys. Used by GitHub to verify JWTs signed by the corresponding private key.
2. **Operator-side encrypted blob** — `~/.secrets/cerberus-pem.gpg`. Offline copy enabling re-deploy without regenerating.
3. **Per-repo Actions secret** — `REVIEWER_APP_PRIVATE_KEY` in each repo. The bytes `auto-reviewer.yml` reads at run time to sign JWTs.

**Revoking the key on the App page (copy 1) makes copies 2 and 3 useless** — GitHub no longer accepts JWTs signed by it. Every repo's auto-approval silently breaks the next time a PR opens.

The previous version of this runbook told operators to revoke right after deploying. **That was wrong** (per unleashed#658). The right pattern: keep the key active on the App for as long as it's deployed in any repo. When you want to rotate, follow [runbook 0939](0939-cerberus-key-rotation.md) — deploy the new key fleet-wide, audit via `tools/audit_cerberus_health.py`, THEN revoke the old key.

You CAN safely `rm ~/.secrets/cerberus-pem.gpg` at any time (deletes only your offline copy; the GitHub-side copies remain functional). Keep it if you want to re-deploy without regenerating.

---

## Checklist

### 1. Run the setup script (bare — no env prefix needed)

**Recommended path — `--cerberus-pem-gpg` (encrypted at rest, reusable):**

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/new_repo.py {name} \
    --cerberus-pem-gpg ~/.secrets/cerberus-pem.gpg [--public]
```

This requires the one-time gpg-encrypt of the Cerberus `.pem` (see "One-time setup" above). The decrypted key only ever lives in the Python heap during the script's run; nothing plaintext touches disk. **You can run this same invocation for as many new repos as you want against the same encrypted blob.** Keep the App-side key active as long as any repo holds it (do NOT revoke per "Three independent copies" above). When you want to rotate the key, follow [runbook 0939](0939-cerberus-key-rotation.md).

**Legacy / single-shot path — `--cerberus-pem` (plaintext, deleted after deploy):**

```bash
cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/new_repo.py {name} --cerberus-pem PATH [--public]
```

The script reads the plaintext `.pem`, deploys, then unlinks the file. Fine for occasional one-off repo creation; for any repeat use the gpg path is strictly better (security + ergonomics).

Either `--cerberus-pem-gpg` OR `--cerberus-pem` is **required** when creating a GitHub repo (#1206) — Cerberus auto-approval is part of the new-repo contract, and without the secrets every PR sits blocked. The only override is `--no-github` (local scaffold only, skips the GitHub side entirely). The two flags are mutually exclusive.

gpg-agent will prompt for your passphrase once per cache window (controlled by `~/.gnupg/gpg-agent.conf`) and the script handles the rest.

**Defaults the script picks unless you override:**
- **License**: PolyForm Noncommercial 1.0.0. Pass `--license mit` if you want MIT instead.
- **Visibility**: private. Pass `--public` to override.
- **Cerberus secrets**: deployed when `--cerberus-pem PATH` is provided (required for new GitHub repos per #1206 — see [Cerberus](#what-cerberus-is-and-why-you-want-it) below).

**Before running the script**, download the `.pem`:

1. Go to <https://github.com/settings/apps/cerberus-az> → **Private keys**
2. Click **Generate a private key** — the browser downloads a `.pem` file (typically to `C:\Users\mcwiz\Downloads\`)
3. Pass that path to `--cerberus-pem` in **Git Bash Unix-style**:
   ```bash
   poetry run python tools/new_repo.py MyNewRepo --private \
     --cerberus-pem /c/Users/mcwiz/Downloads/cerberus-az.2026-04-22.private-key.pem
   ```
   MSYS translates `/c/Users/...` → `C:\Users\...` before `python.exe` sees argv, so pathlib handles it correctly. Windows-style `'C:\Users\mcwiz\Downloads\foo.pem'` also works if single-quoted (or with escaped backslashes), but the Unix-style form matches every other path example in this runbook.
4. Full walkthrough (deploy + delete local `.pem`; key stays active on App page) is in [Section 4](#4-deploy-cerberus-secrets-if-needed) below.

*Why you have to do this manually:* the GitHub App management API does not expose programmatic key generation or revocation — both are browser-only.

**What the script does under the hood (post-#1000 + #1007):**

| Step | Operation | Auth path |
|------|-----------|-----------|
| 12 | Local initial commit — non-workflow files only (includes `.github/dependabot.yml` #1334 and `data-g/` #1563, which need no workflow scope) | (local git) |
| 13 | Create GitHub repo + push initial commit | `gh auth` (fine-grained PAT is sufficient because the push contains no workflow-file changes) |
| 14 | Star the repo | `gh auth` (fine-grained PAT) |
| 15 | **Upload `.github/workflows/*` via Contents API** | In-process classic PAT via `classic_pat_session()` — PAT stays in Python heap |
| 16 | `git pull --rebase` to sync local with the Contents-API commits | `gh auth` (read-only) |
| 17 | **Configure repo settings (wiki/projects/merge strategy)** via PATCH | In-process classic PAT |
| 18 | **Configure branch protection** via PUT | In-process classic PAT |
| 19 | **Create canonical labels** (`implementation`, `lld`) | In-process classic PAT |
| 20 | **Enable Dependabot** (security_and_analysis PATCH + vulnerability-alerts PUT + automated-security-fixes PUT) | In-process classic PAT (#1331) |
| — | **Cerberus secrets** (if `--cerberus-pem` passed): sealed-box encrypt + PUT | In-process classic PAT (#1007) |

Steps in **bold** require classic-PAT scopes. The PAT never enters the env block or subprocess argv — privileged calls share a `classic_pat_session()`, and gpg-agent caches the passphrase across sessions, so you'll typically see the prompt at most once per shell.

The script handles all of the following automatically:
- Local directory structure + all config files
- GitHub repo creation (case preserved from the input name; #1533) + initial push of non-workflow files
- Workflow file upload via Contents API (one PUT per file)
- Repo settings: wiki disabled, projects disabled, squash-only merge, delete branch on merge
- Branch protection: require PR (1 review), block force push, block deletion, enforce_admins, pr-sentinel check
- PR governance workflow (`auto-reviewer.yml` — pr-sentinel check comes from the Cloudflare Worker fleet-wide)
- `.unleashed.json`, `.claude/settings.json`, security hooks
- **Python project bootstrap**: `pyproject.toml`, `poetry.lock`, `pytest`+`pytest-cov` in dev deps, `[tool.pytest.ini_options]` for deterministic test discovery, `tests/conftest.py` for `src/` import path. Pass `--lang none` to skip for non-Python projects. (#1058)
- **Canonical labels**: `implementation` and `lld` on the GitHub repo (#1061)
- **Per-repo `CLAUDE.md` (lean shape per ADR 0219)**: `## Project Identifiers` block plus a project-type-specific `## Project-Specific Context` stub. The scaffolded file is intentionally short (~15-25 lines) and ADDITIVE only — no merge-sequence / branch-protection / PR-rules content; those live in the auto-loaded universal `CLAUDE.md`. Pass `--project-type {minimal,python,chrome-extension,pypi,cf-worker,web}` to pick the stub; default `minimal` is a pure TODO block. Per-repo drift is auditable via `tools/lint_per_repo_claude_md.py` (#1290). See [ADR 0219](../adrs/0219-claude-md-division-of-responsibility.md) for the full division-of-responsibility rule. (#1258, #1291, #1266)
- Cerberus secrets deploy (if `--cerberus-pem` supplied)
- **Generate `.github/dependabot.yml`** (#1334): version-update config written at creation time (script step 11c2). Ecosystems are detected by marker-file presence (`pyproject.toml`→pip, `package.json`→npm, `Dockerfile`→docker) plus `github-actions` always. It rides the initial commit (non-workflow file, so no workflow scope). This is the half that makes #1331's settings-level enablement emit *version-update* PRs — without the yml, only *security* PRs fire.
- **Create `data-g/`** (#1563): a git-tracked source-of-truth data directory with a README explaining the split. `data/` is ignored fleet-wide (ephemeral session artifacts); `data-g/` holds authoritative data the global ignore does not match, so it survives a machine wipe.
- **Enable Dependabot at repo settings level** (#1331): PATCH `security_and_analysis.dependabot_security_updates`, PUT `/vulnerability-alerts`, PUT `/automated-security-fixes`. Without this step the `.github/dependabot.yml` generated above is inert on private repos — Dependabot defaults to disabled and no PRs emit. The defect was confirmed 2026-05-26 on `dependabot-honeypot` (yml in place, 65 decorative deps pinned to ~12-18mo old versions, zero PRs after 11+ hours). The tool `tools/enable_dependabot.py` can also be run standalone to backfill existing repos.

The script prints a summary showing what succeeded and what failed.

### 2. Emergency fallback — `gh auth login` swap (legacy; should never be needed)

All privileged paths now route through in-process classic PAT (#964 + #1000 + #1007). The `gh auth login` swap is retained only as a break-glass fallback if `classic_pat_session()` itself fails (e.g., missing `~/.secrets/classic-pat.gpg` or broken gpg-agent):

```bash
gh auth login -h github.com -p https   # paste classic PAT

cd /c/Users/mcwiz/Projects/AssemblyZero
poetry run python tools/new_repo.py {name} [--public] [--cerberus-pem PATH]

gh auth login -h github.com -p https   # paste fine-grained PAT back — do this immediately
```

**Risk:** if you forget the swap-back, classic-PAT access stays live in `gh auth` storage and any agent using the same storage inherits it.

### 3. Env-block exposure — historical note

Pre-#1000, the runbook required `env GH_TOKEN=$(gpg -d ~/.secrets/classic-pat.gpg) poetry run ...` to give the initial git push `workflow` scope. While `GH_TOKEN` was in the env block, it was readable by same-user processes via OS APIs (`/proc/<pid>/environ` on Linux, `NtQueryInformationProcess` on Windows).

After #1000, the script no longer needs `GH_TOKEN` for the git push — workflow files are deployed via Contents API with an in-process classic PAT instead, and the initial push contains no workflow changes (so fine-grained PAT suffices).

Net effect: **no `GH_TOKEN` env-block exposure for any invocation, including `--cerberus-pem`**. After #1037, the Cerberus secret-set path also runs through the in-process classic PAT, so there is no remaining condition under which `GH_TOKEN` would need to be in the env block.

### 4. Deploy Cerberus secrets (Cerberus = your auto-approver)

#### What Cerberus is and why you want it

**Cerberus-AZ is a GitHub App that automatically approves your own PRs after pr-sentinel passes**, so you don't have to click Approve on every one of your own PRs to satisfy branch protection's "1 approving review" requirement.

End-to-end PR flow on every repo:

1. You open a PR. Branch protection requires (a) a passing `pr-sentinel / issue-reference` check from the Cloudflare Worker, and (b) at least one approving review.
2. **pr-sentinel** (Cloudflare Worker, fleet-wide) reads the PR body, checks for `Closes #N` (linked to an open issue) or `No-Issue: ...` exemption. If valid, it posts a check-success.
3. **Cerberus-AZ** (this GitHub App) listens for that check-success. If the PR is yours, Cerberus posts an approving review using its own GitHub identity. Branch protection now has its review.
4. Tests pass → all gates green → `gh pr merge --squash` succeeds.

**Without Cerberus secrets on the new repo:** step 3 silently fails. Your PRs sit in `mergeable_state: blocked` because there's no approving review. You'd have to manually click Approve via the UI on every PR (ugly) or run a fleet-wide secret-deploy after-the-fact (also annoying).

#### Why secrets are per-repo, and what the .pem actually is

Cerberus-AZ is fleet-installed at the App level — one click in App settings ("All repositories"), and the App has access to every repo you own automatically. **You don't need to install the App per-repo.**

But for Cerberus to authenticate to GitHub at PR-review time, the App's RSA private key has to be present in the repo as two Actions secrets: `REVIEWER_APP_ID` (the App ID, fixed) and `REVIEWER_APP_PRIVATE_KEY` (a fresh private key you generate). The auto-reviewer workflow reads those secrets at job-time, signs a JWT, and acts as Cerberus.

The `.pem` is the App's private key, downloaded from <https://github.com/settings/apps/cerberus-az>. It is **single-use**:

1. **Generate** in browser → `.pem` lands in `Downloads/` (browser-only; App management API doesn't expose this)
2. **Deploy** via `--cerberus-pem PATH` → script encrypts the key with the repo's public key (libsodium sealed-box), PUTs it as a GitHub Actions secret, deletes the .pem on disk
3. **Revoke** in browser → that specific key is invalidated server-side (browser-only too)

After step 3 the secret value lives in GitHub Actions encrypted storage. The local .pem is gone. The Cerberus App can still authenticate using OTHER active keys you generate later, so revoking this one is safe.

#### Why this is an option, not always-on

The script can't auto-do steps 1 and 3 (browser-only). It needs a flag to know whether YOU did step 1 and where you put the .pem. That's what `--cerberus-pem PATH` is for.

**`--cerberus-pem` is REQUIRED on new GitHub repos (#1206).** The script exits 1 with the .pem-acquisition guide if you forget it. The only way to skip Cerberus deploy is `--no-github` (local scaffold only). For repos already created without the flag, the fallback path below (standalone `tools/deploy_cerberus_secrets.py`) still applies.

Two procedural variants follow — **preferred** (integrated into `new_repo.py`, what `--cerberus-pem` does) or **fallback** (standalone fleet-wide script when you want to deploy to many repos at once).

#### Preferred: pass `--cerberus-pem PATH` to `new_repo.py`

When you invoke `new_repo.py` with the flag, the script handles steps 3-5 below automatically after the repo is created:

1. Go to https://github.com/settings/apps/cerberus-az > Private keys
2. Click **Generate a private key** — browser downloads a `.pem` file
3. Run the setup script with the flag (re-using the same invocation if this is the first time):
   ```bash
   cd /c/Users/mcwiz/Projects/AssemblyZero
   poetry run python tools/new_repo.py MyNewRepo --cerberus-pem /c/Users/mcwiz/Downloads/THE-FILE.pem
   ```
   The script deploys both secrets to ONLY the new repo, verifies they landed via `gh api`, then deletes the local `.pem` file.
4. **Keep the key active on the App page** — the deployed Actions secret depends on it remaining active. Do NOT revoke. When you want to rotate the key, follow [runbook 0939](0939-cerberus-key-rotation.md).

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
6. **Keep the App-side key active.** The deployed Actions secrets depend on it. **Do NOT revoke after deploy** — revoking removes the public-half registration on the App page, and every repo's secret becomes unusable (GitHub rejects JWTs signed by the revoked key). Per `unleashed#658` / runbook 0939, the only safe time to revoke is during a structured rotation: deploy a NEW key fleet-wide, audit via `tools/audit_cerberus_health.py`, THEN revoke the old.
7. **Done.** Secrets deployed, local `.pem` deleted, App-side key still active.

**What happens without secrets:** PRs pass pr-sentinel but don't get auto-approved. You can merge manually via the GitHub UI until secrets are deployed.

**To rotate the key later:** see [runbook 0939](0939-cerberus-key-rotation.md). The procedure is deploy-new → audit → revoke-old, never deploy-then-revoke.

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
| 2026-04-22 | v5.0: Phase B of #964 / #1000 landed. Invocation is now bare `poetry run python tools/new_repo.py NAME [...]`; no `env GH_TOKEN` prefix required. Script splits step 13 into non-workflow initial commit (pushed via `git` with fine-grained PAT) + workflow upload via Contents API (PUT with in-process classic PAT) + `git pull` to sync. Env-block exposure of the classic PAT is eliminated for the common path. Cerberus secret-set (`--cerberus-pem`) still uses `gh auth` — bare works if your fine-grained PAT has `Actions: write`, else prepend `env GH_TOKEN=...` for that invocation. Demoted the "`gh auth login` swap" section to emergency-fallback. Replaced Section 3 (env-snooping mitigation) with a historical note. |
| 2026-04-22 | v5.1: #1007 — `tools/deploy_cerberus_secrets.py` migrated to in-process classic PAT (pynacl sealed-box encryption + REST API). `--cerberus-pem` invocation no longer needs `env GH_TOKEN` regardless of fine-grained PAT scope. `gh auth login` swap section updated to reflect it's now fully legacy (only relevant if `classic_pat_session` itself fails). Updated the under-the-hood table to include Cerberus secret-set on the in-process path. |
| 2026-04-22 | v5.2: #1009 — surfaced the Cerberus `.pem` download URL (`https://github.com/settings/apps/cerberus-az > Private keys`) next to the Step 1 invocation so users don't have to scroll to Section 4 to find it when they're about to run `--cerberus-pem`. |
| 2026-04-22 | v5.3: #1014 — made the \`--cerberus-pem\` path-format explicit. Git Bash Unix-style (\`/c/Users/mcwiz/Downloads/...\`) is preferred; noted MSYS translation and the Windows-style fallback with its quoting caveat. Concrete example given in the Step 1 block. |
| 2026-05-07 | v6.0: #1037 — dropped \`--license mit\` from invocation examples (script default is \`polyform\`, was misleading to show MIT as if recommended). Added an explicit "Defaults the script picks unless you override" block. Rewrote Section 4 with three subsections explaining what Cerberus is (auto-approver of your own PRs after pr-sentinel passes), why the secrets must be per-repo (App's RSA private key, used by the auto-reviewer workflow to authenticate as Cerberus), and why \`--cerberus-pem\` is recommended on every new-repo creation. Updated the env-block exposure note to reflect that #1036/#1037 closes the last \`GH_TOKEN\` hold-out. |
| 2026-05-09 | v6.1: #1058 + #1059 + #1060 + #1061 — bundle of post-boostgauge-readiness-audit fixes. Script now bootstraps a Python project by default (\`poetry init\` + \`poetry add --group dev pytest pytest-cov\` + \`[tool.pytest.ini_options]\` + \`tests/conftest.py\`); \`--lang none\` skips for non-Python repos. \`.unleashed.json\` defaults to \`assemblyZero: true\` and no longer emits the deprecated \`pickupThresholdMinutes\`. Two canonical GitHub labels (\`implementation\`, \`lld\`) created on the new repo. |
| 2026-05-22 | v6.2: #1206 — `--cerberus-pem` is REQUIRED for new GitHub repos. Script exits 1 with the .pem-acquisition guide if omitted. Override is `--no-github` (local scaffold only). #1200 + #1202 — extended post-setup verification to GitHub-side state (branch protection, repo settings, workflow content, Cerberus secrets) and added a best-effort `pr-sentinel-mm` Worker installation check that surfaces App-scope drift at creation time instead of when the first PR opens. |
| 2026-05-24 | v6.3: #1254 — applied ADR-0216 gpg-at-rest pattern to the Cerberus `.pem`. New `--cerberus-pem-gpg PATH` flag on both `new_repo.py` and `deploy_cerberus_secrets.py` reads from an encrypted blob (typically `~/.secrets/cerberus-pem.gpg`) and decrypts in-process via `cerberus_pem_session()` -- never plaintext on disk during the script run. Legacy `--cerberus-pem` (plaintext, deleted after) preserved for backward compatibility. Multi-repo creation becomes trivial: one browser-trip generates the .pem, one revokes, the encrypted blob in `~/.secrets/` is reused across any number of `new_repo.py` invocations. Added one-time-setup subsection for the encryption step. |
| 2026-05-26 | v6.4: #1265 — rewrote "Encrypt the Cerberus App private key" subsection. Save-As pattern (target `~/.secrets/cerberus.pem` directly via browser Save-As dialog, bypassing `~/Downloads/`) is now primary; clipboard pattern documented as alternative for classic-PAT recipe parity. Added inline Hygiene Surfaces audit-gate table naming every surface the recipe touches (Downloads, browser history, Recycle Bin, clipboard, editor cache, gpg-agent) and which step closes it. Eliminates the "operator forgets a step" failure mode that compounds under stress. |
| 2026-05-25 | v6.5: #1295 — removed all "revoke after deploy" instructions (lines 49, 128, 264, 283, 287 of prior version). Per `unleashed#658`: revoking the key on the App page removes only the public-half registration; every per-repo `REVIEWER_APP_PRIVATE_KEY` Actions secret becomes unusable (GitHub rejects JWTs signed by the revoked key) — silently breaks every repo holding the just-revoked key. Added "Three independent copies of the key" explanation. All revoke guidance now points at runbook 0939 for the canonical deploy-new → audit → revoke-old rotation pattern. Operator question that surfaced this: "i don't understand. i don't need a pem private key on github? then how does it work?" |
| 2026-05-26 | v6.6: #1293 — documented the per-repo `CLAUDE.md` lean shape per ADR 0219 (#1258) in the "What the script handles automatically" block. Surfaced the new `--project-type` flag (#1291) and pointed at the drift-detector lint tool (#1290). Per-repo CLAUDE.md is now explicitly framed as ADDITIVE only — no restatement of universal-CLAUDE.md content — with the lint tool as the audit-gate that catches regressions. |
| 2026-05-26 | v6.7: #1331 — added Step 20 to the under-the-hood table: Enable Dependabot at the repo settings level (PATCH `security_and_analysis.dependabot_security_updates`, PUT `/vulnerability-alerts`, PUT `/automated-security-fixes`). Without this step the scaffolded `.github/dependabot.yml` is inert on private repos (Dependabot defaults to disabled; no PRs emit). Defect confirmed 2026-05-26 on `dependabot-honeypot`. Companion tool `tools/enable_dependabot.py` runs the same enablement against existing repos (`--repo OWNER/NAME` or `--fleet`, `--apply` per std 0017). |
| 2026-06-10 | v6.8: #1334 + #1563 — script now generates `.github/dependabot.yml` at creation time (step 11c2; ecosystems by marker-file presence — `pyproject.toml`→pip, `package.json`→npm, `Dockerfile`→docker — plus `github-actions` always; non-workflow file, rides the initial commit). This is the version-update half that complements #1331's settings-level enablement — without the yml, only security PRs fire. Also creates `data-g/` (git-tracked source-of-truth data) with a README explaining the split vs the fleet-ignored `data/`. Updated the under-the-hood table (step 12) and the "handles automatically" list. |
