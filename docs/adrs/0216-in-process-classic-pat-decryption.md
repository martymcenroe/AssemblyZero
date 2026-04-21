# ADR-0216: In-process classic PAT decryption

**Status:** Accepted
**Date:** 2026-04-21
**Categories:** Security, Tooling

## 1. Context

A small but persistent slice of operations against this fleet — branch-protection updates, workflow-file pushes, repo-settings PATCH calls — require a GitHub classic Personal Access Token (PAT) with `repo` (full), `workflow`, and sometimes `admin:repo_hook` scopes. The day-to-day fine-grained PAT used by every Claude Code session, Gemini session, and Codex session deliberately lacks those scopes; that exclusion is load-bearing. Without it an agent could edit its own pr-sentinel workflow to disable governance, run `gh pr merge --admin` to bypass branch protection, or rewrite branch-protection rules outright.

The architectural problem: how does the human safely use the elevated token *only* during the moments it's needed, without permanently widening the agent's scope or leaving the token sitting somewhere an agent could read it?

This ADR records the third (and intended-final) iteration of how we answer that question.

### History

| Iteration | Pattern | Year-2026 PR | Lifespan |
|---|---|---|---|
| **v1** | Manual `gh auth login` swap to classic PAT, run script, swap back to fine-grained PAT, delete classic token | (predates the fix sequence) | up to PR #942 |
| **v2** | `env GH_TOKEN=$(gpg -d ~/.secrets/classic-pat.gpg) poetry run python tools/SCRIPT.py` — env-scoped to a single child process, gpg-encrypted at rest | #942 | one day in production |
| **v3 (this ADR)** | `with classic_pat_session() as pat:` — gpg-decrypted *inside* the Python process, held only as a local heap variable, consumed via `requests` (`Authorization: Bearer <pat>`) | #959 / #966 | active |

The iterations were not a planned roadmap. v2 was shipped as "good enough" the day the threat model was first reasoned about properly. The user pushed back the next day asking whether the Python script could deterministically remove the variable from the parent shell's environment after it ran. The honest answer was no — child processes can `os.environ.pop` from their own env block but cannot reach into the parent shell's env. That question forced a clearer look at the threat model and surfaced v3 as the design that actually closes the gap.

## 2. Threat model

| Pattern | At-rest exposure | In-flight exposure | Process-env exposure | Snoopable by sibling user-space process |
|---|---|---|---|---|
| `gh auth login` swap | Plain text in `~/.config/gh/hosts.yml` until manually swapped back | High (paste into terminal) | None (gh CLI reads its own storage) | Via filesystem — any agent reading `gh auth` storage gets the token |
| `export GH_TOKEN=...; cmd; unset GH_TOKEN` | Depends on source | Yes (terminal echo + history) | Yes (parent shell + every child) | Yes — `/proc/<pid>/environ` (Linux), `NtQueryInformationProcess` (Windows) |
| `env GH_TOKEN=$(gpg -d ...) python ...` (#942 / v2) | gpg-encrypted | Decrypted in command-substitution buffer; child env block | Yes (child only) | Yes — same OS APIs, smaller window |
| **`with classic_pat_session() as pat:` (#959 / v3 / this ADR)** | **gpg-encrypted** | **Decrypted in Python heap only** | **No** | **No, without `ptrace` / admin scanning live process heap during the seconds the PAT is in scope** |

The remaining attack surface is essentially: an attacker with `ptrace` privileges or admin scanning the live process heap during the seconds the PAT is in scope. Every cheaper class of attack — sibling-process env-block snooping, shell-history grepping, on-disk file reading, `gh auth` storage hijacking — is closed.

## 3. Decision

**All future tools that need classic-PAT scope MUST acquire the PAT via `tools/_pat_session.classic_pat_session()` and consume it through direct HTTPS calls (`requests` with an `Authorization: Bearer <pat>` header).**

Concretely, the rule:

- The PAT is decrypted by `subprocess.run(["gpg", "--quiet", "--decrypt", str(pat_path)], ...)` inside the calling Python process. `gpg-agent` prompts for the passphrase on first call (then caches per its TTL).
- The decrypted PAT is yielded as a local variable inside a context-manager scope (`with ... as pat:`).
- The caller passes `pat` into `requests`/`pygithub` calls directly. **Never set `os.environ["GH_TOKEN"] = pat`. Never pass the PAT via subprocess argv. Never log it.**
- When the `with` block exits, the local binding is `del`'d. (Python strings are immutable, so this is symbolic — the bytes may persist in the heap until garbage collection. The primary protection is process scope: the OS reclaims the address space when the script exits.)
- `gh` CLI is forbidden in privileged paths because invoking `gh` requires either an env var (re-introduces the v2 leak) or a stored credential (re-introduces v1).

The module is intentionally minimal (`~50` lines). It does not wrap the GitHub API itself — callers compose their own HTTP requests. This keeps each tool explicit about what it does with the elevated scope.

## 4. Alternatives considered

- **OS-level secret store** (Windows Credential Manager / macOS Keychain / Linux libsecret). Most secure long-term, biggest plumbing. Worth filing as a follow-up if `_pat_session.py` proves to be the right abstraction layer to swap underneath. Premature now.
- **GitHub App installation token** for every privileged operation. Heavier — requires designing which Apps have which permissions across the fleet. Real engineering. Also still requires *some* path to install/configure those Apps, which loops back to needing a classic PAT once.
- **Server-side provisioning** (org webhook on `repository.created` triggers a Cloudflare Worker that does the whole setup). Biggest lift; user never touches a classic PAT. Architecturally clean but out of reach today and erases the local-tool composability we depend on.
- **Continue with v2 (env-scoped)**. Shipped, works, lower complexity. Rejected because the snoopable-by-sibling-process gap is exactly the failure mode an agent-coexistence environment makes likely (multiple Claude Code sessions, Codex sessions, Gemini sessions running simultaneously under the same OS user).

## 5. Consequences

### Good

- Eliminates env-block exposure entirely. The PAT no longer lives in a place sibling user-space processes can read.
- No `unset` to forget. The `with`-block scope handles cleanup automatically.
- No "swap back" step. Compared to v1, we removed the human-error opportunity where the classic token gets left in `gh auth` storage.
- Explicit auth surface. Each tool that needs elevation declares it via `with classic_pat_session() as pat:` — easy to grep for, easy to audit. (`grep -r "classic_pat_session" tools/` enumerates every privileged path in seconds.)
- Composes with `requests` rather than `gh` CLI. The tool is portable to non-Windows environments without the gh-CLI process-spawn overhead.
- Aligns with the principle of least privilege at the *moment-of-use* level: scope expands only inside the `with` block, contracts the moment it exits.

### Bad / costs

- More plumbing per tool. Tools must compose `requests` calls and own headers/timeouts/retries themselves rather than delegate to `gh`. The first wave of migrated tools (#961-#965) is real work.
- The `gh` CLI's own correctness checks (rate-limit handling, retry logic, error message formatting) don't apply to direct `requests` calls. Each tool re-implements what it needs.
- `gpg-agent` passphrase caching (default ~10 min) is a usability prop that's also a small risk: if the user steps away from an unlocked terminal mid-cache-window, a different process spawned in that window can decrypt without prompting. Mitigation: shorter `default-cache-ttl` in `~/.gnupg/gpg-agent.conf`, or `default-cache-ttl 0` for hostile environments.
- Best-effort heap scrub. Python strings are immutable; `del pat` releases the binding but the bytes may live in the heap until GC. The primary protection is process scope, not language-level scrubbing. A real adversary with `ptrace`/admin can still extract the bytes during the seconds the script runs.
- The setup ritual (one-time `cat /dev/clipboard | gpg -c -o ~/.secrets/classic-pat.gpg`) is a learning curve for new contributors. The error message in `_pat_session.py` documents the safe form (post-#985); previously it documented the wrong form (`echo '<pat>' | gpg`) which would have leaked the secret into shell history exactly at the moment of onboarding.

### Migration

Five existing tools still use v2 (env-scoped) at time of writing — see issues #961-#965, each a separate follow-up PR:

- `tools/merge_sentinel_permissions_prs.py`
- `tools/fix_branch_protections.py`
- `tools/deploy_auto_reviewer_fleet.py`
- `tools/new_repo_setup.py` (privileged paths only)
- `tools/test_governance_system.py` (audit mode only)

Until those land, mixed v2/v3 usage is tolerated. New tools MUST start at v3.

## 6. References

- PR #966 (issue #959) — the `_pat_session.py` module
- PR #967 (issue #960) — `sentinel_migrate.py`, the first production caller
- PR #976 (issue #975) — `fleet_delete_pr_sentinel.py`, the second
- PR #981 (issue #980) — `--external-issue-ref` + timeout flag, learnings from the first fleet run
- PR #985 (issue #968, #971) — clipboard-pipe setup hint + dependabot tool brought to parity
- PR #942 — the predecessor v2 pattern
- Blog draft: `dispatch/drafts/2026-04-18-pat-swap-friction-pattern-from-AssemblyZero.md` — full design narrative including the user-pushback that surfaced v3
- Follow-up draft: `dispatch/drafts/2026-04-21-in-process-pat-decryption-from-AssemblyZero.md` — companion piece on the v3 pattern itself
