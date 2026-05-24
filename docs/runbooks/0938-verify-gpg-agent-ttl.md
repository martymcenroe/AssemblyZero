# Verify GPG-Agent Cache TTL = 0

Sanity check that the gpg-agent passphrase cache is disabled (TTL=0 on all four directives) per ADR-0216 §6.2, **before** running any classic-PAT `--execute` script. Both the on-disk config AND the running agent are verified, because file-correct-but-agent-stale is a real failure mode immediately after editing the conf without restarting the agent.

Run in **Git Bash** on Windows (or any POSIX shell elsewhere).

## Why this matters

ADR-0216's in-process PAT model assumes the PAT exists only in Python heap during a script invocation. That guarantee dissolves the moment gpg-agent caches the passphrase — any sibling process under the same user account can then call `gpg --decrypt classic-pat.gpg` and silently obtain the decrypted PAT.

With TTL=0, every classic-PAT script invocation pops a fresh pinentry. A sibling's silent decrypt attempt surfaces a pinentry dialog the user can refuse. Without TTL=0, that attempt is invisible.

## Run the check

```
python tools/verify_gpg_agent_ttl.py
```

Exit 0 = pass. Exit non-zero = remediation steps printed to stdout. No third-party dependencies; uses only `gpgconf`, `shutil`, `subprocess`, and `pathlib`.

Two layers are verified:

| Layer | What's checked |
|---|---|
| 1. Conf file | `gpgconf --list-dirs homedir` reports the gpg home directory; the script reads `<homedir>/gpg-agent.conf` and confirms each of `default-cache-ttl`, `max-cache-ttl`, `default-cache-ttl-ssh`, `max-cache-ttl-ssh` is set to `0`. |
| 2. Running agent | `gpgconf --list-options gpg-agent` is queried; the script parses the last colon-separated field per line (the current loaded value) and confirms all four directives report `0`. |

A common failure mode is Layer 1 passing while Layer 2 fails: the conf file was edited but the running agent wasn't restarted, so it's still using the previous in-memory values. Remediation: `gpgconf --kill gpg-agent`. The next gpg invocation spawns a fresh agent that reads the updated conf.

## When to run

- **Before** any `--execute` invocation of a classic-PAT script (any tool that sources `tools/_pat_session.py`).
- After a Windows reboot — the agent restarts; verify its loaded settings still match the conf.
- After a GnuPG upgrade — package installers occasionally relocate the homedir or rewrite default config.
- Any "did this drift?" suspicion before a destructive operation.

## If the conf file is missing the directives

If Layer 1 fails because the conf file doesn't declare the directives, append them and restart the agent:

```
cat >> ~/.gnupg/gpg-agent.conf <<'EOF'
default-cache-ttl 0
max-cache-ttl 0
default-cache-ttl-ssh 0
max-cache-ttl-ssh 0
EOF
gpgconf --kill gpg-agent
```

Then re-run the verification — both layers should now report 0.

## Cross-references

- ADR-0216 §6.2 — passphrase caching as a real-not-theoretical attack class
- Runbook [0930](0930-gpg-and-classic-pat-rotation.md) — full gpg key + classic-PAT rotation lifecycle
- `tools/_pat_session.py` — the classic-PAT context manager whose protection depends on this setting
