#!/usr/bin/env bash
# Load the fleet's fine-grained PAT (`llm-restricting`) into `gh` on Ubuntu, with no echo.
#
# OPERATOR-RUN, in his own terminal; never an agent (runbook 0941 section 3e, ADR-0227).
# On Ubuntu `gh` keeps its token in ~/.config/gh/hosts.yml, and git's credential helper
# is `gh auth git-credential`, so this one load restores both `gh` and `git push`.
#
# The token is read from the keyboard with echo off, checked by length and prefix only,
# and handed to `gh` on a pipe from a shell builtin: it is never in argv, the
# environment, a file, a here-string or the terminal. Both clipboards are cleared at the end.
#
#   bash tools/gh_load_fine_grained_pat.sh

set -uo pipefail

if [ ! -t 0 ]; then
  echo "Run this in a terminal: it reads the token from the keyboard with echo off." >&2
  exit 1
fi

IFS= read -rs -p "Paste the llm-restricting token, then press Enter (nothing will show): " pat
echo >&2

case "$pat" in
  github_pat_*) ;;
  "")
    echo "Nothing was pasted. gh is unchanged." >&2
    exit 1
    ;;
  *)
    unset pat
    echo "That is not a fine-grained token: it must start github_pat_. gh is unchanged." >&2
    exit 1
    ;;
esac
echo "Read ${#pat} characters, starting github_pat_." >&2

printf '%s' "$pat" | gh auth login --with-token -h github.com
status=$?
unset pat
if [ "$status" -ne 0 ]; then
  echo "FAILED: gh auth login exited $status. gh may still hold the old token." >&2
  exit "$status"
fi

login=$(gh api user --jq .login 2>&1)
if [ "$login" != "martymcenroe" ]; then
  echo "FAILED: GitHub did not accept the token. It answered: $login" >&2
  exit 1
fi
echo "GitHub accepts the token for $login." >&2
gh auth status 2>&1 | grep -E 'Logged in|Token:' >&2

if command -v xclip > /dev/null && xclip -selection clipboard /dev/null; then
  echo "Cleared the Ubuntu clipboard." >&2
else
  echo "NOT CLEARED: the Ubuntu clipboard. Copy any harmless text to overwrite it." >&2
fi
# Ubuntu's PATH carries no Windows directories, so Windows PowerShell is named by its path.
winps=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
if [ -x "$winps" ] && "$winps" -NoProfile -Command 'Set-Clipboard -Value $null'; then
  echo "Cleared the Windows clipboard." >&2
else
  echo "NOT CLEARED: the Windows clipboard. In PowerShell run: Set-Clipboard -Value \$null" >&2
fi
echo "If Windows clipboard history is on (Win+V), delete the token's entry there too." >&2
