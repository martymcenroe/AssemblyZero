# 0903 - Windows Scheduled Tasks

**Category:** Runbook / Operational Procedure
**Version:** 1.0
**Last Updated:** 2026-01-17

---

## Purpose

Documents the Windows Task Scheduler tasks that automate Claude Code operations: daily rotating audits across projects and hourly health/usage monitoring.

---

## Scheduled Tasks Overview

| Task Name | Schedule | Purpose |
|-----------|----------|---------|
| Claude-DailyAudit | Daily 4:30 AM | Rotates through projects running `/audit` |
| Claude-Heartbeat | Hourly | Monitors usage quotas and Claude availability |

---

## Claude-DailyAudit

### Configuration

| Property | Value |
|----------|-------|
| **Trigger** | Daily at 4:30 AM |
| **Script** | `C:\Users\mcwiz\Projects\claude-daily-audit.ps1` |
| **Model** | Sonnet |
| **Max Turns** | 15 |

### Rotation Order

The audit rotates through these projects (one per night):

| Index | Project | Path |
|-------|---------|------|
| 0 | Aletheia | `C:\Users\mcwiz\Projects\Aletheia` |
| 1 | AssemblyZero | `C:\Users\mcwiz\Projects\AssemblyZero` |
| 2 | Talos | `C:\Users\mcwiz\Projects\Talos` |
| 3 | maintenance | `C:\Users\mcwiz\Projects\maintenance` |

### Quota Gate

The audit **skips execution** if weekly Claude usage is at or above 75%. This prevents audits from consuming quota needed for interactive work.

```
Weekly usage >= 75% → SKIP (logged as "SKIP | Weekly usage at X%")
Weekly usage < 75%  → RUN next repo in rotation
```

### State Tracking

| File | Purpose |
|------|---------|
| `C:\Users\mcwiz\Projects\claude-audit-state.json` | Tracks last repo index and run time |

State file format:
```json
{
    "lastRepoIndex": 1,
    "lastRun": "2026-01-16 04:30:02",
    "lastRepo": "AssemblyZero"
}
```

### Output

| Output | Location |
|--------|----------|
| **Audit results** | `{project}/docs/audit-results/YYYY-MM-DD.md` |
| **Execution log** | `C:\Users\mcwiz\Projects\claude-daily-audit.log` |

Log format:
```
YYYY-MM-DD HH:MM:SS | OK | RepoName | weekly:X% | input/output tokens | $cost
YYYY-MM-DD HH:MM:SS | SKIP | Weekly usage at X% (threshold: 75%)
YYYY-MM-DD HH:MM:SS | ERROR | RepoName | error details
```

---

## Claude-Heartbeat

### Configuration

| Property | Value |
|----------|-------|
| **Trigger** | Hourly (on the :01) |
| **Script** | `C:\Users\mcwiz\Projects\claude-heartbeat.ps1` |
| **Model** | Sonnet |

### What It Tracks

| Metric | Source |
|--------|--------|
| Session usage % | `claude-usage-scraper.py` |
| Weekly usage % | `claude-usage-scraper.py` |
| Sonnet usage % | `claude-usage-scraper.py` |
| Claude availability | Minimal prompt test |
| Token cost | Claude API response |

### Output

| Output | Location |
|--------|----------|
| **Heartbeat log** | `C:\Users\mcwiz\Projects\claude-heartbeat.log` |

Log format:
```
YYYY-MM-DD HH:MM:SS | session:X% | weekly:Y% | sonnet:Z% | heartbeat:OK | input/output tokens | $cost
```

Warnings appended when:
- Session usage >= 90%: `WARN:HIGH_USAGE`
- Scraper fails: `usage:ERROR(reason)`
- Heartbeat fails: `heartbeat:ERROR`

---

## Verification Commands

### Check Task Status

```powershell
# List both Claude tasks
Get-ScheduledTask | Where-Object {$_.TaskName -like 'Claude-*'} | Format-Table TaskName,State

# Get detailed info for daily audit
Get-ScheduledTask -TaskName 'Claude-DailyAudit' | Get-ScheduledTaskInfo

# Get detailed info for heartbeat
Get-ScheduledTask -TaskName 'Claude-Heartbeat' | Get-ScheduledTaskInfo
```

### Check Task Configuration

```powershell
# View triggers (schedule)
Get-ScheduledTask -TaskName 'Claude-DailyAudit' | Select-Object -ExpandProperty Triggers

# View actions (what runs)
Get-ScheduledTask -TaskName 'Claude-DailyAudit' | Select-Object -ExpandProperty Actions
```

### View Recent Logs

```bash
# Last 20 daily audit entries
tail -20 /c/Users/mcwiz/Projects/claude-daily-audit.log

# Last 20 heartbeat entries
tail -20 /c/Users/mcwiz/Projects/claude-heartbeat.log
```

### Check Current State

```bash
cat /c/Users/mcwiz/Projects/claude-audit-state.json
```

---

## Manual Execution

### Run Daily Audit Immediately

```powershell
# Run the task now (outside normal schedule)
Start-ScheduledTask -TaskName 'Claude-DailyAudit'

# Or run the script directly
powershell -ExecutionPolicy Bypass -File C:\Users\mcwiz\Projects\claude-daily-audit.ps1
```

### Run Heartbeat Immediately

```powershell
Start-ScheduledTask -TaskName 'Claude-Heartbeat'
```

### Force Audit (Bypass Quota Gate)

Edit the script temporarily or run Claude directly:
```bash
cd /c/Users/mcwiz/Projects/Aletheia
claude -p "Run /audit for this project. Save results to docs/audit-results/$(date +%Y-%m-%d).md"
```

---

## Troubleshooting

### "SKIP | Weekly usage at X%"

**Cause:** Weekly usage exceeded the 75% threshold.

**Solution:** This is expected behavior. The audit will run when usage resets or drops below threshold. To force an audit, run Claude manually (see above).

### "SKIP | Usage scraper failed"

**Cause:** The `claude-usage-scraper.py` tool couldn't retrieve usage data.

**Solution:**
1. Test the scraper manually:
   ```bash
   poetry run --directory /c/Users/mcwiz/Projects/AssemblyZero python /c/Users/mcwiz/Projects/AssemblyZero/tools/claude-usage-scraper.py
   ```
2. Check if Claude desktop app is running (scraper reads from app data)

### "ERROR | Repo path not found"

**Cause:** A project in the rotation list no longer exists at the expected path.

**Solution:** Edit `claude-daily-audit.ps1` to update or remove the repo from the `$repos` array.

### Task Not Running

**Diagnosis:**
```powershell
# Check task state
Get-ScheduledTask -TaskName 'Claude-DailyAudit' | Select-Object State

# Check last run result (0 = success)
Get-ScheduledTask -TaskName 'Claude-DailyAudit' | Get-ScheduledTaskInfo | Select-Object LastTaskResult
```

**Common causes:**
- Task disabled → Enable with `Enable-ScheduledTask -TaskName 'Claude-DailyAudit'`
- Computer asleep at trigger time → Check power settings
- User not logged in → Task may need "Run whether user is logged on or not"

---

## Modifying Tasks

### Change Schedule

```powershell
# Change daily audit to 5:00 AM
$trigger = New-ScheduledTaskTrigger -Daily -At 5:00AM
Set-ScheduledTask -TaskName 'Claude-DailyAudit' -Trigger $trigger
```

### Change Quota Threshold

Edit `C:\Users\mcwiz\Projects\claude-daily-audit.ps1`:
```powershell
$quotaThreshold = 75  # Change this value
```

### Add/Remove Projects from Rotation

Edit the `$repos` array in `claude-daily-audit.ps1`:
```powershell
$repos = @(
    @{ Name = "Aletheia"; Path = "C:\Users\mcwiz\Projects\Aletheia" },
    @{ Name = "AssemblyZero"; Path = "C:\Users\mcwiz\Projects\AssemblyZero" },
    # Add or remove entries here
)
```

### Disable/Enable Tasks

```powershell
# Disable
Disable-ScheduledTask -TaskName 'Claude-DailyAudit'

# Enable
Enable-ScheduledTask -TaskName 'Claude-DailyAudit'
```

---

## Creating the Tasks (Reference)

For setting up on a new machine:

```powershell
# Daily Audit
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File C:\Users\mcwiz\Projects\claude-daily-audit.ps1'
$trigger = New-ScheduledTaskTrigger -Daily -At 4:30AM
Register-ScheduledTask -TaskName 'Claude-DailyAudit' -Action $action -Trigger $trigger -Description 'Daily rotating audit of Claude projects'

# Heartbeat
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File C:\Users\mcwiz\Projects\claude-heartbeat.ps1'
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName 'Claude-Heartbeat' -Action $action -Trigger $trigger -Description 'Hourly Claude health and usage monitoring'
```

---

## Related Documents

- [0800 - Audit Index](../audits/0800-audit-index.md) - List of all audits
- [0902 - Nightly AssemblyZero Audit](0902-nightly-assemblyzero-audit.md) - Conceptual audit runbook
- [claude-usage-scraper.py](../../tools/claude-usage-scraper.py) - Usage data scraper

---

## Files Reference

| File | Purpose |
|------|---------|
| `C:\Users\mcwiz\Projects\claude-daily-audit.ps1` | Daily audit script |
| `C:\Users\mcwiz\Projects\claude-heartbeat.ps1` | Heartbeat script |
| `C:\Users\mcwiz\Projects\claude-daily-audit.log` | Daily audit log |
| `C:\Users\mcwiz\Projects\claude-heartbeat.log` | Heartbeat log |
| `C:\Users\mcwiz\Projects\claude-audit-state.json` | Rotation state |

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-17 | Initial version documenting existing scheduled tasks |
