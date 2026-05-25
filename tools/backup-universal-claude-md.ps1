# Nightly backup of universal CLAUDE.md -- silent scheduled-task wrapper.
#
# Invoked by Windows Task Scheduler at 5:55 AM local (Claude-UniversalClaudeMdBackup).
# Follows runbook 0903 Hard Rules: no console window pops up, no subprocess
# allocates its own console, no admin elevation required.
#
# All logging happens inside backup_universal_claude_md.py (JSONL at
# C:\Users\mcwiz\Projects\.universal-claude-md-backup.jsonl). This wrapper
# adds a single status line per run to a sidecar log so failures of the
# wrapper itself (vs the Python script) are visible.
#
# Issue: martymcenroe/AssemblyZero#1262

$ErrorActionPreference = "Continue"

$AssemblyZeroRoot = "C:\Users\mcwiz\Projects\AssemblyZero"
$ScriptPath       = "$AssemblyZeroRoot\tools\backup_universal_claude_md.py"
$WrapperLog       = "C:\Users\mcwiz\Projects\.universal-claude-md-backup-wrapper.log"

function Write-WrapperLog($status, $detail) {
    $ts = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    Add-Content -Path $WrapperLog -Value "$ts | $status | $detail" -Encoding UTF8
}

if (-not (Test-Path $ScriptPath)) {
    Write-WrapperLog "ERROR" "Script not found: $ScriptPath"
    exit 1
}

try {
    Push-Location $AssemblyZeroRoot
    # poetry run -- inherits gh auth from the user profile (runbook 0903 rule #4).
    # Output goes to pipes; subprocess.run inside the Python script never
    # allocates a new console (parent PowerShell window is Hidden).
    & poetry run python $ScriptPath 2>&1 | Out-Null
    $exit = $LASTEXITCODE
    Write-WrapperLog "OK" "exit=$exit"
    exit $exit
} catch {
    Write-WrapperLog "ERROR" "exception: $($_.Exception.Message)"
    exit 1
} finally {
    Pop-Location
}
