# Implementation report: #4784

`tools/store_pr_sentinel_app_key.py`, a program the operator runs, makes `~/.secrets/pr-sentinel-app.gpg`. The App ID comes from `config/fleet-ids.json`. The dry run checks the key file, refuses an existing `--out` or `<out>.tmp`, and proves the key with GitHub (`GET /app` as the App must answer 200 with this App's id). `--apply` pipes the bundle to `gpg --symmetric`, sets mode 600, decrypts the `.tmp` through `pr_sentinel_app_session` and compares, renames it into place, removes the key file and lists the surfaces left by hand.

`tools/_github_app_jwt.py` holds `mint_app_jwt`, copied from new_repo.py, which is unchanged.

Decided differently from the work order: the check decrypts `<out>.tmp` before the rename, so a mistyped passphrase leaves no `<out>`. The key file is also refused when it is a symbolic link or has a second hard link. The `FileNotFoundError` text in `pr_sentinel_app_session` carried the same echo recipe as its docstring and now points at the program too.

Docs: the `_pat_session` docstring, `sentinel/README.md`'s Private key row, and runbook 0927's paragraph on the bundle.
