# Classic-PAT Fleet Tooling Reference Architecture

A cross-fleet playbook for writing Python tools that perform privileged GitHub operations using the in-process classic PAT pattern (ADR-0216). Derived from production experience with `sentinel_migrate.py`, `fleet_delete_pr_sentinel.py`, `merge_aletheia_603_audit_gate.py`, `fleet_set_delete_branch_on_merge.py`, and `new_repo_setup.py`.

This is not prescriptive about specific algorithms. It captures **patterns that worked**, **patterns that didn't**, and **decisions you'll face early** that are expensive to change later.

---

## 1. When to Use This Pattern

Three classes of GitHub operation require a classic PAT (full `repo` scope and/or `Administration: write`) that the day-to-day fine-grained PAT cannot perform:

| Operation | API endpoint | Why fine-grained fails |
|---|---|---|
| **Workflow file edits** | `PUT /repos/{O}/{R}/contents/.github/workflows/...` | Fine-grained PATs cannot create or update files under `.github/workflows/` even with `Contents: write` granted. The `workflow` scope is classic-only on personal-account repos. |
| **Branch protection** | `PUT /repos/{O}/{R}/branches/{B}/protection` | Requires `Administration: write` (fine-grained) or classic `repo`. Most agent-grade fine-grained PATs deliberately omit Administration. |
| **Repo settings** | `PATCH /repos/{O}/{R}` | Same as branch protection. The 2026-04-30 fleet-wide flip of `delete_branch_on_merge` confirmed fine-grained PATs return 403 here. |
| **Repo creation** | `POST /user/repos` | Classic `repo` scope; fine-grained PATs may lack the right account-level permissions. |
| **Secret deployment** | `PUT /repos/{O}/{R}/actions/secrets/...` | Requires `Administration: write` (or classic `repo` + `admin:repo_hook` for some operations). |

If your tool only does the things below, you DON'T need classic PAT — use the fine-grained PAT via `gh api` or `gh pr ...` directly:
- Reading repo metadata, PRs, issues, checks
- Opening, editing, merging PRs whose diff does NOT touch `.github/workflows/`
- Creating issues, comments, labels
- Reading actions runs, jobs, logs

If your tool needs anything in the table above, you need classic PAT, and you need this pattern.

---

## 2. The `classic_pat_session()` Contract

Source: `tools/_pat_session.py`. Authoritative design: ADR-0216.

Yields the gpg-decrypted classic PAT as a string, scoped to a `with` block:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pat_session import classic_pat_session

with classic_pat_session() as pat:
    # PAT lives here. Use for HTTPS calls.
    requests.put(url, headers={"Authorization": f"Bearer {pat}"}, ...)
# PAT is del'd on __exit__. Do not retain references after this block.
```

### What it does

- Reads `~/.secrets/classic-pat.gpg`
- Spawns `gpg --quiet --decrypt` as a subprocess
- Yields the decrypted PAT (string) to the caller
- `del`'s the local binding on exit (best-effort heap scrub)
- Retries up to `MAX_GPG_ATTEMPTS=5` times on bad passphrase (mistypes are common with no-echo pinentry)
- Times out after `GPG_TIMEOUT_S=180` per gpg attempt

### What it does NOT do

- Provide HTTP retry / backoff (caller's job — Section 4)
- Provide rate-limit handling (caller's job)
- Provide auth pre-flight check (caller's job)
- Cache the PAT across calls (intentional — every call decrypts fresh)
- Cache the gpg passphrase (intentional — see Section 6.2)

### Caller MUSTs (per ADR-0216 §3)

- Pass `pat` only as a function argument, never via `os.environ` or subprocess argv
- Send via `Authorization: Bearer <pat>` HTTPS header
- Never log it (not even truncated, not even hashed — length is information)
- Calling `gh` CLI inside the `with` block is FORBIDDEN — gh requires env or stored credentials, both of which leak

### Caller MUSTs (per 2026-04-30 hardenings)

- Assume `default-cache-ttl 0` and `max-cache-ttl 0` are set in `~/.gnupg/gpg-agent.conf`. Otherwise sibling processes can silently re-decrypt during the cache window — defeating the in-process-only guarantee.
- The user runs the script personally; agents must NOT invoke it via their tool surfaces. Section 5.

---

## 3. Authoring Checklist

Every fleet tool that imports `classic_pat_session()` should have:

- [ ] **Module docstring** with: purpose, required scopes, the agent-must-not-run rule, the TTL=0 assumption, usage examples, and a `--dry-run` flag mention
- [ ] **`from _pat_session import classic_pat_session`** with the standard `sys.path.insert(0, ...)` shim for direct invocation
- [ ] **Pre-flight `/user` check** as the first call inside the `with` block — fails fast if auth is wrong
- [ ] **Per-target try/except** in the main loop — one target's failure must not abort the whole run
- [ ] **`_request_with_retry()`** wrapping all HTTP calls (Section 4)
- [ ] **Idempotency** — re-running the script must skip already-applied changes (Section 7)
- [ ] **Distinct status categories** — at least: success, no-op, permission-denied, error
- [ ] **Final summary** — counts per status
- [ ] **Non-zero exit code** on any errors or permission-denied
- [ ] **`--dry-run` flag** — list what would happen, take no action
- [ ] **`--repos` (or similar) flag** — let the user run against a subset for testing
- [ ] **Safety cap** — refuse to process > N targets in one run unless explicitly waived (prevents fat-finger fleet-wide damage)

---

## 4. HTTP Patterns

### 4.1 Standard headers

`_gh_headers(pat)` — single source for the auth + accept + version triplet:

```python
def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
```

### 4.2 Retry with backoff and rate-limit awareness

`_request_with_retry(method, url, pat, **kwargs)` — wraps `requests.request`:

| Condition | Handling |
|---|---|
| Network error (`ConnectionError`, `Timeout`) | Retry with exponential backoff (1s → 2s → 4s, MAX_RETRIES=4) |
| HTTP 5xx | Retry with same backoff |
| HTTP 429 | Honor `Retry-After` header, sleep, retry |
| HTTP 403 + `X-RateLimit-Remaining: 0` | Primary rate limit; sleep until `X-RateLimit-Reset`, retry |
| Other HTTP 4xx | Return as-is — caller decides handling |
| Exhausted retries | Raise the last exception (or RuntimeError if no exception) |

Reference implementation: `tools/fleet_set_delete_branch_on_merge.py` (~50 lines).

### 4.3 Why retries matter

GitHub API has occasional 502/503 spikes (especially during incidents — check status.github.com). Without retry, a fleet tool that hits 50 repos has a non-trivial probability of one transient failure aborting partway. With retry+backoff, the probability drops to near zero.

`merge_aletheia_603_audit_gate.py` lacked retry initially (its operations were one-shot, not fleet). The 2026-04-30 session ran it cleanly because GitHub was healthy — but the window for transient failure is nonzero. New tools that loop over many targets MUST use `_request_with_retry`.

### 4.4 Where to put the helper

Three options, none clearly best:

- **Inline in the tool** (current state of `fleet_set_delete_branch_on_merge.py`) — simplest, but duplicates code across tools
- **`tools/_gh_http.py`** (proposed, not yet built) — dedicated HTTP helper module
- **`tools/_pat_session.py`** — co-locate with `classic_pat_session()`, since both deal with elevated GitHub calls

For now, inline is acceptable. As more tools land that use the same helper, extracting becomes worthwhile. Tracked at #1022 for `new_repo_setup.py`'s migration.

---

## 5. The Agent-Must-Not-Run Discipline

Per ADR-0216 + 2026-04-30 hardenings: scripts importing `classic_pat_session()` MUST be invoked by the user, not by an agent's Bash/tool surface.

### Why

The Python process that decrypts the PAT belongs to whoever's child it is. If the agent invokes it (via Claude Code's Bash tool, Codex, Gemini, etc.), the agent has theoretical heap-read access during the seconds the PAT is in scope. v3's "PAT lives only in heap" guarantee assumes the heap is the user's, not the agent's.

The 2026-04-30 session demonstrated this concretely: the agent attempted to run `merge_aletheia_603_audit_gate.py` via its Bash tool twice. The user redirected: *"You should not be running the Python program for me. That gives you access to the gpg key, right?"* The discipline was added the same day.

### Authoring requirement

Every fleet tool's docstring should include this warning prominently. Future agents reading the file will internalize the rule.

Example (from `fleet_set_delete_branch_on_merge.py`):

```python
"""...

OPERATIONAL RULE (per ADR-0216 + 2026-04-30 hardenings):
  This script MUST be run by the user in their own Git Bash. It MUST NOT be
  invoked by an agent (Claude Code, Codex, Gemini) via the agent's Bash tool.
  Reason: the agent's subprocess inherits theoretical heap-read access to the
  PAT during the seconds the script runs.
..."""
```

### Operational requirement

When an agent designs a flow that needs a fleet tool, it should:
1. Write the tool
2. Hand the user the invocation (file path + command)
3. Wait for the user to report results
4. Verify side effects via GitHub API (read-only, fine-grained PAT works)
5. Continue based on what GitHub says, not what the agent's subprocess saw

The agent-facing memory `feedback_user_runs_classic_pat_scripts.md` records this rule and is auto-loaded on every Claude Code session start.

---

## 6. gpg Hygiene

### 6.1 The encrypted PAT file

`~/.secrets/classic-pat.gpg` — symmetric `gpg -c` encrypted (no asymmetric keypair, just a passphrase). Created via the safe one-time setup ritual in `_pat_session.py`'s docstring (uses `cat /dev/clipboard | gpg -c -o ...` — keeps the secret out of shell history and out of process argv).

### 6.2 gpg-agent caching: must be disabled

`~/.gnupg/gpg-agent.conf` MUST contain:

```
default-cache-ttl 0
max-cache-ttl 0
default-cache-ttl-ssh 0
max-cache-ttl-ssh 0
```

Apply with `gpgconf --kill gpg-agent`. Verify with `gpg --decrypt ~/.secrets/classic-pat.gpg > /dev/null` — should prompt pinentry on every call.

### Why TTL=0 is mandatory, not optional

While a passphrase is cached (default 600s), any process running as the same OS user can call `gpg --decrypt classic-pat.gpg` and silently obtain the PAT. gpg-agent supplies the cached passphrase without prompting; gpg returns the plaintext. No pinentry, no notification, no trace.

The "in-process only" guarantee from ADR-0216 is a guarantee about where the PAT is held *during one script's lifetime*. It is NOT a guarantee about who can decrypt the file *at all*. Caching erases the difference: while the cache is warm, anyone with read access to the `.gpg` file is functionally an authorized decrypter.

ADR-0216 §5 originally framed this as a "small risk" with TTL reduction as a mitigation. The 2026-04-30 hardening showed it's structural — in a multi-agent environment (multiple Claude Code sessions, Codex, Gemini all running as the same user), every co-resident agent is a potential silent-decrypt vector during the cache window. The mitigation is required.

### 6.3 Rotation

The classic PAT and the gpg passphrase should rotate periodically. Procedure: `docs/runbooks/0930-gpg-and-classic-pat-rotation.md`. Rotation makes "is the current key compromised?" stop being a question by making the answer not matter.

After Phase 1 of #1016 (move gpg key to YubiKey), the at-rest gap closes structurally — the file becomes undecryptable without physical possession of the device.

---

## 7. Idempotency

Fleet tools must be re-runnable without side effects. The pattern:

1. **Read current state** of each target (e.g., `delete_branch_on_merge` value)
2. **Compare** with desired state
3. **If equal: skip with a `no-op` status**
4. **If different: apply change**

### Why

Fleet tools occasionally crash mid-run (network, rate limit, 5xx that exhausts retries, user ctrl-C). The user re-runs. If the tool is not idempotent, partially-applied state becomes a manual reconciliation problem.

### Reference

`fleet_set_delete_branch_on_merge.py` checks `delete_branch_on_merge` before PATCHing. Already-true repos return `already_on` status; only false-state repos get a PATCH.

For tools that CREATE rather than UPDATE (e.g., file a tracking issue, create a branch, open a PR), use search-or-create:

```python
existing = find_existing(repo, branch_pattern, pat)
if existing:
    return ("skipped", f"existing PR #{existing}")
# else: create
```

`fleet_delete_pr_sentinel.find_existing_deletion_pr` is the canonical example. `merge_aletheia_603_audit_gate.find_existing_pr` is the single-target version.

---

## 8. Common Pitfalls (2026-04-30 Lessons)

These are mistakes made and corrected during the hardening session.

### 8.1 CRLF / LF line endings (Windows)

`Path.read_bytes()` returns CRLF-terminated bytes when the working tree is Windows-checked-out (`core.autocrlf=true`). Submitting raw bytes via Contents API stores CRLF in the blob. Future commits (which go through normal `git commit` autocrlf-normalization) will then show as whole-file diffs against the CRLF-stored blob.

Always normalize before submitting:

```python
content = LOCAL_FILE.read_bytes().replace(b"\r\n", b"\n")
```

Reference: `merge_aletheia_603_audit_gate.py` (post-fix line 282).

### 8.2 `mergeable_state` for self-referential cleanups

A PR that removes the very check causing it to be UNSTABLE (e.g., audit-schedule, pr-sentinel.yml) can never reach `clean` — the check that's about to die runs on the PR that kills it. Strict-clean polling waits forever.

Pattern: `wait_for_mergeable()` should accept `clean` OR `unstable` for self-referential cleanups. `dirty` and `blocked` (after at least one poll cycle) return as-is for the caller to abort.

Reference: `fleet_delete_pr_sentinel.wait_for_mergeable` — accepts both.

### 8.3 30-second gpg timeout was too short

`_pat_session.GPG_TIMEOUT_S = 30` was too short for a fresh pinentry prompt the user wasn't expecting. Bumped to 180s on 2026-04-30. Cached calls still return instantly; the timeout matters only for first-time-typed prompts.

### 8.4 Mistypes silently abort

Pinentry-w32 doesn't echo characters. Long passphrases get mistyped. Without retry, the tool aborts on the first wrong attempt with `Bad session key`. `_pat_session.py` now retries up to 5 times — caller sees `gpg decrypt failed (attempt N/5): ... Retrying — pinentry will prompt again.`

### 8.5 Edit-and-resume after partial run

If the script fails mid-flight and you edit the script before re-running, the resume picks up against the OLD branch state on origin (which may now have a partial commit). Either: delete the remote branch + PR before re-running, or finish the original run before editing the script.

### 8.6 Writing the decrypted PAT to disk for debugging

NEVER. Even to /tmp, even with `chmod 600`, even briefly. The Sentinel hook will (correctly) block this. Use the PAT as a function argument; never persist it.

---

## 9. Reference Implementations

| Tool | Purpose | Robustness | Use as model? |
|---|---|---|---|
| **`fleet_set_delete_branch_on_merge.py`** (2026-04-30) | Flip repo setting fleet-wide | Pre-flight, retry+backoff, rate-limit, idempotent, status enum, safety cap | YES — best model for fleet-update tools |
| **`merge_aletheia_603_audit_gate.py`** (2026-04-30) | One-shot land single PR via API | Idempotent, accepts unstable for self-ref, CRLF normalize, `--skip-N-nudge` | YES — best model for one-shot tools |
| **`fleet_delete_pr_sentinel.py`** (older) | Fleet-wide file deletion + PR + merge | Per-repo try/except, no retry/backoff | Partial — copy structure, add retry from `fleet_set_delete_branch_on_merge.py` |
| **`sentinel_migrate.py`** (older) | Branch protection updates | Simplest v3 example, no retry | Partial — read for structure only |
| **`new_repo_setup.py`** (complex) | Full new-repo orchestration | Wrapping try/except, no retry on privileged calls | NO — read for context, but #1022 tracks robustness debt |
| **`merge_sentinel_permissions_prs.py`** | DEPRECATED v1 (gh auth swap) | — | NO — anti-example. Documented for context only. |

---

## 10. Pitfalls to Avoid

| Pitfall | Fix |
|---|---|
| Setting `os.environ["GH_TOKEN"] = pat` | Forbidden by ADR-0216. Use `_gh_headers(pat)` instead. |
| Calling `gh` CLI inside a `with classic_pat_session()` block | Forbidden — gh requires env or stored creds. Use `requests` directly. |
| Logging the PAT | Never. Even truncated. Even hashed. Length is sensitive. |
| Skipping the pre-flight `/user` check | Fails late after gpg prompt + first iteration. Pre-flight catches scope mismatches in seconds. |
| Hardcoding repo names instead of `--repos` flag | Makes testing painful. Always provide a way to scope down for safety. |
| No safety cap on target count | A typo in the fleet-discovery query could target 10,000 repos. Cap at e.g. 50 unless overridden. |
| Forgetting the docstring agent-must-not-run rule | Future agents won't know. Put it in every fleet tool. |
| Forgetting CRLF normalization on file uploads | Whole-file diff in git. Cosmetic but ugly and confusing in code review. |
| Strict-clean polling for self-referential cleanups | Infinite wait. Accept `unstable` for that class of PR. |
| Caching the gpg passphrase | Defeats the in-process-only guarantee. TTL=0 is mandatory. |
| Running the script via the agent | The agent's subprocess inherits heap-read access to the PAT. The user runs it. |

---

## 11. Quick-Start Checklist for a New Fleet Tool

When spinning up a new tool that needs classic PAT:

1. **Identify the privileged operation** — workflow file, branch protection, repo settings, etc. Confirm fine-grained PAT can't do it (probe with `gh api -X PATCH ...` first — if it returns 403, you need this pattern).
2. **Pick a name** — `fleet_*` for many-target loops, `merge_*` or `migrate_*` for one-shots. Match existing AssemblyZero tool naming.
3. **Copy the closest reference** — see Section 9. Don't write from scratch.
4. **Write the docstring first** — purpose, scopes, agent-must-not-run rule, TTL=0 assumption, usage. Make it grep-able for future agents.
5. **Implement `_gh_headers` + `_request_with_retry`** — until #1022 lands a shared helper, copy from `fleet_set_delete_branch_on_merge.py`.
6. **Pre-flight `/user` check** as the first call inside the `with` block.
7. **Idempotency check** before mutation in every iteration.
8. **Per-target try/except** with status categorization.
9. **Summary print** at end with counts.
10. **Non-zero exit** if any errors.
11. **`--dry-run` flag** that lists actions without taking them.
12. **`--repos` (or similar) flag** for testing on a subset.
13. **Safety cap** — refuse > N targets without `--force` or similar override.
14. **Hand the user the invocation** — they run it, you observe results via GitHub API.
15. **File a follow-up issue** if you defer any robustness improvements (CLAUDE.md "Closing Discipline" rule).

---

## 12. Related Documents

- ADR-0216 — In-Process Classic PAT Decryption (the foundational design)
- `tools/_pat_session.py` — canonical implementation; docstring is operational MUSTs
- `docs/runbooks/0930-gpg-and-classic-pat-rotation.md` — periodic rotation procedure
- Issue #1016 — Phase 1 of post-ADR-0216 hardening: move gpg key to YubiKey
- Issue #1017 — TODO: execute gpg+pat rotation per runbook 0930
- Issue #1022 — port `_request_with_retry` into `new_repo_setup.py`
- Root `CLAUDE.md` — "When `git push` Is Rejected For Workflow Scope" + "Gotchas (learned the hard way 2026-04-30)" sections
- Blog draft `dispatch/drafts/2026-04-21-in-process-pat-decryption-from-AssemblyZero.md` — companion narrative

---

*Derived from production experience with the AssemblyZero fleet tools (2026-03 through 2026-04). Updated as new patterns emerge.*
