# Test report: #4784

`tests/unit/test_store_pr_sentinel_app_key.py`, 20 tests: gpg and gpg-connect-agent faked by replacing `subprocess.run`, GitHub by replacing `urlopen`, a generated RSA key, every path under `tmp_path`.

Covered: the JWT verifies with the public key and carries `iss`; the App ID comes from the config; the dry run changes nothing; GitHub 401 and 200 with another id stop with exit 1 and keep the key, in dry run and apply; a missing, relative, non-PEM, EC or symlinked key file stops before gpg and GitHub; an existing `<out>` or `<out>.tmp` is refused untouched; apply sends exactly App ID, newline, PEM on stdin, keeps them out of argv and environment, writes no plaintext file, leaves `<out>` mode 600 in a mode 700 folder and removes the key; a decrypt mismatch, a cancelled box and an interrupt keep the key and remove the `.tmp`; root is refused; the docs name the program.

Targeted run, 2026-11-15, with the fleet-ids, pat-session, gpg-wait, new-repo guidance, spelled-root, loud-failure, console and api-key tests: `6 failed, 160 passed`. The six are `TestRealGpg`, which fail on Ubuntu on main too (#4766). Ruff on the new files: all checks passed.

Unit tier, 2026-11-15, on Ubuntu with pytest directly: `6 failed, 15360 passed, 66 skipped, 7 deselected, 7 xfailed, 34 warnings in 973.10s (0:16:13)`. The six are the same `TestRealGpg` tests; no other test failed.

Not tested: the program against real gpg. Whether gpg's box asks for the new passphrase once or twice under `--batch` is unchecked; a mistyped passphrase is caught either way, because the decrypt check fails and the key file is kept.
