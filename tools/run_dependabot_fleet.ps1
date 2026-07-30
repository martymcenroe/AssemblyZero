# PowerShell wrapper for tools/dependabot_review.py --fleet (#1092)
#
# Designed to be called by Windows Task Scheduler. Logs to
# C:\Users\mcwiz\Projects\dependabot-fleet.log so the operator can
# see what happened across runs without opening a console. The tool
# additionally writes its own per-run log under data/dependabot-runs/
# in AssemblyZero (#1403).
#
# Registration (#1836): the Claude-DependabotFleet task does NOT launch
# this script with powershell.exe directly. Launching powershell from a
# scheduled task -- even with -WindowStyle Hidden -- flashes a console
# on the interactive desktop, because Windows allocates the console for
# a console-subsystem app BEFORE SW_HIDE takes effect (measured; see
# AZ #1819). The task instead runs a silent wscript launcher (WshShell
# .Run with window style 0 = SW_HIDE at CreateProcess) that invokes
# this script; the launcher is generated and managed by the private
# environment-tooling repo's converter. Do NOT re-register this task
# with a direct powershell action -- that silently reintroduces the
# console flash the launcher exists to prevent.
#
# Manual run:
#
#     Start-ScheduledTask -TaskName 'Claude-DependabotFleet'
#
# Disable / Enable:
#
#     Disable-ScheduledTask -TaskName 'Claude-DependabotFleet'
#     Enable-ScheduledTask -TaskName 'Claude-DependabotFleet'

$ErrorActionPreference = 'Continue'

# Force UTF-8 for Python stdout/stderr so em-dashes and other non-ASCII
# characters in tool output don't crash the cp1252 default codec. Also
# applies to subprocess output captured via Tee-Object below.
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$LogFile = 'C:\Users\mcwiz\Projects\dependabot-fleet.log'

# #1879: the scheduled run executes a PINNED clone, never the shared
# interactive checkout. The interactive AssemblyZero tree cycles branches
# continuously under concurrent sessions, so "what code runs at 06:00"
# used to be "whatever branch someone left checked out at 05:59". The
# pinned clone is synced ff-only to origin/main each run; on ANY sync
# surprise the run refuses loudly instead of executing wrong code.
# (No force-sync by design: reset --hard is banned fleet-wide, and a
# diverged pinned clone means tampering that deserves eyes, not a wipe.)
$RepoRoot = 'C:\Users\mcwiz\Projects\AssemblyZero-scheduled'
$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

Add-Content -Path $LogFile -Value "$Timestamp | START | dependabot --fleet" -Encoding utf8

# --- #1879 sync gate -------------------------------------------------------
if (-not (Test-Path (Join-Path $RepoRoot '.git'))) {
    Add-Content -Path $LogFile -Value "$Timestamp | BOOTSTRAP | pinned clone absent; cloning" -Encoding utf8
    & gh repo clone martymcenroe/AssemblyZero $RepoRoot 2>&1 | Out-Null
    if (-not (Test-Path (Join-Path $RepoRoot '.git'))) {
        Add-Content -Path $LogFile -Value "$Timestamp | ERROR | bootstrap clone failed; aborting" -Encoding utf8
        exit 1
    }
}

& git -C $RepoRoot fetch origin 2>&1 | Out-Null
$branch = (& git -C $RepoRoot branch --show-current | Out-String).Trim()
if ($branch -ne 'main') {
    Add-Content -Path $LogFile -Value "$Timestamp | SYNC-REFUSED | pinned clone on '$branch', not main — investigate before next run" -Encoding utf8
    exit 1
}
& git -C $RepoRoot merge --ff-only origin/main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Add-Content -Path $LogFile -Value "$Timestamp | SYNC-REFUSED | ff-only to origin/main failed (diverged pinned clone) — investigate" -Encoding utf8
    exit 1
}

# Provenance (#1879 option 3): every run log answers "which code ran".
$sha = (& git -C $RepoRoot rev-parse --short HEAD | Out-String).Trim()
$dirtyCount = (& git -C $RepoRoot status --porcelain | Measure-Object -Line).Lines
Add-Content -Path $LogFile -Value "$Timestamp | PROVENANCE | branch=$branch sha=$sha dirty=$dirtyCount root=$RepoRoot" -Encoding utf8

# Set-Location instead of Push-Location so that environment poetry
# pick-up matches an interactive shell (poetry resolves its venv from
# the current directory).
Set-Location -Path $RepoRoot

# Keep the pinned clone's venv current with its lock (no-op when synced;
# builds the venv on first run after bootstrap).
& cmd.exe /c "poetry install --no-interaction >> `"$LogFile`" 2>&1"

try {
    # Bypass PowerShell's pipeline and use cmd.exe's native >>
    # redirection. Three prior attempts to stream via PowerShell
    # (Tee-Object in #1163, ForEach-Object+Add-Content in #1166)
    # all produced START-only log files in the scheduled-task
    # -WindowStyle Hidden context -- the subprocess ran fine and
    # merged PRs, but per-line output and the terminal OK/EXIT line
    # never reached the log. Suspected cause: Add-Content in Windows
    # PowerShell 5.1 defaults to ASCII encoding; Python's UTF-8 output
    # (em-dashes, etc.) trips a silent encoding error that aborts the
    # pipeline with $ErrorActionPreference = 'Continue' swallowing it.
    # cmd.exe's >> is byte-level, format-agnostic, and unaffected by
    # PowerShell's pipeline mechanics. The OK/EXIT marker is then
    # written by PowerShell with explicit -Encoding utf8 so the same
    # encoding wire doesn't trip later writes. See #1176.
    # #1836/#1339: --limit 15 caps the scheduled harvest at ~30
    # contributions/day (15 review events + up to 15 merges) against the
    # operator's ~260/day calibration. The uncapped 2026-07-28 run
    # produced 35 review events in one morning; consecutive limited runs
    # drain the queue FIFO instead.
    & cmd.exe /c "poetry run python tools\dependabot_review.py --fleet --limit 15 >> `"$LogFile`" 2>&1"
    $exitCode = $LASTEXITCODE

    $endStamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    if ($exitCode -eq 0) {
        Add-Content -Path $LogFile -Value "$endStamp | OK | exit 0" -Encoding utf8
    } else {
        Add-Content -Path $LogFile -Value "$endStamp | EXIT $exitCode" -Encoding utf8
    }
} catch {
    $errStamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LogFile -Value "$errStamp | ERROR | $($_.Exception.Message)" -Encoding utf8
    exit 1
}
