# Implementation report: #4724

One branch with #4723, because both are loose ends of the same retirement.

## R1: who reads each per-repository Cerberus secret

The finding, with file and line, is on #4724 as a comment posted before any change. In short: `REVIEWER_APP_ID` and `REVIEWER_APP_PRIVATE_KEY`, in the Actions scope and the Dependabot scope, are read only by the retired reusable workflow `.github/workflows/auto-reviewer.yml` (lines 60-61, inside the job that is `if: false` at line 54), by the caller template kept beside it (`auto-reviewer-caller.yml`, lines 27-28), and by the per-repository callers being removed (86 on default branches, by GitHub code search). No other workflow in any owned repository names either secret, and a cross-check of 239 local checkouts agrees. The pr-sentinel Worker approves with its own Worker secrets (`sentinel/src/cerberus.js:39`, `:59`). The tools only write or check names, because the Secrets API never returns a value.

So R2 applies to both secrets, and R3 has no subject.

## R2: the checks stop requiring the secrets

- **Governance T08** (`tools/test_governance_system.py`) is retired, as T09 was: `test_cerberus_secrets()` and its call in `run_local_tests()` are removed, and a comment in its place says why and where the readers were searched. The local infrastructure tests are now T07 alone.
- **The readiness audit** (`tools/audit_fleet_auto_merge_readiness.py`): a repository is ready when its branch protection is strict. The Actions secrets stay in the TSV (`actions_secrets_complete`) for visibility, an error reading them leaves the column blank instead of turning the repository UNKNOWN, and `actions_secrets_incomplete` is no longer a failure. `REQUIRED_SECRETS` is renamed `CERBERUS_SECRETS`, since nothing requires them.
- **`new_repo.py`**:
  - The #1206 gate that refused a GitHub repository without `--cerberus-pem` or `--cerberus-pem-gpg` is removed.
  - The #1543 fallback is removed with it. It picked up `~/.secrets/cerberus-pem.gpg` by itself, which asked for a passphrase to deploy a secret nothing reads. `DEFAULT_CERBERUS_PEM_GPG` goes with it.
  - A run without a PEM flag no longer prints the "Cerberus secrets (manual)" steps.
  - The two flags stay, optional and still refused with `--no-github`. They deploy the secrets only when asked, which matters only if Auto Review's `if: false` is ever put back. Their help text says so, and the `--cerberus-pem-gpg` help no longer tells anyone to revoke the key when done, which contradicted #134.
  - The keep-the-key-active advice after an opt-in deploy now says why the key must stay active: the Worker signs with it.
- **Docs**:
  - Runbook 0901: Quick Start drops the flag, the command reference marks it optional, and post-setup step 1 says there is nothing to do.
  - Runbook 0927: the purpose, the checklist invocation, the defaults, Section 4 (now the Worker's approval, with the per-repository deploy kept under "Only if Auto Review is restored"), "What's Automatic" (whose stale "Auto-reviewer workflow file" row is replaced) and the history.
  - Runbook 0933: its readiness surface row for the secrets is removed.
  - Standard 0016: the "Missing Cerberus secrets" troubleshooting row.
  - `docs/0003-file-inventory.md`: the `new_repo.py` row.

## R3

No per-repository secret has a reader, so no check keeps a requirement. The finding is held by a test instead: `tests/unit/test_cerberus_after_auto_review.py` fails if any workflow other than the two retired Auto Review files reads either secret, if the reusable workflow's job loses its `if: false`, if a workflow the scaffolder writes reads them, or if the Worker's approval code starts naming them. Its failure message names the three checks to restore.
