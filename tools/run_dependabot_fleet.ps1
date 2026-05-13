# PowerShell wrapper for tools/dependabot_review.py --fleet (#1092)
#
# Designed to be called by Windows Task Scheduler. Logs to
# C:\Users\mcwiz\Projects\dependabot-fleet.log so the operator can
# see what happened across runs without opening a console.
#
# Setup (run once):
#
#     $action = New-ScheduledTaskAction `
#       -Execute 'powershell.exe' `
#       -Argument '-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File C:\Users\mcwiz\Projects\AssemblyZero\tools\run_dependabot_fleet.ps1'
#     $trigger = New-ScheduledTaskTrigger -Daily -At 06:00
#     Register-ScheduledTask `
#       -TaskName 'Claude-DependabotFleet' `
#       -Action $action -Trigger $trigger `
#       -Description 'Daily fleet-wide dependabot PR review + merge (#1091, #1092)'
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
$RepoRoot = 'C:\Users\mcwiz\Projects\AssemblyZero'
$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

# Set-Location instead of Push-Location so that environment poetry
# pick-up matches an interactive shell (poetry resolves its venv from
# the current directory).
Set-Location -Path $RepoRoot

Add-Content -Path $LogFile -Value "$Timestamp | START | dependabot --fleet"

try {
    # Stream subprocess output to the log line-by-line. Tee-Object (used
    # in the first attempt at this fix) holds a single .NET StreamWriter
    # alive for the duration of the pipeline; in a 10-30 min run the
    # writer's buffer accumulates output and only flushes at pipeline
    # disposal, which defeats the whole point. The user observed the
    # log sit at "START" for 3+ minutes with the task confirmed running.
    # ForEach-Object + Add-Content opens a fresh writer per line and
    # auto-flushes on close, so each line hits disk as produced.
    & poetry run python tools/dependabot_review.py --fleet 2>&1 |
        ForEach-Object { Add-Content -Path $LogFile -Value $_ }
    $exitCode = $LASTEXITCODE

    $endStamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    if ($exitCode -eq 0) {
        Add-Content -Path $LogFile -Value "$endStamp | OK | exit 0"
    } else {
        Add-Content -Path $LogFile -Value "$endStamp | EXIT $exitCode"
    }
} catch {
    $errStamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LogFile -Value "$errStamp | ERROR | $($_.Exception.Message)"
    exit 1
}
