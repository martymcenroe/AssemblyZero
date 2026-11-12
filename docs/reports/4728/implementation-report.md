# Implementation report: #4728

Nothing reads the per-repository Cerberus secrets `REVIEWER_APP_ID` and `REVIEWER_APP_PRIVATE_KEY` since Auto Review's retirement (#4724 traced every reader), but repositories created while it ran still hold them, in the Actions scope, the Dependabot scope or both. This branch adds the program that removes them and retires everything that deployed them.

## R1 to R6: `tools/fleet_remove_cerberus_secrets.py`

- **Credential.** Reading or deleting a repository's secrets needs a permission the agents' fine-grained token lacks, so the program opens `classic_pat_session()` (ADR-0216) and sends every call through `_gh_retry.request_with_retry` with the PAT in the `Authorization` header only. It imports neither `os` nor `subprocess`. The session's `reason` names no repository, since this repository is public.
- **What it reads.** `/user` first (standard 0017's pre-flight), then every repository the token's account owns (`/user/repos?affiliation=owner`, paged), archived ones last. For each repository it asks for each of the two secrets in each of the two scopes by name: 200 holds it, 404 does not, and anything else stops the run. An unreadable repository is never read as clean.
- **Dry run by default.** Without `--apply` it lists, prints what each repository holds and ends with how many hold a secret and the `--apply` command. It writes nothing.
- **`--apply`.** For each secret found: a `DELETE` that must answer 204, then a `GET` that must answer 404. Repositories are handled one at a time, in listing order.
- **Printing.** Each step prints as it happens, with `flush=True`: what the run will do and that a passphrase box is coming, before the decryption; `decrypted` straight after it; then the token check, the listing, one line per repository and one line per deletion and read-back.
- **Stopping.** The first failure (a refused decryption, a failed token check or listing, a read that is neither 200 nor 404, a refused deletion, a read-back that still finds the secret) prints `STOPPED at <step>: ...` on stderr, naming the repository, the scope and the secret, then how many repositories were cleaned, were already clean and were not finished, and exits 1. An archived repository that refuses a deletion is named with what to do: unarchive it, rerun, archive it again.
- **Rerun.** Every run lists again, so a repository already clean prints `clean` and gets no call beyond its four reads.
- **No other secret.** `secret_url()` builds every secret URL and raises `ValueError` for any name but the two, or any scope but `actions` and `dependabot`, before a call is made.
- `--repo NAME` (repeatable) limits a run; a name the account does not own stops the run before any write.

## R7: the deploy path is retired

- `tools/deploy_cerberus_secrets.py` and `tests/unit/test_deploy_cerberus_secrets.py` are **removed**, as #4719 removed the Auto Review deploy tool. A refusing stub would be dead code that every search for the secrets keeps finding.
- `tools/new_repo.py` imported the tool's `deploy_to_repo` and `verify_secrets` for `--cerberus-pem` and `--cerberus-pem-gpg`. Removing the tool alone would have left those flags calling names that no longer exist, and keeping them would have kept a deploy path, so both flags go with it: the import blocks (including the one #3212 found to be malformed), `cerberus_pem_session` from the import list, `_deploy_cerberus()`, the two conflict checks, the deploy and verify steps inside the classic-PAT session, the summary line, the post-deploy advice and the `cerberus_status` argument of `failed_steps()`. argparse now refuses either flag with exit 2. `cerberus_pem_session` stays in `_pat_session.py`, because `tools/cerberus_worker_key.py` puts the key in the pr-sentinel Worker with it.
- Two printed lines of `new_repo.py` named the deploy as an example of a step gated on the initial push; they now name the steps that still are.
- Code that named the tool historically now says it is retired: `tools/_gh_retry.py`, `tools/fleet_ids.py`, and the classifier prompt in `tools/audit_deferred_scope.py`.

## Docs

- Runbook 0927: the purpose, the checklist, the defaults, the under-the-hood table, "What the script handles", the env-block note, Section 4 (now how to remove the secrets older repositories hold) and a history row.
- Runbook 0939: the fourth copy of the key, and the Tool Reference entry, now for the removal program.
- Runbook 0901: the Quick Start note, the Command Reference, post-setup step 1 and a history row.
- Standard 0016 and `docs/0003-file-inventory.md`.
- Historical audit ledgers and reports, and the dated rows of each runbook's history table, are left as written (R8).

## Left for the operator

T3 needs his run: `--apply`, then the dry run, whose last line must read `no repository of the N holds either secret`.
