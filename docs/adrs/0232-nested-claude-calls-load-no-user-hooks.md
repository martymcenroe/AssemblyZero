# ADR 0232: Nested `claude -p` Calls Load No User Hooks

**Date:** 2026-09-24
**Status:** Proposed. The operator accepts or rejects it; the flag it describes has shipped with this ADR, as #3504 directed for this outcome.
**Amends:** ADR 0208 (LLM Invocation Strategy), § Claude CLI Invocation
**Issue:** #3504 (parent #3502)

## 1. Context

`ClaudeCLIProvider` runs every workflow model call as a nested `claude -p`. Its command carries `--setting-sources user`, which loads `~/.claude/settings.json`, and with it every hook registered there. Nothing in the repository recorded which of those hooks fire inside a nested call, what they cost, or whether one could deny a call.

On the machine this was measured on, the user settings register hooks on six events:

| Event | Hooks registered |
|---|---|
| PreToolUse | shell guard, commit-report check, bare-claude guard, hidden-space guard, edit checks, secret-file guard, prose-write guard |
| PostToolUse | edit lint, plan-write hook, prose check |
| PreCompact | prints a facts file |
| SessionStart | prints a directive file; `session-baseline.sh` |
| Stop | `session-leftovers.sh` |
| SessionEnd | a transcript archiver (`jsonl_archive.py`) |

A nested call passes `--tools ""`, so no tool runs and PreToolUse and PostToolUse can never fire. The session events are what remain.

## 2. The evidence

One nested call was run exactly as the provider runs it. It went through `ClaudeCLIProvider("haiku").invoke`, with the prompt "Reply with the single word OK.", from an empty directory inside a git repository. The hooks' own records were then read. The same call was run a second time with `--settings '{"disableAllHooks": true}'` added. The probe script and both JSON reports are kept in the session's working directory. The repeatable form is `tests/integration/test_nested_hooks_live.py` (opt-in; it needs a logged-in `claude` and spends one haiku call).

| | As the provider ran it | With `disableAllHooks` |
|---|---|---|
| Call succeeded, answer | yes, `OK` | yes, `OK` |
| Wall time | 4.5 s | 3.0 s |
| **SessionStart**: `session-baseline.sh` wrote `{repo}/data/.session-baseline/{session_id}.txt` for the repository holding the cwd | **yes**, one file for the nested session id | no |
| **SessionEnd**: the archiver appended to its manifest | **yes**: `"scanned": 17725, "copied": 17, "bytes_copied": 29773442` | no |
| Hook events in the `stream-json` output | none | none |

So on every nested call:

- **SessionStart writes a file into whatever repository contains the process's working directory.** A draft-review loop of a dozen calls leaves a dozen baseline files, each named for a session nobody will ever end by hand, in a repository the run may not own.
- **SessionEnd runs a full transcript-archive pass.** Here that was 17,725 files scanned and 29.8 MB copied, for a one-word haiku answer. It has a 120-second timeout, and it fires on every node of every run.
- Stop prints a message into a stream that nothing reads.
- None of them does anything a nested model call needs. The call has no tools, no repository context and no session a human will resume.

The live test was run against the code before the flag, and it failed as the table predicts: SessionStart wrote `data/.session-baseline/<sid>.txt` inside the throwaway repository. With the flag, it passed.

## 3. Decision

**Nested calls load no user hooks.** Every command `ClaudeCLIProvider` builds, in `invoke` and in `_probe_alive`, carries `--settings '{"disableAllHooks": true}'`. It is defined once, as `assemblyzero.core.llm_provider.NESTED_SETTINGS_ARGS`.

User settings still load (`--setting-sources user` is unchanged), so authentication and model access behave as before. Only hooks are switched off. The large-system-prompt path, which widens `--setting-sources` to `user,project` for its temporary `CLAUDE.md`, keeps the flag too.

Which hook events, if any, are wanted in nested calls? None. No event carries information a nested call needs, and the two that act (SessionStart, SessionEnd) act on things the nested call does not own. If a hook is ever wanted there, it belongs in the provider's own `--settings` payload, named, rather than inherited from whatever the operator's settings hold that day.

## 4. Consequences

- Nested calls stop writing baseline files into repositories and stop triggering transcript-archive passes. Measured, that also takes about 1.5 s off each call.
- The operator's session hooks keep working for real sessions. Nothing about them changed.
- The nested sessions' own transcripts are no longer archived by the SessionEnd hook when they end. They remain in `~/.claude/projects/` and are picked up by the next archive pass of a real session. The workflow's own record of each call is the lineage `calls.jsonl`, which is unchanged.

**Pinned by:**

- `tests/unit/test_nested_claude_env.py::TestNestedCallsLoadNoUserHooks`: the flag is in the `invoke` command, in the large-prompt command, and in the liveness-probe command. All three fail without it.
- `tests/integration/test_nested_hooks_live.py`, opt-in, as above.

## 5. Not decided here

- `tools/audit_deferred_scope.py` also launches `claude --print` on its own, outside the provider. It is a manual tool and is not changed here.
- Whether the SessionEnd archiver should itself skip `-p` sessions is a question for that hook's own repository.
