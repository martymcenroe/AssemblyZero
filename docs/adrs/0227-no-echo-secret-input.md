# 0227 - Operator Secrets Enter Through a Pasteable No-Echo Prompt, Never Through the Command Line

**Status:** Accepted
**Date:** 2026-08-12
**Supersedes:** none
**Related:** ADR-0216 (in-process classic-PAT decryption), ADR-0219 (CLAUDE.md division of responsibility)

---

## Context

Every credential in this fleet begins the same way: a human has a secret on one side of the screen and a file that needs it on the other. The transport between those two points is chosen ad hoc, one script at a time, and almost every obvious choice leaks.

ADR-0216 settled what happens to a secret **at rest** and **at use** — encrypted on disk, decrypted in-process, never in an agent's child process. It says nothing about how the value gets in there the first time. That gap has been filled by improvisation, and improvisation has produced the same four failures repeatedly.

**The command line is a public place.** A secret passed as an argument is visible in `ps`, in `/proc/<pid>/cmdline`, in Windows via `NtQueryInformationProcess`, and in shell history. Any process running as the same user can read another process's argv. A secret in argv is a secret shared with every program on the machine.

**The environment is inherited.** An exported variable is copied into every child process for the lifetime of the shell. Handing a secret to one program through the environment hands it to every program that program launches.

**Here-strings and here-docs write the secret to disk.** This one is invisible and it has nearly bitten. Bash implements `<<<` and `<<EOF` by writing the content to a temporary file in `$TMPDIR` and handing the program a descriptor onto it. On Windows that path is `AppData\Local\Temp` — a location this fleet bans for ordinary work products, let alone plaintext credentials. The construct *looks* like a pipe and is not one.

**Bash `read` silently mutates what it is given.** Plain `read` strips leading and trailing whitespace, because it splits on `$IFS`. An operator who deliberately begins a passphrase with a space — a real convention, because `HISTCONTROL=ignorespace` keeps space-prefixed lines out of history if a window steals focus mid-typing — gets a stored secret that differs from what they typed. Plain `read` also consumes backslashes as escapes. Both transforms are silent, and both are discovered on the day the credential is needed, which is the worst possible day.

The failure these share is that **the damage is invisible at the moment it occurs.** The script exits 0, the file exists, and the leak or the corruption surfaces much later, if ever.

## Decision

**A secret enters a script by being pasted into a no-echo prompt. It never arrives any other way.**

The canonical form, which every tool in the fleet uses verbatim:

```bash
printf 'Paste the value, then press Enter. It will NOT be echoed: '
IFS= read -rs VALUE
echo
[ -n "$VALUE" ] || { echo "empty -- nothing written" >&2; exit 1; }
```

Each part is load-bearing:

| Element | Why |
|---|---|
| `IFS=` | stops `read` splitting on whitespace, which would silently eat a deliberate leading space |
| `-r` | stops backslashes being consumed as escapes |
| `-s` | no echo — nothing on screen, nothing in a screen share, nothing in a session transcript |
| the `echo` after | `-s` swallows the newline the user typed; without this the next output lands mid-line |
| the empty check | a mispaste is caught now rather than becoming an unusable credential later |

**Four prohibitions follow, and they are absolute:**

1. **Never in argv.** No `--password X`, no positional secret. A flag that takes a secret value is a design error.
2. **Never in the environment.** Read it into a shell variable and pass it by descriptor.
3. **Never through `<<<` or a here-doc.** Use process substitution — `<(printf '%s' "$VALUE")` — which is a real pipe. Where a tool offers a descriptor argument (`--passphrase-fd`, `--password-stdin`), use it.
4. **Never echoed, logged, or interpolated into an error message.** An error path that prints the value it failed on is the most common accidental disclosure.

**Verify without disclosing.** A script must confirm the paste survived intact and must do so without printing it: report the length, whether a deliberate leading character survived, whether an expected prefix matched. Where the secret was written somewhere, read it back and compare byte for byte — an exit code of 0 from the writing tool is not evidence the artifact is usable.

**The agent writes the script; the operator runs it.** This extends ADR-0216's reasoning to input. A script an agent invokes is a process the agent parents, so the "only in this process's memory" guarantee does not hold. The deliverable an agent produces is a command the operator can paste into their own terminal.

## Consequences

**Asking an operator for a credential now has one shape.** The agent writes a small script, hands over a single pasteable command, and the operator pastes the secret into a prompt that shows nothing. No clicking through a web console, no secret in chat, no secret in history. This replaces "go into the dashboard and copy this into that file" as the standard ask.

**Some ergonomics are given up on purpose.** A no-echo prompt cannot be piped to in CI and cannot be scripted non-interactively. That is the point: this pattern is for the boundary where a *human* introduces a secret. Machine-to-machine paths use ADR-0216's encrypted-at-rest, decrypted-in-process mechanism, which this ADR feeds rather than replaces.

**`--check` preflight is expected.** Because the failure modes are invisible, a tool taking secret input should offer a mode that verifies its own plumbing — that process substitution is a pipe and not a temp file, that the terminal suppresses echo — while writing nothing.

**Existing tools that violate this are defects, not legacy.** Any script accepting a secret through argv, environment, or here-string is to be corrected when touched, not grandfathered.

## Alternatives considered

**A GUI passphrase prompt (pinentry).** Rejected for operator input. In practice it lost focus mid-typing or failed to take focus at all, which silently truncated what was typed and burned two passphrases. A terminal prompt cannot lose focus to a dialog that is never shown.

**Reading from a file the operator prepares.** Moves the problem rather than solving it: the operator still needs a way to get the secret into that file, and the file is then plaintext on disk with no defined lifetime.

**Environment variable, on the argument that the shell is already trusted.** Rejected. Inheritance is the whole objection — the trust boundary is not the shell, it is every descendant of it, which is unbounded.
