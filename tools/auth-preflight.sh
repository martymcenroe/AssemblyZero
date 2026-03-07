#!/bin/bash
# Auth Preflight — retry claude auth status before spawning a new session.
#
# Why: ~/.claude/.credentials.json has no file lock. When one session refreshes
# the OAuth token, a newly spawned session can read partial/stale JSON and show
# a transient "claude.ai connector needs auth" error.
#
# This script retries auth status with exponential backoff (2s, 4s, 6s),
# then drops into an interactive login shell with CLAUDECODE unset.
#
# Called from /handoff Step 6 spawn command.

for i in 1 2 3; do
    claude auth status > /dev/null 2>&1 && break
    echo "Auth check attempt $i failed, retrying in $((i * 2))s..."
    sleep $((i * 2))
done

unset CLAUDECODE
exec bash -l
