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

$LogFile = 'C:\Users\mcwiz\Projects\dependabot-fleet.log'
$RepoRoot = 'C:\Users\mcwiz\Projects\AssemblyZero'
$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

# Set-Location instead of Push-Location so that environment poetry
# pick-up matches an interactive shell (poetry resolves its venv from
# the current directory).
Set-Location -Path $RepoRoot

Add-Content -Path $LogFile -Value "$Timestamp | START | dependabot --fleet"

try {
    # Capture both stdout and stderr to the log. The tool prints a
    # detailed per-PR trace; the log is the durable record.
    $output = & poetry run python tools/dependabot_review.py --fleet 2>&1
    $exitCode = $LASTEXITCODE
    $output | Add-Content -Path $LogFile

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
