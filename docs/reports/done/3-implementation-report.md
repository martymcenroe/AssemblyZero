# Implementation Report: Issue #3 - Claude Code Usage Quota Scraper

**Issue:** [#3](https://github.com/martymcenroe/AssemblyZero/issues/3)
**Commit:** `f075f88`
**Date:** 2026-01-11
**Status:** Complete

---

## Summary

Implemented terminal automation tool that scrapes usage quota data from Claude Code's TUI. This data (session %, weekly %, Sonnet %) is not available via any programmatic API, so the tool spawns Claude Code in a pseudo-terminal, navigates to `/status` → Usage tab, and parses the output.

---

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `tools/claude-usage-scraper.py` | Created | Core scraper with PTY automation (314 lines) |

---

## Design Decisions

### 1. PTY Approach

**Why PTY instead of subprocess:**
- Claude Code's `/status` command is TUI-only (not available in `-p` mode)
- Usage data is rendered with ANSI escape sequences in a terminal buffer
- No HTTP API or JSON output flag exists
- PTY allows sending keystrokes and reading terminal output

**Implementation:** Uses `pywinpty` (Windows) to spawn Claude Code with:
- 50x150 terminal dimensions (wide enough to capture full output)
- Non-blocking reader thread with queue for async output capture
- Clean exit via `/exit` command

### 2. Navigation Sequence

```
1. Wait 6s for Claude to initialize
2. Type "/status" + Escape (dismiss autocomplete) + Enter
3. Wait 3s for status dialog
4. Tab twice (Status → Config → Usage)
5. Read terminal buffer
6. Parse with regex
7. Exit cleanly
```

### 3. Output Format

Returns JSON to stdout for easy integration:

```json
{
  "status": "success",
  "session": {"percent_used": 42, "resets_at": "in 2 hours"},
  "weekly_all": {"percent_used": 15, "resets_at": "2026-01-18 00:00"},
  "weekly_sonnet": {"percent_used": 0, "resets_at": null},
  "timestamp": "2026-01-11T22:30:00Z"
}
```

### 4. Error Handling

| Error | Response |
|-------|----------|
| `pywinpty` not installed | JSON error + exit 1 |
| Claude not in PATH | JSON error + exit 1 |
| Process exits unexpectedly | JSON error with raw output |
| Parse failure | JSON error with last 2000 chars of output |

---

## Architecture

```
User/Scheduler
    |
    v
claude-usage-scraper.py
    |
    +---> PtyProcess.spawn(['claude'])
    |         |
    |         v
    |     PTY Reader Thread (non-blocking)
    |         |
    |         v
    |     Queue: raw terminal output
    |
    +---> send_commands()
    |         |
    |         v
    |     "/status" → Tab → Tab
    |
    +---> parse_usage_data()
    |         |
    |         v
    |     strip_ansi() → regex extraction
    |
    +---> JSON output to stdout
```

---

## Key Implementation Details

### ANSI Stripping (`tools/claude-usage-scraper.py:40-43`)

```python
def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)
```

Removes all ANSI escape sequences (colors, cursor movement, etc.) from terminal output.

### Non-Blocking Reader (`tools/claude-usage-scraper.py:46-83`)

Background thread continuously reads from PTY and queues chunks. Main thread reads from queue with timeout to avoid blocking indefinitely.

### Regex Parsing (`tools/claude-usage-scraper.py:85-124`)

Three patterns extract percentage and reset times:
- Session: `Current session X% used ... Resets [time]`
- Weekly all: `Current week (all models) X% used ... Resets [time]`
- Weekly Sonnet: `Current week (Sonnet only) X% used ... Resets [time]` (optional)

**Note:** The Sonnet pattern uses an optional group `(?:.*?Resets?\s+([^\n\r│]+))?` to capture the reset time when displayed. If the user is at 0% Sonnet usage, the TUI may not display a reset time, so the field returns `null`.

---

## Deviations from Original Issue Spec

### Script Location
- **Original:** `C:\Users\mcwiz\Projects\claude-usage-scraper.py`
- **Actual:** `tools/claude-usage-scraper.py` (in AssemblyZero tools directory)

This follows AssemblyZero conventions for tool placement.

### Log Integration
The `--log` flag appends NDJSON (newline-delimited JSON) entries to a log file. Each line is a complete JSON object identical to the stdout output, enabling easy ingestion by log aggregators (Splunk, Datadog) and parsing with tools like `jq`.

```bash
# Example log entry (one JSON object per line):
{"status":"success","session":{"percent_used":23,"resets_at":"in 4 hours"},...,"timestamp":"2026-01-11T22:45:00+00:00"}
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (JSON with usage data) |
| 1 | Error (JSON with error details) |

---

## Related Documentation

- Test report: `docs/reports/3/test-report.md`
- GitHub references: #8412, #5621 (Anthropic feature requests for API access)

---

## Retrospective Notes

**What worked well:**
- PTY approach successfully navigates Claude's TUI
- Non-blocking reader prevents hangs
- JSON output integrates easily with other tools

**Limitations:**
- Brittle: Any TUI changes could break navigation
- Slow: ~10-15 seconds to complete
- Windows-only: Uses `pywinpty` (could add `pexpect` for Linux/macOS)
