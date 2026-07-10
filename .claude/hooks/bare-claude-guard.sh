#!/usr/bin/env bash
# bare-claude-guard.sh — PreToolUse[Bash] hook (#1734).
#
# Blocks agent Bash commands that invoke `claude` with a POSITIONAL first
# argument. Claude Code v2.x parses removed subcommands as prompts, so
# `claude config list` silently forks a live auto-mode agent session in cwd
# with prompt "config" — observed 2026-07-10: the forked session performed a
# real handoff and spawned a wrapper window (full evidence in the wrapper
# repo's tracker). A rule in a memory file is advice to a future model; this
# hook is harness-executed enforcement.
#
# Allowed by construction:
#   claude --help / --version / any flag-first invocation
#   CLAUDECODE="" claude --print "..."      (sanctioned LLM-call pattern)
#   prose containing the word claude        (echo claude config, git commit -m "claude x")
#   hyphenated binaries                     (unleashed-claude-tool foo)
#
# Blocked:
#   claude config list | claude doctor | claude "prompt" | cd x && claude foo
#   VAR=val claude foo | $(claude foo) | ... | claude foo
#
# Known limitation (documented, accepted): a claude invocation prefixed by a
# word-form wrapper the anchor list doesn't name (e.g. `time claude foo`)
# passes this guard. The sentinel layer and the banned-pattern list remain
# defense-in-depth; extend BLOCK_RE's anchor group if a new form shows up.
#
# PreToolUse protocol: exit 0 = allow; exit 2 = block, stderr shown to model.

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -z "$cmd" ] && exit 0

# #1739: mask quoted strings BEFORE matching — a regex cannot parse shell
# quoting, and the guard's first live block was a false positive on prose
# inside a quoted --comment argument. Quoted substrings become the bare
# placeholder QSTR: real invocations are unquoted at command position and
# still match; a quoted PROMPT (claude "do x") still matches because QSTR
# itself is a non-flag positional. Residual documented hole: heredoc bodies
# are not masked.
residue=$(printf '%s' "$cmd" | sed -e "s/'[^']*'/QSTR/g" -e 's/"[^"]*"/QSTR/g')

# Anchor: start-of-line / ; & | ( / $( — then optional env-var assignments,
# optional `command`/`exec`, then claude(.exe|.cmd) followed by a first arg
# that does not start with a dash.
BLOCK_RE='(^|[;&|(]|\$\()[[:space:]]*([A-Za-z_][A-Za-z_0-9]*=[^[:space:]]*[[:space:]]+)*(command[[:space:]]+|exec[[:space:]]+)?claude(\.exe|\.cmd)?[[:space:]]+[^-[:space:]]'

if printf '%s' "$residue" | grep -qE "$BLOCK_RE"; then
    cat >&2 <<'MSG'
BLOCKED by bare-claude-guard (#1734): `claude <word>` forks a live agent
session — Claude Code parses removed subcommands as PROMPTS (a one-word
accidental prompt has performed a real handoff before). Use flag-only forms
(claude --help, claude --version) or the sanctioned LLM-call pattern
(CLAUDECODE="" claude --print "..."). If you genuinely need a claude
subcommand, ask the operator to run it in their own terminal.
MSG
    exit 2
fi
exit 0
