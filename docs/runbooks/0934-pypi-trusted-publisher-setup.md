# PyPI Trusted Publisher Setup

**Runbook 0934 — one-time per-repo browser steps to enable tag-push PyPI publishes from a repo bootstrapped by `tools/new_repo_setup.py` (#1074).**

`new_repo_setup.py` deploys `release.yml` to new Python repos **only when `--pypi` is passed** (as of #1269 — was default-on, now opt-in). The workflow is wired to publish to PyPI via OIDC Trusted Publisher — no API token is stored in GitHub secrets. But OIDC trust requires a one-time registration on PyPI's side, and **PyPI's publisher-registration UI is browser-only**. There is no API. This runbook covers the human steps; the script handles everything else.

If you did NOT pass `--pypi` when creating the repo, this runbook does not apply — the repo has no `release.yml` and won't try to publish. To add PyPI publishing to an existing repo, re-run scaffolding or add `release.yml` manually.

---

## Prerequisites

- Repo created via `tools/new_repo_setup.py <name> --pypi`.
- The script's output should include `Created auto-reviewer.yml + release.yml (PyPI publish on tag)`.
- `pyproject.toml` in the repo has `[tool.poetry.scripts]` and `[tool.poetry.urls]` blocks populated. Verify with `grep -A3 "tool.poetry.scripts" pyproject.toml`.
- `.github/workflows/release.yml` exists and uses `environment: pypi` (this is the default; don't edit unless you know what you're doing).
- A PyPI account at https://pypi.org/. If you don't have one, register first.

---

## Section 1 — Register the pending publisher on PyPI

1. Open https://pypi.org/manage/account/publishing/ in a browser. Log in if prompted.

2. Scroll to **"Add a new pending publisher"**. (If you've never published this package name before, "pending publisher" is the right form. Once the first publish succeeds, the entry promotes to "trusted publisher" automatically.)

3. Fill in:

   | Field | Value |
   |---|---|
   | **PyPI Project Name** | The lowercased package name. Matches `name` in your `pyproject.toml`'s `[tool.poetry]`. Example: `boostgauge` for `martymcenroe/boostgauge`. |
   | **Owner** | Your GitHub username (e.g., `martymcenroe`). |
   | **Repository name** | The lowercased repo name on GitHub. Matches the URL path. Example: `boostgauge`. |
   | **Workflow filename** | `release.yml` |
   | **Environment name** | `pypi` |

4. Click **"Add"**.

5. Confirmation: PyPI shows the new pending publisher in the list. The package name is reserved against this publisher — nobody else can register it now.

**Common mistakes:**
- Mismatched project name (e.g., `Boostgauge` vs. `boostgauge`). PyPI is case-insensitive on lookup but stores what you type. Always use lowercase.
- Mismatched workflow filename (e.g., `release.yaml` vs. `release.yml`). The script always emits `.yml`; if you changed it, this step has to match.
- Wrong environment name. The script emits `environment: pypi` exactly. Match it.

---

## Section 2 — First tag push (promotion event)

The publisher is currently "pending." It promotes to "trusted" the first time a tag-push from the matching workflow successfully completes the OIDC handshake.

```bash
cd /c/Users/mcwiz/Projects/<repo>
git tag v0.1.0
git push origin v0.1.0
```

Watch the workflow run:

```bash
gh run watch --repo <owner>/<repo>
```

Expected sequence:

1. **Job: release** starts.
2. Step "Build distributions" produces `dist/*.tar.gz` and `dist/*.whl`.
3. Step "Publish to PyPI" sees `id-token: write` permission, mints an OIDC token, sends it to PyPI's `/publish` endpoint.
4. PyPI matches the token's claims (workflow file + env + repo + owner) against the pending publisher record from Section 1.
5. Match succeeds → publish proceeds → distributions uploaded.

**On success:** The release page at `https://pypi.org/project/<package>/0.1.0/` is live within a few seconds. Verify with:

```bash
pip install <package>==0.1.0
<package>  # if entry point is wired (default)
```

**On failure:** Section 3.

---

## Section 3 — Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Workflow step "Publish to PyPI" fails with `Trusted publisher not found` | Section 1 not done OR fields mismatched | Re-check the publisher record on PyPI. Owner / repo / workflow filename / environment must all match exactly. |
| Workflow fails at "Publish to PyPI" with `Project name not available` | The package name is already taken on PyPI by someone else | Pick a different name. Update `pyproject.toml` `[tool.poetry] name = "..."` AND the PyPI publisher record (delete + re-add with new name). |
| Workflow doesn't start at all on tag push | `release.yml` missing OR tag pattern doesn't match | Verify `release.yml` exists in `.github/workflows/`. Check tag is `v*.*.*` format — `v0.1.0` matches; `0.1.0` does NOT. |
| Workflow runs but skips the release job | `if:` filter on the job (none in the default template) OR ref protection | Check `gh run view <id>` for the skip reason. |
| Publish step fails with `403 Forbidden` from PyPI | OIDC token's `aud` claim mismatch — typically a PyPI-side outage or the package was reserved by someone else after Section 1 | Wait 5 minutes and retry the tag push (delete the failed run, re-tag, push). If persistent, file a PyPI support ticket. |
| Publish succeeds but `pip install <pkg> && <pkg>` doesn't run anything | `[tool.poetry.scripts]` block missing OR points at a module that doesn't exist | Check `pyproject.toml`. The script writes `<module> = "<module>.__main__:main"` by default. If you renamed the module without updating this, fix it manually and re-publish a new version. |

---

## Section 4 — Subsequent releases

After the first successful publish, every tag push of the form `v*.*.*` publishes automatically. No further browser steps. The workflow:

1. Tag → push → workflow triggers.
2. OIDC handshake proceeds (now against the trusted publisher, no longer pending).
3. Distribution uploads.

**Versioning discipline:**
- The version number in `pyproject.toml` `[tool.poetry] version = "..."` should match the tag. Mismatches result in PyPI rejecting the publish (`File already exists` for the tagged version, or wrong version landing on PyPI).
- Bump the version BEFORE tagging. Common workflow:
  ```bash
  poetry version patch  # 0.1.0 -> 0.1.1
  git add pyproject.toml
  git commit -m "chore: bump to v0.1.1"
  git tag v0.1.1
  git push origin main v0.1.1
  ```

---

## Section 5 — Test PyPI (optional)

If you want to test the publish path without polluting the real PyPI index:

1. Add a separate workflow `release-testpypi.yml` (manual edit; not generated by the script).
2. Use `repository-url: https://test.pypi.org/legacy/` in the publish action.
3. Register a separate pending publisher on https://test.pypi.org/manage/account/publishing/ with the same fields.
4. Trigger via a different tag pattern (e.g., `pre-v*.*.*`).

This is out of scope for the default `new_repo_setup.py` flow. If demand for it grows, file a follow-up issue to add a `--testpypi` flag.

---

## Section 6 — Rolling back a published release

PyPI **does not allow re-uploading** the same version (filename collision). If a published version is broken:

1. **Yank the version** from PyPI: https://pypi.org/manage/project/<package>/release/<version>/ → "Yank release."
   - Yanked versions are still installable by pinned consumers but excluded from `pip install <pkg>` (latest) resolution.
   - This is the recommended path for "this version had a critical bug."
2. **Bump and republish** with a new version (e.g., `0.1.0` → `0.1.1`). The yanked version stays as a historical record.

**Do not** delete the release entirely unless absolutely necessary — it breaks anyone with the version pinned.

---

## Maintenance

When `release.yml` template in `tools/new_repo_setup.py` changes:

1. Update the template string in `create_github_workflows()`.
2. Re-run `new_repo_setup.py` on a throwaway test repo to verify the new workflow lands correctly.
3. For repos already created with the old workflow, decide: leave them on the old version, or land a follow-up PR per repo to update `release.yml` (Contents API path per ADR-0216).
4. Update this runbook if the publisher fields change (e.g., environment name, workflow filename).

---

## References

- **PyPI Trusted Publisher docs:** https://docs.pypi.org/trusted-publishers/
- **OIDC + GitHub Actions:** https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect
- **PyPI publishing GitHub Action:** https://github.com/pypa/gh-action-pypi-publish
- **AZ #1074** — issue that surfaced the need for this runbook.
- **`tools/new_repo_setup.py`** — script that deploys `release.yml`.
- **Standard 0009** — canonical project structure (defines `src/<module>/` layout).
- **Speed-run plan** — `boostgauge/docs/speedrun/0003-az-implementation-plan.md` §6.4 calls out the browser-only nature of this step.
